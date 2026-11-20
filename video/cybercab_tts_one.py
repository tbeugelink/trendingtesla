"""Regenerate one Cybercab sentence with the same Noah settings and its neighbours as context.

The other takes are left untouched. This writes a single mp3 plus its alignment.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cybercab_tts as tts  # noqa: E402
import short  # noqa: E402

TEXT = "But that is not Tesla's name for it."
PREVIOUS = "Start Model 2 in december."
NEXTS = "Model 2 is a nickname commentators used for a cheap Tesla that never arrived as a normal car."
OUT = Path(__file__).resolve().parent.parent / "video" / "out" / "one"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "s001.mp3"
    voice = short.NOAH_VOICE_ID
    chars, starts, ends = tts.request_sentence(TEXT, PREVIOUS, NEXTS, dest, voice)
    manifest = {
        "voice": voice,
        "model": short.NARRATION_MODEL,
        "seed": tts.SEED,
        "text": TEXT,
        "previous_text": PREVIOUS,
        "next_text": NEXTS,
        "chars": chars,
        "starts": starts,
        "ends": ends,
    }
    (OUT / "s001.json").write_text(json.dumps(manifest), encoding="utf-8")
    heard = "".join(chars)
    print(f"voice {voice} model {short.NARRATION_MODEL} seed {tts.SEED}")
    print(f"heard {heard!r} end {ends[-1] if ends else 0:.3f}s")
    if heard.strip() != TEXT:
        raise SystemExit(f"alignment does not match the sentence: {heard!r}")


if __name__ == "__main__":
    main()
