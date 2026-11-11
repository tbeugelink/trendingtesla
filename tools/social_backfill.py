"""Post Shorts that never reached TikTok / Instagram / Facebook, one at a time (ops/social-queue.json).

ops/social-queue.json: [{"slug": "...", "after": "2026-11-12T08:00:00+00:00"}, ...]. Each run (every ~15-60 minutes in
shorts-page.yml) posts at most ONE entry whose "after" time has passed, through tools/tiktok_post.py, using the mp4
that is already on the GitHub release "tiktok-<slug>". The result goes to ops/social-log.jsonl; the entry is removed
(after 3 failed tries it is removed too and reported). Prints "changed" when it wrote something.
"""
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / "ops/social-queue.json"
REPO = "tbeugelink/trendingtesla"


def main():
    queue = json.loads(Q.read_text(encoding="utf-8")) if Q.exists() else []
    now = datetime.now(timezone.utc)
    due = next((e for e in queue if datetime.fromisoformat(e["after"]) <= now), None)
    if not due:
        return
    slug = due["slug"]
    name = f"{slug}-en-short.mp4"
    url = f"https://github.com/{REPO}/releases/download/tiktok-{slug[:90]}/{name}"
    out = ROOT / "video/out" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, out)  # also proves the public link Buffer will fetch really works
        r = subprocess.run([sys.executable, str(ROOT / "tools/tiktok_post.py"), str(out), url], capture_output=True, text=True)
        text = r.stdout + r.stderr
    except Exception as e:
        text = f"::warning::social post for {slug} failed: video file not on the release ({e})"
    print(text)
    if "::warning::" in text:
        due["tries"] = due.get("tries", 0) + 1
        if due["tries"] >= 3:
            queue.remove(due)
            print(f"::error::Short {slug} could not be posted to TikTok/Instagram/Facebook after 3 tries")
    else:
        queue.remove(due)
        print(f"::notice::Short {slug} posted to TikTok/Instagram/Facebook (catch-up)")
    Q.write_text(json.dumps(queue, indent=1) + "\n", encoding="utf-8")
    print("changed")


if __name__ == "__main__":
    main()
