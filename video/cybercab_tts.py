"""Speak the Cybercab narration with Noah on Eleven v4. Artifact only. No YouTube upload.

Uses the same request as video/short.py: model eleven_v4, language en, stability 0,
similarity 0, clone strength 0, and the [enthousiast] tag before every sentence.
The tag is stripped from the alignment so captions can follow the script.
A [pause] between sections is an Eleven v4 audio tag. It is stripped the same way,
so the breath stays in the timestamps and does not reach the captions.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import short  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEXT_PATH = ROOT / "video/cybercab/narration.txt"
OUT = ROOT / "video/out"
PAUSE_TAG = re.compile(r"\[(?:long )?pause\]\s*", re.IGNORECASE)


def drop_pause_tags(chars, starts, ends):
    """Remove pause-tag characters. The silence they create stays between the words."""
    text = "".join(chars)
    drop = [False] * len(text)
    for match in PAUSE_TAG.finditer(text):
        for i in range(match.start(), match.end()):
            drop[i] = True
    if not any(drop):
        return chars, starts, ends
    kept = [(c, s, e) for c, s, e, gone in zip(chars, starts, ends, drop) if not gone]
    if not kept:
        return chars, starts, ends
    return [c for c, _, _ in kept], [s for _, s, _ in kept], [e for _, _, e in kept]


def main():
    raw = TEXT_PATH.read_text(encoding="utf-8").strip()
    text = short.spoken(raw, "en")
    tagged = short.tag_sentences(text)
    print(f"chars {len(text)} tagged {len(tagged)} sentences {tagged.count(short.NARRATION_TAG)}")
    if len(tagged) > 10000:
        raise SystemExit("tagged narration is over the ElevenLabs request ceiling")
    OUT.mkdir(parents=True, exist_ok=True)
    mp3 = OUT / "cybercab-narration.mp3"
    chars, starts, ends = short.tts_elevenlabs(text, mp3)
    chars, starts, ends = drop_pause_tags(chars, starts, ends)
    spoken_text = re.sub(r"[ \t]{2,}", " ", PAUSE_TAG.sub("", text)).strip()
    heard = "".join(chars)
    if re.search(r"\bpause\b", heard, re.IGNORECASE):
        print("::warning::the alignment still contains the word pause")
    payload = {
        "voice": short.NOAH_VOICE_ID,
        "model": short.NARRATION_MODEL,
        "text": spoken_text,
        "chars": chars,
        "starts": starts,
        "ends": ends,
    }
    (OUT / "cybercab-alignment.json").write_text(json.dumps(payload), encoding="utf-8")
    last = ends[-1] if ends else 0
    print(f"alignment {len(chars)} last {last:.2f} bytes {mp3.stat().st_size}")


if __name__ == "__main__":
    main()
