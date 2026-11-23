# Liveblog

Use this when a launch or an earnings release is still moving and the page should gain timestamped updates. It is not the daily article. Do not upload a Short from a liveblog.

## File

`content/articles/YYYY-MM-DD-slug.json`

Add these fields. Leave `short` and `video` out.

```json
{
  "type": "live",
  "live": true,
  "updates": [
    {
      "at": "2026-11-23T18:04:00+01:00",
      "en": "One sentence of what just happened.",
      "nl": "Eén zin over wat er net gebeurde.",
      "sources": [
        {"title": "Outlet, date", "url": "https://example.com/one"},
        {"title": "Second outlet, date", "url": "https://example.com/two"}
      ]
    }
  ]
}
```

- `live` true shows a red LIVE badge on cards. Set it to false when the event is over. The updates stay on the page.
- `at` is Europe/Amsterdam, with the offset. Newest update is shown first.
- Every update has English and Dutch text and two sources. Do not invent a number.
- The title still follows the title rules. The byline stays the TrendingTesla editorial team. Never a person's name.
- `python3 build.py` then commit the article file and `public/`. Do not send a newsletter from this task.
