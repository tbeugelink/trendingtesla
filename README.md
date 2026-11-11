# trendingtesla.com

Static, bilingual (EN at `/`, NL at `/nl/`) Tesla news site.

- Articles: `content/articles/YYYY-MM-DD-slug.json` (format described at the top of `build.py`)
- Build: `python3 build.py` → writes the full site to `public/`, including a generated cover image per article and language (`covers.py`, needs Pillow: `pip install --break-system-packages pillow`)
- Deploy: push to `main`; Cloudflare deploys `public/` automatically (see `wrangler.jsonc`)

`public/` is generated — never edit it by hand, always rebuild.

## RELIABILITY AND QUALITY (William, 11 Nov 2026) - read first; no more lost days, and the numbers must go up

The task instructions live in the repo: **ops/tasks/article.md** (midday, evening, Saturday), **ops/tasks/monitor.md**
(twice a day) and **ops/tasks/daily-review.md** (every morning). The scheduled tasks only say which one to follow.

**The daily loop**
- ~06:00 statistics and scouting (yt-learn.yml): ops/short-signals.md, ops/performance.md, ops/scout-tesla.md and
  **ops/proven-topics.md** (Shorts of the last 30 days that already pulled 100K+ views).
- ~07:10 daily review task: analyses yesterday and writes **ops/daily-review.md** with at most 3 instructions and the
  one test for today. Every article task reads it and follows it.
- ~12:40 midday article + Short + long video; ~14:35 monitor. ~21:10 evening article + Short; ~22:35 monitor.
- The monitor runs `tools/health.py` (article there? Short and long video public on YouTube? reached TikTok,
  Instagram and Facebook? page live? script and render rules kept? a run failed or stuck?), repairs what is safe
  and tells William the same day. `ops/health.md` holds the last report.

**PROVEN TOPICS** - only topics whose popularity is already proven: from ops/proven-topics.md, the outliers in
ops/scout-tesla.md or our own best Shorts; a news event of the last 48 hours only when clearly bigger. The proof goes
into `short.proof` {"source", "views", "why"}. Take the topic and the kind of angle, never the script or the title.

**PROVEN TACTICS** (what demonstrably keeps viewers on Shorts; all are checkable)
- One idea per Short. The hook raises ONE question; the answer comes in the last two beats, not earlier.
- Hook = a contradiction ("... On purpose."), a clash of two numbers ("30 engines failed. SpaceX uses 33.") or
  concrete stakes ("Catch $6 million falling from space."). Never an announcement, a date, a definition or a name
  the viewer does not know yet.
- The first picture is the most dramatic one of the story and shows what the hook claims (fire, a crash, a strange
  object, hands doing something); never a parked car or a wide empty shot.
- Every middle beat adds one new, concrete fact and pulls toward the answer ("but", "so", "then"). Numbers beat
  adjectives. Cut every beat the payoff does not need.
- A new picture at least every 2 seconds (the renderer cuts quickly in the overlay format; give every beat 2 pictures).
- 20-30 seconds is the target: our 29-second Short was watched 122% (it loops), the 45-55 second ones 60-87%.
- The payoff is a real answer with a small surprise; then the loop line.
- Title: at most 45 characters, the hook's contrast or number, no extra words.
- Test ONE thing at a time: every Short names in `short.learning.test` the single variable it changes compared with
  the previous Short of its slot. The format itself stays fixed for at least 7 days (until 19 Nov 2026) so the
  morning review can tell what works; the watch-time numbers arrive 2-3 days late.

**CHECK BEFORE COMMIT** - `python3 tools/check_article.py <article file>` must report 0 errors (parts, overlays,
beat length, pictures, loop, proof, required fields). A beat's `"part"` is only "hook", "tension" or "payoff".

**Guards in the pipeline** (do not remove): the renderer tolerates an unknown part; the watchdog (hourly) asks once for
a missing Short or long video, never while a video run is waiting or working, and never re-runs an old request;
every post to Buffer is logged in ops/social-log.jsonl and a failed post turns the run red; ops/social-queue.json
posts Shorts that were missed, one at a time.

