"""Render three narration samples with the existing ElevenLabs call.

The key is read from the environment and never printed. Baseline (a) uses the
current voice and the long-video settings from video/full.py. (b) and (c) are
two other premade voices suited to calm documentary narration.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = (ROOT / "video" / "voice-sample.txt").read_text(encoding="utf-8").strip()
OUT = Path(os.environ.get("VOICE_OUT", ROOT / "video" / "out" / "voice-samples"))
MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# Long-video baseline, from video/full.py: SPEED en 1.07, FULL_STABILITY 0.45, FULL_STYLE 0.3.
BASELINE = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3, "speed": 1.07}
# Calm documentary: moderate stability, low style, near-natural pace.
DOCUMENTARY = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.25, "speed": 1.02}

# Premade narration voices, used only if the account's voice list includes them.
CANDIDATES = [
    ("Brian", "nPczCjzI2devNBz1zQrb"),
    ("Bill", "pqHfZKP75CvOlQylNhV4"),
    ("Daniel", "onwK4e9ZLuTAKqWW03F9"),
    ("George", "JBFqnCBsd6RMkjVDRZzb"),
]


def key():
    value = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not value:
        sys.exit("ELEVENLABS_API_KEY is missing")
    return value


def request(url, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"xi-api-key": key(), "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            return content_type, raw
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:400].replace(key(), "[redacted]")
        sys.exit(f"ElevenLabs HTTP {err.code} on {url.split('?')[0].rsplit('/', 1)[-1]}: {detail}")


def voices():
    _, raw = request("https://api.elevenlabs.io/v1/voices")
    data = json.loads(raw)
    return data.get("voices") or []


def subscription():
    _, raw = request("https://api.elevenlabs.io/v1/user/subscription")
    data = json.loads(raw)
    count = data.get("character_count")
    limit = data.get("character_limit")
    remaining = None if count is None or limit is None else max(0, limit - count)
    return {
        "tier": data.get("tier"),
        "status": data.get("status"),
        "character_count": count,
        "character_limit": limit,
        "remaining": remaining,
        "next_reset_unix": data.get("next_character_count_reset_unix"),
    }


def choose(catalog, current_id):
    by_id = {v.get("voice_id"): v for v in catalog}
    by_name = {}
    for voice in catalog:
        by_name.setdefault((voice.get("name") or "").strip().lower(), voice)
    picked = []
    for name, voice_id in CANDIDATES:
        voice = by_id.get(voice_id) or by_name.get(name.lower())
        if not voice or voice.get("voice_id") == current_id:
            continue
        picked.append(voice)
        if len(picked) == 2:
            break
    if len(picked) < 2:
        for voice in catalog:
            if voice.get("voice_id") in {current_id, *(p.get("voice_id") for p in picked)}:
                continue
            labels = voice.get("labels") or {}
            blob = " ".join(str(labels.get(k) or "") for k in ("use case", "description", "accent", "age")).lower()
            if voice.get("category") == "premade" and any(word in blob for word in ("narrat", "document", "news")):
                picked.append(voice)
            if len(picked) == 2:
                break
    if len(picked) < 2:
        sys.exit("Could not find two documentary voices besides the current one")
    return picked


def render(voice_id, settings, dest):
    # Same call as video/short.py tts_elevenlabs: multilingual v2, timestamps, mp3 44.1 kHz.
    _, raw = request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_192",
        method="POST",
        body={"text": TEXT, "model_id": MODEL, "voice_settings": settings},
    )
    payload = json.loads(raw)
    dest.write_bytes(__import__("base64").b64decode(payload["audio_base64"]))


def describe(voice):
    labels = voice.get("labels") or {}
    return {
        "name": voice.get("name"),
        "voice_id": voice.get("voice_id"),
        "category": voice.get("category"),
        "labels": {k: labels.get(k) for k in ("gender", "age", "accent", "description", "use case") if labels.get(k)},
    }


def main():
    current_id = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if not current_id:
        sys.exit("ELEVENLABS_VOICE_ID is missing")
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = voices()
    current = next((v for v in catalog if v.get("voice_id") == current_id), None)
    if current is None:
        current = {"name": "current", "voice_id": current_id, "category": "configured", "labels": {}}
    other = choose(catalog, current_id)
    before = subscription()
    jobs = [
        ("voice-a-current.mp3", current, BASELINE, "baseline: current long-video settings"),
        (f"voice-b-{(other[0].get('name') or 'b').lower().replace(' ', '-')}.mp3", other[0], DOCUMENTARY, "calm documentary"),
        (f"voice-c-{(other[1].get('name') or 'c').lower().replace(' ', '-')}.mp3", other[1], DOCUMENTARY, "calm documentary"),
    ]
    written = []
    for filename, voice, settings, role in jobs:
        dest = OUT / filename
        render(voice["voice_id"], settings, dest)
        info = describe(voice)
        info.update({"file": filename, "role": role, "settings": settings, "bytes": dest.stat().st_size})
        written.append(info)
        print(f"wrote {filename} voice={info['name']} id={info['voice_id']} bytes={info['bytes']}")
    after = subscription()
    report = {
        "model": MODEL,
        "words": len(TEXT.split()),
        "characters_per_sample": len(TEXT),
        "samples": 3,
        "characters_sent": len(TEXT) * 3,
        "music_bed": False,
        "subscription_before": before,
        "subscription_after": after,
        "voices": written,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("words", "characters_per_sample", "characters_sent", "subscription_before", "subscription_after")}))


if __name__ == "__main__":
    main()
