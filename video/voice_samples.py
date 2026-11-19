"""Render three young-adult narration samples with the existing ElevenLabs call.

The key is read from the environment and never printed. Voices are chosen from
the account list and, if needed, the shared library: English, age young,
narration or informative, two male and one female. This run does not repeat
the earlier samples.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = (ROOT / "video" / "voice-sample.txt").read_text(encoding="utf-8").strip()
OUT = Path(os.environ.get("VOICE_OUT", ROOT / "video" / "out" / "voice-samples"))
MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
# Young-adult explainer: credible, not salesy. Same settings on all three.
YOUNG = {"stability": 0.48, "similarity_boost": 0.75, "style": 0.30, "speed": 1.05}
SKIP_IDS = {
    "q1OMOTZNtqpS50TIQtu4",  # current long-form voice
    "nPczCjzI2devNBz1zQrb",  # Brian, already sampled
    "pqHfZKP75CvOlQylNhV4",  # Bill, already sampled
}
BLOCK = ("child", "kid", "cartoon", "anime", "sales", "commercial", "advert", "promo", "hype", "asmr")
NARRATION = ("narrat", "informative", "educational", "explainer", "documentary", "youtube")


def key():
    value = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not value:
        sys.exit("ELEVENLABS_API_KEY is missing")
    return value


def request(url, method="GET", body=None, fatal=True):
    data = None if body is None else json.dumps(body).encode()
    headers = {"xi-api-key": key(), "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            return response.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:400].replace(key(), "[redacted]")
        if not fatal:
            print(f"::warning::ElevenLabs HTTP {err.code}: {detail}")
            return None
        sys.exit(f"ElevenLabs HTTP {err.code}: {detail}")


def subscription():
    data = json.loads(request("https://api.elevenlabs.io/v1/user/subscription"))
    count = data.get("character_count")
    limit = data.get("character_limit")
    remaining = None if count is None or limit is None else max(0, limit - count)
    return {
        "tier": data.get("tier"),
        "status": data.get("status"),
        "character_count": count,
        "character_limit": limit,
        "remaining": remaining,
        "next_reset_unix": data.get("next_character_count_reset_unix"),
    }


def field(voice, *names):
    labels = voice.get("labels") or {}
    for name in names:
        if voice.get(name):
            return str(voice.get(name))
        if labels.get(name):
            return str(labels.get(name))
    return ""


def blob(voice):
    return " ".join(
        field(voice, name) for name in ("name", "description", "use_case", "use case", "descriptive", "accent")
    ).lower()


def eligible(voice):
    if voice.get("voice_id") in SKIP_IDS:
        return False
    if "young" not in field(voice, "age").lower():
        return False
    text = blob(voice)
    if any(word in text for word in BLOCK):
        return False
    language = field(voice, "language").lower()
    accent = field(voice, "accent").lower()
    if language and not language.startswith("en"):
        return False
    english_accent = ("american", "british", "english", "irish", "australian", "canadian", "neutral", "")
    if accent and not any(item in accent for item in english_accent if item):
        return False
    use = field(voice, "use_case", "use case").lower()
    if use and not any(word in use for word in NARRATION):
        return False
    return True


def score(voice):
    text = blob(voice)
    value = 0
    if any(word in text for word in ("narrat", "informative", "educational", "explainer", "documentary")):
        value += 5
    if any(word in text for word in ("clear", "confident", "warm", "conversational", "neutral", "calm")):
        value += 2
    return value


def account_voices():
    data = json.loads(request("https://api.elevenlabs.io/v1/voices"))
    return [v for v in (data.get("voices") or []) if eligible(v)]


def shared_voices(gender):
    found = []
    for use in ("informative_educational", "narration", "narrative_story"):
        query = urllib.parse.urlencode({
            "page_size": 30,
            "gender": gender,
            "age": "young",
            "language": "en",
            "use_cases": use,
        })
        raw = request(f"https://api.elevenlabs.io/v1/shared-voices?{query}", fatal=False)
        if not raw:
            continue
        data = json.loads(raw)
        for voice in data.get("voices") or []:
            voice["source"] = "shared"
            if eligible(voice):
                found.append(voice)
        if found:
            break
    return found


def pick(pool, gender, accent_avoid, count):
    chosen = []
    ranked = sorted((v for v in pool if field(v, "gender").lower() == gender), key=score, reverse=True)
    for voice in ranked:
        accent = field(voice, "accent").lower()
        if accent and accent in accent_avoid and len(ranked) > count:
            continue
        if any(voice.get("voice_id") == got.get("voice_id") for got in chosen):
            continue
        chosen.append(voice)
        accent_avoid.add(accent)
        if len(chosen) == count:
            break
    if len(chosen) < count:
        for voice in ranked:
            if any(voice.get("voice_id") == got.get("voice_id") for got in chosen):
                continue
            chosen.append(voice)
            if len(chosen) == count:
                break
    return chosen


def render(voice_id, dest):
    raw = request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_192",
        method="POST",
        body={"text": TEXT, "model_id": MODEL, "voice_settings": YOUNG},
        fatal=False,
    )
    if raw is None and voice_id:
        return False
    payload = json.loads(raw)
    dest.write_bytes(__import__("base64").b64decode(payload["audio_base64"]))
    return True


def add_shared(voice):
    owner = voice.get("public_owner_id")
    voice_id = voice.get("voice_id")
    if not owner or not voice_id:
        return False
    raw = request(
        f"https://api.elevenlabs.io/v1/voices/add/{owner}/{voice_id}",
        method="POST",
        body={"new_name": (voice.get("name") or "sample")[:40]},
        fatal=False,
    )
    if not raw:
        return False
    added = json.loads(raw)
    if added.get("voice_id"):
        voice["voice_id"] = added["voice_id"]
        voice["added_to_library"] = True
    return True


def slug(name):
    token = (name or "voice").split("-")[0].split(" ")[0]
    cleaned = "".join(ch for ch in token.lower() if ch.isalnum())
    return cleaned or "voice"


def describe(voice):
    return {
        "name": voice.get("name"),
        "voice_id": voice.get("voice_id"),
        "description": field(voice, "description") or None,
        "gender": field(voice, "gender") or None,
        "age": field(voice, "age") or None,
        "accent": field(voice, "accent") or None,
        "use_case": field(voice, "use_case", "use case") or None,
        "descriptive": field(voice, "descriptive") or None,
        "category": voice.get("category"),
        "source": voice.get("source") or "account",
        "added_to_library": bool(voice.get("added_to_library")),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pool = account_voices()
    print(f"account young narration voices: {len(pool)}")
    males = pick(pool, "male", set(), 2)
    females = pick(pool, "female", set(), 1)
    if len(males) < 2:
        males = pick(pool + shared_voices("male"), "male", set(), 2)
    if len(females) < 1:
        females = pick(shared_voices("female"), "female", set(), 1)
    chosen = males[:2] + females[:1]
    if len(chosen) != 3:
        sys.exit(f"Need 2 young male and 1 young female narration voices, found {len(chosen)}")
    for voice in chosen:
        print(
            "selected",
            voice.get("name"),
            voice.get("voice_id"),
            field(voice, "gender"),
            field(voice, "accent"),
            field(voice, "use_case", "use case"),
        )
    before = subscription()
    letters = "def"
    written = []
    for index, voice in enumerate(chosen):
        filename = f"voice-{letters[index]}-{slug(voice.get('name'))}.mp3"
        dest = OUT / filename
        if not render(voice["voice_id"], dest):
            if not add_shared(voice) or not render(voice["voice_id"], dest):
                sys.exit(f"Could not render {voice.get('name')}")
        info = describe(voice)
        info.update({"file": filename, "settings": YOUNG, "bytes": dest.stat().st_size})
        written.append(info)
        print(f"wrote {filename} voice={info['name']} id={info['voice_id']} bytes={info['bytes']}")
    after = subscription()
    report = {
        "model": MODEL,
        "words": len(TEXT.split()),
        "characters_per_sample": len(TEXT),
        "samples": 3,
        "characters_sent": len(TEXT) * 3,
        "music_bed": False,
        "set": "young-adult",
        "subscription_before": before,
        "subscription_after": after,
        "voices": written,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "words": report["words"],
        "characters_sent": report["characters_sent"],
        "subscription_after": after,
        "voices": [{"name": v["name"], "id": v["voice_id"], "file": v["file"]} for v in written],
    }))


if __name__ == "__main__":
    main()