## SHORT FORMAT v4 (William, 9 Nov 2026, afternoon) - replaces the loop rule of v3/v3.1; everything else stays

Earlier versions failed because the hook came too late, the text density was too low, or the loop felt
mechanical. That is forbidden from now on.
- **Smart loop, never an exact repeat**: the last line must NOT be the same as the opening line. Write it so that,
  when the Short starts again, it runs on logically and smoothly into the first sentence: an unnoticeable
  transition. Model: last line "That's why SpaceX uses 33." -> restart "30 engines failed. SpaceX uses 33." =
  "...That's why SpaceX uses 33. 30 engines failed. SpaceX uses 33." (Overrides "the last beat repeats the hook".)
- Add `"loop": {"last": "<last line>", "how": "<how it runs on into the opening line>"}` to `"short"`; the summary
  to William states the last line and how it runs on into the opening line.
- Self-learning also names how the loop line connects. The renderer reports the loop pair and warns when the last
  line repeats the hook word for word.
- All other rules stay: hook in 0-2 s (3 variants + why), big text from frame 1 on 70%+ of the seconds (in practice
  100% with an overlay per beat), max 2 lines and ~36 characters per overlay (hook included), numbers and years
  yellow, a dark band on bright photos, a beat every 2.5-4 s, a second photo for beats over 3 s.

Model Short ("30 Engines Failed. SpaceX Uses 33"):
```
0-2s   overlay "30 engines failed. SpaceX uses 33."        voice: "30 engines failed. SpaceX uses 33."
2-6s   overlay "N1 flew 4 times. Failed 4 times."          voice: "The N1 flew four times. It failed four times."
6-10s  overlay "Its 30 engines never fired together."      voice: "Its 30 engines never fired together on the ground."
10-14s overlay "One engine failed, the rest went with it." voice: the same
14-18s overlay "Apollo's F-1 took over 3 years to tame."   voice: the same
18-22s overlay "Starship fires all 33 on the pad first."   voice: the same
22-26s overlay "Flight 14 lost an engine. Made orbit anyway." voice: "Flight 14 lost an engine. It made orbit anyway."
26-30s overlay "That's why SpaceX uses 33."                voice: the same (runs on into the hook)
```
Visuals: fast cuts between N1 crash pictures, the Saturn V F-1 and Starship Super Heavy; no logo in the first 2 s.

## SHORT FORMAT v3.1 (William, 9 Nov 2026) - additions to v3 below; no exceptions

Text overlays
- At most 2 lines per beat; a sentence never runs over 3 lines. Write overlays of at most ~36 characters
  ("December 21: first upright orbital landing" is the limit; better shorter). The renderer never shrinks text
  below 72 px: a longer overlay is split into two halves of the beat and reported.
- The hook overlay must fit on 2 lines too (max ~36 characters), so it stands WHOLE for the first 2 seconds.
- Numbers and years are always yellow (the renderer does this for every word with a digit, $, %, EUR or GBP sign).
- Readable on every background: on bright photos (explosions, sunsets) the renderer adds a soft semi-transparent
  dark band behind the text and reports in which beats.

Timing and density
- Every beat lasts at least 2.5 and at most 4 seconds (about 7-11 spoken words).
- A beat longer than 3 seconds MUST change photo: give it 2 pictures (`"lib"` with 2 files, or "img" + "lib").
  Never 4+ seconds of the same still.
- The hook sentence stands alone for the full first 2 seconds: no logo, no date, no extra label.

Loop
- (Replaced by v4: the last line runs on into the hook instead of repeating it.)

Self-learning output (required in every summary to William)
- Which text rules were applied (e.g. "sentence shortened to 2 lines", "overlay of beat 5 shortened to 34 characters").
- Whether contrast adjustments are expected (bright photos: explosion, sunset) and in which beats.
- Whether all beats stay within 2.5-4 seconds (estimate at ~2.6 spoken words per second).
After rendering, the renderer writes what it actually did to `ops/short-reports/<slug>.txt` (splits, contrast
bands, beats outside 2.5-4 s, beats with one photo over 3 s, loop check); the next task reads the previous report
in its self-learning step.

