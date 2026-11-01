"""Visitors of trendingtesla.com from Cloudflare Web Analytics (cookieless, totals only).

Usage (GitHub Actions, secret CF_API_TOKEN with Account Analytics: Read):
  python3 tools/site_stats.py            print the last 7 days: visits and page views per day, top pages, referrers
  python3 tools/site_stats.py --history  also append yesterday's totals to ops/stats/site.jsonl
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = os.environ["CF_API_TOKEN"].strip()
HOST = "trendingtesla.com"


def api(path, body=None):
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/" + path,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


acct = os.environ.get("CF_ACCOUNT_ID", "").strip()
if not acct:  # listing accounts needs the extra permission Account Settings: Read on the token
    accounts = api("accounts")["result"]
    if not accounts:
        sys.exit("::error::The token cannot list the account: add 'Account Settings: Read' to the token, "
                 "or set the repository variable CF_ACCOUNT_ID")
    acct = accounts[0]["id"]

end = date.today()
start = end - timedelta(days=7)
Q = """query($a: String!, $s: Date!, $e: Date!, $h: String!) { viewer { accounts(filter: {accountTag: $a}) {
  days: rumPageloadEventsAdaptiveGroups(limit: 100, filter: {date_geq: $s, date_leq: $e, requestHost_like: $h},
        orderBy: [date_ASC]) { count sum { visits } dimensions { date } }
  pages: rumPageloadEventsAdaptiveGroups(limit: 15, filter: {date_geq: $s, date_leq: $e, requestHost_like: $h},
        orderBy: [count_DESC]) { count dimensions { requestPath } }
  refs: rumPageloadEventsAdaptiveGroups(limit: 15, filter: {date_geq: $s, date_leq: $e, requestHost_like: $h},
        orderBy: [sum_visits_DESC]) { count sum { visits } dimensions { refererHost } }
  countries: rumPageloadEventsAdaptiveGroups(limit: 10, filter: {date_geq: $s, date_leq: $e, requestHost_like: $h},
        orderBy: [sum_visits_DESC]) { sum { visits } dimensions { countryName } }
} } }"""
d = api("graphql", {"query": Q, "variables": {"a": acct, "s": start.isoformat(), "e": end.isoformat(),
                                               "h": f"%{HOST}"}})
if d.get("errors"):
    sys.exit("::error::Cloudflare GraphQL: " + json.dumps(d["errors"])[:800])
a = d["data"]["viewer"]["accounts"][0]

out = ["Visits and page views per day (Cloudflare Web Analytics, all pages of trendingtesla.com):", ""]
for r in a["days"]:
    out.append(f"  {r['dimensions']['date']}: {r['sum']['visits']} visits, {r['count']} page views")
out += ["", "Top pages (last 7 days, page views):"]
out += [f"  {r['count']:>5}  {r['dimensions']['requestPath']}" for r in a["pages"]]
out += ["", "Where visitors come from (visits; empty = direct, bookmarks or apps):"]
out += [f"  {r['sum']['visits']:>5}  {r['dimensions']['refererHost'] or '(direct)'}" for r in a["refs"]]
out += ["", "Countries (visits):"]
out += [f"  {r['sum']['visits']:>5}  {r['dimensions']['countryName']}" for r in a["countries"]]
print("\n".join(out))

if "--history" in sys.argv:
    y = (end - timedelta(days=1)).isoformat()
    row = next((r for r in a["days"] if r["dimensions"]["date"] == y), None)
    if row:
        p = ROOT / "ops/stats/site.jsonl"
        lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
        if not any(json.loads(l).get("date") == y for l in lines if l.strip()):
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"date": y, "visits": row["sum"]["visits"], "pageviews": row["count"]}) + "\n")
