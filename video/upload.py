"""Upload a finished video to YouTube with the title/description/tags from its .txt file.

Usage:  python3 video/upload.py video/out/<name>.mp4 [en|nl]

Needs the repository secrets YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN (OAuth client of the
"TrendingTesla Uploader" Google Cloud project, scope youtube.upload, authorised for the TrendingTesla
channel). Privacy comes from YT_PRIVACY (default "private": Google keeps uploads from unaudited API
projects private anyway until the project passes its audit).
"""
import json
import urllib.error
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"].strip(),
        "client_secret": os.environ["YT_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["YT_REFRESH_TOKEN"].strip(),
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=60) as r:
        return json.load(r)["access_token"]


def read_meta(txt):
    parts, key = {}, None
    for line in txt.read_text(encoding="utf-8").splitlines():
        if line.rstrip(":") in ("TITLE", "DESCRIPTION", "TAGS") and line.endswith(":"):
            key = line[:-1]
            parts[key] = []
        elif key:
            parts[key].append(line)
    get = lambda k: "\n".join(parts.get(k, [])).strip()
    return get("TITLE"), get("DESCRIPTION"), [t.strip() for t in get("TAGS").split(",") if t.strip()]


def set_thumbnail(vid, mp4, at=None, at_sec=1.0):
    """Use the opening frame (photo + label) of a long video as its YouTube thumbnail (1280x720 JPEG)."""
    import subprocess
    import tempfile
    jpg = Path(tempfile.mkdtemp()) / f"{vid}.jpg"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at_sec), "-i", str(mp4), "-frames:v", "1",
                    "-vf", "scale=1280:720:flags=lanczos", "-q:v", "2", str(jpg)], check=True)
    req = urllib.request.Request(
        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
        data=jpg.read_bytes(), method="POST",
        headers={"Authorization": f"Bearer {at or token()}", "Content-Type": "image/jpeg"})
    try:
        with urllib.request.urlopen(req, timeout=120):
            print(f"::notice::Thumbnail set for https://youtu.be/{vid}")
    except urllib.error.HTTPError as e:  # a missing thumbnail must never fail the upload
        print(f"::warning::Thumbnail for {vid} failed: {e.code} {e.read().decode(errors='replace')[:300]}")


def main():
    mp4 = Path(sys.argv[1])
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    title, desc, tags = read_meta(mp4.with_suffix(".txt"))
    if "#Shorts" in title and "#Shorts" not in desc:
        desc += "\n\n#Shorts #Tesla"
    body = {
        "snippet": {"title": title[:100], "description": desc[:4900], "tags": tags[:15], "categoryId": "2",
                    "defaultLanguage": lang, "defaultAudioLanguage": lang},
        "status": {"privacyStatus": os.environ.get("YT_PRIVACY") or "private",
                   "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    at = token()
    size = mp4.stat().st_size
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    with urllib.request.urlopen(req, timeout=60) as r:
        loc = r.headers["Location"]
    with open(mp4, "rb") as f:
        put = urllib.request.Request(loc, data=f.read(), method="PUT",
                                     headers={"Authorization": f"Bearer {at}", "Content-Type": "video/mp4"})
    with urllib.request.urlopen(put, timeout=600) as r:
        vid = json.load(r)["id"]
    # remember the length of long videos; the site shows it ("▶ 4:15") and YouTube's feed has none
    if mp4.name.endswith("-full.mp4"):
        set_thumbnail(vid, mp4, at)
        import subprocess
        secs = round(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                    "-of", "csv=p=0", str(mp4)], text=True).strip()))
        lf = Path(__file__).resolve().parent.parent / "content" / "video_lengths.json"
        lengths = json.loads(lf.read_text(encoding="utf-8")) if lf.exists() else {}
        lengths[vid] = secs
        lf.write_text(json.dumps(lengths, indent=2) + "\n", encoding="utf-8")
    print(f"::notice::Uploaded {mp4.name} to YouTube ({body['status']['privacyStatus']}): https://youtu.be/{vid}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"YouTube upload failed: {e.code} {e.read().decode(errors='replace')[:800]}")
