# trendingtesla.com

Static, bilingual (EN at `/`, NL at `/nl/`) Tesla news site.

- Articles: `content/articles/YYYY-MM-DD-slug.json` (format described at the top of `build.py`)
- Build: `python3 build.py` → writes the full site to `public/`, including a generated cover image per article and language (`covers.py`, needs Pillow: `pip install --break-system-packages pillow`)
- Deploy: push to `main`; Cloudflare deploys `public/` automatically (see `wrangler.jsonc`)

`public/` is generated — never edit it by hand, always rebuild.

## Learning from YouTube (read this before choosing and writing an article)

Every morning a GitHub Action (`.github/workflows/yt-learn.yml`) saves the views and likes of every video
(`ops/stats/history.jsonl`) and `tools/learn.py` turns them into **`ops/performance.md`**: which topics, label
types, title styles and hooks get the most views 48 hours after publishing, compared with a typical video.

Every article task reads `ops/performance.md` before picking the story and follows the rules at its bottom:
- news value and accuracy come first; never pick an older or weaker story, never bend facts for a hook;
- use the patterns to choose between comparable stories and to sharpen the title, the label and the first
  sentence of the Short;
- keep exploring: about one in three articles tries a topic, label type or title style that is not in the
  "does well" list, so the channel keeps learning.
