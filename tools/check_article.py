"""Check an article's "short" (and "video") script BEFORE it is committed, so a slip never stops a video again.

Usage: python3 tools/check_article.py content/articles/<file>.json [...]      (exit code 1 when there are errors)

ERRORS must be fixed before the commit; WARNINGS should be fixed where possible. The rules are the Short format in
README.md (v4 with v3.1/v3). The article task runs this before `git commit`; the video workflow runs it too and shows
the result, and the health check (tools/health.py) repeats it for the last articles.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTS = ("hook", "tension", "payoff")
BANNED = re.compile(r"like and subscribe|full story|trending ?tesla(\.com| dot com)|see you there", re.I)


def words(t):
    return len(re.findall(r"[\w$%'-]+", t or ""))


def photo_ok(kind, name):
    base = ROOT / "static/img"
    if kind == "lib":
        return (base / "lib" / name).resolve().is_file()
    return any((base / d / name).resolve().is_file() for d in ("", "models", "topics", "news", "gen", "real", "lib")) \
        or (base / name).resolve().is_file()


def check(path):
    err, warn = [], []
    try:
        a = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"not valid JSON: {e}"], []
    sh = a.get("short") or {}
    story = sh.get("story") or []
    if not story:
        return ["no short.story: every article needs a Short"], []
    if not 6 <= len(story) <= 10:
        err.append(f"short.story has {len(story)} beats (rule: 6-10)")
    total = 0
    for i, b in enumerate(story, 1):
        t, ov = (b.get("text") or "").strip(), (b.get("overlay") or "").strip()
        if b.get("part") not in PARTS:
            err.append(f"beat {i}: part '{b.get('part')}' is not one of hook/tension/payoff")
        if not t:
            err.append(f"beat {i}: no text (voice)")
        if not ov:
            err.append(f"beat {i}: no overlay (the exact text on screen)")
        elif len(ov) > 42:
            err.append(f"beat {i}: overlay has {len(ov)} characters (max ~36, it must fit on 2 lines): {ov}")
        elif len(ov) > 36:
            warn.append(f"beat {i}: overlay has {len(ov)} characters (aim for 36 or fewer): {ov}")
        n = words(t)
        total += n
        if n > 13:
            err.append(f"beat {i}: {n} spoken words, about {n / 2.6:.1f} s (rule 2.5-4 s, 7-11 words): split it")
        elif n < 5 and i not in (1, len(story)):
            warn.append(f"beat {i}: only {n} spoken words, about {n / 2.6:.1f} s (rule 2.5-4 s)")
        if BANNED.search(t) or BANNED.search(ov):
            err.append(f"beat {i}: call to action or site name in the script (only allowed in the description)")
        pics = ([b["lib"]] if isinstance(b.get("lib"), str) else b.get("lib") or [])
        other = ([b["img"]] if isinstance(b.get("img"), str) else b.get("img") or [])
        for p in pics:
            if not photo_ok("lib", p):
                err.append(f"beat {i}: lib photo not found: {p}")
        for p in other:
            if not photo_ok("img", p):
                warn.append(f"beat {i}: img photo not found: {p}")
        if not pics and not other and not b.get("photo"):
            err.append(f"beat {i}: no picture (lib, img or photo)")
        if n >= 8 and len(pics) + len(other) + len(b.get("photo") or []) < 2:
            warn.append(f"beat {i}: longer than 3 s with one picture (give it 2)")
    if story:
        hook = (story[0].get("text") or "").strip()
        if words(hook) > 10:
            err.append(f"hook has {words(hook)} words: it must land within 2 seconds (max ~8 words)")
        if re.match(r"(in|on|back in|when|during)\s+(\d{4}|january|february|march|april|may|june|july|august|september|"
                    r"october|november|december)", hook, re.I):
            err.append("hook opens with a date or scene setting: start with the claim or the number")
        last = (story[-1].get("text") or "").strip()
        if last.lower() == hook.lower() or (story[-1].get("overlay") or "").strip().lower() == \
                (story[0].get("overlay") or "").strip().lower():
            err.append("the last beat repeats the hook word for word (rule v4: a different line that runs on into it)")
    if not 38 <= total <= 92:
        (err if total > 100 or total < 30 else warn).append(
            f"Short has {total} spoken words, about {total / 2.6:.0f} s (rule 15-35 s = 40-90 words)")
    if len(sh.get("hooks") or []) != 3:
        err.append("short.hooks must hold exactly 3 hook variants")
    for k in ("hook_pick", "loop", "signals", "learning", "yt_title_en", "yt_title_nl", "en", "nl"):
        if not sh.get(k):
            err.append(f"short.{k} is missing")
    pr = sh.get("proof")
    if not (isinstance(pr, dict) and pr.get("source") and pr.get("why")):
        err.append("short.proof is missing or incomplete ({source, views, why}): the proof that this topic already "
                   "pulls viewers (README, PROVEN TOPICS)")
    if not (sh.get("learning") or {}).get("test"):
        warn.append("short.learning.test is missing: the ONE thing this Short changes compared with the previous one")
    if len(sh.get("yt_title_en") or "") > 48:
        warn.append(f"yt_title_en has {len(sh['yt_title_en'])} characters (aim for 45 or fewer)")
    v = (a.get("video") or {}).get("en")
    if v:
        texts = [b for b in v if b.get("text")]
        n = sum(words(b["text"]) for b in texts)
        if not 650 <= n <= 1450:
            warn.append(f"long video has {n} spoken words (rule 900-1,300, 6-8 minutes at most)")
        bare = sum(1 for b in texts if not b.get("img") and not b.get("photo"))
        if bare:
            warn.append(f"long video: {bare} text block(s) without their own picture")
        if texts and words(re.split(r"(?<=[.!?])\s", texts[0]["text"])[0]) > 16:
            warn.append("long video: the first sentence is long; it must be the hook claim itself")
        if texts and BANNED.search(texts[-1]["text"]):
            err.append("long video ends with a call to action (rule: a payoff that links back to the opening)")
        for k in ("yt_title_en", "yt_title_nl"):
            if not (a.get("video") or {}).get(k):
                err.append(f"video.{k} is missing")
    return err, warn


def main():
    bad = False
    for p in sys.argv[1:]:
        err, warn = check(p)
        print(f"{Path(p).name}: {len(err)} error(s), {len(warn)} warning(s)")
        for e in err:
            print(f"  ERROR   {e}")
        for w in warn:
            print(f"  warning {w}")
        bad = bad or bool(err)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
