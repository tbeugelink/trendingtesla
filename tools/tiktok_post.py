"""Post a finished Short to TikTok, Instagram (Reel) and Facebook (Reel) through Buffer.

Buffer is an approved partner of TikTok and Meta, so posts are public. Which networks: env SOCIAL_SERVICES
(comma list, default "tiktok,instagram,facebook"); every connected Buffer channel of those services gets it.

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


ENUMS = {"mode", "schedulingType", "type"}


def literal(v, key=None):
    """Python value -> GraphQL input literal (enum fields unquoted)."""
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {literal(x, k)}" for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(literal(x) for x in v) + "]"
    if key in ENUMS:
        return v
    return json.dumps(v)


def channels(services):
    out = []
    orgs = gql("query { account { organizations { id name } } }")["account"]["organizations"]
    for o in orgs:
        chans = gql(f"query {{ channels(input: {{organizationId: {json.dumps(o['id'])}}}) {{ id name service }} }}")["channels"]
        out += [c for c in chans if c["service"].lower() in services]
    if not out:
        raise RuntimeError(f"no {'/'.join(services)} channel connected in Buffer")
    return out


def metadata(service, title):
    """Per network: post as a Reel where that applies, and always the network's own AI-content label."""
    return {"tiktok": {"tiktok": {"isAiGenerated": True, "title": title[:90]}},
            "instagram": {"instagram": {"type": "reel", "isAiGenerated": True, "shouldShareToFeed": True}},
            "facebook": {"facebook": {"type": "reel"}}}.get(service, {})


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
    services = [x.strip().lower() for x in os.environ.get("SOCIAL_SERVICES", "tiktok,instagram,facebook").split(",") if x.strip()]
    text = caption(slug)
    a = json.loads(next((ROOT / "content/articles").glob(f"*-{slug}.json")).read_text(encoding="utf-8"))
    # cover: a frame from the video (Buffer refuses custom cover images); 0.5 s = photo + label on screen
    asset = [{"video": {"url": url, "metadata": {"thumbnailOffset": 500}}}]
    mut = """mutation { createPost(input: %s) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message } } }"""
    failed = []
    for ch in channels(services):
        svc = ch["service"].lower()
        base = {"text": text, "channelId": ch["id"], "schedulingType": "automatic", "assets": asset,
                "metadata": metadata(svc, a["en"]["title"])}
        attempts = [{**base, "mode": "shareNow"},
                    {**base, "mode": "customScheduled",
                     "dueAt": (datetime.now(timezone.utc) + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")}]
        last, ok = None, False
        for inp in attempts:
            try:
                res = gql(mut % literal(inp))["createPost"]
            except RuntimeError as e:
                last = e
                continue
            if res.get("post"):
                print(f"::notice::{svc} via Buffer ({ch['name']}): post {res['post']['id']} for {slug} ({inp['mode']})")
                ok = True
                break
            last = RuntimeError(res.get("message"))
        if not ok:
            print(f"::warning::{svc} post for {slug} failed: {last}")
            failed.append(svc)
    return failed


def introspect():
    """Print the input fields Buffer accepts for posts (used to find the TikTok and asset options)."""
    q = """query($n: String!) { __type(name: $n) { name inputFields { name type { name kind ofType { name kind ofType { name kind ofType { name kind ofType { name } } } } } } } }"""
    todo, seen = ["CreatePostInput"], set()
    while todo:
        n = todo.pop(0)
        if n in seen:
            continue
        seen.add(n)
        t = gql(q, {"n": n})["__type"]
        if not t or not t.get("inputFields"):
            continue
        print("TYPE", n, json.dumps([(f["name"], f["type"]) for f in t["inputFields"]])[:1500])
        for f in t["inputFields"]:
            ty = f["type"]
            while ty and not ty.get("name"):
                ty = ty.get("ofType")
            if ty and re.search(r"metadata|asset|video|tiktok", ty["name"] or "", re.I):
                todo.append(ty["name"])


if __name__ == "__main__":
    if sys.argv[1:] == ["--introspect"]:
        for n in ("PostType", "PostTypeFacebook", "ShareMode", "SchedulingType"):
            t = gql('query { __type(name: "%s") { enumValues { name } } }' % n)["__type"]
            print("ENUM", n, [e["name"] for e in (t or {}).get("enumValues") or []])
        sys.exit(0)
    if not os.environ.get("BUFFER_API_KEY"):
        print("::warning::BUFFER_API_KEY missing, skipping TikTok")
        sys.exit(0)
    try:
        post(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"::warning::social post for {sys.argv[1]} failed: {e}")
