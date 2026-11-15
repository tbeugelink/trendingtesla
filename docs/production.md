# Production reference

How the site and the videos are built. The publishing rules are in `README.md`. This file is the technical reference that used to be scattered through that document.

## Build and deploy

- Articles: `content/articles/YYYY-MM-DD-slug.json`. The fields the builder reads are documented at the top of `build.py`.
- `python3 build.py` writes the whole site to `public/`, including a cover per article and language (`covers.py`, Pillow).
- Push to `main`. Cloudflare deploys `public/` (`wrangler.jsonc`). Never edit `public/` by hand.
- Author in the page and in NewsArticle JSON-LD is the organization (`EDITORIAL_ORG` in `build.py`), never a person.

## Photos

Real, freely licensed photos come first.

1. `real_photos`: 0–3 entries. Wikimedia Commons files that are public domain, CC0 or CC BY (open the File page and check; not CC BY-SA, not NC, not ND), or photos published by a US federal agency (NTSB, NHTSA, NASA, FAA, DOT and similar; public domain). Never a news-agency, press, social-media or fire-department photo.
   - `{"page": "https://commons.wikimedia.org/wiki/File:...", "describe": "what is visible"}`
   - or `{"page": "<agency page>", "src": "<direct .jpg>", "credit": "NTSB", "describe": "..."}`
   - `tools/real_photos.py` (the video workflow) checks the licence again, downloads the file, puts it first in `images`, and adds the credit under the article and in the YouTube description.
2. `images`: 4–6 fitting photos from `PHOTOS.md`, not the same opening photos as the latest articles in that category.
3. `gen_image.extra`: 1–2 more scenes of the same subject, each `{"prompt", "describe"}`.

A picture of something the voice names starts when that thing is said. Describe library and real photos with the words the voice will use. In a beat with two pictures, put them in spoken order.

The first photo is the cover, the Short's opening frame and the long video's opening frame. One concrete subject, large and sharp, in the horizontal centre (the Short crops to the middle third). Keep the lower-left third calm for the label. `tools/gen_image.py` adds that thumbnail instruction to the main scene.

Checked detail photos live in `ops/library.json` and are referenced as `lib/<file>`. They are preferred when they show exactly what the beat says.

## Generated images

`gen_image`: `prompt`, `subject`, `refs`, `describe`, optional `profile` (`editorial`, `cinematic`, `technical`) and `category` (`A`, `B`, `C`). At least one reference is `{"src": "lib/<file>"}` or another photo whose rights allow a derivative (the checked library, or CC0 / public domain). References must be the same product and the same version.

New article photos are made by OpenAI, with Gemini as the check and the fallback. The monthly image budget is about $11 (25 images a day). Every image is logged in `ops/images-log.jsonl`. `IMAGE_PROVIDER=gemini` switches the maker. Skip `gen_image` for a story about one specific car model; its real photos are used. The scene is an illustration, never a fake photo of the news event.

The moving hook clip (`tools/video_clip.py`) is separate: about $0.41 per clip, capped at **$15 a month** (`CLIP_MONTH_CAP_USD`, log in `ops/clips-log.jsonl`). `STORY_CLIP=0` switches it off.

## Video pipeline

| Piece | Role |
|---|---|
| `.github/workflows/shorts.yml` | On a push that adds an article (or changes `video/queue.txt`): photos, the Short, the upload, and a long video only when the article has `video.en`. |
| `video/story.py` | The Short. Constants for the cut and the voice are at the top of the file: `XFADE`, `SHOT_MAX`, `SPEED`, `STORY_STABILITY`, `STORY_STYLE`, `USE_DEFAULT_SFX`. |
| `video/full.py` | The long video. `SCENE_MAX` and `SCENE_XFADE` set the shot length and the crossfade. `SPEED`, `FULL_STABILITY` and `FULL_STYLE` set the voice. It exits if the article has no `video` script for that language. |
| `video/upload.py` | Uploads to YouTube. Refuses a Short whose slug or title is already in `content/shorts.json`, `ops/story-pending.json` or `ops/short-uploads.json`, and records every new Short in `ops/short-uploads.json`. |
| `tools/video_watchdog.py` | Every 15 minutes (`shorts-page.yml`). Asks once for a missing Short or, when the article has `video.en`, a missing long video. It treats a slug in the upload ledger as already done, so a feed outage cannot order a second copy. |
| `video/short.py` | Shared layout, voice helper and metadata. The story Short and the long video both use it. The legacy portrait renderer is not the daily path. |

