"""Add the channel's public YouTube Shorts to content/shorts.json.

Reads the public feed of the TrendingTesla channel (no API key needed; it only lists public
videos, the newest 15) and keeps every Short in content/shorts.json, so the list keeps growing
past those 15. The article a Short belongs to comes from the "Read the full article" link in
its description. Prints "changed" when the file was updated.

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
FILE = Path(__file__).resolve().parent.parent / "content" / "shorts.json"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}


def main():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 trendingtesla.com"})
    with urllib.request.urlopen(req, timeout=60) as r:
        root = ET.fromstring(r.read())
    old = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else []
    have = {s["id"]: s for s in old}
    seen, oldest = set(), None
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        link = (e.find("a:link", NS).get("href") or "") if e.find("a:link", NS) is not None else ""
        pub = e.findtext("a:published", default="", namespaces=NS)
        oldest = min(oldest or pub, pub)
        seen.add(vid)
        if not vid or "/shorts/" not in link:
            continue
        desc = e.findtext("m:group/m:description", default="", namespaces=NS)
        m = re.search(r"trendingtesla\.com/(?:nl/)?([a-z0-9-]+)/", desc)
        item = {"id": vid, "slug": m.group(1) if m else "",
                "title": re.sub(r"\s*#Shorts\s*$", "", e.findtext("a:title", default="", namespaces=NS)).strip(),
                "published": e.findtext("a:published", default="", namespaces=NS)}
        have[vid] = {**have.get(vid, {}), **item}
    # a Short within the feed's time span that is no longer in it was made private or removed
    if oldest and len(root.findall("a:entry", NS)) > 0:
        have = {k: v for k, v in have.items() if k in seen or v["published"] < oldest}
    new = sorted(have.values(), key=lambda s: s["published"], reverse=True)
    if new != old:
        FILE.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("changed")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # a hiccup at YouTube should not break anything; next run tries again
        print(f"::warning::Shorts feed not read: {ex}", file=sys.stderr)
