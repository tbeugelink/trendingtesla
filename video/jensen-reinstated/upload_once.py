"""Upload the reviewed Jensen reinstated Short once, public, with the approved thumbnail.

The video file is the finished render. This script does not re-encode it and does not
touch the site, the Shorts queue, or ops/videos-paused.
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
MP4 = HERE / "jensen-reinstated-short.mp4"
THUMB_9X16 = HERE / "jensen-reinstated-thumb-9x16.jpg"
THUMB_16X9 = HERE / "jensen-reinstated-thumb-16x9.jpg"
TITLE = "Jensen Huang REINSTATED!"
DESCRIPTION = """Nvidia's board unanimously reinstated Jensen Huang as president and CEO, 11 days after he resigned. The board says input from senior US officials convinced it his return poses no national security risk.

Full story: https://trendingtesla.com/nvidia-brings-jensen-huang-back-as-ceo/

Photos: Anders Eidesvik, CC BY 4.0 / CC BY-SA 4.0, via Wikimedia Commons. US Capitol: Architect of the Capitol, public domain.
#Shorts #Nvidia #JensenHuang"""
TAGS = ["Nvidia", "Jensen Huang", "Shorts"]


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


def permission_denied(result):
    body = (result.get("body") or "").lower()
    return result.get("code") in (401, 403) and (
        "thumbnail" in body or "permission" in body or "forbidden" in body or "insufficient" in body
    )


def set_thumbnail(vid, at):
    first = post_thumbnail(vid, THUMB_9X16, at)
    if first["ok"]:
        print(json.dumps({"thumbnail": "set", "file": first["file"]}))
        return
    print(json.dumps({"thumbnail": "rejected", **{k: first[k] for k in ("file", "code", "body")}}))
    if permission_denied(first):
        print(json.dumps({
            "thumbnail": "failed",
            "reason": "The channel has no custom-thumbnail permission.",
            "detail": first.get("body"),
        }))
        return
    second = post_thumbnail(vid, THUMB_16X9, at)
    if second["ok"]:
        print(json.dumps({"thumbnail": "set", "file": second["file"], "fallback": True}))
        return
    print(json.dumps({"thumbnail": "rejected", **{k: second[k] for k in ("file", "code", "body")}}))
    reason = "The channel has no custom-thumbnail permission." if permission_denied(second) else "YouTube rejected both thumbnail files."
    print(json.dumps({"thumbnail": "failed", "reason": reason, "detail": second.get("body")}))


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
    if TITLE != "Jensen Huang REINSTATED!":
        raise SystemExit("title drifted")
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
    set_thumbnail(vid, at)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"YouTube upload failed: {e.code} {e.read().decode(errors='replace')[:800]}")
