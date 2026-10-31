"""Post the story Short to TikTok, Instagram and Facebook through Buffer, reusing tools/tiktok_post.py.
The Short has no site article, so this supplies its own title and caption (no article link)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT))
SLUG = "cybercab-unboxed"
TITLE = "Tesla broke Henry Ford's assembly line"
TEXT = ("Tesla broke Henry Ford's assembly line 🏭\n\nThe Cybercab is unboxed: front, back and middle are built separately, "
        "then joined in \"the marriage\". Goal: one Cybercab every 10 seconds.\n\nMore Tesla news: trendingtesla.com\n\n"
        "#Tesla #Cybercab #Robotaxi #TeslaNews #Manufacturing #EV\n\n"
        "AI-generated voice-over and images; script written and checked by TrendingTesla.")
# tiktok_post reads the article for the title; give it a throwaway one in the runner only (never committed)
art = ROOT / "content/articles" / f"2026-10-31-{SLUG}.json"
art.write_text(json.dumps({"slug": SLUG, "category": "robotaxi", "en": {"title": TITLE}}))
import tiktok_post as tp
tp.caption = lambda slug: TEXT
failed = tp.post(sys.argv[1], sys.argv[2])
sys.exit(1 if failed else 0)
