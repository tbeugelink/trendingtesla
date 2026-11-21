"""Check an article's "short" (and "video") script BEFORE it is committed, so a slip never stops a video again.

Usage: python3 tools/check_article.py content/articles/<file>.json [...]      (exit code 1 when there are errors)

ERRORS must be fixed before the commit; WARNINGS should be fixed where possible. The rules are the Short section of
README.md. `short.proof`, `short.learning` and `short.signals` are optional (a warning, not an error). The beat,
hook, overlay and no-call-to-action checks stay errors. A Short title over 8 words, over 50 characters, with an
ellipsis, with a clause comma, or with "but" / "maar" is an error. A comma inside a number (1,020 or 1.020) is
not. A long-video title over 70 characters or with an ellipsis is an error. The article task runs this before `git commit`.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTS = ("hook", "tension", "payoff")
BANNED = re.compile(r"like and subscribe|full story|trending ?tesla(\.com| dot com)|see you there", re.I)
MAX_TITLE_WORDS = 8
MAX_TITLE_CHARS = 50
MAX_LONG_TITLE_CHARS = 70
ELLIPSIS = re.compile(r"…|\.{3}")
BUT = re.compile(r"\b(?:but|maar)\b", re.I)
# thousands separators sit between digits (1,020 / 1.020 / 1,020,000); a clause comma does not
NUMBER_SEP = re.compile(r"(?<=\d)[.,](?=\d)")


def words(t):
    return len(re.findall(r"[\w$%'-]+", t or ""))


def claim_text(title):
    """YouTube claim with a trailing #Shorts tag removed. The text is not shortened."""
    return re.sub(r"\s*#shorts\s*$", "", (title or "").strip(), flags=re.I).strip()


def title_words(title):
    """Word count for a title. A number with a thousands separator counts as one word."""
    return words(NUMBER_SEP.sub("", title or ""))


def clause_comma(title):
    """A comma that separates clauses. A comma inside a number is kept."""
    return "," in NUMBER_SEP.sub("", title or "")


def yt_title_errors(title, field, kind="short"):
    """Hard failures for a YouTube title. Article headlines are not passed in.

    kind 'short': at most 8 words and 50 characters, no ellipsis, no clause comma, no but/maar.
    kind 'long': a search title, at most 70 characters, no ellipsis. Not the Short limits.
    """
    t = claim_text(title)
    out = []
    if ELLIPSIS.search(t):
        out.append(f"{field} is cut off with an ellipsis")
    if kind == "long":
        if len(t) > MAX_LONG_TITLE_CHARS:
            out.append(f"{field} has {len(t)} characters (max {MAX_LONG_TITLE_CHARS})")
        return out
    n = title_words(t)
    if n > MAX_TITLE_WORDS:
        out.append(f"{field} has {n} words (max {MAX_TITLE_WORDS})")
    if len(t) > MAX_TITLE_CHARS:
        out.append(f"{field} has {len(t)} characters (max {MAX_TITLE_CHARS})")
    if clause_comma(t):
        out.append(f"{field} contains a comma that separates clauses")
    if BUT.search(t):
        out.append(f"{field} uses 'but' or 'maar' (one claim, not a lede)")
    return out


def youtube_line(raw, kind):
    """Title line for the upload file. Never cuts the claim and never adds an ellipsis.

    kind 'short' appends ' #Shorts'. kind 'long' does not. Raises ValueError when the claim breaks
    the title rules or the line would pass YouTube's 100-character limit.
    """
    claim = claim_text(raw)
    errs = yt_title_errors(claim, "title", kind)
    if errs:
        raise ValueError("; ".join(errs))
    shown = f"{claim} #Shorts" if kind == "short" else claim
    if len(shown) > 100:
        raise ValueError(f"YouTube title is {len(shown)} characters (max 100) and is not cut off")
    if ELLIPSIS.search(shown):
        raise ValueError("YouTube title is cut off with an ellipsis")
    return shown


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
        if (ROOT / "ops/videos-paused").exists() and not a.get("short") and not a.get("video"):
            # while videos are paused (ops/videos-paused) an article is published without a Short
            return [], ["no Short: videos are paused (ops/videos-paused), so the article goes out without one"]
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
    for k in ("hook_pick", "loop", "yt_title_en", "yt_title_nl", "en", "nl"):
        if not sh.get(k):
            err.append(f"short.{k} is missing")
    if not sh.get("signals"):
        warn.append("short.signals is missing (optional)")
    if not sh.get("learning"):
        warn.append("short.learning is missing (optional)")
    elif not (sh.get("learning") or {}).get("test"):
        warn.append("short.learning.test is missing (optional): the one thing this Short changes")
    pr = sh.get("proof")
    if not (isinstance(pr, dict) and pr.get("source") and pr.get("why")):
        warn.append("short.proof is missing or incomplete (optional): {source, views, why}")
    if story and not story[0].get("sfx"):
        warn.append("beat 1 has no sfx: describe the natural sound of what moves in the hook picture")
    for k in ("yt_title_en", "yt_title_nl"):
        if sh.get(k):
            err.extend(yt_title_errors(sh[k], f"short.{k}", "short"))
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
        if texts:
            # The news-package close may say "Read the full article on trendingtesla.com".
            # Other plugs ("like and subscribe", "see you there") stay banned.
            end_check = re.sub(
                r"read the full article on trending ?tesla(\.com| dot com)",
                "",
                texts[-1]["text"],
                flags=re.I,
            )
            if BANNED.search(end_check):
                err.append("long video ends with a call to action (rule: a payoff that links back to the opening)")
        for k in ("yt_title_en", "yt_title_nl"):
            val = (a.get("video") or {}).get(k)
            if not val:
                err.append(f"video.{k} is missing")
            else:
                err.extend(yt_title_errors(val, f"video.{k}", "long"))
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
