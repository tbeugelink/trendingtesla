"""Speak the Cybercab narration with Noah on Eleven v4. Artifact only. No YouTube upload.

Uses the same request as video/short.py: model eleven_v4, language en, stability 0,
similarity 0, clone strength 0, and the [enthousiast] tag before every sentence.
The tag is stripped from the alignment so captions can follow the script.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import short  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEXT_PATH = ROOT / "video/cybercab/narration.txt"
OUT = ROOT / "video/out"


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
    payload = {
        "voice": short.NOAH_VOICE_ID,
        "model": short.NARRATION_MODEL,
        "text": text,
        "chars": chars,
        "starts": starts,
        "ends": ends,
    }
    (OUT / "cybercab-alignment.json").write_text(json.dumps(payload), encoding="utf-8")
    last = ends[-1] if ends else 0
    print(f"alignment {len(chars)} last {last:.2f} bytes {mp3.stat().st_size}")


if __name__ == "__main__":
    main()
