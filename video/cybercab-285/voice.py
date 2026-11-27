"""Narration for the Cybercab 285 preview Short. Nothing is uploaded or published.

Tony Smyles, ElevenLabs q1OMOTZNtqpS50TIQtu4, eleven_multilingual_v2.
Same request as video/short.py short_narration_body: stability 0.45,
similarity 0.8, style 0.3, speaker boost on, speed 1.07. No delivery tags.
Noah (9hb1f7xQcMLB90qbYSY3) is refused. No music, no sound effects.
Output: video/cybercab-285/out/<id>.mp3 and alignment.json.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
VOICE = "q1OMOTZNtqpS50TIQtu4"
NOAH = "9hb1f7xQcMLB90qbYSY3"
MODEL = "eleven_multilingual_v2"
SETTINGS = {
    "stability": 0.45,
    "similarity_boost": 0.8,
    "style": 0.3,
    "use_speaker_boost": True,
    "speed": 1.07,
}


def tts(text):
    if VOICE == NOAH:
        raise SystemExit("refusing Noah")
    body = {"text": text, "model_id": MODEL, "voice_settings": SETTINGS}
    for attempt in range(4):
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_192",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            err = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(8 * (attempt + 1))
                continue
            print(err)
            raise


def main():
    if "[" in json.dumps(SETTINGS) or NOAH in VOICE:
        raise SystemExit("refusing a delivery tag or Noah")
    OUT.mkdir(exist_ok=True)
    script = json.loads((HERE / "script.json").read_text(encoding="utf-8"))
    print(
        "voice id=q1OMOTZNtqpS50TIQtu4 model=eleven_multilingual_v2 "
        "stability=0.45 similarity_boost=0.8 style=0.3 use_speaker_boost=true "
        "speed=1.07 no_delivery_tags=true music=off",
        flush=True,
    )
    result = {
        "voice_id": VOICE,
        "voice": "Tony Smyles",
        "model": MODEL,
        "voice_settings": SETTINGS,
        "no_delivery_tags": True,
        "music": False,
        "sentences": [],
    }
    for s in script["sentences"]:
        if "[" in s["text"] or "]" in s["text"]:
            raise SystemExit(f"{s['id']}: no audio tags allowed")
        d = tts(s["text"])
        (OUT / f"{s['id']}.mp3").write_bytes(base64.b64decode(d["audio_base64"]))
        al = d.get("alignment") or d["normalized_alignment"]
        ends = al["character_end_times_seconds"]
        result["sentences"].append({
            "id": s["id"],
            "text": s["text"],
            "hook": bool(s.get("hook")),
            "chars": al["characters"],
            "starts": al["character_start_times_seconds"],
            "ends": ends,
        })
        print(s["id"], f"{ends[-1]:.2f}s" if ends else "?", s["text"], flush=True)
    (OUT / "alignment.json").write_text(json.dumps(result), encoding="utf-8")
    print("wrote", OUT / "alignment.json", flush=True)


if __name__ == "__main__":
    main()
