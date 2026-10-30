"""Give existing long videos their thumbnail (opening frame: photo + label) and report the token's scopes.

Usage (in GitHub Actions, with the YT_* secrets):  python3 tools/yt_thumbs.py [video_id ...]
Without ids: every video in content/videos.json. Renders only the first 2 seconds (silent), so no ElevenLabs.
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "video"))
import upload  # noqa: E402

at = upload.token()
with urllib.request.urlopen(f"https://oauth2.googleapis.com/tokeninfo?access_token={at}", timeout=60) as r:
    print("::notice::YouTube token scopes:", json.load(r).get("scope"))
vids = json.loads((ROOT / "content/videos.json").read_text(encoding="utf-8"))
# "ID=path.jpg": upload that image as the thumbnail of video ID (e.g. the opening frame of a Short)
for arg in [x for x in sys.argv[1:] if "=" in x]:
    vid, jpg = arg.split("=", 1)
    upload.set_thumbnail(vid, None, at, jpg=ROOT / jpg)
want = {x for x in sys.argv[1:] if "=" not in x}
if len(want) < len(sys.argv[1:]) and not want:
    sys.exit(0)
for v in vids:
    if want and v["id"] not in want:
        continue
    lang = v.get("lang", "en")
    out = ROOT / "video/out" / f"{v['slug']}-{lang}-full.mp4"
    env = {k: x for k, x in os.environ.items() if not k.startswith("ELEVENLABS")}
    env["FULL_PREVIEW"] = "0-2"
    subprocess.run([sys.executable, str(ROOT / "video/full.py"), v["slug"], lang], check=True, env=env,
                   stdout=subprocess.DEVNULL)
    upload.set_thumbnail(v["id"], out, at)
