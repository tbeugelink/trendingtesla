"""Post a finished Short to TikTok through Buffer (Buffer is an approved TikTok partner, so posts are public).

Usage (in GitHub Actions):  python3 tools/tiktok_post.py <video/out/...-en-short.mp4> <public video URL>
Needs the secret BUFFER_API_KEY. The video must stay reachable at the URL until Buffer has published it
(the workflow puts it on a GitHub release of the public repo). Caption: the article title, a link to the
article, a few hashtags and the AI note TikTok asks for. Never fails the workflow: problems are warnings.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
API = "https://api.buffer.com"


def gql(query, variables=None):
    req = urllib.request.Request(API, data=json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['BUFFER_API_KEY'].strip()}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Buffer HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
    if d.get("errors"):
        raise RuntimeError(f"Buffer: {json.dumps(d['errors'])[:300]}")
    return d["data"]


ENUMS = {"mode", "schedulingType"}


def literal(v, key=None):
    """Python value -> GraphQL input literal (enum fields unquoted)."""
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {literal(x, k)}" for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(literal(x) for x in v) + "]"
    if key in ENUMS:
        return v
    return json.dumps(v)


def tiktok_channel():
    orgs = gql("query { account { organizations { id name } } }")["account"]["organizations"]
    for o in orgs:
        chans = gql(f"query {{ channels(input: {{organizationId: {json.dumps(o['id'])}}}) {{ id name service }} }}")["channels"]
        for c in chans:
            if c["service"].lower() == "tiktok":
                return c["id"], c["name"]
    raise RuntimeError("no TikTok channel connected in Buffer")


def caption(slug):
    import build
    f = next((ROOT / "content/articles").glob(f"*-{slug}.json"))
    a = json.loads(f.read_text(encoding="utf-8"))
    tags = ["#Tesla", "#TeslaNews"]
    extra = {"robotaxi": "#Robotaxi", "fsd": "#FSD", "optimus": "#Optimus", "energy": "#Powerwall",
             "spacex": "#SpaceX", "starlink": "#Starlink", "xai": "#Grok", "charging": "#Supercharger",
             "boring": "#BoringCompany", "earnings": "#TSLA"}.get(a.get("category"))
    if extra:
        tags.append(extra)
    for m in a.get("models", [])[:2]:
        name = build.MODELS.get(m, {}).get("name", "")
        if name:
            tags.append("#" + re.sub(r"[^A-Za-z0-9]", "", name))
    tags += ["#EV", "#ElectricCars"]
    return (f"{a['en']['title']}\n\nFull story: trendingtesla.com/{slug}/\n\n"
            f"{' '.join(dict.fromkeys(tags))}\n\nAI-generated voice-over; script written and checked by TrendingTesla.")


def post(mp4, url):
    slug = re.sub(r"-(en|nl)-short\.mp4$", "", Path(mp4).name)
    cid, name = tiktok_channel()
    text = caption(slug)
    asset = [{"video": {"url": url, "metadata": {"thumbnailOffset": 1000}}}]  # opening frame with the label
    mut = """mutation { createPost(input: %s) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message } } }"""
    base = {"text": text, "channelId": cid, "schedulingType": "automatic", "assets": asset}
    attempts = [{**base, "mode": "shareNow"},
                {**base, "mode": "customScheduled",
                 "dueAt": (datetime.now(timezone.utc) + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")}]
    last = None
    for inp in attempts:
        try:
            res = gql(mut % literal(inp))["createPost"]
        except RuntimeError as e:
            last = e
            continue
        if res.get("post"):
            print(f"::notice::TikTok via Buffer ({name}): post {res['post']['id']} for {slug} ({inp['mode']})")
            return
        last = RuntimeError(res.get("message"))
    raise last


if __name__ == "__main__":
    if not os.environ.get("BUFFER_API_KEY"):
        print("::warning::BUFFER_API_KEY missing, skipping TikTok")
        sys.exit(0)
    try:
        post(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"::warning::TikTok post for {sys.argv[1]} failed: {e}")
