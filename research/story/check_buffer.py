"""Research: look up what happened to the Buffer posts of the Falcon 1 Short."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import tiktok_post as tp
IDS = ["6ae5e3dcb84259308bd89aa2", "6ae5e3e7eaa24d6f9a75ab09", "6ae5e3e91891472093d2b3cb"]
t = tp.gql('query { __type(name: "Post") { fields { name type { name kind ofType { name } } } } }')["__type"]
names = [f["name"] for f in t["fields"]]
print("Post fields:", names)
q = tp.gql('query { __type(name: "Query") { fields { name args { name type { name ofType { name } } } } } }')["__type"]
print("Query fields:", [(f["name"], [a["name"] for a in f["args"]]) for f in q["fields"] if "post" in f["name"].lower()])
want = [n for n in ("id", "status", "error", "errorMessage", "dueAt", "sentAt", "externalLink", "text") if n in names]
for i in IDS:
    for form in ('post(input: {id: "%s"})', 'post(id: "%s")'):
        try:
            d = tp.gql("query { %s { %s } }" % (form % i, " ".join(want)))
            print(i, json.dumps(d)[:600]); break
        except Exception as e:
            print(i, "form failed:", str(e)[:300])
