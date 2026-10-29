"""YouTube playlists per topic: every long video goes into the playlist of its article's category.

Playlists are found by title on the channel (created when missing), so nothing has to be stored.
Needs a token with the youtube scope (YT_REFRESH_TOKEN). Used by video/upload.py after each long-video
upload; run by hand to sort existing videos:  python3 tools/yt_playlists.py   (all videos in content/videos.json)
"""
import glob
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://www.googleapis.com/youtube/v3"
# playlist title per category (English channel); categories not listed fall back to "news"
TITLES = {
    "news": "Tesla News", "models": "Tesla Models: Model 3, Model Y, Cybertruck & more",
    "charging": "Tesla Charging & Superchargers", "software": "Tesla Software Updates",
    "fsd": "Tesla FSD & Autopilot", "robotaxi": "Tesla Robotaxi & Cybercab", "optimus": "Tesla Optimus Robot",
    "factories": "Tesla Gigafactories", "xai": "xAI & Grok in Tesla", "energy": "Tesla Energy: Powerwall, Megapack & Solar",
    "spacex": "SpaceX & Tesla", "starlink": "Starlink Explained", "boring": "The Boring Company",
    "musk": "Elon Musk & Tesla", "earnings": "Tesla Earnings & Stock", "guides": "Tesla Tips & Guides",
}
DESC = ("{t}: independent news and plain-language explainers by TrendingTesla. "
        "Read the full articles on https://trendingtesla.com")


def call(at, method, path, params=None, body=None):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, method=method,
                                 headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def playlists(at):
    out, tok = {}, None
    while True:
        p = {"part": "snippet", "mine": "true", "maxResults": 50}
        if tok:
            p["pageToken"] = tok
        d = call(at, "GET", "playlists", p)
        out.update({x["snippet"]["title"]: x["id"] for x in d.get("items", [])})
        tok = d.get("nextPageToken")
        if not tok:
            return out


def category(slug):
    for f in glob.glob(str(ROOT / "content/articles" / f"*{slug}.json")):
        a = json.load(open(f, encoding="utf-8"))
        if a.get("slug") == slug:
            return a["category"]
    return "news"


def add(vid, slug, at, cache=None):
    """Put video `vid` (long video of article `slug`) in its topic playlist. Never raises."""
    try:
        title = TITLES.get(category(slug), TITLES["news"])
        have = cache if cache is not None else playlists(at)
        pid = have.get(title)
        if not pid:
            pid = call(at, "POST", "playlists", {"part": "snippet,status"},
                       {"snippet": {"title": title, "description": DESC.format(t=title), "defaultLanguage": "en"},
                        "status": {"privacyStatus": "public"}})["id"]
            have[title] = pid
            print(f"::notice::Created playlist '{title}'")
        items = call(at, "GET", "playlistItems", {"part": "snippet", "playlistId": pid, "videoId": vid})
        if not items.get("items"):
            call(at, "POST", "playlistItems", {"part": "snippet"},
                 {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}})
            print(f"::notice::Added https://youtu.be/{vid} to playlist '{title}'")
    except urllib.error.HTTPError as e:
        print(f"::warning::Playlist for {vid} failed: {e.code} {e.read().decode(errors='replace')[:300]}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "video"))
    import upload  # noqa: E402
    at = upload.token()
    cache = playlists(at)
    for v in json.loads((ROOT / "content/videos.json").read_text(encoding="utf-8")):
        add(v["id"], v["slug"], at, cache)
