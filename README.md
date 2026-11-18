# trendingtesla.com

Static bilingual site (English at `/`, Dutch at `/nl/`). Articles are JSON in `content/articles/`. `python3 build.py` writes `public/`. A push to `main` deploys `public/` through Cloudflare. Do not edit `public/` by hand.

This file is the publishing spec. Photo licences, image budgets and the video pipeline are in `docs/production.md`. The article JSON fields the builder reads are at the top of `build.py`.

Authorship is the organization: the TrendingTesla editorial team (`Redactie TrendingTesla` in Dutch). Never a person's name, in the article, the byline, JSON-LD, a commit message, or a comment.

## Cadence

One article and one Short every day, published around **21:00 Europe/Amsterdam**. On Saturday the article is the weekly evergreen guide and it also gets one long video. No other day gets a long video. A second article on the same day is not part of this cadence.

Everything publishes automatically. There is no approval step after the draft is written.

## What gets written

The writing task is `ops/tasks/article.md`. It does not choose the topic. It writes from a fact sheet it is given.

- **Weekdays and Sunday:** an article (about 600–900 words) and a Short. No `video` key.
- **Saturday:** the evergreen guide (about 1,200–1,800 words), a Short, and a `video` script for one long video of about 8–10 minutes.

Topics are surprising company-history stories and practical news for owners (what it costs, what can go wrong, a feature worth knowing). Prefer a story with a visual moment or a twist. An approval, a vote or a policy item is not the default daily pick; when one is published, its YouTube title is still a single claim (the shape of `FSD Just Reached Its 10th EU Country`), not the news lede. Do not copy a viral topic that larger channels already cover with real footage, unless the fact sheet has an angle nobody else has. One in three topics may be an experiment. Do not repeat a topic from the last ~40 articles.

## Facts

Every core fact (number, date, name, quote) is on the fact sheet with at least two independent sources, preferably one of them primary. Nothing that is not on the fact sheet goes into the article or the script. Do not invent numbers, scenes or quotes. What someone says will happen is a statement, not a fact ("Musk says…"). If a fact is uncertain, attribute it or leave it out.

A correction to a published article is a real edit: set `updated` and add a short update paragraph. Do not silently rewrite history.

## Dates

`date` and `time` are the actual publication moment in Europe/Amsterdam (`TZ=Europe/Amsterdam date`), set immediately before the commit. Never backdate. `updated` is set only when the article body really changes. Attaching a video, rebuilding the site, or any other non-edit must not change `updated`, `dateModified`, or that article's sitemap `lastmod`.

Older articles whose `date` is earlier than their first commit are listed in `ops/date-audit.md`. What to delete and what to redate is proposed in `ops/backdated-proposal.md`. That proposal is not applied until the owner acts on it.

## The article

English leads. Dutch is natural and fluent, not a word-for-word translation, with Dutch number formats.

- Title: specific, and still readable in a year. No "today" or "this week". Description: one or two sentences.
- Body: simple HTML (`<p>`, `<h2>`, `<ul>/<li>`, `<strong>`, `<em>`). The intro opens on the strongest claim and ends on the next problem as a plain statement, never a question. Then four to six `<h2>` headings phrased as the question that problem raises. One or two headings may start with "So". Each section starts with the direct answer in bold and ends on the next problem as a statement.
- `sources`: the sources actually used, title prefixed with the outlet, plus the URL.
- `category` from `CATEGORIES` in `build.py`. `models` from `MODELS` when the piece is about specific vehicles.
- Stock and earnings pieces end with the information-only disclaimer (the Dutch line is in `ops/tasks/article.md`).
- `label`: two lines, two colours (types `a`, `c` or `n`). The one-block type `r` is only for real bad news.
- `gen_image` and real photos: see `docs/production.md`. Illustrations are never a fake documentary photo of a real event or a real person.

## The Short

One Short per article, in English. The script lives in `short`.

- About 25–35 seconds (roughly 65–90 spoken words; the checker allows 38–92).
- `story`: 6–10 beats. Each beat has `part` (`hook`, `tension` or `payoff` only; the last beat is `payoff`), `t`, `text` (the voice), `overlay` (the exact on-screen sentence, about 36 characters, the spoken words rather than a summary), and at least one picture (`lib`, `img` or `photo`).
- The hook is the first spoken words: one claim or one hard number, within about two seconds (at most ~8 words). No date and no scene-setting as the opening. The first picture shows what the hook claims.
- The last line is not a copy of the hook. It is a different line that runs on into the hook when the Short restarts. Record that in `loop` (`last`, `how`).
- On-screen text is the spoken words, at most two lines. Numbers and years are shown as digits (the renderer paints them yellow). No logo in the first two seconds.
- Title (`yt_title_en`, `yt_title_nl`): one claim, at most 8 words and 50 characters, measured before ` #Shorts`. The upload adds ` #Shorts`. Never the article lede, never a clause joined by a comma or by "but" / "maar", and never a title cut off with an ellipsis. A comma or period inside a number is allowed (`1,020`, `1.020`). Shapes that fit: `X did Y` (subject plus a strong past-tense verb), a number against a number (`30 Engines Failed. SpaceX Uses 33.`), `Why X [surprising thing]`, or a surprising fact with a concrete number. At most one word in capitals; that word is optional and has no proven gain. The claim must be true on the fact sheet, and the video has to pay it off.
- Also required: `hooks` (exactly three variants), `hook_pick`, `en` and `nl` (the spoken text as one paragraph).
- Optional, and not an error if absent: `proof`, `learning`, `signals`.
- No spoken or on-screen call to action, and no site name, in the script. The description carries the link to the article.
- The first ~4 seconds may be a moving clip made from the hook photo (`tools/video_clip.py`). Budget: **$15 a month**. `STORY_CLIP=0` switches it off. The clip is an illustration, never fake footage of a real event. `short.hook_motion` can say what should move.

