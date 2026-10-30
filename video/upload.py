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


def set_thumbnail(vid, mp4, at=None, at_sec=1.0, jpg=None):
    """Use the opening frame (photo + label) as the YouTube thumbnail: 1280x720 for long videos, 720x1280 for
    Shorts (otherwise YouTube picks a random frame, and Shorts with shared photos end up looking the same).
    jpg: upload this ready-made image instead of taking a frame from mp4."""
    import subprocess
    import tempfile
    if jpg is None:
        jpg = Path(tempfile.mkdtemp()) / f"{vid}.jpg"
        size = "720:1280" if str(mp4).endswith("-short.mp4") else "1280:720"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at_sec), "-i", str(mp4), "-frames:v", "1",
                        "-vf", f"scale={size}:flags=lanczos", "-q:v", "2", str(jpg)], check=True)
    jpg = Path(jpg)
    req = urllib.request.Request(
        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
        data=jpg.read_bytes(), method="POST",
        headers={"Authorization": f"Bearer {at or token()}", "Content-Type": "image/jpeg"})
    try:
        with urllib.request.urlopen(req, timeout=120):
            print(f"::notice::Thumbnail set for https://youtu.be/{vid}")
    except urllib.error.HTTPError as e:  # a missing thumbnail must never fail the upload
        print(f"::warning::Thumbnail for {vid} failed: {e.code} {e.read().decode(errors='replace')[:300]}")


def register(vid, mp4, lang, title):
    """Put the new (public) video on the site right away, instead of waiting for YouTube's slow feed."""
    import re
    import subprocess
    from datetime import datetime, timezone
    if (os.environ.get("YT_PRIVACY") or "private") != "public":
        return
    long = mp4.name.endswith("-full.mp4")
    slug = re.sub(r"-(en|nl)-(full|short)\.mp4$", "", mp4.name)
    f = Path(__file__).resolve().parent.parent / "content" / ("videos.json" if long else "shorts.json")
    items = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    if any(x["id"] == vid for x in items):
        return
    item = {"id": vid, "slug": slug, "title": re.sub(r"\s*#Shorts\s*$", "", title).strip(),
            "published": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
    if long:
        item["lang"] = lang
        item["seconds"] = round(float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)], text=True)))
        items = [x for x in items if not (x.get("slug") == slug and x.get("lang", "en") == lang)]  # a remake replaces
    items.insert(0, item)
    f.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    register(vid, mp4, lang, title)
    if mp4.name.endswith("-short.mp4"):
        set_thumbnail(vid, mp4, at)
    # remember the length of long videos; the site shows it ("▶ 4:15") and YouTube's feed has none
    if mp4.name.endswith("-full.mp4"):
        set_thumbnail(vid, mp4, at)
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import yt_playlists  # topic playlist on YouTube (needs the youtube scope; never fails the upload)
        yt_playlists.add(vid, mp4.name.rsplit(f"-{lang}-full.mp4", 1)[0], at)
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
