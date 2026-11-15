"""Upload a finished video to YouTube with the title/description/tags from its .txt file.

Usage:  python3 video/upload.py video/out/<name>.mp4 [en|nl]

Needs the repository secrets YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN (OAuth client of the
"TrendingTesla Uploader" Google Cloud project, scope youtube.upload, authorised for the TrendingTesla
channel). Privacy comes from YT_PRIVACY (default "private": Google keeps uploads from unaudited API
projects private anyway until the project passes its audit).
"""
import json
import re
import urllib.error
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNEL = "UCwbxx3sGDHFtX035A7eFYXQ"
SHORT_LISTS = ("content/shorts.json", "ops/story-pending.json", "ops/short-uploads.json")


def token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"].strip(),
        "client_secret": os.environ["YT_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["YT_REFRESH_TOKEN"].strip(),
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=60) as r:
        return json.load(r)["access_token"]


def norm_title(title):
    return " ".join(re.sub(r"\s*#shorts\s*$", "", (title or ""), flags=re.I).split()).lower()


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def known_short_rows():
    rows = []
    for rel in SHORT_LISTS:
        data = load_json(ROOT / rel, [])
        if isinstance(data, list):
            rows.extend(x for x in data if isinstance(x, dict))
    return rows


def local_duplicate(slug, title):
    """A Short already recorded for this article or this YouTube title, or None."""
    nt = norm_title(title)
    for row in known_short_rows():
        if slug and row.get("slug") == slug:
            return row.get("id") or "listed"
        if nt and norm_title(row.get("title")) == nt:
            return row.get("id") or "listed"
    return None


def remember_short(vid, slug, title):
    """Durable record, kept after story-pending is cleared and before the YouTube feed catches up."""
    p = ROOT / "ops" / "short-uploads.json"
    rows = load_json(p, [])
    if not isinstance(rows, list):
        rows = []
    title = re.sub(r"\s*#Shorts\s*$", "", title or "").strip()
    if any(x.get("id") == vid or (slug and x.get("slug") == slug) for x in rows):
        return
    rows.insert(0, {"id": vid, "slug": slug, "title": title,
                    "published": datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    p.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def remote_duplicate(title, at):
    """Best-effort: the public feed, then a channel search. A failure here must not block a first upload."""
    nt = norm_title(title)
    if not nt:
        return None
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}",
            headers={"User-Agent": "trendingtesla.com"})
        with urllib.request.urlopen(req, timeout=20) as r:
            xml = r.read().decode("utf-8", "replace")
        for block in xml.split("<entry>")[1:]:
            vid = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", block)
            shown = re.search(r"<media:title>([^<]+)</media:title>", block) or re.search(r"<title>([^<]+)</title>", block)
            if vid and shown and norm_title(shown.group(1)) == nt:
                return vid.group(1)
    except Exception as e:
        print(f"::warning::YouTube feed not checked for an existing Short ({e})")
    if not at:
        return None
    try:
        q = urllib.parse.urlencode({"part": "snippet", "channelId": CHANNEL, "type": "video",
                                    "maxResults": "5", "q": title[:80]})
        req = urllib.request.Request("https://www.googleapis.com/youtube/v3/search?" + q,
                                     headers={"Authorization": f"Bearer {at}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        for it in data.get("items") or []:
            sn = it.get("snippet") or {}
            if norm_title(sn.get("title")) == nt:
                vid = (it.get("id") or {}).get("videoId")
                if vid:
                    return vid
    except Exception as e:
        print(f"::warning::YouTube title search skipped ({e})")
    return None


def merge_saved(src):
    """After a hard reset, put this run's new Short rows back (upload ledger and shorts.json)."""
    src = Path(src)

    def merge(path, mine):
        cur = load_json(path, [])
        if not isinstance(cur, list):
            cur = []
        ids = {x.get("id") for x in cur}
        slugs = {x.get("slug") for x in cur if x.get("slug")}
        add = []
        for x in mine:
            if x.get("id") in ids or (x.get("slug") and x.get("slug") in slugs):
                continue
            add.append(x)
            if x.get("id"):
                ids.add(x["id"])
            if x.get("slug"):
                slugs.add(x["slug"])
        if add:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(add + cur, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    merge(ROOT / "content" / "shorts.json", load_json(src / "shorts.json", []))
    merge(ROOT / "ops" / "short-uploads.json", load_json(src / "short-uploads.json", []))


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


def set_thumbnail(vid, mp4, at=None, at_sec=None, jpg=None):
    """Use the opening frame (photo + label) as the YouTube thumbnail: 1280x720 for long videos, 720x1280 for
    Shorts (otherwise YouTube picks a random frame, and Shorts with shared photos end up looking the same).
    A little extra contrast, colour and sharpness makes it stand out in the small feed tiles.
    jpg: upload this ready-made image instead of taking a frame from mp4."""
    import subprocess
    import tempfile
    if at_sec is None:  # story Shorts show their big title only in the first moment, before the first key word
        at_sec = float(os.environ.get("THUMB_AT", "1.0"))
    if jpg is None:
        jpg = Path(tempfile.mkdtemp()) / f"{vid}.jpg"
        size = "720:1280" if str(mp4).endswith("-short.mp4") else "1280:720"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at_sec), "-i", str(mp4), "-frames:v", "1",
                        "-vf", f"scale={size}:flags=lanczos,eq=contrast=1.08:saturation=1.22,unsharp=5:5:0.6", "-q:v", "2", str(jpg)], check=True)
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


