"""Watchdog: every article must get its Short and its long video. Runs every 15 minutes (shorts-page.yml).

For each article published 1.5-36 hours ago that has a "short" or "video" script but no Short (content/shorts.json)
or no long video (content/videos.json) yet, it requests the missing video once through video/queue.txt
(the video workflow then makes and uploads it). A second failure is reported in ops/video-problems.md and as a
failed run, so it never goes unnoticed. Prints "changed" when it wrote something.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "ops/video-retries.json"


def load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    now = datetime.now(timezone.utc)
    shorts = {x.get("slug") for x in load(ROOT / "content/shorts.json", [])}
    longs = {x.get("slug") for x in load(ROOT / "content/videos.json", [])}
    tried = load(LOG, {})
    queue = ROOT / "video/queue.txt"
    busy = queue.exists() and any(l.strip() and not l.startswith("#") for l in queue.read_text().splitlines()) and \
        (now.timestamp() - queue.stat().st_mtime) < 3600
    missing, problems = [], []
    for f in sorted((ROOT / "content/articles").glob("*.json"))[-12:]:
        a = load(f, {})
        try:
            at = datetime.fromisoformat(f"{a['date']}T{a.get('time', '00:00')}:00").replace(
                tzinfo=timezone(timedelta(hours=1)))
        except Exception:
            continue
        age = now - at
        if not (timedelta(hours=1.5) < age < timedelta(hours=36)):
            continue
        s = a["slug"]
        if (a.get("video") or {}).get("en") and s not in longs:
            missing.append((s, "full"))
        if a.get("short") and s not in shorts:
            missing.append((s, "short"))
    changed = False
    for s, kind in missing:
        key = f"{s}:{kind}"
        if kind == "short" and tried.get(key, 0) < 1:  # Shorts are not remade automatically: report it right away
            tried[key] = 1
        if tried.get(key, 0) >= 1:
            problems.append(f"- {now:%Y-%m-%d %H:%M} UTC: {kind} video for {s} still missing after a retry")
            tried[key] = 2
            continue
        if busy:
            continue
        queue.write_text(f"{s} en {'--full ' if kind == 'full' else ''}--upload\n# watchdog {now.isoformat()}\n")
        tried[key] = 1
        busy = changed = True
        print(f"::warning::{kind} video for {s} was missing: requested it again")
    if problems:
        p = ROOT / "ops/video-problems.md"
        old = p.read_text(encoding="utf-8") if p.exists() else "# Videos that failed twice\n\n"
        new = [x for x in problems if x.split(": ", 1)[1] not in old]
        if new:
            p.write_text(old.rstrip() + "\n" + "\n".join(new) + "\n", encoding="utf-8")
            changed = True
            for x in new:
                print(f"::error::{x}")
    LOG.write_text(json.dumps(tried, indent=1) + "\n", encoding="utf-8")
    if changed:
        print("changed")


if __name__ == "__main__":
    main()
