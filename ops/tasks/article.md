# Article task (midday, evening, Saturday) - the full instruction

The scheduled task tells you which SLOT you are: `midday`, `evening` or `saturday`. Work fully unattended: nobody is
watching, do not ask questions, publish directly. Never skip the run. README.md holds the rules; where README.md and
this file differ, the sections at the top of README.md win (newest first).

| slot | what | long video | topic source |
|---|---|---|---|
| midday (~12:40) | a timeless EXPLAINER (how/why/what/which, a myth checked, a comparison) | YES: "video" script required | proven topic |
| evening (~21:10, Sun-Fri) | a true STORY (history, people, a turning point, a near failure, a bold bet) | no "video" key | proven topic |
| saturday (~21:10) | the weekly evergreen explainer, `"evergreen": true` | no "video" key | first unchecked topic in ops/evergreen-topics.md that also has proof |

Right after the push a GitHub Action turns the article into a YouTube Short (public at once, then TikTok, Instagram
and Facebook) and, for midday, a long video. The Short is where the growth comes from.

## 1. Read first
Clone is done by the task prompt. Read completely: README.md; **ops/daily-review.md** (this morning's analysis and the
instructions for today - follow them); **ops/proven-topics.md** and ops/scout-tesla.md (topics that already pull
viewers); ops/short-signals.md (our own numbers per Short); ops/hook-log.md (what earlier Shorts tried); the newest
files in ops/short-reports/ (what the renderer really did); ops/health.md if present; ops/library.json (William's
checked photos); ops/evergreen-topics.md; the docstring at the top of build.py (article format).

## 2. Choose a PROVEN topic (William, 11 Nov 2026: only topics whose popularity is already proven)
- List the titles of the last ~40 articles in content/articles/ so you never repeat a topic (a clearly new angle is fine).
- Pick from, in this order: (a) ops/proven-topics.md: a Short of the last 30 days with 100K+ views, or a small channel
  that broke out; (b) an outlier in ops/scout-tesla.md; (c) a topic or angle of our own best Shorts
  (ops/short-signals.md: most views AND most watched). A real news event of the last 48 hours may win only when it is
  clearly bigger (several large outlets, and Tesla/SpaceX fans are visibly talking about it).
- Take the TOPIC and the kind of ANGLE, never the script, the title or the pictures. Make it better and more accurate.
- Write down the proof in `short.proof`: `{"source": "<title> - <url>", "views": 471000, "why": "one line: why this
  topic fits our viewers and what our angle adds"}`. No proof, no topic.
- Topics: Tesla's cars, FSD/Robotaxi/Cybercab, Optimus, energy, charging, software, factories; SpaceX, Starlink, The
  Boring Company, xAI/Grok when there is a clear link (categories "spacex", "starlink", "xai", "boring"; never
  "ecosystem"); "musk" strictly factual and balanced, at most one Musk-series episode per week.
- Research properly: WebSearch + WebFetch the key pages, prefer primary and reputable sources, verify every number,
  date and quote against a source you fetched. What Musk says will happen is a statement, not a fact.

## 3. Self-learning before writing
From ops/daily-review.md, ops/short-signals.md, ops/hook-log.md and the previous render report: name what was weak in
the previous Short of your slot and decide the ONE thing you change now (`short.learning.test`). Change one variable
at a time, otherwise the morning review cannot tell what worked.

## 4. Write the article (English leads; natural, fluent Dutch, not word for word; Dutch number formats)
- Title: specific and timeless (no "today", "this week"); explainers phrased the way people search. Description 1-2 sentences.
- Body: simple HTML (<p>, <h2>, <ul>/<li>, <strong>, <em>), 600-900 words (Saturday 700-1,000). An intro that opens
  with the strongest claim or moment and ends with a clear problem as a plain statement (never a question); then 4-6
  <h2> headings phrased as the question that problem raises (one or two start with "So"); each section starts with
  the direct answer in bold and ends with the next problem as a plain statement. Never a question right before a heading.
- Your own words only; at most one short quote per source; no invented facts, quotes, scenes or numbers.
- Stock/earnings topics end with: <p><em>This article is for information only and is not financial advice.</em></p>
  (Dutch: <p><em>Dit artikel is alleen bedoeld als informatie en is geen financieel advies.</em></p>).
- "sources": the 2-4 sources really used (title prefixed with the outlet, and URL). "category" from CATEGORIES in
  build.py; "models" from MODELS when mainly about specific vehicles.
- "images": 3 photo files (at least 2) from PHOTOS.md or "lib/<file>" from ops/library.json that really show the subject.
- "gen_image" (skip only when mainly about one car model): {"prompt", "subject", "refs": [at least one {"src":
  "lib/<file>"} of exactly the same product], "profile": "editorial|cinematic|technical", "category": "A|B|C",
  "describe", "extra": [two more scenes]}. Left-hand drive, right side of the road. Illustrations only, never a fake
  documentary photo of a real event or a real person.