## SHORT FORMAT v3 (William, 9 Nov 2026) - the model for every Short; no exceptions, no interpretation

Earlier versions failed because the hook came too late and there was too little (or no) big text on screen. That is
forbidden from now on. Rules 1-5 of "HARD RULES" below stay, with this format:
- **Hook in 0-2 s**: the first spoken words ARE the sharpest claim or the most surprising fact; no "In 2015...".
- **Every beat has an `"overlay"`**: the exact on-screen sentence for that beat (5-12 words, it may be the spoken
  line itself or a condensed version). The renderer shows it big (white with a black edge, numbers in yellow,
  centred) for the WHOLE beat, from frame 1 to the next beat: 100% of the seconds carry text, fully understandable
  without sound. The old "pop" key words and `hook_text` are not used when beats have overlays.
- **A beat lasts 2.5-4 s** (8-12 spoken words); a beat that runs longer gets 2 pictures (`"lib"` with 2 files) so
  something changes every 2.5-4 s.
- (Replaced by v4: smart loop.) ~~The last beat repeats the hook~~.
- No logo and no label in the first 2 seconds: only the hook (the renderer does this).
- Description only: "like and subscribe", "full story on TrendingTesla.com".

Required in `"short"`: `yt_title_en`/`yt_title_nl` (the title), `hooks` (3 variants) + `hook_pick` {index, why},
`story` beats {"part", "t": "0-2s", "text" (voice), "overlay" (exact text), "lib"/"img"/"photo", "visual"},
`signals`, `learning` {"prev", "prev_stats", "weakest_hook", "why_stalled", "change"}, `en`/`nl` (spoken text).

