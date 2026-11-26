"""Upload the reviewed LINK pivotal-trial Short once, public, with its thumbnail.

The video file is the finished 27.6 s render. This script does not re-encode it
and does not touch the site, the Shorts queue, or ops/videos-paused.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video"))
import upload  # noqa: E402

HERE = Path(__file__).resolve().parent
MP4 = HERE / "render-out" / "neuralink-fda-link-trial-short.mp4"
THUMB = HERE / "render-out" / "neuralink-fda-link-trial-thumb.jpg"
TITLE = "FDA Approved Neuralink's First Pivotal Trial #Shorts"
APPROVED_BYTES = 12615574
DESCRIPTION = """The FDA just approved Neuralink's first pivotal trial.

On 25 November 2026 Neuralink announced FDA approval to launch LINK, the first pivotal trial of an implantable brain-computer interface in the United States. It is for adults with severe paralysis from ALS. The study tests thought control of a cursor, typing, and apps. It builds on more than 30 people already implanted. Enrollment is open. Taking part costs nothing, and travel and lodging for study visits are supported.

This is not market approval. The N1 implant is still investigational.

Full story: https://trendingtesla.com/neuralink-gets-fda-approval-for-pivotal-als-trial/

Sources:
Neuralink, 25 Nov 2026: https://x.com/neuralink/status/2125694580544680185
Neuralink, Neuralink Receives FDA Approval to Launch LINK Pivotal Study: https://neuralink.com/updates/neuralink-receives-fda-approval-to-launch-link-pivotal-study/
Neuralink, device-control trials: https://neuralink.com/trials/device-control/

Footage: Neuralink's announcement montage, 25 Nov 2026, from that post. The @cb_doge clip was not used. That video is a host at a table cut with Starlink satellites, not the N1 or the trial.

Voice-over generated with AI (ElevenLabs); script written and checked by TrendingTesla.
#Shorts #Neuralink"""
TAGS = ["Neuralink", "Shorts", "FDA"]


def privacy(vid, at):
    q = urllib.parse.urlencode({"part": "status,snippet", "id": vid})
    req = urllib.request.Request("https://www.googleapis.com/youtube/v3/videos?" + q,
                                 headers={"Authorization": f"Bearer {at}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        items = json.load(r).get("items") or []
    if not items:
        return {}
    item = items[0]
    return {"privacy": (item.get("status") or {}).get("privacyStatus"),
            "title": (item.get("snippet") or {}).get("title")}


def post_thumbnail(vid, path, at):
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId="
        + urllib.parse.quote(vid) + "&uploadType=media",
        data=path.read_bytes(), method="POST",
        headers={"Authorization": f"Bearer {at}", "Content-Type": "image/jpeg"})
    try:
        with urllib.request.urlopen(req, timeout=120):
            return {"ok": True, "file": path.name}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"ok": False, "file": path.name, "code": e.code, "body": body[:800]}


def upload_video(at):
    body = {
        "snippet": {"title": TITLE, "description": DESCRIPTION, "tags": TAGS, "categoryId": "2",
                    "defaultLanguage": "en", "defaultAudioLanguage": "en"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True},
    }
    size = MP4.stat().st_size
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    with urllib.request.urlopen(req, timeout=60) as r:
        loc = r.headers["Location"]
    with open(MP4, "rb") as f:
        put = urllib.request.Request(loc, data=f.read(), method="PUT",
                                     headers={"Authorization": f"Bearer {at}", "Content-Type": "video/mp4"})
    with urllib.request.urlopen(put, timeout=600) as r:
        return json.load(r)["id"]


def main():
    if TITLE != "FDA Approved Neuralink's First Pivotal Trial #Shorts":
        raise SystemExit("title drifted")
    if not MP4.is_file() or not THUMB.is_file():
        raise SystemExit("the reviewed mp4 or thumbnail is missing")
    size = MP4.stat().st_size
    if size != APPROVED_BYTES:
        raise SystemExit(f"refusing to upload {size} bytes; the approved render is {APPROVED_BYTES} bytes")
    at = upload.token()
    existing = upload.remote_duplicate(TITLE, at)
    if existing:
        vid = existing
        print(json.dumps({"upload": "exists", "url": f"https://youtu.be/{vid}"}))
    else:
        vid = upload_video(at)
        print(json.dumps({"upload": "created", "url": f"https://youtu.be/{vid}"}))
    state = privacy(vid, at)
    print(json.dumps({"url": f"https://youtu.be/{vid}", "privacy": state.get("privacy"),
                      "title": state.get("title")}))
    thumb = post_thumbnail(vid, THUMB, at)
    if thumb["ok"]:
        print(json.dumps({"thumbnail": "set", "file": thumb["file"]}))
    else:
        print(json.dumps({"thumbnail": "failed", "file": thumb["file"], "code": thumb["code"],
                          "body": thumb["body"]}))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"YouTube upload failed: {e.code} {e.read().decode(errors='replace')[:800]}")
