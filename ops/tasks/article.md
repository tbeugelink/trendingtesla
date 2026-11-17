# Article task — one article and one Short a day

Work unattended. Publish directly. Do not ask for approval. The spec is `README.md`. Where this file and `README.md` differ, `README.md` wins. Photo and pipeline detail is in `docs/production.md`. The builder's JSON fields are at the top of `build.py`.

| when | article | Short | long video |
|---|---|---|---|
| every day, publish around 21:00 Europe/Amsterdam | one article from the fact sheet you were given | yes | no |
| Saturday | the weekly evergreen guide, `"evergreen": true`, about 1,200–1,800 words | yes | yes: a `video` script |

There is no midday slot and no evening slot. Do not write a second article the same day.

## 1. Input

You are given a fact sheet: the topic, the angle, the hook to consider, and every core fact with two source URLs. Write only from that sheet. Do not search for a different topic and do not add facts that are not on the sheet.

Read, as far as you need them: `README.md`; the fact sheet; the docstring at the top of `build.py`; `docs/production.md`; `PHOTOS.md`; `ops/library.json` (checked detail photos). `ops/performance.md` is a hint for the angle, not a list of topics you must copy.

List the titles of the last ~40 articles in `content/articles/` and do not repeat one of those topics.

## 2. Topic

The fact sheet has already chosen the topic. It should be either a surprising company-history story or practical news for an owner (cost, risk, or a feature they need to know). Do not copy a viral topic. If the sheet is a saturated mega-story, use only the angle on the sheet. Skip the sheet and say so in the report only when it repeats one of the last ~40 articles or a core fact has fewer than two sources.

### What to pick for a Short

Prefer a story with a visual moment or a twist. An approval, a vote or a policy item is not the default daily pick. When the sheet is one of those anyway, the Short title is still a single claim, in the shape of `FSD Just Reached Its 10th EU Country`, never the news lede.

## 3. Facts

- Every number, date, name and quote you use is on the fact sheet, with two independent sources.
- Do not invent a number, a scene or a quote. Do not go and find a new fact to fill a gap. Leave the gap out.
- What Musk says will happen is written as a statement ("Musk says…"), not as a fact.
- Uncertain → "according to …" or omit.

## 4. Write the article

English leads. Dutch is natural and fluent, not word for word, with Dutch number formats.

- Title: specific, still readable in a year. No "today" or "this week". Description: 1–2 sentences.
- Body: simple HTML (`<p>`, `<h2>`, `<ul>/<li>`, `<strong>`, `<em>`). Weekdays and Sunday: about 600–900 words. Saturday: about 1,200–1,800 words.
- The intro opens on the strongest claim and ends on a problem stated as a plain sentence, never a question. Then 4–6 `<h2>` headings (Saturday may need a few more) phrased as the question that problem raises. One or two may start with "So". Each section starts with the direct answer in bold and ends on the next problem as a statement. Never a question immediately before a heading.
- `sources`: the sources you actually used (outlet prefixed to the title, and the URL). Two to four is normal.
- `category` from `CATEGORIES` in `build.py`. `models` from `MODELS` when the piece is mainly about specific vehicles.
- Stock or earnings pieces end with `<p><em>This article is for information only and is not financial advice.</em></p>` and, in Dutch, `<p><em>Dit artikel is alleen bedoeld als informatie en is geen financieel advies.</em></p>`.
- `images`: 4–6 photos from `PHOTOS.md` or `lib/<file>` from `ops/library.json` that really show the subject. Different from the photos the latest articles in the same category open with.
- `real_photos` when a freely licensed photo of the subject exists. Rules are in `docs/production.md`. Public domain, CC0 or CC BY only.
- `gen_image` (skip when the piece is mainly about one car model): `prompt`, `subject`, `refs` (at least one `{"src": "lib/<file>"}` of the same product), `profile` (`editorial`, `cinematic` or `technical`), `category` (`A`, `B` or `C`), `describe`, and `extra` (one or two more scenes). Left-hand drive, right side of the road. Illustrations only.
- `label`: two lines in two colours (`a`, `c` or `n`). Type `r` only for real bad news. The label carries the hook.
- `date` and `time`: the real moment of publication in Europe/Amsterdam, set in the last step before the commit (`TZ=Europe/Amsterdam date`). Never backdate. File name: `content/articles/YYYY-MM-DD-slug.json`.
- The author is the organization. Do not add a byline name.

## 5. Write the Short (`short`)

