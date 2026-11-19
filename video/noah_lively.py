"""Render Noah comparison clips. Does not change the default voice.

The API key is read from the environment and never printed.
VOICE_SET=lively renders the first three clips.
VOICE_SET=hype (the workflow default for the follow-up) renders only the two v3 takes.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

TEXT = (Path(__file__).resolve().parent / "voice-sample.txt").read_text(encoding="utf-8").strip()
HOOK = "Thirty engines doomed the Soviet moon rocket."
PUNCH = "And the whole set is lit on the pad first, the test the N1 never ran."
OUT = Path(os.environ.get("VOICE_OUT", "video/out/noah-lively"))
NOAH = "9hb1f7xQcMLB90qbYSY3"
V3 = "eleven_v3"
# Eleven v3 exposes stability as three modes: 0.0 Creative, 0.5 Natural, 1.0 Robust.
V3_STABILITY = (0.0, 0.5, 1.0)


def tagged_script(text=TEXT):
    """Light v3 tags: [excited] on the opening line and the closing punchline only."""
    if not text.startswith(HOOK) or PUNCH not in text:
        raise SystemExit("voice-sample.txt no longer has the hook and punchline anchors")
    return "[excited] " + text.replace(PUNCH, "[excited] " + PUNCH, 1)


def creative_stability(value):
    """Map a requested stability onto a v3 mode, preferring Creative on a tie."""
    if value in V3_STABILITY:
        return value
    if abs(value - 0.0) <= abs(value - 0.5):
        return 0.0
    return min(V3_STABILITY, key=lambda choice: abs(choice - value))


def hype_payloads():
    """Requested settings first, then the smaller payloads v3 is documented to accept."""
    a_full = {
        "stability": 0.25,
        "similarity_boost": 0.75,
        "style": 0.70,
        "speed": 1.10,
        "use_speaker_boost": True,
    }
    a_creative = {**a_full, "stability": 0.0}
    a_min = {"stability": 0.0}
    b_full = {
        "stability": 0.0,
        "similarity_boost": 0.75,
        "style": 0.80,
        "speed": 1.12,
        "use_speaker_boost": True,
    }
    b_min = {"stability": 0.0}
    tagged = tagged_script()
    return [
        {
            "file": "noah-v3-hype-a.mp3",
            "model": V3,
            "text": TEXT,
            "tags": [],
            "attempts": [a_full, a_creative, a_min],
        },
        {
            "file": "noah-v3-hype-b.mp3",
            "model": V3,
            "text": tagged,
            "tags": ["[excited]"],
            "attempts": [b_full, b_min, {**b_full, "_drop_tags": True}, {**b_min, "_drop_tags": True}],
        },
    ]


LIVELY = [
    {
        "file": "noah-lively-1.mp3",
        "model": "eleven_multilingual_v2",
        "text": TEXT,
        "tags": [],
        "attempts": [{
            "stability": 0.38,
            "similarity_boost": 0.75,
            "style": 0.45,
            "speed": 1.08,
            "use_speaker_boost": True,
        }],
    },
    {
        "file": "noah-lively-2.mp3",
        "model": "eleven_multilingual_v2",
        "text": TEXT,
        "tags": [],
        "attempts": [{
            "stability": 0.30,
            "similarity_boost": 0.75,
            "style": 0.60,
            "speed": 1.10,
            "use_speaker_boost": True,
        }],
    },
    {
        "file": "noah-lively-3-eleven_v3.mp3",
        "model": V3,
        "text": TEXT,
        "tags": [],
        "attempts": [{
            "stability": 0.35,
            "similarity_boost": 0.75,
            "style": 0.55,
            "speed": 1.08,
            "use_speaker_boost": True,
        }],
    },
]


def key():
    value = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not value:
        raise SystemExit("ELEVENLABS_API_KEY is missing")
    return value


def post(model, text, settings):
    body = {"text": text, "model_id": model, "voice_settings": settings}
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{NOAH}?output_format=mp3_44100_192",
        data=json.dumps(body).encode(),
        headers={"xi-api-key": key(), "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            return response.read(), None, response.status
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:400].replace(key(), "[redacted]")
        return None, f"HTTP {err.code}: {detail}", err.code


def write_mp3(raw, dest):
    if raw[:1] in (b"{", b"["):
        payload = json.loads(raw)
        dest.write_bytes(__import__("base64").b64decode(payload["audio_base64"]))
    else:
        dest.write_bytes(raw)


def render_variant(variant):
    """Try each payload until v3 accepts one. Returns the record of what was sent."""
    notes = []
    for attempt in variant["attempts"]:
        drop_tags = attempt.pop("_drop_tags", False) if isinstance(attempt, dict) else False
        settings = {k: v for k, v in attempt.items() if not k.startswith("_")}
        text = TEXT if drop_tags else variant["text"]
        tags = [] if drop_tags else variant["tags"]
        raw, err, status = post(variant["model"], text, settings)
        if raw is None:
            notes.append({"settings": settings, "tags": tags, "error": err, "status": status})
            print(f"::warning::{variant['file']} rejected {json.dumps(settings)}: {err}")
            if status not in (400, 422):
                break
            continue
        dest = OUT / variant["file"]
        write_mp3(raw, dest)
        if dest.stat().st_size < 10000:
            raise SystemExit(f"{variant['file']} is too small to be an mp3 ({dest.stat().st_size} bytes)")
        stability = settings.get("stability")
        note = None
        if variant["model"] == V3 and stability not in V3_STABILITY:
            note = (
                f"API accepted stability {stability}. "
                "v3 documents only 0.0 Creative, 0.5 Natural and 1.0 Robust, so the service may snap this value."
            )
        return {
            "file": variant["file"],
            "model": variant["model"],
            "voice_id": NOAH,
            "settings_sent": settings,
            "stability_note": note,
            "tags": tags,
            "tag_placements": [] if not tags else ["before the hook", "before the punchline"],
            "spoken_text_has_tags": bool(tags),
            "characters": len(text),
            "bytes": dest.stat().st_size,
            "rejected_attempts": notes,
        }
    raise SystemExit(f"{variant['file']} failed: {json.dumps(notes)}")


def variants_for(mode):
    if mode == "hype":
        return hype_payloads()
    if mode == "lively":
        return LIVELY
    raise SystemExit(f"unknown VOICE_SET {mode}")


def main():
    mode = os.environ.get("VOICE_SET", "hype")
    OUT.mkdir(parents=True, exist_ok=True)
    written = [render_variant(variant) for variant in variants_for(mode)]
    for item in written:
        print(
            f"wrote {item['file']} settings={json.dumps(item['settings_sent'])} "
            f"tags={item['tags']} bytes={item['bytes']}"
        )
    report = {
        "voice_id": NOAH,
        "voice_name": "Noah - Confident Canadian Narrator",
        "set": mode,
        "words": len(TEXT.split()),
        "script_characters": len(TEXT),
        "v3_stability_modes": {"0.0": "Creative", "0.5": "Natural", "1.0": "Robust"},
        "variants": written,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
