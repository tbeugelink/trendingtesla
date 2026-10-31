"""Research: make the closing frame of the Cybercab Short with Nano Banana, using our own photos as reference."""
import base64, io, json, sys
from pathlib import Path
from PIL import Image
D = Path(__file__).parent; ROOT = D.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import gen_image as g
PROMPT = ("Photorealistic photo, vertical 9:16. The exact same gold-coloured Tesla Cybercab from the reference photos "
          "(same body shape, light bar, wheels, gold paint), complete and finished, seen from the REAR three-quarter angle, "
          "driving away from the camera out of a huge bright modern factory gate onto an open road, slight motion blur on "
          "the wheels and road, late golden-hour sunlight, red and yellow factory details, cinematic, sharp focus on the car. "
          "The car is centred horizontally. No people, no text, no logos.")
parts = [{"text": PROMPT}]
for f in sorted((D / "refs").glob("*.jpg")):
    parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(f.read_bytes()).decode()}})
mdl = g.model(); print("model", mdl)
out = D / "out_img"; out.mkdir(exist_ok=True)
for k in range(2):
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}}
    d = g.api(f"models/{mdl}:generateContent", body)
    for c in d.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            blob = p.get("inline_data") or p.get("inlineData")
            if blob:
                Image.open(io.BytesIO(base64.b64decode(blob["data"]))).convert("RGB").save(out / f"final_{k}.jpg", quality=92)
                print("saved", k)