- About 25–35 seconds, roughly 65–90 spoken words.
- `story`: 6–10 beats. Every beat has `part` (only `hook`, `tension` or `payoff`; the last beat is `payoff`), `t` (`0-2s`, `2-5s`, …), `text` (the voice), `overlay` (the same words, at most ~36 characters, numbers as digits), at least one picture (`lib`, `img` or `photo`), and `visual` (one line on what is seen).
- Beat 1 is the hook: the sharpest claim or the most surprising number, at most ~8 words. No date, no scene setting, no announcement. Its first picture is the most dramatic picture of the story and shows the claim.
- The last beat is not the hook again. It is a different line that runs on into the hook when the Short restarts.
- Optional `hook_motion`: one line on what moves in the hook picture. The first ~4 seconds can become a clip from that picture, inside the $15 monthly cap. Pick a first picture where something can really move. The clip falls back to the still if it distorts anything.
- A beat may set `sfx` to a natural sound of what is on screen (a roar, a hiss, a click). Do not describe a cinematic impact, a boom or a drone. Those defaults are off.
- `yt_title_en` and `yt_title_nl` are the YouTube title, one claim in each language. At most 8 words and at most 50 characters, counted before ` #Shorts` (the upload adds that tag; do not put it in the field). Never the article lede. Never a clause joined by a comma or by "but" / "maar". A comma or period inside a number is allowed (`1,020`, `1.020`). Never a title cut off with an ellipsis (`…` or `...`). The builder does not shorten a title. Use one of these shapes, and still stay inside the limits: `X did Y` (a subject and a strong past-tense verb, as in `SpaceX Tried to Catch $6M With a Net`); a number against a number (`30 Engines Failed. SpaceX Uses 33.`); `Why X [surprising thing]`; or a surprising fact with a concrete number (`Starship's First Flight Lasted 4 Minutes`, `Tesla's Next Wiper Might Be a Laser`). At most one word in capitals. That word is optional and has no proven gain. The claim must be true and backed by the fact sheet. Do not promise a twist the video does not pay off.
- Required besides the titles: `hooks` (exactly 3 variants, `{"text", "type"}`), `hook_pick` (`index`, `why`), `loop` (`last`, `how`), `en` and `nl` (the spoken text as one paragraph).
- Optional, and fine to omit: `proof`, `learning`, `signals`. Do not chase a "proven topic".
- Never "like and subscribe", "full story" or the site name in the script.

## 6. Saturday only: the long video (`video`)

On Saturday, and only then, add:

`{"en": [...], "nl": [...], "yt_title_en", "yt_title_nl"}`

About 1,100–1,400 spoken words (about 8–10 minutes), following the article's headings. The first sentence is the hook claim. The first 15–20 seconds say what the viewer will know at the end. A new number, turn or comparison at least every 20–30 seconds. Every text block has its own `img` and/or `photo` (2–4 pictures). The last block pays off the opening. No call to action. Short sentences, no brackets, no URLs, numbers as digits.

`yt_title_*`: a search title, not the Short rules. One clear claim or question that contains the main search phrase, at most 70 characters. No ellipsis and no truncation. `Why SpaceX Called Off the Starship Booster Catch on Flight 15` fits. No ` #Shorts`. A missing title is not filled from the article headline.

On every other day, omit the `video` key. The pipeline builds a long video only when that key has an English script.

## 7. Check

`python3 tools/check_article.py content/articles/<file>.json` must report **0 errors**. Fix every error, then run it again. Do not commit with errors. Fix warnings when the fix is real. A missing `proof`, `learning` or `signals` is a warning, not an error. A Short title over 8 words, over 50 characters, with an ellipsis, with a comma that separates clauses, or with "but" / "maar" is an error. A comma inside a number is not. A long-video title over 70 characters or with an ellipsis is an error.

## 8. Build and publish

- If the fact sheet used an idea from `ops/evergreen-topics.md`, tick it with the slug. You may add 1–3 new ideas you actually used.
- `python3 build.py` must succeed. If Pillow is missing: `pip install --break-system-packages pillow`. Confirm `public/<slug>/index.html` and `public/nl/<slug>/index.html` exist.
- Set `date` and `time` to now in Europe/Amsterdam, then commit. The identity is the repository account:

```bash
git add -A
git -c user.name="tbeugelink" -c user.email="345708345+tbeugelink@users.noreply.github.com" commit -m "Article: <english title>"
git pull --rebase origin main
git push origin main
```

  If `public/` conflicts on rebase, run `build.py` again, add, and continue. Do not use any other commit email. The commit message is the English title only, with no person's name.
- The new article file must be in the push. The video workflow diffs that whole push, so other commits in the same push do not hide the article.
- With curl, confirm `https://trendingtesla.com/<slug>/` shows the new title and `https://trendingtesla.com/nl/<slug>/` returns 200. Give the deploy a couple of minutes first.
- Do not change `build.py`, `covers.py`, `static/`, the workflows, the tools, this file, or other articles. Do not delete or redate anything.

## 9. Report

A short note back, in Dutch: the title; the hook you used and why; the last line and how it runs on into the opening; the `check_article.py` result; on Saturday, the long video's YouTube title; any problem, starting that line with `PROBLEEM:`.