def add_captions(vid, path, lang, at):
    """Closed captions (CC) for long videos; needs the youtube.force-ssl scope. Never fails the upload."""
    if not path.exists():
        return
    meta = json.dumps({"snippet": {"videoId": vid, "language": lang, "name": {"en": "English", "nl": "Nederlands"}[lang],
                                   "isDraft": False}}).encode()
    b = "ttcaptions"
    body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + meta +
            f"\r\n--{b}\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + path.read_bytes() +
            f"\r\n--{b}--\r\n".encode())
    req = urllib.request.Request("https://www.googleapis.com/upload/youtube/v3/captions?part=snippet&uploadType=multipart",
                                 data=body, method="POST", headers={"Authorization": f"Bearer {at}",
                                                                     "Content-Type": f"multipart/related; boundary={b}"})
    try:
        with urllib.request.urlopen(req, timeout=120):
            print(f"captions added to {vid}")
    except urllib.error.HTTPError as e:
        print(f"::warning::captions not added ({e.code}): {e.read().decode('utf-8', 'replace')[:200]}")


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--merge-lists":
        merge_saved(sys.argv[2])
        return
    mp4 = Path(sys.argv[1])
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    title, desc, tags = read_meta(mp4.with_suffix(".txt"))
    slug = re.sub(r"-(en|nl)-(full|short)\.mp4$", "", mp4.name)
    if mp4.name.endswith("-short.mp4"):
        hit = local_duplicate(slug, title)
        if hit:
            print(f"::notice::Skip upload of {mp4.name}: a Short already exists ({hit}). Not uploading a second copy.")
            return
    if "#Shorts" in title and "#Shorts" not in desc:
        desc += "\n\n#Shorts #Tesla"
    body = {
        "snippet": {"title": title[:100], "description": desc[:4900], "tags": tags[:15], "categoryId": "2",
                    "defaultLanguage": lang, "defaultAudioLanguage": lang},
        "status": {"privacyStatus": os.environ.get("YT_PRIVACY") or "private",
                   "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    at = token()
    if mp4.name.endswith("-short.mp4"):
        hit = remote_duplicate(title, at)
        if hit:
            print(f"::notice::Skip upload of {mp4.name}: YouTube already has this title ({hit}). Not uploading a second copy.")
            remember_short(hit, slug, title)
            return
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
        remember_short(vid, slug, title)
        set_thumbnail(vid, mp4, at)
    # remember the length of long videos; the site shows it ("▶ 4:15") and YouTube's feed has none
    if mp4.name.endswith("-full.mp4"):
        set_thumbnail(vid, mp4, at)
        if os.environ.get("YT_CAPTIONS") == "1":  # off: YouTube makes its own captions, translatable into most languages
            add_captions(vid, mp4.with_suffix(".srt"), lang, at)
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
