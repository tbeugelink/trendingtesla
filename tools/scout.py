"""Look at OTHER YouTube channels to find what works: outlier videos and questions viewers keep asking.

Usage (in GitHub Actions, with the YT_* secrets; settings in ops/scout.json):
  python3 tools/scout.py tesla        daily: Tesla/SpaceX/xAI outliers of the last days -> ops/scout-tesla.md
  python3 tools/scout.py niches       weekly: compares candidate niches for a second channel -> ops/niches.md
Raw results are saved in ops/scout/ (one JSON file per run) so trends over weeks can be compared.

Method:
- Outlier: a video's views divided by the median views of the same channel's recent uploads of the same kind
  (Short or long video). 5x = five times what that channel normally gets. This shows which TOPIC pulls
  viewers, separate from how big the channel is.
- A niche looks good when SEVERAL different, preferably small or new channels have outliers in it
  (one channel can just be lucky or have a popular presenter).
- Viewer questions: the most-liked comments with a question under the strongest outliers that the creator
  did not answer. Each is a possible video with proven interest.
Uses only the YouTube Data API (search = 100 units, other calls 1 unit; the daily quota of 10,000 is shared
with the uploads), with a unit budget so a scan never eats the upload quota.
"""
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "video"))

CFG = json.loads((ROOT / "ops/scout.json").read_text(encoding="utf-8"))
BUDGET = {"tesla": 1500, "niches": 1800}  # 4 uploads a day (1,600 each) also need quota  # API units per run (uploads need the rest of the daily 10,000)
units = 0
at = None


class OutOfBudget(Exception):
    pass


KEY = os.environ.get("YT_API_KEY", "").strip()  # plain API key: needed to read comments (the OAuth token lacks that scope)
no_comments = False


def get(path, cost=1, key=False):
    global units
    if units + cost > LIMIT:
        raise OutOfBudget
    units += cost
    if key:
        req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/{path}&key={KEY}")
    else:
        req = urllib.request.Request("https://www.googleapis.com/youtube/v3/" + path,
                                     headers={"Authorization": f"Bearer {at}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def q(**kw):
    return urllib.parse.urlencode(kw)


def seconds(iso):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def videos(ids):
    out = {}
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 50):
        for v in get("videos?" + q(part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50])))["items"]:
            secs = seconds(v["contentDetails"].get("duration"))
            out[v["id"]] = {"id": v["id"], "title": v["snippet"]["title"], "channel_id": v["snippet"]["channelId"],
                            "channel": v["snippet"]["channelTitle"], "published": v["snippet"]["publishedAt"],
                            "lang": v["snippet"].get("defaultAudioLanguage") or v["snippet"].get("defaultLanguage") or "",
                            "seconds": secs, "kind": "short" if secs <= 180 else "long",
                            "views": int(v["statistics"].get("viewCount", 0)),
                            "comments": int(v["statistics"].get("commentCount", 0))}
    return out


def channels(ids):
    out = {}
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 50):
        for c in get("channels?" + q(part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50])))["items"]:
            st = c["statistics"]
            out[c["id"]] = {"subs": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0)),
                            "videos": int(st.get("videoCount", 0)), "created": c["snippet"]["publishedAt"],
                            "uploads": c["contentDetails"]["relatedPlaylists"]["uploads"]}
    return out


def baseline(ch, skip):
    """Median views of the channel's last 20 uploads, per kind (short/long), leaving out the videos being judged
    and uploads younger than 2 days (they have not had time to collect views)."""
    items = get("playlistItems?" + q(part="contentDetails", maxResults=20, playlistId=ch["uploads"]))["items"]
    ids = [i["contentDetails"]["videoId"] for i in items if i["contentDetails"]["videoId"] not in skip]
    recent = videos(ids)
    cut = datetime.now(timezone.utc) - timedelta(days=2)
    rows = [v for v in recent.values() if ts(v["published"]) < cut]
    med = {}
    for kind in ("short", "long"):
        vs = [v["views"] for v in rows if v["kind"] == kind]
        if len(vs) >= 3:
            med[kind] = statistics.median(vs)
    allv = [v["views"] for v in rows]
    med["all"] = statistics.median(allv) if len(allv) >= 3 else None
    return med


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def search(query, days, n=25, short=False):
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    extra = {"videoDuration": "short"} if short else {}
    d = get("search?" + q(part="id", type="video", q=query, order="viewCount", publishedAfter=after,
                          maxResults=n, relevanceLanguage="en", **extra), cost=100)
    return [i["id"]["videoId"] for i in d.get("items", []) if i["id"].get("videoId")]


