"""Noah narration for the "Jensen Huang REINSTATED!" Short, v2. Professional but a bit more cheerful and upbeat
than v1: slightly lower stability, a little style, slightly faster pace. Still no audio tags (no [energetically]).
Uploads and publishes nothing.
Output: video/jensen-reinstated/out/<id>.mp3 and alignment.json."""
import base64, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from short import NOAH_VOICE_ID  # noqa: E402
OUT = HERE / "out"

def tts(text):
    body = {"text": text, "model_id": "eleven_v4", "language_code": "en",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.75, "style": 0.2, "speed": 1.06}}
    for attempt in range(4):
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{NOAH_VOICE_ID}/with-timestamps?output_format=mp3_44100_192",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(8 * (attempt + 1)); continue
            print(e.read().decode(errors="replace")[:500]); raise

def main():
    OUT.mkdir(exist_ok=True)
    script = json.loads((HERE / "script.json").read_text(encoding="utf-8"))
    res = {"voice_id": NOAH_VOICE_ID, "model": "eleven_v4", "tone": "professional, a bit upbeat (v2), no tags", "sentences": []}
    for s in script["sentences"]:
        if "[" in s["text"]:
            raise SystemExit(f"{s['id']}: no audio tags allowed")
        d = tts(s["text"])
        (OUT / f"{s['id']}.mp3").write_bytes(base64.b64decode(d["audio_base64"]))
        al = d.get("alignment") or d["normalized_alignment"]
        res["sentences"].append({"id": s["id"], "text": s["text"], "chars": al["characters"],
                                 "starts": al["character_start_times_seconds"], "ends": al["character_end_times_seconds"]})
        print(s["id"], s["text"])
    (OUT / "alignment.json").write_text(json.dumps(res), encoding="utf-8")

if __name__ == "__main__":
    main()
