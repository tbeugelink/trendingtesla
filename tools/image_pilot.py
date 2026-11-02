"""Image pilot: 5 topics, OpenAI GPT Image 2.5 vs William's ChatGPT library images. Nothing is published.

python3 tools/image_pilot.py [--dry]   (--dry: no paid calls; only checks the setup and judges the ChatGPT images)

Per topic: Flare (high) with 1, 2 and 3 references; Sunburst (xhigh, 2 references) for the technical topics.
A rejected image gets at most 2 more tries (1: same model with the checker's errors, 2: Sunburst high).
Hard stop at PILOT_CAP_USD. Results: ops/pilot/out/ (images + sheet.jpg, uploaded as artifact),
ops/images-log.jsonl (one line per image) and ops/pilot/summary.md.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import image_check as C  # noqa: E402
import image_openai as O  # noqa: E402

CAP = float(os.environ.get("PILOT_CAP_USD", "5"))
LIB = ROOT / "static/img/lib"
OUT = ROOT / "ops/pilot/out"
LOG = ROOT / "ops/images-log.jsonl"
FLARE, SUNBURST = os.environ.get("FLARE_MODEL", "gpt-image-2.5-flare"), os.environ.get("SUNBURST_MODEL", "gpt-image-2.5-sunburst")

TOPICS = [
    {"id": "charge-port", "profile": "technical", "cat": "A", "size": "1536x1024", "baseline": "charge-port-us-open.jpg",
     "refs": ["charge-port-us-open.jpg", "charge-port-us-plugged.jpg", "charge-port-open-alt.jpg"],
     "subject": "the open charge port of a white 2025 Tesla Model Y (Juniper): the NACS inlet sits inside the LEFT "
                "rear tail light, behind a small flap that is part of the light unit; it is NOT on the body panel",
     "prompt": "Close-up at a home garage in the morning: the charge port flap of a white 2025 Tesla Model Y "
               "(Juniper) is open, the inlet glowing blue, a grey home charging cable hanging ready next to it. "
               "Soft daylight from the open garage door, a blue sky outside, a red toolbox blurred in the background."},
    {"id": "cybercab-doors", "profile": "technical", "cat": "B", "size": "1536x1024", "baseline": "cybercab-doors-open.jpg",
     "refs": ["cybercab-doors-open.jpg", "cybercab-nap-arrival.jpg", "cybercab-street-day.jpg"],
     "subject": "the gold Tesla Cybercab, a two-seat robotaxi with NO steering wheel and NO pedals; each side has one "
                "large door hinged at the FRONT TOP corner near the windscreen pillar, swinging up and forward",
     "prompt": "The gold Tesla Cybercab parked at a quiet hotel entrance at dusk, both doors swung up and forward, "
               "warm light from the cabin showing the two seats and the wide dashboard screen. Wet pavement with "
               "yellow and red reflections, a deep blue sky."},
    {"id": "supercharger-v4", "profile": "editorial", "cat": "A", "size": "1536x1024", "baseline": "supercharger-v4.jpg",
     "refs": ["supercharger-v4.jpg", "connector-handle.jpg", "supercharger-row-night.jpg"],
     "subject": "Tesla V4 Supercharger posts: tall slim white posts with a red light edge and one long black cable "
                "each, one post at the head of each parking bay",
     "prompt": "A Tesla V4 Supercharger site beside a motorway in light rain at night: two cars charging, the posts' "
               "red light edges glowing, wet asphalt reflecting blue and yellow lights, a roadside diner far away."},
    {"id": "optimus", "profile": "cinematic", "cat": "A", "size": "1024x1536", "baseline": "optimus-pick-part.jpg",
     "refs": ["optimus-pick-part.jpg", "optimus-walking.jpg", "optimus.jpg"],
     "subject": "Tesla Optimus humanoid robot, latest generation: slim white body panels, black joints, glossy black "
                "face plate without a face, five-fingered hands",
     "prompt": "Vertical shot: Tesla Optimus carefully placing a battery module onto a conveyor in a bright Tesla "
               "factory, yellow robot arms and red machine frames blurred behind it, strong side light."},
    {"id": "powerwall", "profile": "editorial", "cat": "A", "size": "1536x1024", "baseline": "powerwall-garage.jpg",
     "refs": ["powerwall-garage.jpg", "solar-roof-house.jpg"],
     "subject": "a Tesla Powerwall 3 home battery: one slim white rectangular unit with rounded corners and a smooth "
                "flat front, mounted on a wall",
     "prompt": "During a neighbourhood power cut at night, a family kitchen stays lit; through the open door to the "
               "utility room a white Tesla Powerwall 3 is visible on the wall, a small status light on. The street "
               "outside the window is dark. Warm yellow kitchen light, cool blue night outside."},
]


def spent():
    if not LOG.exists():
        return 0.0
    return sum(json.loads(l).get("cost_usd", 0) for l in LOG.read_text().splitlines() if l.strip())


def log(row):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def one(t, model, quality, nref, start_cost):
    refs = [LIB / r for r in t["refs"][:nref] if (LIB / r).exists() and O.allowed_ref(LIB / r)]
    prompt, tries, res = t["prompt"] + f"\nIt must show exactly: {t['subject']}.", 0, None
    while tries < 3:
        if spent() - start_cost + 0.25 > CAP:
            print(f"::warning::pilot budget ${CAP} reached, stopping")
            return None
        m = model if tries < 2 else SUNBURST
        q = quality if tries < 2 else "high"
        try:
            im, info = O.generate(prompt, refs, m, q, t["size"], t["profile"])
        except Exception as e:
            log({"at": now(), "topic": t["id"], "model": m, "quality": q, "refs": [r.name for r in refs], "error": str(e)[:300],
                 "cost_usd": 0})
            print(f"::warning::{t['id']} {m} {q}: {e}")
            return None
        chk = C.check(im, t["subject"], refs, t["cat"])
        name = f"{t['id']}-{m.split('-')[-1]}-{q}-r{len(refs)}-t{tries}.jpg"
        im.save(OUT / name, "JPEG", quality=90)
        row = {"at": now(), "topic": t["id"], "file": name, **info, "refs": [r.name for r in refs], "try": tries,
               "check": chk, "approved_auto": chk["ok"], "approved_william": None, "category": t["cat"]}
        log(row)
        print(f"{name}: visual {chk['visual']} tech {chk.get('technical_pass')} journ {chk.get('journalistic_pass')} "
              f"${info['cost_usd']} {info['seconds']}s {chk.get('technical_errors')}")
        res = row
        if chk["ok"]:
            break
        prompt += "\nAvoid these errors of the previous attempt: " + "; ".join(chk.get("technical_errors", []) +
                                                                             chk.get("journalistic_issues", []))
        tries += 1
    return res


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sheet(rows, base):
    f = ImageFont.load_default()
    W, H = 384, 256
    lines = []
    for t in TOPICS:
        cells = [(LIB / t["baseline"], f"ChatGPT  v{base[t['id']]['visual']:.0f} "
                  f"{'OK' if base[t['id']]['ok'] else 'NO'}")]
        cells += [(OUT / r["file"], f"{r['file'][len(t['id']) + 1:-4]} v{r['check']['visual']:.0f} "
                   f"{'OK' if r['check']['ok'] else 'NO'} ${r['cost_usd']}") for r in rows if r and r["topic"] == t["id"]]
        lines.append(cells)
    cols = max(len(c) for c in lines)
    sh = Image.new("RGB", (cols * W, len(lines) * (H + 18)), (16, 16, 16))
    d = ImageDraw.Draw(sh)
    for y, cells in enumerate(lines):
        for x, (p, lab) in enumerate(cells):
            im = Image.open(p).convert("RGB")
            im.thumbnail((W, H))
            sh.paste(im, (x * W, y * (H + 18)))
            d.text((x * W + 4, y * (H + 18) + H + 3), lab, fill=(255, 214, 0), font=f)
    sh.save(OUT / "sheet.jpg", quality=88)


def main():
    dry = "--dry" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    print("visual standard:", len(O.standard("technical")), "chars; refs allowed:",
          {t["id"]: sum(O.allowed_ref(LIB / r) for r in t["refs"]) for t in TOPICS})
    base = {}
    for t in TOPICS:  # the ChatGPT images through the same check: the benchmark (free)
        base[t["id"]] = C.check(Image.open(LIB / t["baseline"]).convert("RGB"), t["subject"],
                                [LIB / r for r in t["refs"] if r != t["baseline"]][:2], t["cat"])
        print(f"baseline {t['id']}: {base[t['id']]}")
    if dry:
        return
    print("OpenAI image models:", O.models())
    start, rows = spent(), []
    for t in TOPICS:
        for n in range(1, min(3, len(t["refs"])) + 1):
            rows.append(one(t, FLARE, "high", n, start))
        if t["profile"] == "technical":
            rows.append(one(t, SUNBURST, "xhigh", 2, start))
    rows = [r for r in rows if r]
    sheet(rows, base)
    finals = {}
    for r in rows:
        finals[(r["topic"], r["model"], r["quality"], len(r["refs"]))] = r
    ok = sum(1 for r in finals.values() if r["check"]["ok"])
    total, secs = round(spent() - start, 3), [r["seconds"] for r in rows]
    md = [f"# Image pilot {now()}", "", f"- variants: {len(finals)}, automatically approved: {ok} "
          f"({round(100 * ok / max(1, len(finals)))} %)", f"- images made (incl. retries): {len(rows)}",
          f"- cost: ${total} (cap ${CAP})", f"- time per image: {min(secs, default=0)}-{max(secs, default=0)} s", "",
          "| topic | variant | visual | technical | journalistic | errors | $ | s |", "|---|---|---|---|---|---|---|---|"]
    for t in TOPICS:
        b = base[t["id"]]
        md.append(f"| {t['id']} | ChatGPT (library) | {b['visual']} | {b.get('technical_pass')} | "
                  f"{b.get('journalistic_pass')} | {'; '.join(b.get('technical_errors', []))[:120]} | - | - |")
        for r in rows:
            if r["topic"] == t["id"]:
                c = r["check"]
                md.append(f"| {t['id']} | {r['model'].split('-')[-1]} {r['quality']} {len(r['refs'])} refs try {r['try']} | "
                          f"{c['visual']} | {c.get('technical_pass')} | {c.get('journalistic_pass')} | "
                          f"{'; '.join(c.get('technical_errors', []))[:120]} | {r['cost_usd']} | {r['seconds']} |")
    (ROOT / "ops/pilot/summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
