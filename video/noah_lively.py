"""Render livelier Noah samples of the N1 narration. Does not change defaults.

The API key is read from the environment and never printed.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

TEXT = (Path(__file__).resolve().parent / "voice-sample.txt").read_text(encoding="utf-8").strip()
OUT = Path(os.environ.get("VOICE_OUT", "video/out/noah-lively"))
NOAH = "9hb1f7xQcMLB90qbYSY3"

VARIANTS = [
    {
        "file": "noah-lively-1.mp3",
        "model": "eleven_multilingual_v2",
        "settings": {
            "stability": 0.38,
            "similarity_boost": 0.75,
            "style": 0.45,
            "speed": 1.08,
            "use_speaker_boost": True,
        },
    },
    {
        "file": "noah-lively-2.mp3",
        "model": "eleven_multilingual_v2",
        "settings": {
            "stability": 0.30,
            "similarity_boost": 0.75,
            "style": 0.60,
            "speed": 1.10,
            "use_speaker_boost": True,
        },
    },
]
EXPRESSIVE = {
    "stability": 0.35,
    "similarity_boost": 0.75,
    "style": 0.55,
    "speed": 1.08,
    "use_speaker_boost": True,
}
THIRD_MODELS = ("eleven_v3", "eleven_flash_v2_5", "eleven_turbo_v2_5")


def key():
    value = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not value:
        raise SystemExit("ELEVENLABS_API_KEY is missing")
    return value


def post(model, settings):
    body = {"text": TEXT, "model_id": model, "voice_settings": settings}
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{NOAH}?output_format=mp3_44100_192",
        data=json.dumps(body).encode(),
        headers={"xi-api-key": key(), "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            return response.read(), None
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:300].replace(key(), "[redacted]")
        return None, f"HTTP {err.code}: {detail}"


def write_mp3(raw, dest):
    # The timestamped endpoint returns JSON. A plain audio response is MP3 bytes.
    if raw[:1] in (b"{", b"["):
        payload = json.loads(raw)
        dest.write_bytes(__import__("base64").b64decode(payload["audio_base64"]))
    else:
        dest.write_bytes(raw)


def render(model, settings, dest):
    raw, err = post(model, settings)
    if raw is None:
        return err
    write_mp3(raw, dest)
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for variant in VARIANTS:
        dest = OUT / variant["file"]
        err = render(variant["model"], variant["settings"], dest)
        if err:
            raise SystemExit(f"{variant['file']} failed: {err}")
        written.append({**variant, "bytes": dest.stat().st_size, "voice_id": NOAH})
        print(f"wrote {variant['file']} model={variant['model']} bytes={dest.stat().st_size}")
    third = None
    notes = []
    for model in THIRD_MODELS:
        dest = OUT / f"noah-lively-3-{model}.mp3"
        err = render(model, EXPRESSIVE, dest)
        if err is None:
            third = {"file": dest.name, "model": model, "settings": EXPRESSIVE, "bytes": dest.stat().st_size, "voice_id": NOAH}
            print(f"wrote {dest.name} model={model} bytes={dest.stat().st_size}")
            break
        notes.append(f"{model}: {err}")
        print(f"::warning::{model} skipped: {err}")
    report = {
        "voice_id": NOAH,
        "voice_name": "Noah - Confident Canadian Narrator",
        "words": len(TEXT.split()),
        "characters_per_sample": len(TEXT),
        "variants": written,
        "third": third,
        "third_attempts": notes,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": [v["file"] for v in written] + ([third["file"]] if third else []), "third_attempts": notes}))


if __name__ == "__main__":
    main()
