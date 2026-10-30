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

## Photos: real ones first, and more of them (read this before writing an article)

Videos repeat the same few pictures when an article has only 2-3 photos, and real photos of the news
perform much better than illustrations. So for every new article:

1. **Real, freely licensed photos first** (`"real_photos"`, 0-3 entries). Look for photos of the actual
   subject or event that may be reused: Wikimedia Commons files with **public domain, CC0 or CC BY**
   (open the File: page and check the licence; **not CC BY-SA, not NC/ND**), or photos published by a
   **US federal agency** (NTSB, NHTSA, NASA, FAA, DOT ...; public domain). Never news-agency, press,
   social media, fire-department or other photos, however newsworthy: they are copyrighted.
   Format: `{"page": "https://commons.wikimedia.org/wiki/File:...", "describe": "what is visible"}` or
   `{"page": "<agency page>", "src": "<direct .jpg on the agency site>", "credit": "NTSB", "describe": "..."}`.
   `tools/real_photos.py` (run by the video workflow) checks the licence again, downloads them, puts them
   first in "images", makes a real photo the cover and adds the required credit under the article and in
   the YouTube descriptions. Only add a photo whose visible subject really is the story's subject.
2. **"images": give 4-6 fitting photos** from PHOTOS.md (was 3), different from the ones the latest
   articles in the same category open with.
3. **`gen_image.extra`: 1-2 more AI scenes** of the same subject (same refs), each `{"prompt": "...",
   "describe": "..."}`: a different setting, angle or moment than the main scene, so the video can change
   pictures without repeating. Same rules as gen_image: illustrations, never a fake photo of the event.