Model (William's rewrite of the first Falcon 9 landing Short):
```
0-2s   overlay "Two crashes. One explosion. Then it landed."            voice: the same line
2-6s   overlay "January 2015: steering fins ran out of fluid"           voice: "January 2015. The first booster
                                                                        slams into the ship. Its steering fins ran out of fluid."
6-10s  overlay "April: lands and tips over"                             voice: "April. The next one lands and tips over."
10-14s overlay "June: the whole rocket breaks apart"                    voice: "June. The whole rocket breaks apart."
14-20s overlay "December 21: first upright landing of an orbital rocket" voice: "December 21st. A booster flies back to
                                                                        Florida and lands upright. A first for an orbital rocket."
20-26s overlay "Today one booster has flown 37 times. The first one is a monument."
26-30s overlay "Two crashes. One explosion. Then it landed."            voice: the same line (loop)
```
Visuals: fast cuts between photos of the crashes and the landing; nothing else in the first 2 seconds.

## HARD RULES (William, 8 Nov 2026, afternoon) - sharpen the ALGORITHM RULES below; no exceptions

The previous versions stalled because the hook came too late, text overlays were missing and the density was too
low. That must not happen again.
1. **The hook is literally in the first 2 seconds.** No build-up, no "In the Tesla Semi...", no "Rocket fuel is...".
   Start with the sharpest claim or the most surprising number: "$9 a kilo vs $54,000. Here's why." or "Why Tesla
   put the driver in the MIDDLE." At most ~5 spoken words before the claim lands. Always 3 hook variants; say why
   the chosen one wins.
2. **Big, permanent text from frame 1.** Fully understandable without sound; at least 70% of the seconds carry big
   readable text that holds the claim or the fact. Shorts: `"short.hook_text"` (max 5 words, exact text, e.g.
   "$9 A KILO VS $54,000") is shown big from the very first frame until the hook beat ends; after that every beat
   has 1-3 "pop" overlays that each carry a fact on their own ("$54,500 / KG", "LOST. EVERY FLIGHT"), never a
   fragment like "PRICED LIKE". The renderer reports the % of seconds with text and warns under 70%.
   Long videos: the subtitles run the whole time; the label carries the hook in the first seconds.
3. **Pattern interrupt every 2.5-4 seconds**: new information, a new number, a new picture or new text. No long
   voice-over block without an interrupt.
4. **The end is loopable**: the last sentence or text links seamlessly back to the opening claim. No "like and
   subscribe" and no "full story on the site" as the last beat: only in the description. (The Short's
   "FULL STORY" line and the long video's spoken outro and end card are switched off.)
5. **Self-learning is required and visible**: after every Short and video write down explicitly what was weak in
   the previous one (e.g. "hook started too late") and which concrete change is made now; in `"short.learning"`,
   in ops/hook-log.md and in the task's summary to William.

Short output (all required): title, 3 hook variants + chosen hook + why, `hook_text`, the full script with timing
per beat (`"t"`: "0-2s", "2-6s", ...), the exact text overlays per beat (`"pop"` "show"), visual cues
(`"visual"`), which signals it serves better than the previous one (`"signals"`), the self-learning note
(`"learning"`).
Long videos: the same hard hook in the first 15-20 s (the first sentence is the claim itself), high density,
6-8 minutes at most unless the subject really needs more, and they end on a loopable payoff, never a call to action.
Stay factually correct; the article is the source. No soft explainer videos any more.

## ALGORITHM RULES (William, 8 Nov 2026) - read first; they override every older rule below where they differ

Goal: Shorts and videos that maximise the algorithm signals: **viewed vs swiped away over 70% in the first 3 s,
high completion plus loops, shares**. Organic distribution, not just a neat explanation. Apply without exception.
Where we stood on 8 Nov 2026 (`ops/short-signals.md`, updated every morning): stayed ~55% (goal 70%+), watched
~70% (goal 90%+ with loops), Shorts ~57 s long. Most Shorts stalled around 1,000 views.

**General (Shorts and long videos)**
- Factually correct, based on the article it belongs to. Never invented drama, never a claim the video does not keep.
- No soft intro: the first words are the strongest claim or the most surprising fact. No "In 2019...", no "Tesla is...",
  no scene setting before the claim.
- Big readable text from frame 1 (sound-off proof): the label shows from the first frame, the key words follow.
- A new beat every 2.5-4 seconds: a new picture, a new key word or a new piece of information.
- End with a payoff that rewards the opening, and let the end run into the beginning (loopable): the last line
  is written so that the hook makes sense right after it (it answers the hook's question with a twist, or it
  ends on a half sentence the hook completes). The Short has NO end card and NO spoken slogan any more; a small
  silent "FULL STORY" line was tried and is switched off again (HARD RULES, rule 4).
- After every publication, analyse why the previous one stalled around ~1,000 views and name the concrete change
  in the next one (see "Self-learning" below).

**Shorts (2 per day: midday and evening, 15-35 seconds)**
- 15-35 s = about 40-80 spoken words (the voice runs at 1.17). The renderer warns above 35 s.
- Structure: 1. **Hook (0-3 s)**: pattern interrupt + curiosity gap or a specific claim, at most ~8 words.
  2. **Retain**: dense information with open loops (raise a question, answer it a beat later, raise the next).
  3. **Reward**: a clear payoff + the loop back to the hook.
- Always write 3 hook variants and choose the strongest (the one that makes it hardest to swipe away and that
  the Short fully keeps).
- `"story"`: 6-11 beats, each 2.5-4 s spoken (about 7-11 words), each with its own picture and 1-3 key words.
- Output per Short, in `"short"` (all required):
  - `"yt_title_en"` / `"yt_title_nl"`: the title (= the hook, 4-8 words).
  - `"hooks"`: `[{"text": "...", "type": "number|consequence|contrast|question|first"}, x3]`, and
    `"hook_pick": {"index": 0, "why": "one line"}`; the chosen hook is the first beat's text.
  - `"story"`: the full script with timing: every beat gets `"t": "0-3s"` (estimated at ~2.6 words per second),
    `"text"`, `"pop"` (the text overlays), `"lib"`/`"img"` and `"visual"` (one line: what is seen and how it moves).
  - `"signals"`: which signals this Short serves better than the previous one, and how (one or two lines).
  - `"learning"`: `{"prev": "<slug of the previous Short>", "prev_stats": "views / stayed / watched from
    ops/short-signals.md", "weakest_hook": "...", "why_stalled": "...", "change": "the concrete change now, e.g.
    hook is now a contrarian claim instead of a factual announcement"}`.
  - `"en"` / `"nl"`: the same spoken text as one paragraph (for the description and the Dutch version).

**Long videos (1 per day: only the midday explainer)**
- Only the midday article gets a `"video"` script; the evening story and the Saturday explainer get no long video
  (they get their Short). The watchdog only checks a long video when there is a `"video"` script.
- The same hook principle in the first 15-20 s: the strongest claim first, an open loop the video pays off later.
- Keep the density high: no long monologue without a visual or informative interrupt (a number, a question, a
  turn, a comparison) at least every 20-30 s; pictures change every ~3 s and the subtitles run along.
- End with a strong, loopable payoff; no call to action at the end (the referral is in the description).
- At most 6-8 minutes (about 900-1,300 spoken words) unless the subject really needs more.

**Self-learning (required after every Short and long video)**
- Before writing, read `ops/short-signals.md` and `ops/hook-log.md`.
- Add one entry at the top of `ops/hook-log.md` (newest first): date, slug, the 3 hook variants with the pick,
  the previous Short's stats, which hook was weakest in the previous one and why it stalled, and the concrete
  change made now. Fill the same in `"short.learning"`. For the long video add one line: what changed in its
  first 20 s compared with the previous long video.

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

## Topic choice: what plays THIS week first, the lists only as reserve (decided 3 Nov 2026)

The first purely historical topics (the 2008 Roadster, the first chopsticks catch, a phone rumour) got far fewer
views than topics with a fresh angle. So every run starts from what Tesla fans talk about right now: search the
news of the last 3-7 days and read ops/scout-tesla.md (outlier videos at other channels, viewers' questions).
Pick the topic that is hot now AND can be told in a lasting way: the current event is the hook, the article
explains or tells what stays true ("Starship is being caught again this week: how the chopsticks actually
work", not "the story of the first catch"). Only when nothing fits, take a topic from ops/evergreen-topics.md,
and then still open with a link to something current where one exists.

Hooks (Short, label, titles): sharp but playful and intriguing. Make people curious with a surprising fact, a
twist, a question they cannot leave unanswered, a wink or a rhyme ("Grok does the mapping, you do the napping?",
"Tesla Broke Henry Ford's Assembly Line"). Never clickbait the video does not keep, never fake drama.

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

## Article photos: OpenAI first, Gemini as fallback (decided 2 Nov 2026)

New article photos ("gen_image") are made by OpenAI GPT Image 2.5 Flare (quality high) with 1-2 reference
photos, following ops/visual-standard.md (TrendingTesla Visual Standard v1.0). Gemini checks each one on three
separate points (visual >= 7, no critical technical error, journalistically sound); a rejected photo gets at
most 2 more tries (the last with Sunburst), then Nano Banana makes it as before. References for OpenAI are only
William's library photos ("lib/...") and CC0 / public-domain photos: give at least one such reference
(`{"src": "lib/<file>"}` from ops/library.json) in "gen_image.refs", and optionally "profile": "editorial",
"cinematic" or "technical" and "category": "A", "B" or "C". Budget: about $11 (EUR 10) a month and 25 images a
day (ops/images-log.jsonl logs every image). Switch back to Gemini only: repository variable IMAGE_PROVIDER=gemini.

## YouTube titles: Short = hook, long video = search (decided 2 Nov 2026)

Long videos only get views from search (Semi fire 338, Emergency Drive Away 157), Shorts from the feed. So:
- `short.yt_title_*`: the story hook, as before ("Tesla Broke Henry Ford's Assembly Line").
- `video.yt_title_*`: the words people type into YouTube or Google: the subject named plainly (model, feature,
  person) plus the question or the answer, 6-12 words, e.g. "How Tesla's First Roadster Was Built From a Lotus
  Elise", "Can You Sleep While Tesla FSD Drives? What the Law Says", "How Long Does a Tesla Battery Last?
  Real Data". No teaser without the subject. This replaces "a story or a sharp question" in the task prompts
  for the long video's title.

## Thumbnail label keeps the hook (decided 2 Nov 2026)

Always two lines in two colours (types "a", "c" or "n"): that is the TrendingTesla look and fits the two-part
hook. The one-block type "r" only for real bad news (a recall, a ban, a death, a cancellation), never for an
explainer or a story.

When the title is a catchy line (a rhyme, a pun, a slogan, e.g. "Grok does the mapping, you do the napping?"),
the "label" uses exactly that line: type "c" with the first half as "sub" and the second half as "text" (up to
about 22 characters each). Never replace a strong hook with a plain summary ("NO NAPPING YET" lost the rhyme).

## Pictures in sync with the voice (decided 2 Nov 2026)

A picture of something the voice names (the Roadster in space, the Falcon Heavy, the Model S) starts when that
word is spoken, never before. The renderer does this from the picture's description, so describe library and
real photos with the words the voice will use, and in a beat with two pictures put them in spoken order.

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
  the video then holds the last fitting photo. Aim for 25-40 different fitting pictures in a long video (a new shot every 3 s, like the Shorts: give
  each text block 2-4 pictures, ideally several "photo" searches).
  This replaces the older "6-12 photos" and "optional img" wording in the task prompts: every text block
  needs its own "img" or "photo".
- **No chapter cards in the long video** (decided 1 Nov 2026): the heads are spoken in the flow and shown as a
  big key word; list keywords too. Key words stay on screen until the next one.
- **Long video rules from William (2 Nov 2026), always:** a photo never comes back until at least 8 other photos
  were shown (the renderer enforces it, so give enough pictures: 30+ for a 6-7 minute video, 2-4 per text block);
  the right picture with the right words; a car model on screen only when the words are about THAT model
  (Model 3 words -> Model 3 photo, never another model); key words only, 1-4 words, one line, in the centre,
  a fraction before the voice. Heads are shown as key words too: give every {"head": ...} block a
  `"pop": [{"say": "", "show": "WHY A LOTUS?"}]` with 1-4 words. The thumbnail stays the opening frame with the label.
- **Subtitles in the long video** (decided 5 Nov 2026, replaces the key words and key phrases): the whole spoken
  script, heads included, is shown as subtitles: at most 3 words at a time, bold capitals, white with a black edge,
  one word in yellow (a number, else a name, else the longest word), low in the picture (about 85% down),
  horizontally centred, the same size every time, a fraction before the voice. Small linking words (a, an, the,
  in, into, if, because, want, so, that, just) are left out for calm; everything else stays so the sense is kept.
  A new subtitle starts at every comma or full stop; a number stays with the word after it ("40 TONNE LOAD").
  "pop" lists in the script are no longer shown (FULL_KEYPHRASES=1 brings the old key phrases back).
- **Keep the Short's promise** (decided 1 Nov 2026): every Short ends with "for the full story go to
  TrendingTesla.com", so the article and the long video must really give the full story: clearly more than
  the Short (the background, the how and why, the numbers, the turns, what it means), never the same 60
  seconds again in longer words. Write the Short as the most gripping slice of the story; keep one or two
  strong details for the article and the long video. The Short's description always links to the article.
  The end card speaks that line itself: never put "for the full story...", "like and subscribe" or
  "TrendingTesla.com" in the Short's script (the renderer removes it from the last beat anyway, 5 Nov 2026).
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

## Story Shorts are published straight away (decided 3 Nov 2026): no private review any more; they go public on
upload and on to TikTok, Instagram and Facebook within ~15 minutes.

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
