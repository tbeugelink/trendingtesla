"""Learn from YouTube statistics which kinds of articles and videos perform best.

Runs daily in GitHub Actions after tools/yt_stats.py has added a snapshot to ops/stats/history.jsonl.
  python3 tools/learn.py
Writes ops/performance.md: the guidance the article-writing tasks read before choosing and writing a story.

Method (kept simple on purpose, the channel is young and numbers are small):
- Fair comparison: every video is measured by its views 48 hours after publishing (interpolated between
  daily snapshots; videos not yet 48 hours old are left out of the learning).
- Score = log(views_48h + 1) minus the median of the same kind (Short or long video). 0 = typical,
  +0.7 = about twice as many views as typical, -0.7 = about half.
- For each feature of the article (topic, label type, kind of label, models, title style, morning/evening)
  the average score of its videos, with the number of videos. Values from fewer than 3 videos count as a hint.
- Newer data counts more (half-life 30 days), so tastes that change are followed.
- Exploration: the guidance always tells the writers to keep trying other topics and styles, so the
  system does not lock itself into a few early winners.
"""
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "ops/stats/history.jsonl"
OUT = ROOT / "ops/performance.md"
AGE = 48.0  # hours
HALF_LIFE = 30.0  # days


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def articles():
    out = {}
    for f in (ROOT / "content/articles").glob("*.json"):
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out[a["slug"]] = a
    return out


def features(a):
    lab = a.get("label") or {}
    en = lab.get("en") or {}
    text = f"{en.get('sub', '')} {en.get('text', '')}".strip()
    title = (a.get("en") or {}).get("title", "")
    hour = int((a.get("time") or "12:00")[:2])
    f = {
        "topic": a.get("category", "?"),
        "label type": {"a": "a (red kicker + yellow line)", "c": "c (yellow + red block)",
                       "n": "n (number)", "r": "r (negative news, red)"}.get(lab.get("style"), lab.get("style") or "none"),
        "label has a question": "yes" if "?" in text else "no",
        "label starts with a number": "yes" if re.match(r"[\d$€]", en.get("text", "") or en.get("sub", "")) else "no",
        "about a specific car": ", ".join(sorted(a.get("models", []))) or "no (company-wide)",
        "title has a number": "yes" if re.search(r"\d", title) else "no",
        "title length": "short (<= 10 words)" if len(title.split()) <= 10 else "long (> 10 words)",
        "explainer or news": "explainer" if re.search(r"explained|how |what |which |why |vs\b", title.lower()) else "news",
        "published": "morning" if hour < 15 else "evening",
    }
    return f, title, text


