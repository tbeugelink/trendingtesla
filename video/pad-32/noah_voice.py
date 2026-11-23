"""Narrate the pad-turnaround preview Short with Noah. Nothing is uploaded or published.

Every sentence is rendered on its own, with [energetically] in front of it, on the with-timestamps
endpoint. The tag is stripped from the alignment so captions stay on the spoken words.
Output: video/pad-32/out/<id>.mp3 and alignment.json.
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
from short import NOAH_VOICE_ID, alignment_without_tags  # noqa: E402

OUT = HERE / "out"


def tts(voice, text):
    body = {
        "text": text,
        "model_id": "eleven_v4",
        "language_code": "en",
        "voice_settings": {"stability": 0.0, "similarity_boost": 0.0, "clone_strength": 0.0},
    }
    for attempt in range(4):
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_192",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(8 * (attempt + 1))
                continue
            print(e.read().decode(errors="replace")[:500])
            raise


def main():
    OUT.mkdir(exist_ok=True)
    voice = NOAH_VOICE_ID
    script = json.loads((HERE / "script.json").read_text(encoding="utf-8"))
    result = {"voice_id": voice, "model": "eleven_v4", "tag": "[energetically]", "sentences": []}
    for s in script["sentences"]:
        tag = s.get("tag") or "[energetically]"
        if tag != "[energetically]":
            raise SystemExit(f"{s['id']} must be tagged [energetically]")
        text = f"{tag} {s['text']}".strip()
        d = tts(voice, text)
        (OUT / f"{s['id']}.mp3").write_bytes(base64.b64decode(d["audio_base64"]))
        al = d.get("alignment") or d["normalized_alignment"]
        chars, starts, ends = alignment_without_tags(
            al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"], tag)
        result["sentences"].append({
            "id": s["id"], "text": s["text"], "caption": s.get("caption") or "",
            "hook": bool(s.get("hook")), "chars": chars, "starts": starts, "ends": ends,
        })
        print(s["id"], f"{ends[-1]:.2f}s" if ends else "?", s["text"])
    (OUT / "alignment.json").write_text(json.dumps(result), encoding="utf-8")
    print("wrote", OUT / "alignment.json")


if __name__ == "__main__":
    main()