Pictures change quickly: a crossfade of about 0.15 seconds and no shot longer than about 2 seconds (`XFADE` and `SHOT_MAX` in `video/story.py`). The voice settings are the constants in that file (`STORY_STABILITY`, `STORY_STYLE`, `SPEED`). Generic impact hits and the ambient drone are off. A beat may still name its own natural `sfx`.

## The Saturday long video

Only an article with a `video` section gets a long video. The workflow does not build one otherwise. Put `video` on the Saturday guide only.

`video` is `{"en": [...], "nl": [...], "yt_title_en", "yt_title_nl"}`. The first sentence is the hook claim. Aim for about 1,100–1,400 spoken words (about 8–10 minutes). A new fact, turn or comparison at least every 20–30 seconds. Every text block has its own picture. Chapters come from the headings. The description leads with the link to the article. The end is a payoff, not a call to action. The YouTube title is a search title, not the Short rules: one clear claim or question that contains the main search phrase, at most 70 characters, with no ellipsis and no truncation. `Why SpaceX Called Off the Starship Booster Catch on Flight 15` fits. No ` #Shorts`. A missing title is not filled from the article headline.

Shot length for the long video is `SCENE_MAX` in `video/full.py` (about 2 seconds). The crossfade is `SCENE_XFADE` in the same file.

## Checks

Before the commit:

```bash
python3 tools/check_article.py content/articles/<file>.json
python3 build.py
```

`check_article.py` must report **0 errors**. Warnings should be fixed when the fix is real. Errors include a missing Short, a bad beat, a missing or overlong overlay, a hook that is too long or opens on a date, a repeated hook, a call to action, and a missing title or `loop`. A Short title over 8 words, over 50 characters, with an ellipsis, with a comma that separates clauses, or with "but" / "maar" is an error. A comma inside a number is allowed. A long-video title over 70 characters or with an ellipsis is an error. Missing `proof`, `learning` or `signals` is a warning. Then confirm `public/<slug>/index.html` and `public/nl/<slug>/index.html` exist.

`tools/health.py` checks the chain after publication (article, Short, long video only when the article has one, social posts, the live page). It is not a separate publishing task.

## Publishing

One commit, then push to `main`. The article file is part of that push. The video workflow diffs the whole push (`github.event.before` .. `HEAD`), not only the last commit, and builds:

- a Short for every newly added article that has `short` and does not already have one;
- a long video only when the new article has `video.en`, and only if that long video is not already uploaded.

Story Shorts go public on upload. They are not held for review. A second Short for an article that already has one is not uploaded.

Commit as the repository account, not under a person's name:

```bash
git -c user.name="tbeugelink" -c user.email="345708345+tbeugelink@users.noreply.github.com" commit -m "Article: <english title>"
```

Set `date` and `time` immediately before that commit. Do not commit secrets. Changes to `build.py`, `video/`, the workflows, this file or `ops/tasks/` go through a pull request. The writing task does not change those files, and it does not delete or redate published articles.

## Briefings, promises and guides

- `content/briefings/*.md` is one weekly briefing. A file whose name starts with `_` is not published. `content/briefings/_template.md` is the layout sample and is left out of the build.
- `content/data/promises.json` fills `/promises/` and `/nl/beloftes/`. Rows in `rows` are shown. `_example` is not.
- `content/guides/*.md` is a buying guide. A file whose name starts with `_` is not published.
- `ADS_ENABLED` in `build.py` is false. Ad slots are omitted until it is true, so they take no space. The AdSense script stays deferred. `public/ads.txt` is written from the publisher id already in `content/monetization.json`.

## Safety

- No person's name anywhere in the repo.
- No invented facts, quotes or scenes. Two sources on the fact sheet for every core fact.
- No call to action in a script. No "like and subscribe", no "full story", no site name in the spoken words.
- Illustrations are not evidence. Real photos only when the licence allows commercial reuse (public domain, CC0 or CC BY — not NC, ND or BY-SA). No clips from other YouTube channels.
- The moving hook stays inside the $15 monthly cap.
- Accidents, lawsuits and injury recalls are still published on this cadence when the fact sheet meets the two-source rule. They are not a reason to invent detail.
- Do not publish a second article the same day, and do not spend money beyond the hook-clip budget, without the owner asking for it.
