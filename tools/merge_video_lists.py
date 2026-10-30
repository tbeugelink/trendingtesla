"""Merge this run's video lists into the newest ones on main, so parallel video runs never conflict.

Usage (in the workflow):
  python3 tools/merge_video_lists.py save DIR   # before pulling: keep this run's copies in DIR
  python3 tools/merge_video_lists.py apply DIR  # after resetting to origin/main: add what this run added

videos.json / shorts.json: entries are joined by video id (this run's entry wins, a remake of the same
slug + language replaces the old long video); a "seconds" of 0 never overwrites a real length.
video_lengths.json: keys are added or updated.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["videos.json", "shorts.json", "video_lengths.json"]


def load(p, empty):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty


def merge_list(cur, mine, long):
    """Main's list stays as it is; videos only this run has go on top, and a real length fills a 0."""
    by_id = {c["id"]: c for c in cur}
    new = []
    for x in mine:
        old = by_id.get(x["id"])
        if old is None:
            new.append(x)
        elif long and not old.get("seconds") and x.get("seconds"):
            old["seconds"] = x["seconds"]
    for x in reversed(new):
        if long:  # a remake replaces the old long video of the same article and language
            cur = [c for c in cur if not (c.get("slug") == x.get("slug") and c.get("lang", "en") == x.get("lang", "en"))]
        cur.insert(0, x)
    return cur


def main():
    mode, d = sys.argv[1], Path(sys.argv[2])
    d.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = ROOT / "content" / name
        if mode == "save":
            if src.exists():
                shutil.copy(src, d / name)
            continue
        mine_p = d / name
        if not mine_p.exists():
            continue
        if name == "video_lengths.json":
            out = load(src, {})
            out.update({k: v for k, v in load(mine_p, {}).items() if v})
        else:
            out = merge_list(load(src, []), load(mine_p, []), name == "videos.json")
        # long videos: fill a missing length from video_lengths.json
        src.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    vl = load(ROOT / "content/video_lengths.json", {})
    vp = ROOT / "content/videos.json"
    vids = load(vp, [])
    if any(not v.get("seconds") and vl.get(v["id"]) for v in vids):
        for v in vids:
            if not v.get("seconds") and vl.get(v["id"]):
                v["seconds"] = vl[v["id"]]
        vp.write_text(json.dumps(vids, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
