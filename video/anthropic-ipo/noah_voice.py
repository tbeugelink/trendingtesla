"""Narrate the Anthropic IPO preview Short with Noah. Nothing is uploaded or published.

Each sentence is rendered on its own with the with-timestamps endpoint, so the video can be cut
exactly to the voice. Delivery tags are only used where script.json sets one (the real peaks).
Output: video/anthropic-ipo/out/<id>.mp3 and alignment.json (characters with start/end seconds).
"""
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from short import NOAH_VOICE_ID, alignment_without_tags  # noqa: E402  same voice and tag handling as the pipeline

OUT = HERE / "out"


def main():
    OUT.mkdir(exist_ok=True)
    voice = (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip() or NOAH_VOICE_ID
    if voice != NOAH_VOICE_ID:
        print("note: ELEVENLABS_VOICE_ID differs from Noah; using Noah for this preview")
        voice = NOAH_VOICE_ID
    script = json.loads((HERE / "script.json").read_text(encoding="utf-8"))
    result = {"voice_id": voice, "model": "eleven_v4", "sentences": []}
    for s in script["sentences"]:
        tag = s.get("tag") or ""
        text = f"{tag} {s['text']}".strip()
        body = {"text": text, "model_id": "eleven_v4", "language_code": "en",
                "voice_settings": {"stability": 0.0, "similarity_boost": 0.0, "clone_strength": 0.0}}
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_192",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.load(r)
        (OUT / f"{s['id']}.mp3").write_bytes(base64.b64decode(d["audio_base64"]))
        al = d.get("alignment") or d["normalized_alignment"]
        chars, starts, ends = alignment_without_tags(
            al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"], tag)
        result["sentences"].append({"id": s["id"], "text": s["text"], "chars": chars, "starts": starts, "ends": ends})
        print(s["id"], f"{ends[-1]:.2f}s" if ends else "?")
    (OUT / "alignment.json").write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
