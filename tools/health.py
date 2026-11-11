"""Health check of the whole chain: article -> Short -> long video -> YouTube -> TikTok/Instagram/Facebook -> stats.

Usage: python3 tools/health.py            prints the report, writes ops/health.md, exit code 1 when there are problems
       python3 tools/health.py --no-net   only what the repository itself shows (no YouTube/site/GitHub requests)

Written after 11 Nov 2026: a Short that crashed, a video run GitHub never started and social posts that failed for
11 days all went unnoticed. The monitor task (ops/tasks/monitor.md) runs this twice a day and reports to William.
Checks, for every article of the last 36 hours (times in Europe/Amsterdam):
  - today's midday article exists after 13:30 and the evening article after 22:00;
  - the Short exists and is public on YouTube (after 45 minutes); the midday article also has its long video
    (after 100 minutes);
  - the Short reached TikTok, Instagram and Facebook (ops/social-log.jsonl, after 150 minutes);
  - the article page is live in English and Dutch;
  - the script passes tools/check_article.py and the render report has no rule warnings;
  - no video run failed or hangs in GitHub's queue; the daily statistics are fresh.
"""
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
NET = "--no-net" not in sys.argv
SITE = "https://trendingtesla.com"
REPO = "tbeugelink/trendingtesla"
SERVICES = ("tiktok", "instagram", "facebook")


def load(p, default):
    try:
        return json.loads((ROOT / p).read_text(encoding="utf-8"))
    except Exception:
        return default


def ams_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Amsterdam"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=1)))


def http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrendingTesla-health/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def on_youtube(vid):
    return http(f"https://www.youtube.com/oembed?url=https://youtu.be/{vid}&format=json")


