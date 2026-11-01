"""Publish a story Short that is waiting for review: set its thumbnail to the opening title and make it public.
Buffer (TikTok, Instagram, Facebook) and the site follow by themselves (tools/story_approve.py, sync_shorts.py).

Usage (GitHub Actions, YT_* secrets):  python3 tools/story_publish.py <video id> <mp4>
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "video"))
import upload  # noqa: E402

vid, mp4 = sys.argv[1], sys.argv[2]
at = upload.token()
upload.set_thumbnail(vid, mp4, at, at_sec=0.2)
req = urllib.request.Request("https://www.googleapis.com/youtube/v3/videos?part=status&id=" + vid,
                             headers={"Authorization": f"Bearer {at}"})
with urllib.request.urlopen(req, timeout=60) as r:
    st = json.load(r)["items"][0]["status"]
st["privacyStatus"] = "public"
body = {"id": vid, "status": {k: st[k] for k in ("privacyStatus", "embeddable", "license", "publicStatsViewable",
                                                 "selfDeclaredMadeForKids") if k in st}}
req = urllib.request.Request("https://www.googleapis.com/youtube/v3/videos?part=status", data=json.dumps(body).encode(),
                             method="PUT", headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=60) as r:
    print(f"::notice::https://youtu.be/{vid} is now {json.load(r)['status']['privacyStatus']}")
