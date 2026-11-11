"""For a video/queue.txt request: is it a story Short that must be uploaded like a normal one?

Prints GitHub outputs: "story=<slug>" and "qstory=1" when the line asks for a Short (no --full) with --upload of an
article that has a "short.story" script. Such a request is then rendered with video/story.py and published through
the normal Short upload step (public, thumbnail, on to TikTok/Instagram/Facebook) instead of the plain queue upload.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
q = (sys.argv[1] if len(sys.argv) > 1 else "").split()
if q and "--full" not in q and "--upload" in q:
    for f in (ROOT / "content/articles").glob(f"*-{q[0]}.json"):
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if a.get("slug") == q[0] and (a.get("short") or {}).get("story"):
            print(f"story={q[0]}")
            print("qstory=1")
