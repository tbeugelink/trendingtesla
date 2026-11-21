"""Narrate the Anthropic IPO long-form video with Noah. Nothing is uploaded or published.

One with-timestamps request per narration chunk (the spoken runs between Nasdaq sound bites), so
the voice keeps its flow inside a chunk and the video can be cut exactly to it. Delivery tags are
only used where voice_long.json sets one (the real peaks) and are stripped from the timings.
Output: video/anthropic-ipo-long/out/<chunk>.mp3 and alignment.json with per-item character timings.
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
from short import NOAH_VOICE_ID, alignment_without_tags  # noqa: E402  same voice and tag handling as the pipeline

OUT = HERE / "out"


def tts(voice, text):
    body = {"text": text, "model_id": "eleven_v4", "language_code": "en",
            "voice_settings": {"stability": 0.0, "similarity_boost": 0.0, "clone_strength": 0.0}}
    for attempt in range(4):
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_192",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            print(e.read().decode(errors="replace")[:500])
            raise


def split_items(items, chars, starts, ends):
    """Give each item its own slice of the chunk alignment by walking the non-space characters."""
    out, pos = {}, 0
    n = len(chars)
    for it in items:
        need = [c for c in it["text"] if not c.isspace()]
        while pos < n and chars[pos].isspace():
            pos += 1
        a, got = pos, 0
        while pos < n and got < len(need):
            if not chars[pos].isspace():
                got += 1
            pos += 1
        out[it["id"]] = {"text": it["text"], "chars": chars[a:pos], "starts": starts[a:pos], "ends": ends[a:pos]}
    return out


def main():
    OUT.mkdir(exist_ok=True)
    voice = NOAH_VOICE_ID
    script = json.loads((HERE / "voice_long.json").read_text(encoding="utf-8"))
    result = {"voice_id": voice, "model": "eleven_v4", "chunks": {}, "items": {}}
    for ch in script["chunks"]:
        text = " ".join(f"{i['tag']} {i['text']}".strip() for i in ch["items"])
        d = tts(voice, text)
        (OUT / f"{ch['id']}.mp3").write_bytes(base64.b64decode(d["audio_base64"]))
        al = d.get("alignment") or d["normalized_alignment"]
        chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
        for tag in {i["tag"] for i in ch["items"] if i["tag"]}:
            chars, starts, ends = alignment_without_tags(chars, starts, ends, tag)
        result["chunks"][ch["id"]] = {"file": f"{ch['id']}.mp3", "chars": chars, "starts": starts, "ends": ends}
        result["items"].update(split_items(ch["items"], chars, starts, ends))
        print(ch["id"], len(text), "chars", f"{ends[-1]:.2f}s" if ends else "?")
    (OUT / "alignment.json").write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