def main():
    if not HIST.exists():
        print("no history yet")
        return
    snaps = defaultdict(list)  # id -> [(time, views, likes, row)]
    for line in HIST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        snaps[r["id"]].append((ts(r["at"]), r["views"], r.get("likes", 0), r))
    slug_of = {}
    for name, kind in (("shorts.json", "short"), ("videos.json", "long")):
        p = ROOT / "content" / name
        for v in json.loads(p.read_text(encoding="utf-8")) if p.exists() else []:
            slug_of[v["id"]] = (v["slug"], kind)
    arts = articles()
    now = datetime.now(timezone.utc)

    rows = []
    for vid, ss in snaps.items():
        ss.sort(key=lambda x: x[0])
        last = ss[-1][3]
        slug, kind = slug_of.get(vid, (None, last.get("type", "long")))
        if not slug or slug not in arts:
            continue
        pub = ts(last["published"])
        pts = [(0.0, 0, 0)] + [((t - pub).total_seconds() / 3600, v, lk) for t, v, lk, _ in ss]
        if pts[-1][0] < AGE:
            continue
        for (h0, v0, l0), (h1, v1, l1) in zip(pts, pts[1:]):
            if h1 >= AGE:
                k = (AGE - h0) / (h1 - h0) if h1 > h0 else 1
                v48, l48 = v0 + k * (v1 - v0), l0 + k * (l1 - l0)
                break
        w = 0.5 ** ((now - pub).days / HALF_LIFE)
        rows.append({"id": vid, "slug": slug, "kind": kind, "v48": v48, "l48": l48, "w": w,
                     "feat": features(arts[slug])[0], "title": features(arts[slug])[1],
                     "label": features(arts[slug])[2]})

    for kind in ("short", "long"):
        logs = sorted(math.log(r["v48"] + 1) for r in rows if r["kind"] == kind)
        med = logs[len(logs) // 2] if logs else 0
        for r in rows:
            if r["kind"] == kind:
                r["score"] = math.log(r["v48"] + 1) - med
                r["median"] = math.exp(med) - 1

    lines = ["# What works on the TrendingTesla YouTube channel", "",
             f"Updated {now:%Y-%m-%d %H:%M} UTC by tools/learn.py from daily YouTube statistics "
             f"({len(rows)} videos at least {AGE:.0f} hours old). Do not edit by hand.", ""]
    if len(rows) < 6:
        lines += ["Not enough data yet (fewer than 6 videos that are 48 hours old). Write as usual and keep "
                  "varying topics, label types and title styles so the channel learns what works.", ""]
    else:
        def avg(rs):
            ws = sum(r["w"] for r in rs)
            return sum(r["score"] * r["w"] for r in rs) / ws if ws else 0

        def mult(s):
            return f"{math.exp(s):.1f}x"

        for kind, name in (("short", "Shorts"), ("long", "Long videos")):
            rs = [r for r in rows if r["kind"] == kind]
            if rs:
                lines.append(f"- {name}: {len(rs)} videos, typical {rs[0]['median']:.0f} views after 48 hours.")
        lines.append("")

        both = defaultdict(list)
        for r in rows:
            for k, v in r["feat"].items():
                both[(k, v)].append(r)
        strong, weak = [], []
        lines += ["## By feature", "",
                  "Views after 48 hours compared with a typical video of the same kind (1.0x = typical). "
                  "n = number of videos; below 3 it is only a hint.", ""]
        by_key = defaultdict(list)
        for (k, v), rs in both.items():
            by_key[k].append((v, rs))
        for k in sorted(by_key):
            lines.append(f"**{k}**")
            for v, rs in sorted(by_key[k], key=lambda x: -avg(x[1])):
                s = avg(rs)
                lines.append(f"- {v}: {mult(s)} (n={len(rs)})")
                if len(rs) >= 3 and s >= 0.35:
                    strong.append((s, f"{k}: {v} ({mult(s)}, n={len(rs)})"))
                if len(rs) >= 3 and s <= -0.35:
                    weak.append((s, f"{k}: {v} ({mult(s)}, n={len(rs)})"))
            lines.append("")

        top = sorted(rows, key=lambda r: -r["score"])
        lines += ["## Best performers", ""]
        for r in top[:5]:
            lines.append(f"- {r['kind']}: {r['v48']:.0f} views at 48h ({mult(r['score'])}) - {r['title']} "
                         f"[label: {r['label']}]")
        lines += ["", "## Weakest", ""]
        for r in top[-3:][::-1]:
            lines.append(f"- {r['kind']}: {r['v48']:.0f} views at 48h ({mult(r['score'])}) - {r['title']} "
                         f"[label: {r['label']}]")
        lines += ["", "## Guidance for the next articles", ""]
        if strong:
            lines.append("Does well (prefer this when two stories are about equally newsworthy, and use these styles):")
            lines += [f"- {t}" for _, t in sorted(strong, reverse=True)[:6]]
        if weak:
            lines.append("Does less well (still cover it when it is the important news, but give it a sharper hook):")
            lines += [f"- {t}" for _, t in sorted(weak)[:6]]
        if not strong and not weak:
            lines.append("No clear patterns yet (no feature with at least 3 videos differs much from typical).")
        lines.append("")
    lines += ["## Rules for using this", "",
              "- News value and accuracy always come first: never pick an older, weaker or less important story "
              "because a topic scores well, and never change facts for a better hook.",
              "- Use the patterns for choices between comparable stories, and for the title, label and the first "
              "sentence of the Short (the hook).",
              "- Keep exploring: about one in three articles should try a topic, label type or title style that "
              "is not in the 'does well' list, so the channel keeps learning.",
              ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
