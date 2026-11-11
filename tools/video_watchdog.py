"""Watchdog: every article must get its Short and its long video. Runs every 15 minutes (shorts-page.yml).

For each article published 1.5-36 hours ago that has a "short" or "video" script but no Short (content/shorts.json)
or no long video (content/videos.json) yet, it requests the missing video once through video/queue.txt
(the video workflow then makes and uploads it). A second failure is reported in ops/video-problems.md and as a
failed run, so it never goes unnoticed. Prints "changed" when it wrote something and "queued" when it asked for a video.
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
    # busy = the watchdog itself asked for a video less than an hour ago (its own "# watchdog <time>" line; the
    # file's modification time is useless here: a fresh checkout always looks seconds old)
    busy = False
    for line in (queue.read_text().splitlines() if queue.exists() else []):
        if line.startswith("# watchdog "):
            try:
                busy = (now - datetime.fromisoformat(line[11:].strip())).total_seconds() < 3600
            except ValueError:
                pass
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
    changed = queued = False
    for s, kind in missing:
        key = f"{s}:{kind}"
        if tried.get(key, 0) >= 1:
            problems.append(f"- {now:%Y-%m-%d %H:%M} UTC: {kind} video for {s} still missing after a retry")
            tried[key] = 2
            continue
        if busy:
            continue
        queue.write_text(f"{s} en {'--full ' if kind == 'full' else ''}--upload\n# watchdog {now.isoformat()}\n")
        tried[key] = 1
        busy = changed = queued = True
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
    if queued:  # only then may the workflow start the video run (never on a problem report alone: that once
        print("queued")  # re-made and re-uploaded whatever old request was still in video/queue.txt)


if __name__ == "__main__":
    main()
