"""Render Noah on Eleven v4 with a tag before every sentence. Does not change defaults.

Reads ELEVENLABS_API_KEY from the environment and never prints it.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

TEXT = (Path(__file__).resolve().parent / "voice-sample.txt").read_text(encoding="utf-8").strip()
OUT = Path(os.environ.get("VOICE_OUT", "video/out/noah-v4"))
NOAH = "9hb1f7xQcMLB90qbYSY3"
TAGS = ("[enthousiast]", "[enthusiastic]")
SPOKEN_HITS = ("enthousiast", "enthousiaste", "enthusiastic", "enthusiasm")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def key():
    value = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not value:
        raise SystemExit("ELEVENLABS_API_KEY is missing")
    return value


def request(url, data=None, headers=None, timeout=300):
    hdrs = {"xi-api-key": key()}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read(), response.status, None
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:500].replace(key(), "[redacted]")
        return None, err.code, detail


def models():
    raw, status, err = request("https://api.elevenlabs.io/v1/models")
    if raw is None:
        raise SystemExit(f"GET /v1/models failed: HTTP {status}: {err}")
    return json.loads(raw)


def pick_model(items):
    tts = [m for m in items if m.get("can_do_text_to_speech")]
    listed = [{"model_id": m.get("model_id"), "name": m.get("name")} for m in tts]
    for m in tts:
        if m.get("model_id") == "eleven_v4":
            return "eleven_v4", False, listed
    for m in tts:
        mid = m.get("model_id") or ""
        name = (m.get("name") or "").strip().lower()
        if mid.startswith("eleven_v4") and "turbo" not in mid and "flash" not in mid:
            return mid, False, listed
        if name == "eleven v4":
            return mid, False, listed
    if any(m.get("model_id") == "eleven_v3" for m in tts):
        return "eleven_v3", True, listed
    raise SystemExit("neither eleven_v4 nor eleven_v3 is available for text to speech")


def tag_sentences(text, tag):
    parts = [p.strip() for p in SENTENCE.split(text.strip()) if p.strip()]
    return " ".join(p if p.startswith(tag) else f"{tag} {p}" for p in parts)


def payloads(model, text):
    """Owner UI: stability 0%, similarity 0%, clone strength 0%, language English."""
    full = {
        "text": text,
        "model_id": model,
        "language_code": "en",
        "voice_settings": {"stability": 0.0, "similarity_boost": 0.0, "clone_strength": 0.0},
    }
    no_clone = {**full, "voice_settings": {"stability": 0.0, "similarity_boost": 0.0}}
    no_lang = {k: v for k, v in full.items() if k != "language_code"}
    bare = {k: v for k, v in no_clone.items() if k != "language_code"}
    return [full, no_clone, no_lang, bare]


def speak(model, text):
    notes = []
    for body in payloads(model, text):
        raw, status, err = request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{NOAH}/with-timestamps?output_format=mp3_44100_192",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if raw is None:
            notes.append({"status": status, "error": err, "sent": {k: v for k, v in body.items() if k != "text"}})
            if status not in (400, 422):
                break
            continue
        data = json.loads(raw)
        audio = __import__("base64").b64decode(data["audio_base64"])
        alignment = data.get("alignment") or data.get("normalized_alignment") or {}
        return audio, alignment, {k: v for k, v in body.items() if k != "text"}, notes
    return None, None, None, notes


def tag_timing(alignment):
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    text = "".join(chars)
    spans = []
    for match in re.finditer(r"\[[^\[\]]+\]", text):
        spans.append({
            "text": match.group(),
            "seconds": round(ends[match.end() - 1] - starts[match.start()], 3),
        })
    return {"present_in_alignment": bool(spans), "count": len(spans), "spans": spans[:12]}


def multipart(fields, file_bytes, filename):
    boundary = "----NoahV4Check"
    chunks = []
    for name, value in fields.items():
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    chunks.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: audio/mpeg\r\n\r\n".encode() + file_bytes + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def transcribe(audio, filename):
    notes = []
    for model in ("scribe_v2", "scribe_v1"):
        body, boundary = multipart({"model_id": model, "language_code": "en", "tag_audio_events": "false"}, audio, filename)
        raw, status, err = request(
            "https://api.elevenlabs.io/v1/speech-to-text",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        if raw is None:
            notes.append({"model": model, "status": status, "error": err})
            continue
        data = json.loads(raw)
        return data.get("text") or "", model, notes
    return "", None, notes


def audible(transcript):
    words = re.findall(r"[A-Za-zÀ-ÿ']+", transcript.lower())
    hits = [w for w in words if any(tok in w for tok in SPOKEN_HITS)]
    return hits


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model, fell_back, listed = pick_model(models())
    (OUT / "models.json").write_text(json.dumps(listed, indent=2) + "\n", encoding="utf-8")
    print(f"model={model} fell_back_to_v3={fell_back}")
    report = {"voice_id": NOAH, "model_id": model, "fell_back_to_v3": fell_back, "clips": []}
    for tag in TAGS:
        text = tag_sentences(TEXT, tag)
        slug = "nl" if tag == "[enthousiast]" else "en"
        audio, alignment, sent, notes = speak(model, text)
        if audio is None:
            raise SystemExit(f"{tag} failed: {json.dumps(notes)}")
        dest = OUT / f"noah-v4-{slug}.mp3"
        dest.write_bytes(audio)
        transcript, stt_model, stt_notes = transcribe(audio, dest.name)
        hits = audible(transcript)
        item = {
            "file": dest.name,
            "tag": tag,
            "sentences": text.count(tag),
            "characters": len(text),
            "bytes": dest.stat().st_size,
            "request": sent,
            "rejected": notes,
            "alignment_tags": tag_timing(alignment or {}),
            "stt_model": stt_model,
            "stt_errors": stt_notes,
            "transcript": transcript,
            "audible_tag_words": hits,
            "tag_spoken": bool(hits),
        }
        report["clips"].append(item)
        print(f"wrote {dest.name} tag={tag} spoken={bool(hits)} hits={hits} stt={stt_model}")
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
