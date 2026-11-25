"""Noah narration for the Texas register Short. Nothing is uploaded or published.

Professional newsreader, slightly cheerful. No delivery tags: no [energetically],
no [enthousiast]. Output: video/waymo-texas/out/<id>.mp3 and alignment.json.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from short import NOAH_VOICE_ID  # noqa: E402

OUT = HERE / "out"
VOICE = "9hb1f7xQcMLB90qbYSY3"


def tts(text):
    if VOICE != NOAH_VOICE_ID:
        raise SystemExit("voice id does not match Noah")
    body = {
        "text": text,
        "model_id": "eleven_v4",
        "language_code": "en",
        "voice_settings": {
            "stability": 0.42,
            "similarity_boost": 0.75,
            "clone_strength": 0.35,
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
        "model": "eleven_v4",
        "tone": "professional newsreader, slightly cheerful, no audio tags",
        "sentences": [],
    }
    for s in script["sentences"]:
        if "[" in s["text"]:
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
