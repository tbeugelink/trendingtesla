"""(Re-run 31 Oct: Instagram only, after refreshing the channel in Buffer.)
Post the story Short to TikTok, Instagram and Facebook through Buffer, reusing tools/tiktok_post.py.
The Short has no site article, so this supplies its own title and caption (no article link)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT))
SLUG = "falcon-1-fourth-try"
TITLE = "SpaceX had money for ONE more launch"
TEXT = ("SpaceX had money for ONE more launch 🚀\n\nThree launches. Three failures. Then Falcon 1 flight 4, "
        "September 28, 2008.\n\nMore Tesla & SpaceX news: trendingtesla.com\n\n"
        "#SpaceX #Falcon1 #ElonMusk #RocketLaunch #SpaceHistory #Tesla\n\n"
        "AI-generated voice-over; script written and checked by TrendingTesla.")
# tiktok_post reads the article for the title; give it a throwaway one in the runner only (never committed)
art = ROOT / "content/articles" / f"2026-10-31-{SLUG}.json"
art.write_text(json.dumps({"slug": SLUG, "category": "spacex", "en": {"title": TITLE}}))
import tiktok_post as tp
tp.caption = lambda slug: TEXT
failed = tp.post(sys.argv[1], sys.argv[2])
sys.exit(1 if failed else 0)
