"""Post the reviewed Jensen reinstated Short once to TikTok, Instagram and Facebook.

Checks Buffer for a queued or sent post of this video first. Creates nothing when one already exists.
Uses the 9:16 still as the cover only when Buffer's video input accepts a cover URL.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import tiktok_post as T  # noqa: E402

MARKER = "Jensen Huang is back as Nvidia CEO"
TITLE = "Jensen Huang REINSTATED!"
CAPTION = (
    "Jensen Huang is back as Nvidia CEO, 11 days after he resigned. "
    "The board says US officials see no national security risk. "
    "Full story at trendingtesla.com #Nvidia #JensenHuang #AI"
)


def existing(org_id):
    found = []
    after = None
    for _ in range(8):
        data = T.gql(
            """query($org: OrganizationId!, $after: String) {
              posts(first: 50, after: $after, input: {organizationId: $org, filter: {status: [sent, scheduled, sending]}}) {
                edges { node { id text status channelId } }
                pageInfo { hasNextPage endCursor }
              }
            }""",
            {"org": org_id, "after": after},
        )["posts"]
        for edge in data["edges"]:
            node = edge["node"]
            text = node.get("text") or ""
            if MARKER in text or TITLE in text:
                found.append(node)
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return found


def cover_field():
    """Name of a cover-image field on Buffer's video metadata, when the schema has one."""
    data = T.gql("query { __schema { types { name kind inputFields { name } } } }")
    types = {t["name"]: t for t in data["__schema"]["types"] if t.get("inputFields")}
    for t in types.values():
        names = {f["name"] for f in t["inputFields"]}
        if "thumbnailOffset" not in names:
            continue
        for name in ("thumbnailUrl", "coverUrl", "thumbnail", "cover"):
            if name in names:
                return t["name"], name
    return None, None


def asset(video_url, image_url):
    meta = {"thumbnailOffset": 0}
    type_name, field = cover_field()
    if field and image_url:
        meta[field] = image_url
        print(json.dumps({"cover": "custom", "schema": type_name, "field": field}))
    else:
        print(json.dumps({"cover": "frame", "reason": "Buffer's video input has no cover-image field"}))
    return [{"video": {"url": video_url, "metadata": meta}}]


def main():
    video_url, image_url = sys.argv[1], sys.argv[2]
    services = [x.strip().lower() for x in os.environ.get(
        "SOCIAL_SERVICES", "tiktok,instagram,facebook").split(",") if x.strip()]
    orgs = T.gql("query { account { organizations { id name } } }")["account"]["organizations"]
    hits = []
    for org in orgs:
        hits.extend(existing(org["id"]))
    by_channel = {}
    for node in hits:
        by_channel.setdefault(node["channelId"], node)
    assets = asset(video_url, image_url)
    mut = """mutation { createPost(input: %s) {
        ... on PostActionSuccess { post { id status } }
        ... on MutationError { message } } }"""
    for ch in T.channels(services):
        svc = ch["service"].lower()
        prior = by_channel.get(ch["id"])
        if prior:
            print(json.dumps({"service": svc, "channel": ch["name"], "action": "exists",
                              "id": prior["id"], "status": prior.get("status")}))
            continue
        base = {"text": CAPTION, "channelId": ch["id"], "schedulingType": "automatic", "assets": assets,
                "metadata": T.metadata(svc, TITLE)}
        attempts = [dict(base, mode="shareNow"),
                    dict(base, mode="customScheduled",
                         dueAt=(datetime.now(timezone.utc) + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z"))]
        last = None
        posted = False
        for inp in attempts:
            try:
                res = T.gql(mut % T.literal(inp))["createPost"]
            except RuntimeError as e:
                last = str(e)
                if "thumbnail" in last.lower() or "cover" in last.lower():
                    bare = [{"video": {"url": video_url, "metadata": {"thumbnailOffset": 0}}}]
                    inp = dict(inp, assets=bare)
                    try:
                        res = T.gql(mut % T.literal(inp))["createPost"]
                    except RuntimeError as e2:
                        last = str(e2)
                        continue
                else:
                    continue
            if res.get("post"):
                print(json.dumps({"service": svc, "channel": ch["name"], "action": "created",
                                  "id": res["post"]["id"], "status": res["post"].get("status"),
                                  "mode": inp["mode"]}))
                posted = True
                break
            last = res.get("message")
        if not posted:
            print(json.dumps({"service": svc, "channel": ch["name"], "action": "error", "detail": last}))


if __name__ == "__main__":
    main()
