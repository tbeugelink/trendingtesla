"""Story Shorts wait for William's review: they are uploaded as PRIVATE videos and listed in ops/story-pending.json.
He checks them in YouTube Studio and DELETES the ones that are not good. This script (every 15 minutes, in
shorts-page.yml) makes a Short that is still private after REVIEW_HOURS public (with its title as thumbnail), and
posts every public one to TikTok, Instagram and Facebook via Buffer; the site picks it up from the public feed.

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
REVIEW_HOURS = 2
keep, changed = [], False
now = datetime.now(timezone.utc)
for p in pending:
    st = status.get(p["id"])
    if st == "private" and now - datetime.fromisoformat(p["made"]) > timedelta(hours=REVIEW_HOURS):
        mp4 = ROOT / "video/out" / f"{p['slug']}-en-short.mp4"
        mp4.parent.mkdir(parents=True, exist_ok=True)
        if not mp4.exists():
            subprocess.run(["gh", "run", "download", str(p["run"]), "-n", f"story-{p['slug']}", "-D", str(mp4.parent)])
        if mp4.exists() and subprocess.run([sys.executable, str(ROOT / "tools/story_publish.py"), p["id"], str(mp4)]).returncode == 0:
            st = "public"
    if st == "public":
        mp4 = ROOT / "video/out" / f"{p['slug']}-en-short.mp4"
        mp4.parent.mkdir(parents=True, exist_ok=True)
        ok = mp4.exists() or subprocess.run(["gh", "run", "download", str(p["run"]), "-n", f"story-{p['slug']}",
                                             "-D", str(mp4.parent)]).returncode == 0
        if ok and mp4.exists():
            r = subprocess.run(["bash", str(ROOT / "tools/tiktok_publish.sh"), str(mp4)], capture_output=True, text=True)
            print(r.stdout + r.stderr)
            if "::warning::" in r.stdout + r.stderr:  # say it loudly: for 11 days this failed with a false "posted"
                print(f"::error::Story Short {p['slug']} was NOT posted to TikTok/Instagram/Facebook (see the warning above)")
            else:
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
