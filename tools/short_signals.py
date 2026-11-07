"""Algorithm signals of the recent Shorts -> ops/short-signals.md (read by every article task, rules of 8 Nov 2026).

Per Short, newest first: views, "stayed" (engaged views / views: roughly YouTube's "viewed vs swiped away", goal
over 70%), average % watched (completion; over 100% means people loop it, goal 90%+), likes per 1000 views
(a share/like proxy; the Data API gives no share count), length, hook type and the first spoken line (the hook).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    last = {}
    for line in (ROOT / "ops/stats/history.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") == "short":
            last[r["id"]] = r
    slug_of = {x["id"]: x["slug"] for x in load(ROOT / "content/shorts.json", []) if x.get("id")}
    arts = {}
    for f in (ROOT / "content/articles").glob("*.json"):
        a = load(f, {})
        if a.get("slug"):
            arts[a["slug"]] = a
    rows = []
    for vid, r in last.items():
        a = arts.get(slug_of.get(vid, ""), {})
        sh = a.get("short") or {}
        story = sh.get("story") or []
        hook = (story[0]["text"] if story else (sh.get("en") or "").split(". ")[0])[:110]
        views = r.get("views") or 0
        stayed = round(100 * (r.get("engaged") or 0) / views) if views else 0
        pct = r.get("avg_pct") or 0
        length = round(100 * (r.get("avg_sec") or 0) / pct) if pct else 0
        rows.append((r.get("published", ""), vid, views, stayed, pct, round(1000 * (r.get("likes") or 0) / views, 1)
                     if views else 0, length, sh.get("hook", "-"), hook))
    rows.sort(reverse=True)
    good = [x for x in rows if x[2] >= 300 and x[4]]  # analytics arrive 2-3 days after publishing
    avg = lambda k: round(sum(x[k] for x in good) / len(good)) if good else 0  # noqa: E731
    out = [f"# Short signals (updated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
           "Goals (William, 8 Nov 2026): stayed > 70% (viewed vs swiped), watched >= 90% with loops (over 100%),",
           "likes and shares up. 'stayed' = engaged views / views. Length in seconds is estimated from the stats.", "",
           f"Average of Shorts with 300+ views: stayed {avg(3)}%, watched {avg(4)}%, length {avg(6)} s.", "",
           "| published | views | stayed | watched | likes/1000 | length | hook type | hook (first line) |",
           "|---|---|---|---|---|---|---|---|"]
    for p, vid, v, st, pc, lk, ln, ht, hk in rows[:20]:
        if not pc:
            st = pc = ln = "-"
        else:
            st, pc, ln = f"{st}%", f"{pc}%", f"{ln} s"
        out.append(f"| {p[:10]} [{vid}](https://youtu.be/{vid}) | {v} | {st} | {pc} | {lk} | {ln} | {ht} | "
                   f"{hk.replace('|', '/')} |")
    (ROOT / "ops/short-signals.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out[:8]))


if __name__ == "__main__":
    main()