- "label": two lines in two colours (types "a", "c" or "n"; one-block "r" only for real bad news): the hook claim.
- "date"/"time": now in Europe/Amsterdam (`TZ=Europe/Amsterdam date`). File: content/articles/YYYY-MM-DD-slug.json.

## 5. Write the Short ("short") - README "SHORT FORMAT v4" (+ v3.1, v3) and "PROVEN TACTICS" are binding
- 20-30 seconds is the target (15-35 allowed): 55-80 spoken words.
- `story`: 6-10 beats. Every beat: `"part"` (ONLY "hook", "tension" or "payoff"; nothing else, the last beat is
  "payoff"), `"t"` ("0-2s", "2-6s", ...), `"text"` (the voice, 7-11 words, 2.5-4 s), `"overlay"` (the exact sentence
  on screen, at most 36 characters, numbers as digits), two pictures (`"lib"` with 2 files, or "img"/"photo"), `"visual"`.
- Beat 1 = the hook: the first spoken words ARE the sharpest claim or the most surprising number (max ~8 words). No
  date, no scene setting, no announcement. Its first picture is the most dramatic picture of the story.
- The last beat is NOT the hook again: a different line that runs on smoothly into the hook when the Short restarts.
- Also required: `yt_title_en`, `yt_title_nl` (max 45 characters, the hook's contrast or number), `hooks` (3 variants
  {"text", "type"}), `hook_pick` {"index", "why"}, `loop` {"last", "how"}, `signals`, `learning` {"prev",
  "prev_stats", "weakest_hook", "why_stalled", "change", "test"}, `proof` (see 2), `en`, `nl` (spoken text as one paragraph).
- Never "like and subscribe", "full story" or "TrendingTesla.com" in the script.

## 6. Midday only: write the long video ("video")
{"en": [...], "nl": [...], "yt_title_en", "yt_title_nl"}: at most 6-8 minutes (900-1,300 words), the article's
headings. The very first sentence is the hook claim itself; the first 15-20 s promise what the viewer will know at the
end and open a loop that is paid off late; a new number, question, turn or comparison at least every 20-30 s; every
text block has its own fitting "img" and/or "photo" (2-4 pictures per block); the last block is a payoff that links
back to the opening (no call to action). Short sentences, no brackets, no URLs, numbers as digits.
"yt_title_*": the words people search for (subject plainly + the question or answer, 6-12 words).

## 7. CHECK before you commit (required - a slip here once cost a day)
`python3 tools/check_article.py content/articles/<your file>.json` must report **0 errors**. Fix every ERROR and as
many warnings as you can, then run it again. Never commit with errors.

## 8. Log, build, publish
- Add the entry at the top of ops/hook-log.md: date, slug, the proof, the 3 hooks and the pick, what was weak in the
  previous Short, the one change (test) now, how the loop line connects.
- If you used a topic from ops/evergreen-topics.md, tick it with "(<slug>)"; add 1-3 new ideas you came across.
- `python3 build.py` must succeed (if Pillow is missing: pip install --break-system-packages pillow); check that
  public/<slug>/index.html and public/nl/<slug>/index.html exist.
- `git add -A`, commit with `git -c user.name="tbeugelink" -c user.email="345708345+tbeugelink@users.noreply.github.com"`
  (never any other email address: the repository is public), message "Article: <english title>". The new article file
  must be in this one commit (the video workflow looks at the last commit). `git pull --rebase origin main` (if
  public/ conflicts: rerun build.py, git add -A, continue), then `git push origin main`.
- After ~2 minutes check the Cloudflare build: `gh api repos/tbeugelink/trendingtesla/commits/$(git rev-parse HEAD)/check-runs
  --jq '.check_runs[] | .name+" "+.status+" "+(.conclusion//"")'`; no run or failed: push an empty commit "Trigger
  deploy" (same name and email) and check again. With curl (not WebFetch) verify that
  https://trendingtesla.com/<slug>/ shows the new title and https://trendingtesla.com/nl/<slug>/ returns 200.
- Then check that the video run really STARTED: `gh run list -R tbeugelink/trendingtesla -w shorts.yml -L 3`. If the
  run for your commit is still "queued" after 5 minutes, say so clearly in your summary (the monitor task repairs it).
- Do not change build.py, covers.py, static/, the workflows, the tools or other articles.

## 9. Summary for William (Dutch, short)
Title; the proof for the topic (source + views); the 3 hooks, the pick and why; the script with timing and the exact
overlay per beat; the last line and how it runs on into the opening; visual cues in one line; which signals it serves;
the self-learning note (what was weak, the one change now, text rules applied, whether all beats stay within 2.5-4 s);
the result of check_article.py; midday: the long video's YouTube title; any problem.