def is_question(text):
    """A real question: a sentence ending in '?' with at least 5 words (not 'WHAT?!' or 'Where's the car?')."""
    for sent in re.findall(r"[^.!?]*\?", text):
        words = re.findall(r"[A-Za-z']+", sent)
        if len(words) >= 5 and not re.match(r"\s*what an? ", sent, re.I):
            return True
    return False


def questions(v, keep=6):
    """Most-liked top-level comments that ask something and got no answer from the creator."""
    global no_comments
    if no_comments:
        return []
    if not KEY:
        no_comments = True
        print("::notice::No YT_API_KEY secret: skipping viewer questions (outliers still work)")
        return []
    try:
        d = get("commentThreads?" + q(part="snippet,replies", videoId=v["id"], order="relevance",
                                      maxResults=100, textFormat="plainText"), key=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if "commentsDisabled" not in body:
            print(f"::warning::comments {v['id']}: HTTP {e.code} " + re.sub(r"\s+", " ", body)[:300])
            if e.code in (400, 403) and "commentsDisabled" not in body:
                no_comments = True  # key problem: do not repeat the same error for every video
        return []
    out = []
    for t in d.get("items", []):
        top = t["snippet"]["topLevelComment"]["snippet"]
        text = re.sub(r"\s+", " ", top.get("textDisplay", "")).strip()
        if not (15 <= len(text) <= 300) or not is_question(text):
            continue
        replies = (t.get("replies") or {}).get("comments", [])
        answered = any(r["snippet"].get("authorChannelId", {}).get("value") == v["channel_id"] for r in replies)
        if answered:
            continue
        out.append({"text": text, "likes": int(top.get("likeCount", 0)), "replies": t["snippet"]["totalReplyCount"]})
    out.sort(key=lambda c: (c["likes"], c["replies"]), reverse=True)
    seen, uniq = set(), []
    for c in out:
        k = c["text"].lower()[:80]
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq[:keep]


def own_channel():
    try:
        return get("channels?part=id&mine=true")["items"][0]["id"]
    except Exception:
        return None


def english(v):
    """English videos only: the channels we make are English-language (Dutch versions come from our own text)."""
    if v["lang"] and not v["lang"].lower().startswith("en"):
        return False
    letters = [ch for ch in v["title"] if ch.isalpha()]
    return bool(letters) and sum(ch.isascii() for ch in letters) / len(letters) >= 0.9


def judge(ids, own, top=25):
    """Outlier factor for each video, with its channel's size and age. Only the `top` most-viewed videos are
    judged (each new channel costs 2 API units for its baseline)."""
    vids = sorted((v for v in videos(ids).values() if v["channel_id"] != own and english(v)), key=lambda v: v["views"], reverse=True)
    vids = {v["id"]: v for v in vids[:top]}
    chans = channels([v["channel_id"] for v in vids.values()])
    base = {}
    for cid in chans:
        try:
            base[cid] = baseline(chans[cid], set(vids))
        except OutOfBudget:
            raise
        except Exception as e:  # one odd channel should not stop the scan
            print(f"::warning::baseline {cid}: {e}")
    rows = []
    now = datetime.now(timezone.utc)
    for v in vids.values():
        c, b = chans.get(v["channel_id"]), base.get(v["channel_id"])
        if not c or not b:
            continue
        med = b.get(v["kind"]) or b.get("all")
        if not med:
            continue
        rows.append({**v, "median": med, "factor": round(v["views"] / max(med, 50), 1), "subs": c["subs"],
                     "channel_age_days": (now - ts(c["created"])).days, "channel_videos": c["videos"]})
    rows.sort(key=lambda r: r["factor"], reverse=True)
    return rows


def fmt(n):
    if n is None:
        return "?"
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}K" if n >= 1e3 else str(int(n))


def link(v):
    return f"[{v['title']}](https://youtu.be/{v['id']})"


