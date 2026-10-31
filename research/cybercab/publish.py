"""Research: upload the Cybercab Short with its designed thumbnail (instead of a frame from the video)."""
import sys
from pathlib import Path
D = Path(__file__).parent; ROOT = D.parents[1]
sys.path.insert(0, str(ROOT / "video"))
import upload
_orig = upload.set_thumbnail
upload.set_thumbnail = lambda vid, mp4, at=None, **k: _orig(vid, mp4, at, jpg=D / "publish" / "thumb.jpg")
sys.argv = ["upload.py", str(D / "publish" / "cybercab-unboxed-en-short.mp4"), "en"]
upload.main()
