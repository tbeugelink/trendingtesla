"""Upload the reviewed 32-hour pad Short and queue it in Buffer.

Run from GitHub Actions, where the YouTube and Buffer secrets are available.
The picture is the v5 file. The thumbnail is the v2 image, passed in explicitly.
Buffer's AI-content label stays off when BUFFER_AI_GENERATED=0. Nothing is posted to X.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SLUG = "spacex-relaunched-one-pad-after-32-hours"
CLAIM = "SpaceX Used One Pad Twice In 32 Hours"
SRC = HERE / "publish" / "spacex-one-pad-32-hours-short-v5.mp4"
THUMB = HERE / "publish" / "thumb-v2.jpg"


def article():
    return json.loads(next((ROOT / "content" / "articles").glob(f"*-{SLUG}.json")).read_text(encoding="utf-8"))


def meta():
    sys.path.insert(0, str(ROOT / "tools"))
    import check_article
    title = check_article.youtube_line(CLAIM, "short")
    a = article()
    url = f"https://trendingtesla.com/{SLUG}/"
    desc = (
        f"{a['en']['description']}\n\n"
        f"Read the full article: {url}\n\n"
        "Footage: SpaceX webcasts of USSF-317 (20 November 2026) and NROL-136 (22 November 2026).\n\n"
        "Voice-over generated with AI (ElevenLabs); script written and checked by TrendingTesla."
    )
    tags = ["Tesla", "TrendingTesla", "SpaceX"]
    return title, desc, tags


def already_listed(title):
    sys.path.insert(0, str(ROOT / "video"))
    import upload
    return upload.local_duplicate(SLUG, title)


def prepare():
    title, desc, tags = meta()
    if "tbeugelink" in (title + desc).lower():
        raise SystemExit("refusing to upload: the owner name is in the YouTube text")
    out = ROOT / "video" / "out"
    out.mkdir(parents=True, exist_ok=True)
    mp4 = out / f"{SLUG}-en-short.mp4"
    shutil.copyfile(SRC, mp4)
    mp4.with_suffix(".txt").write_text(
        f"TITLE:\n{title}\n\nDESCRIPTION:\n{desc}\n\nTAGS:\n{', '.join(tags)}\n",
        encoding="utf-8")
    return mp4, title


def video_id(text):
    m = re.search(r"https://youtu\.be/([A-Za-z0-9_-]+)", text or "")
    return m.group(1) if m else None


def ensure_public(vid):
    sys.path.insert(0, str(ROOT / "video"))
    import upload
    at = upload.token()
    import urllib.request
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/videos?part=status,snippet&id=" + vid,
        headers={"Authorization": f"Bearer {at}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        item = json.load(r)["items"][0]
    status = item["status"]
    title = item["snippet"]["title"]
    print(f"youtube title: {title}")
    print(f"youtube privacy: {status.get('privacyStatus')}")
    if status.get("privacyStatus") != "public":
        status["privacyStatus"] = "public"
        body = {"id": vid, "status": {k: status[k] for k in (
            "privacyStatus", "embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids") if k in status}}
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/videos?part=status",
            data=json.dumps(body).encode(), method="PUT",
            headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"privacy set to {json.load(r)['status']['privacyStatus']}")
    upload.set_thumbnail(vid, None, at, jpg=THUMB)
    return title


def main():
    if not SRC.exists() or not THUMB.exists():
        raise SystemExit(f"missing {SRC} or {THUMB}")
    if not os.environ.get("YT_CLIENT_ID"):
        raise SystemExit("YT_CLIENT_ID is missing. This runs in GitHub Actions.")
    mp4, title = prepare()
    hit = already_listed(title)
    if hit:
        raise SystemExit(f"a Short for this article or title is already listed ({hit}). Not uploading again.")
    env = os.environ.copy()
    env["YT_PRIVACY"] = "public"
    env["BUFFER_AI_GENERATED"] = "0"
    proc = subprocess.run([sys.executable, str(ROOT / "video" / "upload.py"), str(mp4), "en"],
                          capture_output=True, text=True, env=env)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    vid = video_id(proc.stdout)
    if not vid:
        raise SystemExit("YouTube upload did not return a video id")
    shown = ensure_public(vid)
    if shown != title:
        raise SystemExit(f"uploaded title is {shown!r}, expected {title!r}")
    print(f"YOUTUBE https://youtu.be/{vid}")
    rel = subprocess.run(["bash", str(ROOT / "tools" / "tiktok_publish.sh"), str(mp4)],
                         capture_output=True, text=True, env=env)
    print(rel.stdout)
    if rel.stderr:
        print(rel.stderr, file=sys.stderr)
    if "::warning::" in rel.stdout + rel.stderr:
        raise SystemExit("Buffer did not accept every network. See the warning above.")
    print("BUFFER_DONE")


if __name__ == "__main__":
    main()
