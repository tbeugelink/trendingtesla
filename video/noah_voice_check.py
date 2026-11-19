"""Render the N1 narration once and confirm which voice ElevenLabs used.

The voice id arrives in ELEVENLABS_VOICE_ID (already chosen). The key is never printed.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import short as S  # noqa: E402

TEXT = (Path(__file__).resolve().parent / "voice-sample.txt").read_text(encoding="utf-8").strip()
OUT = Path(os.environ.get("VOICE_OUT", "video/out/noah-check"))


def api(url):
    req = urllib.request.Request(url, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    voice = S.narration_voice()
    dest = OUT / "noah-n1-sample.mp3"
    S.LANG[0] = "en"
    S.tts_elevenlabs(TEXT, dest)
    history = api("https://api.elevenlabs.io/v1/history?page_size=8")
    match = None
    for item in history.get("history") or []:
        if (item.get("text") or "").startswith("Thirty engines doomed"):
            match = item
            break
    sub = api("https://api.elevenlabs.io/v1/user/subscription")
    count, limit = sub.get("character_count"), sub.get("character_limit")
    report = {
        "source": os.environ.get("VOICE_SOURCE", ""),
        "requested_voice_id": voice,
        "history_voice_id": None if match is None else match.get("voice_id"),
        "history_voice_name": None if match is None else match.get("voice_name"),
        "history_character_count": None if match is None else match.get("character_count"),
        "words": len(TEXT.split()),
        "characters": len(TEXT),
        "settings": {"model": "eleven_multilingual_v2", "stability": 0.48, "style": 0.30, "speed": 1.05, "similarity_boost": 0.75},
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
    if report["history_voice_id"] != "9hb1f7xQcMLB90qbYSY3":
        sys.exit("History voice is not Noah")


if __name__ == "__main__":
    main()
