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

## Scouting other channels

`tools/scout.py` (settings in `ops/scout.json`) looks at other YouTube channels:
- **Daily, Tesla/SpaceX/xAI** (in `yt-learn.yml`): outlier videos of the last 7 days (views divided by what
  that channel usually gets) and the most-liked viewer questions the creator left unanswered, written to
  `ops/scout-tesla.md` and added to the bottom of `ops/performance.md`, so article tasks see it automatically.
  It is a hint, never a reason to drop news value or accuracy, and never a reason to copy a script or title.
- **Weekly, candidate niches for a second channel** (`niche-scout.yml`, Sundays): compares the niches in
  `ops/scout.json` by how many different small or young channels have outliers in them -> `ops/niches.md`.
Raw results per run are kept in `ops/scout/`. The scans stay within a YouTube API unit budget so uploads
always keep enough quota.

## Thumbnail and first frame (read this before choosing photos)

The first photo of an article is the YouTube thumbnail, the first frame of the Short and the long video, and
the cover on the site. Viewers decide in a second, so it must show something striking right away:

- **One concrete subject, big and sharp**: the car, robot, battery, charger or rocket the story is about,
  filling roughly half of the frame, seen close from a dynamic angle, with strong light and contrast.
  Never a wide landscape with a tiny car, a generic interior, a screen full of text or a cluttered scene.
- **The main `gen_image` scene is that photo** (it is put first automatically): write its prompt as a
  close, eye-catching shot of the subject. Use `gen_image.extra` for the wider or calmer scenes.
  `tools/gen_image.py` adds this thumbnail instruction to the main scene by itself.
- Without a `gen_image` (stories about one car model, or when a real photo becomes the cover), put the
  most striking fitting photo first in `"images"`.
- Keep the lower-left third calm: the label goes there.
- Keep the subject in the **horizontal centre**: the vertical Short shows only the middle third of the photo.

Early hint from the first Shorts (not yet a rule, ops/performance.md takes over once there is enough data):
stories about a **concrete thing you can see** (how a product works, what is inside it, why something
happened to it) with a **WHY/HOW question label** got about 3-5 times more views than stories about
procedures, votes or rules. When two stories are about equally newsworthy, prefer the concrete one, and for a
procedural story look for the concrete angle (what changes for the car or the driver). News value and
accuracy still come first.

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

## Shorts first (decided 31 Oct 2026, read this before writing the "short" script)

The numbers of the first days were clear: Shorts got 450-1,400 views each, long news videos 4-243 (mostly ~15),
and the story-style Shorts ("SpaceX Had Money for ONE More Launch": 1,122 views in 7 hours) beat the news
Shorts (typically 741 views after 48 hours) by far. So:
- **Every article still gets a long video too** (a "video" script is required), so the video series on the
  site and the channel is never interrupted (decided 1 Nov 2026). The Short is where the growth comes from, so
  it gets the most care.
- **The long video uses the same story style** (decided 1 Nov 2026): its first sentence is the hook (the most
  striking concrete fact or turn, never a dry summary), the opening builds what is at stake before the first
  heading, every section answers one question and raises the next, and the last block ends on the strongest
  line, not a summary. It keeps exactly the article's headings, so readers can follow along. It also gets its
  own YouTube title: `"video": {"en": [...], "nl": [...], "yt_title_en": "...", "yt_title_nl": "..."}`,
  5-10 words, title case, a story or a sharp question in one line ("The $539 Button Tesla Owners Keep Pressing
  by Accident"), factually exact, never a promise the video does not keep.
- **Write the Short as a story: hook -> tension -> payoff**, under 60 seconds. Hook: the most striking concrete
  fact or turn, in the first sentence. Tension: what was at stake, what stood in the way, what people expected.
  Payoff: what happened and why it matters, ending on the strongest line. Short sentences, a few words in
  capitals for spoken emphasis ("ONE more launch"), never invented drama: the same facts as the article.
- **Add a YouTube title for the Short**: `"short": {..., "yt_title_en": "...", "yt_title_nl": "..."}`, 4-8 words,
  title case, a story in one line ("Tesla Broke Henry Ford's Assembly Line", "SpaceX Had Money for ONE More
  Launch"); at most one word in capitals; factually exact; no number unless the number IS the story; never a
  promise the Short does not keep. The long search-friendly article title stays on the site.
- Explainers hold viewers best ("How Starlink works": 93% watched): a "why/how" angle on the news works well.
  Small routine items (a list of new Supercharger sites) do badly: only cover them when they are big.

## Story Shorts (video/story.py, read this before writing "short.story")

A story Short is a list of beats in `"short": {"story": [...]}`: one beat per sentence or two,
`{"part": "hook|tension|payoff", "text": "...", "lib": ["file.jpg"], "pop": [{"say": "...", "show": "..."}]}`.
- **Pictures follow the words:** every beat shows what is said at that moment. Use William's checked detail
  photos in `static/img/lib/` (see `ops/library-prompts.md`) first; a beat with two subjects gets two photos.
- **Key words tell the story on their own** (there are no running subtitles): 2-5 per beat, in the rhythm of the
  voice, each a short phrase of 1-3 words (4 at most, shown on two lines), in capitals, the way a headline would
  put it - e.g. NEVER MOVED, BILL $539, WHY?, SINCE OCTOBER, HIDDEN BUTTON, EMERGENCY, REPAIRS?, TAPPED ACTIVATE,
  READ BEFORE YOU TAP. `"say"` = the exact spoken words where it appears (it shows 0.15 s before them), `"show"`
  = what is on screen. Every shot has a key word; never one that belongs to another sentence.
- Calm pictures: about 3 s per photo, long crossfades, slow steady motion; shaking only for launches.

## Openings and variety (read this before writing the "short" and "video" scripts)

Viewers decide in the first 1-2 seconds whether to swipe away, and YouTube gives less reach to channels
whose videos all look mass-produced. The videos therefore no longer read the label aloud: the voice starts
straight with the first sentence of the script while the label is shown for about 2 seconds (this
replaces the older instruction that the voice first reads the label).

- **The first sentence of the Short and of the long video is the hook**: the single most striking concrete
  fact or consequence of the story, at most about 12 words, no greeting, no "today", no "Tesla news".
  It must make sense on its own, because the label is not spoken. Never repeat the label word for word.
- **Tag the hook type** in the Short: `"short": {"en": ..., "nl": ..., "hook": "<type>"}`, one of
  `number` (a striking figure), `consequence` (what it means for owners, riders or investors),
  `contrast` (expectation vs reality, before vs after), `question` (a real open question the Short answers),
  `first` (a first, record or end). The learning loop (ops/performance.md) measures which types work;
  rotate types so every type keeps being tested, and do not use the same type as the previous Short.
- **Vary the long-video shape** with the story: 3-6 heads (not always 5), sometimes start with the
  consequence and then the facts, sometimes with the facts; at least one section that is our own analysis
  (why it matters, what is new compared with earlier news, what to watch for) rather than a summary of the sources.