def save_raw(name, data):
    p = ROOT / "ops/scout" / f"{datetime.now(timezone.utc):%Y-%m-%d}-{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def run_tesla(own):
    cfg = CFG["tesla"]
    ids, notes = [], []
    for query in cfg["queries"]:
        try:
            ids += search(query, cfg["days"])
        except OutOfBudget:
            notes.append(f"stopped searching at '{query}' (API budget)")
            break
    rows = []
    try:
        rows = judge(ids, own, top=35)
    except OutOfBudget:
        notes.append("not all channels judged (API budget)")
    top = [r for r in rows if r["factor"] >= 3][:12]
    for r in top[:5]:
        try:
            r["questions"] = questions(r)
        except OutOfBudget:
            break
    save_raw("tesla", {"rows": rows, "units": units, "notes": notes})
    now = datetime.now(timezone.utc)
    L = ["# What works at other Tesla / SpaceX / xAI channels", "",
         f"Updated {now:%Y-%m-%d %H:%M} UTC by tools/scout.py (videos from the last {cfg['days']} days, "
         f"{len(rows)} judged, {units} API units). Do not edit by hand.", "",
         "Outlier = views divided by what that channel normally gets for the same kind of video. "
         "A 5x video shows a topic or angle that pulls viewers, regardless of channel size.", ""]
    if not top:
        L += ["No clear outliers (3x or more) this time.", ""]
    else:
        L += ["## Outliers", ""]
        for r in top:
            L.append(f"- **{r['factor']}x** ({fmt(r['views'])} views vs {fmt(r['median'])} usual, {r['kind']}, "
                     f"{r['channel']}, {fmt(r['subs'])} subs) - {link(r)}")
        L.append("")
        asked = [(c, r) for r in top[:5] for c in r.get("questions", [])]
        if asked:
            L += ["## Questions viewers asked that the creator did not answer", "",
                  "Each is a possible article or video with proven interest (check first that it is still open "
                  "and that the answer is factual and current).", ""]
            seen = set()
            for c, r in sorted(asked, key=lambda x: x[0]["likes"], reverse=True):
                if c["text"].lower()[:80] in seen or len(seen) >= 12:
                    continue
                seen.add(c["text"].lower()[:80])
                L.append(f"- \"{c['text']}\" ({c['likes']} likes, under {link(r)})")
            L.append("")
    L += ["## How to use this", "",
          "- Only as a hint: news value and accuracy still decide which story to cover. Never copy a script, "
          "title or thumbnail; take the topic or angle and do it better and more accurately.",
          "- When a current story matches an outlier topic, give it priority among comparable stories and borrow "
          "the kind of angle (not the words) for the title and the first sentence of the Short.",
          "- An unanswered viewer question about a current topic can become the angle of the article or the "
          "weekly evergreen explainer.", ""]
    if notes:
        L += [f"Note: {'; '.join(notes)}.", ""]
    (ROOT / "ops/scout-tesla.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


def run_proven(own):
    """ops/proven-topics.md: Shorts of the last 30 days in our niche that already proved they pull viewers
    (William, 11 Nov 2026: choose topics whose popularity is proven). Every article task picks from this list."""
    cfg = CFG.get("proven") or {}
    ids, notes = [], []
    for query in cfg.get("queries", []):
        try:
            ids += search(query, cfg.get("days", 30), n=30, short=True)
        except OutOfBudget:
            notes.append(f"stopped searching at '{query}' (API budget)")
            break
    rows = []
    try:
        rows = [r for r in judge(ids, own, top=45) if r["kind"] == "short"]
    except OutOfBudget:
        notes.append("not all channels judged (API budget)")
    save_raw("proven", {"rows": rows, "units": units, "notes": notes})
    now = datetime.now(timezone.utc)
    floor = cfg.get("min_views", 100000)
    top = sorted((r for r in rows if r["views"] >= floor and r["factor"] >= 2), key=lambda r: r["views"], reverse=True)[:25]
    small = sorted((r for r in rows if r["subs"] < 20000 and r["factor"] >= 5 and r not in top),
                   key=lambda r: r["factor"], reverse=True)[:8]
    L = ["# Proven topics: Shorts that already pulled viewers", "",
         f"Updated {now:%Y-%m-%d %H:%M} UTC by tools/scout.py (Shorts of the last {cfg.get('days', 30)} days, "
         f"{len(rows)} judged). Do not edit by hand.", "",
         "Rule (README, PROVEN TOPICS): every article and Short is about a topic from this list, from the outliers in "
         "ops/scout-tesla.md or from our own best Shorts (ops/short-signals.md), unless a real news event of the last "
         "48 hours is clearly bigger. Take the TOPIC and the kind of ANGLE, never the script, title or pictures; check "
         "the facts yourself. Put the proof in `short.proof`.", "",
         f"## Biggest Shorts ({fmt(floor)}+ views)", ""]
    for r in top:
        age = (now - ts(r["published"])).days
        L.append(f"- **{fmt(r['views'])} views** ({r['factor']}x that channel's usual, {r['channel']}, {fmt(r['subs'])} subs, "
                 f"{age} d old) - {link(r)}")
    if small:
        L += ["", "## Small channels that broke out (proof that the topic carries a small channel like ours)", ""]
        for r in small:
            L.append(f"- **{r['factor']}x** ({fmt(r['views'])} views, {r['channel']}, {fmt(r['subs'])} subs) - {link(r)}")
    if notes:
        L += ["", f"Note: {'; '.join(notes)}."]
    (ROOT / "ops/proven-topics.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12]))


def run_niches(own):
    cfg = CFG["candidates"]
    result, notes = {}, []
    for key, n in cfg["niches"].items():
        ids = []
        try:
            for query in n["queries"]:
                ids += search(query, cfg["days"])
            rows = judge(ids, own)
        except OutOfBudget:
            notes.append(f"stopped at niche '{key}' (API budget); the rest is scanned next week first")
            break
        hits = [r for r in rows if r["factor"] >= 3]
        small = {r["channel_id"] for r in hits if r["subs"] is not None and r["subs"] < 100_000}
        young = {r["channel_id"] for r in hits if r["channel_age_days"] <= 365}
        result[key] = {"label": n["label"], "judged": len(rows), "outliers": hits[:15],
                       "channels_with_outliers": len({r["channel_id"] for r in hits}),
                       "small_channels": len(small), "young_channels": len(young),
                       "median_views": statistics.median([r["views"] for r in rows]) if rows else 0}
        for r in hits[:3]:
            try:
                r["questions"] = questions(r, keep=4)
            except OutOfBudget:
                break
    # niches that ran out of budget go first next time
    done = list(result)
    rest = [k for k in cfg["niches"] if k not in done]
    if rest:
        CFG["candidates"]["niches"] = {k: cfg["niches"][k] for k in rest + done}
        (ROOT / "ops/scout.json").write_text(json.dumps(CFG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_raw("niches", {"niches": result, "units": units, "notes": notes})

    def score(x):  # several different small/young channels with outliers = proven demand that newcomers can reach
        return x["small_channels"] * 2 + x["young_channels"] * 2 + x["channels_with_outliers"]

    ranked = sorted(result.items(), key=lambda kv: score(kv[1]), reverse=True)
    now = datetime.now(timezone.utc)
    L = ["# Candidate niches for a second channel", "",
         f"Updated {now:%Y-%m-%d} by tools/scout.py (videos from the last {cfg['days']} days, {units} API units). "
         "Do not edit by hand; change the niches in ops/scout.json.", "",
         "A niche looks promising when several DIFFERENT channels, preferably small (<100K subscribers) or young "
         "(<1 year), have videos at 3x or more of their usual views: then the interest is in the topic, not in "
         "one lucky channel or presenter.", "",
         "| Niche | Channels with 3x+ outliers | of which small | of which young | Median views of top videos | Score |",
         "|---|---|---|---|---|---|"]
    for k, x in ranked:
        L.append(f"| {x['label']} | {x['channels_with_outliers']} | {x['small_channels']} | {x['young_channels']} | "
                 f"{fmt(x['median_views'])} | {score(x)} |")
    L.append("")
    for k, x in ranked:
        L += [f"## {x['label']}", ""]
        if not x["outliers"]:
            L += ["No outliers of 3x or more.", ""]
            continue
        for r in x["outliers"][:6]:
            age = f", channel {r['channel_age_days'] // 30} months old" if r["channel_age_days"] <= 365 else ""
            L.append(f"- **{r['factor']}x** ({fmt(r['views'])} views, {r['kind']}, {r['channel']}, "
                     f"{fmt(r['subs'])} subs{age}) - {link(r)}")
        qs = [c for r in x["outliers"][:3] for c in r.get("questions", [])]
        if qs:
            L += ["", "Unanswered viewer questions:"]
            L += [f"- \"{c['text']}\" ({c['likes']} likes)" for c in sorted(qs, key=lambda c: c["likes"], reverse=True)[:5]]
        L.append("")
    if notes:
        L += [f"Note: {'; '.join(notes)}.", ""]
    (ROOT / "ops/niches.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "tesla"
    LIMIT = BUDGET[mode]
    import upload  # noqa: E402
    at = upload.token()
    own = own_channel()
    if mode == "tesla":
        run_tesla(own)
        try:
            run_proven(own)
        except Exception as e:  # the daily outlier list must never be lost because the proven list failed
            print(f"::warning::proven topics failed: {e}")
    else:
        run_niches(own)
    print(f"::notice::scout {mode}: {units} API units used")
