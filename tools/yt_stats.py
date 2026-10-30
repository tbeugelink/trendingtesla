"""Views, likes and comments of every video on the channel (long videos and Shorts).

Usage (in GitHub Actions, with the YT_* secrets):  python3 tools/yt_stats.py
Prints one JSON line per video (for Claude to read in the log) and a table in the run summary.
With --history: also appends this snapshot to ops/stats/history.jsonl (used by tools/learn.py).
Public counts come from the YouTube Data API. When the token also has the yt-analytics.readonly scope, it adds per
video from the YouTube Analytics API: average view percentage and duration (how long people keep watching) and,
where YouTube provides it, engaged views. Without that scope those fields are simply missing.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "video"))
import upload  # noqa: E402

at = upload.token()


def get(url):
    req = urllib.request.Request("https://www.googleapis.com/youtube/v3/" + url,
                                 headers={"Authorization": f"Bearer {at}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


ch = get("channels?part=contentDetails,statistics&mine=true")["items"][0]
uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
ids, page = [], ""
while True:
    d = get(f"playlistItems?part=contentDetails&maxResults=50&playlistId={uploads}{page}")
    ids += [i["contentDetails"]["videoId"] for i in d["items"]]
    if not d.get("nextPageToken"):
        break
    page = "&pageToken=" + d["nextPageToken"]

shorts = {x["id"] for x in json.loads((ROOT / "content/shorts.json").read_text(encoding="utf-8"))}
rows = []
for i in range(0, len(ids), 50):
    d = get("videos?part=snippet,statistics,contentDetails&id=" + ",".join(ids[i:i + 50]))
    for v in d["items"]:
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", v["contentDetails"]["duration"])
        secs = sum(int(x or 0) * k for x, k in zip(m.groups(), (3600, 60, 1)))
        s = v["statistics"]
        rows.append({"id": v["id"], "type": "short" if v["id"] in shorts or secs <= 180 else "long",
                     "published": v["snippet"]["publishedAt"], "title": v["snippet"]["title"],
                     "seconds": secs, "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                     "comments": int(s.get("commentCount", 0))})
rows.sort(key=lambda r: r["published"], reverse=True)


def analytics(rows):
    """Watch-time figures per video from the YouTube Analytics API (needs the yt-analytics.readonly scope)."""
    from datetime import date
    ids = ",".join(r["id"] for r in rows)
    for metrics in ("views,engagedViews,averageViewDuration,averageViewPercentage",
                    "views,averageViewDuration,averageViewPercentage"):
        q = urllib.parse.urlencode({"ids": "channel==MINE", "startDate": "2026-01-01", "endDate": date.today().isoformat(),
                                    "metrics": metrics, "dimensions": "video", "filters": f"video=={ids}",
                                    "maxResults": 200})
        req = urllib.request.Request(f"https://youtubeanalytics.googleapis.com/v2/reports?{q}",
                                     headers={"Authorization": f"Bearer {at}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("::notice::No YouTube Analytics access yet (scope yt-analytics.readonly missing); views only")
                return
            continue  # e.g. a metric YouTube does not offer: try the shorter list
        cols = [c["name"] for c in d.get("columnHeaders", [])]
        by = {row[0]: dict(zip(cols, row)) for row in d.get("rows", [])}
        for r in rows:
            m = by.get(r["id"])
            if m:
                r["avg_pct"] = round(float(m.get("averageViewPercentage", 0)), 1)
                r["avg_sec"] = round(float(m.get("averageViewDuration", 0)))
                if "engagedViews" in m:
                    r["engaged"] = int(m["engagedViews"])
        print(f"::notice::YouTube Analytics: watch-time figures for {len(by)} videos")
        return


if rows:
    analytics(rows)
print("CHANNEL", json.dumps(ch["statistics"]))
if "--history" in sys.argv:
    from datetime import datetime, timezone
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    h = ROOT / "ops/stats/history.jsonl"
    h.parent.mkdir(parents=True, exist_ok=True)
    with h.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"at": at, **{k: r[k] for k in ("id", "type", "published", "views", "likes", "comments", "avg_pct", "avg_sec", "engaged") if k in r}}) + "\n")
for r in rows:
    print("STAT", json.dumps(r, ensure_ascii=False))
summ = os.environ.get("GITHUB_STEP_SUMMARY")
if summ:
    with open(summ, "a", encoding="utf-8") as f:
        f.write(f"Channel: {ch['statistics']}\n\n| Published | Type | Views | Likes | Comments | Title |\n|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['published'][:16]} | {r['type']} | {r['views']} | {r['likes']} | {r['comments']} | "
                    f"[{r['title'][:70]}](https://youtu.be/{r['id']}) |\n")
