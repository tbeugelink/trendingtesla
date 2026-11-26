"""Narration for the LINK pivotal-trial Short. Nothing is uploaded or published.

This is the English voice from before Noah (chosen 19 Nov 2026).
Tony Smyles, ElevenLabs q1OMOTZNtqpS50TIQtu4, eleven_multilingual_v2.
Same request as video/story.py on 18 Nov 2026: stability 0.45, similarity 0.8,
style 0.3, speaker boost on, speed 1.07. No delivery tags.
Output: video/neuralink-link/out/<id>.mp3 and alignment.json.
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
# Tony Smyles, the voice id in vars.ELEVENLABS_VOICE_ID before Noah.
# Noah is 9hb1f7xQcMLB90qbYSY3 and must not be used here.
VOICE = "q1OMOTZNtqpS50TIQtu4"
NOAH = "9hb1f7xQcMLB90qbYSY3"


def tts(text):
    if VOICE == NOAH:
        raise SystemExit("refusing Noah")
    body = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.3,
            "use_speaker_boost": True,
            "speed": 1.07,
        },
    }
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
    OUT.mkdir(exist_ok=True)
    script = json.loads((HERE / "script.json").read_text(encoding="utf-8"))
    result = {
        "voice_id": VOICE,
        "voice": "Tony Smyles - The Voice of Trust",
        "model": "eleven_multilingual_v2",
        "tone": "pre-Noah story Short: stability 0.45, similarity 0.8, style 0.3, speaker boost, speed 1.07; no audio tags",
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
            "caption": s.get("caption") or "",
            "hook": bool(s.get("hook")),
            "chars": al["characters"],
            "starts": al["character_start_times_seconds"],
            "ends": ends,
        })
        print(s["id"], f"{ends[-1]:.2f}s" if ends else "?", s["text"])
    (OUT / "alignment.json").write_text(json.dumps(result), encoding="utf-8")
    print("wrote", OUT / "alignment.json")


if __name__ == "__main__":
    main()
