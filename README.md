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

## Timeless content first (decided 1 Nov 2026, read this before choosing a topic)

TrendingTesla is a trend site, not a news site: news channels exist plenty, and news is only relevant for a
few days. Every article (and its Short and long video) must stay interesting for months or years, so it keeps
bringing views and visitors. Our best videos prove it: "Tesla Broke Henry Ford's Assembly Line" (1,987 views),
"SpaceX Had Money for ONE More Launch" (1,139) and "How Starlink works" (93% watched) beat every news item.
Goal: **interesting, entertaining and educational**, always factually exact.

- **Morning task: an explainer** people search for and keep asking: how/why/what/which, comparisons
  ("Model 3 vs Model Y"), myths ("Does a Tesla battery really die after 8 years?"), "what happens if…",
  how-to for owners. First choice: the first unchecked topic in ops/evergreen-topics.md (check the site does
  not already answer it; if it does, tick it with "(already covered: <slug>)" and take the next).
- **Evening task: a story** that entertains and teaches: the history and the people behind a product or a
  decision, how something is made, a turning point, a near failure, a record, a bold bet and how it played
  out (like Henry Ford's assembly line and the Cybercab's unboxed process, or SpaceX's last-chance launch).
  First choice: the first unchecked topic under "Stories" in ops/evergreen-topics.md.
- **Trending is the hook, not the subject.** Use what Tesla fans talk about now (the news of the week,
  ops/scout-tesla.md: other channels' outlier videos and viewers' questions) to pick WHICH timeless topic to
  do today, and mention the current event in a sentence or two as the reason it matters now. The article
  itself answers the lasting question. Example: the Robotaxi got longer hours -> "How does Tesla's Robotaxi
  actually work, and why does it still stop at night?" rather than "Robotaxi now runs until 2 a.m.".
- Big lasting news (a new model, a first, a milestone) may be the subject, written with the lasting angle
  (what it is, how it works, why it matters) and a title that will still make sense next year.
- **Space and Optimus get much more room** (decided 1 Nov 2026): SpaceX (Starship, the Moon, Mars, Starlink
  launches) is a core subject, about one in three articles; the link to Tesla can be the Tesla-SpaceX merger or
  the shared technology and vision, one or two sentences are enough. Optimus, which Musk calls Tesla's biggest
  product ever, comes back often: as its own topic, and named wherever it plays a role (factories, Robotaxi,
  Mars). Keep promises and facts apart: what Musk says will happen is a statement, not a fact.
- **Series "How did Elon Musk ...?"**: at most one per week, in the evening slot, from the series list in
  ops/evergreen-topics.md. Strictly factual and balanced (successes, failures, criticism), no political opinion.
- Titles, headings, labels and YouTube titles must not date quickly: no "today", "this week", no dates; a year
  only when it is part of the question ("in 2026").
- After writing, tick the topic in ops/evergreen-topics.md with the slug, and add 1-3 new ideas you came
  across (explainers to the list, stories under "Stories"), so the lists never run dry. Never repeat a topic
  the site already covers; a new angle on it is fine.
- Still: own words, verified facts with sources, no invented drama, no hype words, no promise the title does
  not keep.

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
- **Pictures in the long video must follow the story** (decided 1 Nov 2026): give EVERY "text" block its own
  fitting picture, never let one block borrow another's. Use, in this order: `"img": ["lib/<file>"]` from
  ops/library.json when it shows exactly what is said; this article's own gen/ photos and model/topic photos
  from PHOTOS.md; and for everything else (history, old cars, places, factories, launches) a real photo:
  `"photo": [{"q": ["2008 Tesla Roadster", "Tesla Roadster first generation"], "want": "a first-generation
  Tesla Roadster, the 2008 sports car"}]` (Wikimedia Commons, checked by Gemini; give 2-3 search phrasings).
  Never a recognisable real person. A photo that does not show the subject of the block is worse than none:
  the video then holds the last fitting photo. Aim for 15-25 different fitting pictures in a long video.
- **Key words in the long video** (decided 1 Nov 2026): no captions in the picture any more (YouTube makes its own
  closed captions, CC, which viewers can translate into almost any language); instead big yellow key words in the centre, like the story Shorts. Give
  every "text" block of the "video" script a `"pop": [{"say": "...", "show": "..."}]` list of 2-4 headline-style
  key words in the rhythm of the voice (same rules as "Story Shorts": "say" = the exact words as spoken in that
  block, "show" = 1-3 capitalised words, 4 at most, two lines at most; e.g. NEVER MOVED, BILL $539, WHY?).
  Each shows for up to 3 s. The last block's last key word is the core message. Without a "pop" list only
  numbers and words in capitals pop up, which is too little. "key" blocks keep their keyword bar.
- **Keep the Short's promise** (decided 1 Nov 2026): every Short ends with "for the full story go to
  TrendingTesla.com", so the article and the long video must really give the full story: clearly more than
  the Short (the background, the how and why, the numbers, the turns, what it means), never the same 60
  seconds again in longer words. Write the Short as the most gripping slice of the story; keep one or two
  strong details for the article and the long video. The Short's description always links to the article.
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
  photos (`"lib"`, the list with what each one shows is `ops/library.json`) first; a beat with two subjects gets
  two photos. Where no library photo fits, use the article's own photos (`"img"` with a file from `"images"`).
  Never a photo that shows something else than what is said (a door handle is not a charger handle).
- Review: a story Short is uploaded private; William deletes bad ones in YouTube Studio, the rest goes public
  automatically after 2 hours (`tools/story_approve.py`) and then to TikTok, Instagram and Facebook.
- **Key words tell the story on their own** (there are no running subtitles): 2-5 per beat, in the rhythm of the
  voice, each a short phrase of 1-3 words (4 at most, shown on two lines), in capitals, the way a headline would
  put it - e.g. NEVER MOVED, BILL $539, WHY?, SINCE OCTOBER, HIDDEN BUTTON, EMERGENCY, REPAIRS?, TAPPED ACTIVATE,
  READ BEFORE -> YOU TAP! (split a longer phrase into two pops that follow the voice), $25,000!. `"say"` = the exact spoken words where it appears (it shows 0.15 s before them), `"show"`
  = what is on screen. Every shot has a key word; never one that belongs to another sentence.
- Every frame carries the small TrendingTesla logo top left; the render stops with an error when it is missing.
- The last key word is the core message of the Short (e.g. YOU TAP!): it stays 1 s longer after the voice.
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
