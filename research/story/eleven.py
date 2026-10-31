"""Research only: voice (ElevenLabs, same voice + settings as the Shorts) and sound effects for the story Short."""
import base64, json, os, urllib.request
from pathlib import Path

D = Path(__file__).parent
KEY, VOICE = os.environ["ELEVENLABS_API_KEY"], os.environ.get("ELEVENLABS_VOICE_ID_2") or os.environ["ELEVENLABS_VOICE_ID"]
OUT = D / ("out_v2" if os.environ.get("ELEVENLABS_VOICE_ID_2") else "out"); OUT.mkdir(exist_ok=True)
SFX = os.environ.get("MAKE_SFX", "1") == "1"
H = {"xi-api-key": KEY, "Content-Type": "application/json"}

def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=H)
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()

script = json.load(open(D / "script.json"))
for i, s in enumerate(script):
    if not s["text"]:
        continue
    d = json.loads(post(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_192",
                        {"text": s["text"], "model_id": "eleven_multilingual_v2",
                         "voice_settings": {"stability": 0.28, "similarity_boost": 0.8, "style": 0.5,
                                            "speed": 1.12 if s["part"] != "payoff" else 1.0}}))
    (OUT / f"voice_{i:02d}.mp3").write_bytes(base64.b64decode(d["audio_base64"]))
    al = d.get("alignment") or d["normalized_alignment"]
    json.dump(al, open(OUT / f"voice_{i:02d}.json", "w"))
    print("voice", i, "ok")

for name, (prompt, dur) in (json.load(open(D / "request.json"))["sfx"].items() if SFX else []):
    audio = post("https://api.elevenlabs.io/v1/sound-generation",
                 {"text": prompt, "duration_seconds": dur, "prompt_influence": 0.5})
    (OUT / f"sfx_{name}.mp3").write_bytes(audio)
    print("sfx", name, "ok")
