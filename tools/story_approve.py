"""Story Shorts wait for William's review: they are uploaded as PRIVATE videos and listed in ops/story-pending.json.
He approves one by setting it to Public in YouTube Studio. This script (run every 15 minutes by shorts-page.yml)
then posts the approved Short to TikTok, Instagram and Facebook via Buffer (the site picks it up from the public
feed by itself). A Short that stays private is simply never posted; entries older than 30 days are dropped.

Usage (GitHub Actions, with the YT_* secrets, BUFFER_API_KEY and GH_TOKEN):  python3 tools/story_approve.py
Prints "changed" when ops/story-pending.json was updated.
"""
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "ops/story-pending.json"
pending = json.loads(P.read_text(encoding="utf-8")) if P.exists() else []
if not pending:
    sys.exit(0)
sys.path.insert(0, str(ROOT / "video"))
import upload  # noqa: E402

at = upload.token()
ids = ",".join(p["id"] for p in pending)
req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/videos?part=status&id={ids}",
                             headers={"Authorization": f"Bearer {at}"})
with urllib.request.urlopen(req, timeout=60) as r:
    status = {v["id"]: v["status"]["privacyStatus"] for v in json.load(r)["items"]}
keep, changed = [], False
now = datetime.now(timezone.utc)
for p in pending:
    st = status.get(p["id"])
    if st == "public":
        mp4 = ROOT / "video/out" / f"{p['slug']}-en-short.mp4"
        mp4.parent.mkdir(parents=True, exist_ok=True)
        ok = subprocess.run(["gh", "run", "download", str(p["run"]), "-n", f"story-{p['slug']}", "-D", str(mp4.parent)]).returncode == 0
        if ok and mp4.exists():
            subprocess.run(["bash", str(ROOT / "tools/tiktok_publish.sh"), str(mp4)])
            print(f"::notice::Approved story Short {p['slug']} (https://youtu.be/{p['id']}): posted via Buffer")
        else:
            print(f"::warning::Approved story Short {p['slug']}: video file not found (run {p['run']}), not posted via Buffer")
        changed = True
    elif st is None:  # deleted on YouTube
        print(f"::notice::Story Short {p['slug']} was deleted on YouTube")
        changed = True
    elif now - datetime.fromisoformat(p["made"]) > timedelta(days=30):
        changed = True
    else:
        keep.append(p)
if changed:
    P.write_text(json.dumps(keep, indent=1) + "\n", encoding="utf-8")
    print("changed")