Only English videos are built (`langs=en`).

### Which articles get a video

The workflow diffs `github.event.before`..`HEAD` for that push (`fetch-depth: 0`), and keeps added files under `content/articles/` (`--diff-filter=A`). A push that contains the article plus later commits still sees the article. Files that were only modified are not built again, so the photo commit that follows an article does not upload a second Short.

- `short` present, and the slug is not already uploaded → Short (`video/story.py` when `short.story` is set).
- `video.en` present, and the slug is not already in `content/videos.json` → long video, after the Short.
- No `video` section → no long video.

`video/queue.txt` (first non-comment line: `slug [langs] [--full] [--upload]`) still requests one video on demand. The watchdog writes that file. `--full` is how it asks for a long video.

Shorts are uploaded public. `tools/story_approve.py` posts a story Short that has gone public to TikTok, Instagram and Facebook, and when it takes the slug off `ops/story-pending.json` it also writes the slug into `content/shorts.json`, so the watchdog still sees it while the YouTube feed is down.

### Voice and picture constants

These are estimates, kept as named constants so they can be changed in one place. The voice id is not one of them: the workflow sets `STORY_VOICE=1`, which uses `ELEVENLABS_VOICE_ID`.

| Constant | File | Value |
|---|---|---|
| `XFADE` | `video/story.py` | 0.15 s |
| `SHOT_MAX` | `video/story.py` | 2.0 s |
| `SPEED` | `video/story.py` | 1.07 for hook, tension and payoff |
| `STORY_STABILITY` | `video/story.py` | 0.45 (env `STORY_STABILITY` overrides) |
| `STORY_STYLE` | `video/story.py` | 0.3 (env `STORY_STYLE` overrides) |
| `USE_DEFAULT_SFX` | `video/story.py` | `False` (no default impact hit, bass drop or drone; a beat's own `sfx` still plays) |
| `SCENE_MAX` | `video/full.py` | 2.0 s |
| `SCENE_XFADE` | `video/full.py` | 0.15 s |
| `SPEED` | `video/full.py` | 1.07 |
| `FULL_STABILITY` / `FULL_STYLE` | `video/full.py` | 0.45 / 0.3 |

## YouTube text

- Short title: the hook, about 45 characters (`short.yt_title_*`).
- Long-video title: searchable words (`video.yt_title_*`).
- The description links to the article. The long video's description also has chapters from the headings (`full.py` `meta()`).
- No spoken call to action. The end card and the spoken slogan are off (`STORY_ENDCARD` and `FULL_OUTRO` are not set).

## Jobs that still run

These are not publishing tasks. They only write reports.

- `.github/workflows/yt-learn.yml` — channel and site stats (`ops/stats/`), `ops/performance.md`, `ops/short-signals.md`, `ops/scout-tesla.md`, `ops/proven-topics.md`. Proven topics are a hint, not a rule.
- `.github/workflows/shorts-page.yml` — YouTube feed into `content/shorts.json` and `content/videos.json`, social catch-up, the watchdog.
- `tools/health.py` — the chain check. Run it when something looks wrong. It expects one article a day around 18:00 Europe/Amsterdam, and a long video only when that article has a `video` script.

## Retired

`ops/tasks/daily-review.md` and `ops/tasks/monitor.md` are in `ops/tasks/archive/`. `ops/rework-brief.md` is in `ops/archive/`. They are not instructions. The morning look at yesterday's numbers, and the check after publication, are done by the owner outside this repo. Repairs that need a commit still follow the safety rules in `README.md`: no deletions, no unpublished rewrites, and code changes only as a pull request.
