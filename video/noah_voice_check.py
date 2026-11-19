"""Render the N1 narration with Noah and name the stored voice ids.

The API key is never printed. Stored ids are passed in only so their names
can be read from ElevenLabs.
"""
import json
import os
import time
import urllib.request
from pathlib import Path

TEXT = (Path(__file__).resolve().parent / "voice-sample.txt").read_text(encoding="utf-8").strip()
OUT = Path(os.environ.get("VOICE_OUT", "video/out/noah-check"))
NOAH = "9hb1f7xQcMLB90qbYSY3"
SETTINGS = {"stability": 0.48, "similarity_boost": 0.75, "style": 0.30, "speed": 1.05}


def api(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


def voice_name(voice_id):
    if not voice_id:
        return None
    try:
        data = api(f"https://api.elevenlabs.io/v1/voices/{voice_id}")
    except Exception as err:
        return f"unavailable ({err.__class__.__name__})"
    return data.get("name")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    voice = (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip() or NOAH
    dest = OUT / "noah-n1-sample.mp3"
    payload = api(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_192",
        {"text": TEXT, "model_id": "eleven_multilingual_v2", "voice_settings": SETTINGS},
    )
    dest.write_bytes(__import__("base64").b64decode(payload["audio_base64"]))
    match = None
    seen = []
    for _ in range(6):
        history = api("https://api.elevenlabs.io/v1/history?page_size=10")
        seen = []
        for item in history.get("history") or []:
            seen.append({
                "voice_id": item.get("voice_id"),
                "voice_name": item.get("voice_name"),
                "text": (item.get("text") or "")[:48],
            })
            if item.get("voice_id") == NOAH:
                match = item
                break
        if match:
            break
        time.sleep(3)
    sub = api("https://api.elevenlabs.io/v1/user/subscription")
    count, limit = sub.get("character_count"), sub.get("character_limit")
    stored = {
        "ELEVENLABS_VOICE_ID": voice_name(os.environ.get("STORED_VOICE_ID", "")),
        "ELEVENLABS_VOICE_ID_2": voice_name(os.environ.get("STORED_VOICE_ID_2", "")),
    }
    report = {
        "source": os.environ.get("VOICE_SOURCE", ""),
        "requested_voice_id": voice,
        "history_voice_id": None if match is None else match.get("voice_id"),
        "history_voice_name": None if match is None else match.get("voice_name"),
        "history_seen": seen,
        "stored_voice_names": stored,
        "words": len(TEXT.split()),
        "characters": len(TEXT),
        "settings": {"model": "eleven_multilingual_v2", **SETTINGS},
        "subscription": {
            "tier": sub.get("tier"),
            "status": sub.get("status"),
            "character_count": count,
            "character_limit": limit,
            "remaining": None if count is None or limit is None else max(0, limit - count),
        },
        "bytes": dest.stat().st_size,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    if report["history_voice_id"] != NOAH:
        print("warning: history did not list Noah yet")


if __name__ == "__main__":
    main()
