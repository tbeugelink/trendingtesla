"""Speak the Cybercab narration with Noah on Eleven v4, one sentence at a time.

Each sentence is its own request, with the same voice settings and seed, and with
the previous and next sentence passed as context so the prosody stays consistent.
The mp3s are artifacts only. Assembly, gaps, and the film happen outside this job.
No YouTube upload.
"""
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import short  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEXT_PATH = ROOT / "video/cybercab/narration.txt"
OUT = ROOT / "video/out/sentences"
PAUSE_TAG = re.compile(r"\[(?:long )?pause\]\s*", re.IGNORECASE)
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
# One seed for every sentence, so the takes stay in the same delivery.
SEED = 20261113


def paragraphs(raw):
    text = PAUSE_TAG.sub("\n\n", raw).strip()
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def sentences_of(raw):
    """Sentences in order. section_end marks the breath before the next paragraph."""
    out = []
    paras = paragraphs(raw)
    for pi, para in enumerate(paras):
        parts = [p.strip() for p in SENTENCE_BREAK.split(para) if p.strip()]
        for si, sentence in enumerate(parts):
            out.append({
                "text": sentence,
                "section_end": si == len(parts) - 1 and pi < len(paras) - 1,
            })
    return out


def request_sentence(text, previous, nxt, dest, voice):
    body = short.narration_body(text)
    body["seed"] = SEED
    if previous:
        body["previous_text"] = previous
    if nxt:
        body["next_text"] = nxt
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_192"
    data = json.dumps(body).encode()
    last_err = None
    for attempt in range(4):
        req = urllib.request.Request(
            url, data=data,
            headers={"xi-api-key": os_key(), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:400]
            last_err = f"HTTP {err.code}: {detail}"
            if err.code == 400 and "seed" in detail.lower() and "seed" in body:
                body.pop("seed", None)
                data = json.dumps(body).encode()
                continue
            if err.code not in (429, 500, 502, 503):
                raise SystemExit(last_err)
            time.sleep(2 + attempt * 3)
        except urllib.error.URLError as err:
            last_err = str(err)
            time.sleep(2 + attempt * 3)
    else:
        raise SystemExit(last_err or "ElevenLabs request failed")
    dest.write_bytes(base64.b64decode(payload["audio_base64"]))
    alignment = payload.get("alignment") or payload["normalized_alignment"]
    chars, starts, ends = short.alignment_without_tags(
        alignment["characters"],
        alignment["character_start_times_seconds"],
        alignment["character_end_times_seconds"],
        short.narration_tag())
    chars, starts, ends = short.pad_alignment(text, chars, starts, ends)
    heard = "".join(chars)
    if re.search(r"\bpause\b", heard, re.IGNORECASE):
        print(f"::warning::sentence alignment contains the word pause: {text[:60]}")
    return chars, starts, ends


def os_key():
    import os
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is not set")
    return key


def main():
    raw = TEXT_PATH.read_text(encoding="utf-8").strip()
    text = short.spoken(raw, "en")
    items = sentences_of(text)
    if not items:
        raise SystemExit("narration has no sentences")
    voice = short.NOAH_VOICE_ID
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "voice": voice,
        "model": short.NARRATION_MODEL,
        "seed": SEED,
        "stability": 0,
        "similarity_boost": 0,
        "clone_strength": 0,
        "sentences": [],
    }
    print(f"sentences {len(items)} voice {voice} model {short.NARRATION_MODEL} seed {SEED}")
    for i, item in enumerate(items):
        previous = items[i - 1]["text"] if i else ""
        nxt = items[i + 1]["text"] if i + 1 < len(items) else ""
        dest = OUT / f"s{i:03d}.mp3"
        chars, starts, ends = request_sentence(item["text"], previous, nxt, dest, voice)
        manifest["sentences"].append({
            "index": i,
            "text": item["text"],
            "section_end": item["section_end"],
            "file": dest.name,
            "chars": chars,
            "starts": starts,
            "ends": ends,
        })
        print(f"  {i:02d} {ends[-1] if ends else 0:.2f}s  {item['text'][:72]}")
    (OUT / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    print(f"wrote {len(items)} takes to {OUT}")


if __name__ == "__main__":
    main()
