"""Keep content/shorts.json and content/videos.json in step with the public YouTube channel.

Reads the public feed of the TrendingTesla channel (no API key needed; it only lists public
videos, the newest 15) and keeps every Short in content/shorts.json and every long video in
content/videos.json, so the lists keep growing past those 15. The article a video belongs to
comes from the trendingtesla.com link in its description ("/nl/" in that link means the Dutch
article). For long videos the length is read once from the watch page. Prints "changed" when a
file was updated.

Usage:  python3 tools/sync_shorts.py
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNEL = "UCwbxx3sGDHFtX035A7eFYXQ"  # @TrendingTesla
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}"
DIR = Path(__file__).resolve().parent.parent / "content"
FILES = {"short": DIR / "shorts.json", "long": DIR / "videos.json"}
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}
UA = {"User-Agent": "Mozilla/5.0 trendingtesla.com"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def seconds(vid):
    try:
        m = re.search(rb'"lengthSeconds":"(\d+)"', get(f"https://www.youtube.com/watch?v={vid}"))
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def main():
    root = ET.fromstring(get(FEED))
    entries = root.findall("a:entry", NS)
    old = {k: json.loads(f.read_text(encoding="utf-8")) if f.exists() else [] for k, f in FILES.items()}
    have = {k: {s["id"]: s for s in v} for k, v in old.items()}
    seen, oldest = set(), None
    for e in entries:
        vid = e.findtext("yt:videoId", namespaces=NS)
        if not vid:
            continue
        link = e.find("a:link", NS).get("href", "") if e.find("a:link", NS) is not None else ""
        pub = e.findtext("a:published", default="", namespaces=NS)
        oldest = min(oldest or pub, pub)
        seen.add(vid)
        kind = "short" if "/shorts/" in link else "long"
        desc = e.findtext("m:group/m:description", default="", namespaces=NS)
        m = re.search(r"trendingtesla\.com/(nl/)?([a-z0-9-]+)/", desc)
        item = {"id": vid, "slug": m.group(2) if m else "",
                "title": re.sub(r"\s*#Shorts\s*$", "", e.findtext("a:title", default="", namespaces=NS)).strip(),
                "published": pub}
        if kind == "long":
            item["lang"] = "nl" if m and m.group(1) else "en"
            prev = have["long"].get(vid, {})
            item["seconds"] = prev.get("seconds") or seconds(vid)
        have[kind][vid] = {**have[kind].get(vid, {}), **item}
    changed = False
    for kind, items in have.items():
        # a video within the feed's time span that is no longer in it was made private or removed
        if oldest and entries:
            items = {k: v for k, v in items.items() if k in seen or v["published"] < oldest}
        new = sorted(items.values(), key=lambda s: s["published"], reverse=True)
        if new != old[kind] and (new or FILES[kind].exists()):
            FILES[kind].write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            changed = True
    if changed:
        print("changed")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # a hiccup at YouTube should not break anything; next run tries again
        print(f"::warning::YouTube feed not read: {ex}", file=sys.stderr)