def main():
    import check_article
    now = ams_now()
    problems, notes, ok = [], [], []
    shorts = {x["slug"]: x["id"] for x in load("content/shorts.json", []) if x.get("id")}
    shorts.update({x["slug"]: x["id"] for x in load("ops/story-pending.json", []) if x.get("id")})
    longs = {x["slug"]: x["id"] for x in load("content/videos.json", []) if x.get("id")}
    social = {}
    p = ROOT / "ops/social-log.jsonl"
    for line in (p.read_text(encoding="utf-8").splitlines() if p.exists() else []):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        social.setdefault(r["slug"], {})[r["service"]] = r  # the last attempt per network counts
    waiting = {e["slug"] for e in load("ops/social-queue.json", [])}

    arts = []
    for f in sorted((ROOT / "content/articles").glob("*.json"))[-10:]:
        a = load(f.relative_to(ROOT), {})
        try:
            at = datetime.fromisoformat(f"{a['date']}T{a.get('time', '00:00')}:00").replace(tzinfo=now.tzinfo)
        except Exception:
            continue
        if now - at < timedelta(hours=36):
            arts.append((at, a, f))
    today = [x for x in arts if x[0].date() == now.date()]
    hm = now.hour * 60 + now.minute
    if hm >= 13 * 60 + 30 and not any(at.hour < 17 for at, _, _ in today):
        problems.append("No midday article today (expected around 12:45): the midday task did not publish.")
    if hm >= 22 * 60 and not any(at.hour >= 17 for at, _, _ in today):
        problems.append("No evening article today (expected around 21:20): the evening task did not publish.")

    for at, a, f in arts:
        s, age = a["slug"], now - at
        name = (a.get("en") or {}).get("title", s)[:70]
        if a.get("short"):
            if s not in shorts:
                if age > timedelta(minutes=45):
                    problems.append(f"SHORT MISSING for '{name}' ({int(age.total_seconds() // 60)} min after publishing).")
            else:
                if NET and on_youtube(shorts[s]) not in (200, 0):
                    problems.append(f"Short of '{name}' is not public on YouTube (https://youtu.be/{shorts[s]}).")
                done = social.get(s, {})
                bad = [v for v in SERVICES if not (done.get(v) or {}).get("ok")]
                if bad and age > timedelta(minutes=150) and s not in waiting:
                    why = (done.get(bad[0]) or done.get("all") or {}).get("detail", "no attempt logged")
                    problems.append(f"Short of '{name}' did NOT reach {', '.join(bad)} ({why}).")
                elif not bad:
                    ok.append(f"Short of '{name}': YouTube + TikTok + Instagram + Facebook")
        if (a.get("video") or {}).get("en"):
            if s not in longs:
                if age > timedelta(minutes=100):
                    problems.append(f"LONG VIDEO MISSING for '{name}' ({int(age.total_seconds() // 60)} min after publishing).")
            elif NET and on_youtube(longs[s]) not in (200, 0):
                problems.append(f"Long video of '{name}' is not public on YouTube (https://youtu.be/{longs[s]}).")
            else:
                ok.append(f"Long video of '{name}'")
        if NET and age > timedelta(minutes=20):
            for u in (f"{SITE}/{s}/", f"{SITE}/nl/{s}/"):
                c = http(u)
                if c not in (200, 0):
                    problems.append(f"Article page gives {c}: {u}")
        err, warn = check_article.check(f)
        err = [e for e in err if "short.proof" not in e or at.date() >= datetime(2026, 11, 12).date()]
        if err:
            notes.append(f"Script of '{name}' breaks {len(err)} rule(s): " + "; ".join(err[:4]))
        rep = ROOT / "ops/short-reports" / f"{s}.txt"
        if rep.exists():
            bad = [x for x in rep.read_text(encoding="utf-8").splitlines() if "rule" in x or "shorten" in x or "split into" in x]
            if bad:
                notes.append(f"Render report of '{name}': " + "; ".join(bad[:4]))

    stats = [json.loads(x) for x in (ROOT / "ops/stats/channel.jsonl").read_text().splitlines()[-1:]] \
        if (ROOT / "ops/stats/channel.jsonl").exists() else []
    if not stats or datetime.now(timezone.utc) - datetime.fromisoformat(stats[0]["at"]) > timedelta(hours=30):
        problems.append("The daily YouTube statistics are older than 30 hours (the morning stats run failed).")
    for line in ((ROOT / "ops/video-problems.md").read_text(encoding="utf-8").splitlines()[-3:]
                 if (ROOT / "ops/video-problems.md").exists() else []):
        if line.startswith(f"- {datetime.now(timezone.utc):%Y-%m-%d}"):
            notes.append("Watchdog today: " + line[2:])

    if NET:
        try:
            out = subprocess.run(["gh", "api", f"repos/{REPO}/actions/runs?per_page=40", "--jq",
                                  '.workflow_runs[] | [.name, .status, (.conclusion // ""), .created_at, .html_url] | @tsv'],
                                 capture_output=True, text=True, timeout=60).stdout
            utc = datetime.now(timezone.utc)
            for row in out.splitlines():
                nm, st, con, created, url = (row.split("\t") + [""] * 5)[:5]
                age = utc - datetime.fromisoformat(created.replace("Z", "+00:00"))
                # a problem only while a video is really missing; otherwise it was already repaired (a note)
                missing = any("MISSING" in x for x in problems)
                if st == "queued" and timedelta(minutes=30) < age < timedelta(hours=30):
                    (problems if missing else notes).append(
                        f"GitHub run '{nm}' has been waiting in the queue for {int(age.total_seconds() // 60)} min: {url}")
                if con == "failure" and age < timedelta(hours=13) and nm == "Make YouTube videos":
                    (problems if missing else notes).append(f"Video run failed {int(age.total_seconds() // 3600)} h ago: {url}")
        except Exception as e:
            notes.append(f"GitHub runs not checked ({e})")

    L = [f"# Health {now:%Y-%m-%d %H:%M} (Europe/Amsterdam)", "",
         "PROBLEMS: " + (str(len(problems)) if problems else "none"), ""]
    L += [f"- PROBLEM: {x}" for x in problems] + [f"- note: {x}" for x in notes] + [f"- ok: {x}" for x in ok]
    text = "\n".join(L) + "\n"
    (ROOT / "ops/health.md").write_text(text, encoding="utf-8")
    print(text)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
