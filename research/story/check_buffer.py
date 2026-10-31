"""Research: look up what happened to the Buffer posts of the Falcon 1 Short."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import tiktok_post as tp
IDS = ["6ae6144bab019b9087118382", "6ae614ff21c807e9d572ba4d", "6ae6150a21c807e9d572c179", "6ae6150cf0984eef331bdde8"]
t = tp.gql('query { __type(name: "Post") { fields { name type { name kind ofType { name } } } } }')["__type"]
names = [f["name"] for f in t["fields"]]
print("Post fields:", names)
q = tp.gql('query { __type(name: "Query") { fields { name args { name type { name ofType { name } } } } } }')["__type"]
print("Query fields:", [(f["name"], [a["name"] for a in f["args"]]) for f in q["fields"] if "post" in f["name"].lower()])
ef = tp.gql('query { __type(name: "PostPublishingError") { fields { name } } }')["__type"]["fields"]
print("error fields:", [f["name"] for f in ef])
want = ["id", "status", "channelService", "dueAt", "sentAt", "externalLink", "error { %s }" % " ".join(f["name"] for f in ef)]
for i in IDS:
    for form in ('post(input: {id: "%s"})',):
        try:
            d = tp.gql("query { %s { %s } }" % (form % i, " ".join(want)))
            print(i, json.dumps(d)[:600]); break
        except Exception as e:
            print(i, "form failed:", str(e)[:300])
