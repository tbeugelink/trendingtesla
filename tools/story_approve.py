"""Story Shorts are listed in ops/story-pending.json until they are public and posted to the other networks.

This script does not upload to YouTube and does not change a video's privacy. A manual
"Publish story Short" run makes one public. Every 15 minutes (shorts-page.yml) this script
then posts each public one to TikTok, Instagram and Facebook via Buffer, and writes it into
content/shorts.json before it leaves the pending list.

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


def ensure_listed(p):
    """The slug stays in the upload ledger after it leaves ops/story-pending.json."""
    title = p.get("title") or ""
    led = ROOT / "ops/short-uploads.json"
    rows = json.loads(led.read_text(encoding="utf-8")) if led.exists() else []
    known = next((x for x in rows if x.get("id") == p["id"] or x.get("slug") == p.get("slug")), None)
    if known and not title:
        title = known.get("title") or ""
    if not known:
        rows.insert(0, {"id": p["id"], "slug": p.get("slug") or "", "title": title, "published": p.get("made") or now.isoformat()})
        led.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    sf = ROOT / "content/shorts.json"
    items = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else []
    if any(x.get("id") == p["id"] or (p.get("slug") and x.get("slug") == p["slug"]) for x in items):
        return
    items.insert(0, {"id": p["id"], "slug": p.get("slug") or "", "title": title,
                     "published": p.get("made") or now.replace(microsecond=0).isoformat()})
    sf.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


for p in pending:
    st = status.get(p["id"])
    if st == "public":
        ensure_listed(p)
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
