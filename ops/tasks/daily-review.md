# Daily review task (every morning) - analyse yesterday, steer today

Work unattended. Goal (William, 11 Nov 2026): the numbers lag behind; analyse the results every day and use them to
improve the next run. Be honest and exact: say what the numbers show, how sure that is, and what they do not show.

1. Read: ops/short-signals.md (per Short: views, stayed = engaged views / views, watched %, likes per 1,000, length),
   ops/stats/channel.jsonl and ops/stats/site.jsonl (last 14 days), ops/performance.md, ops/proven-topics.md,
   ops/scout-tesla.md, ops/hook-log.md (what each Short tried: hook type, test, proof), ops/short-reports/,
   ops/health.md, yesterday's ops/daily-review.md and ops/review-log.md. Run `python3 tools/health.py`.
   Watch-time numbers arrive 2-3 days late: judge a Short on views and likes in its first 24-48 hours, and on stayed /
   watched only once they are filled in.
2. Analyse:
   - Yesterday's Shorts and long video against our own typical numbers (median of the last 14 days) and against the
     goals: stayed over 70%, watched 90%+, views well above 1,000 in 48 hours.
   - What the best and the weakest Shorts of the last 14 days have in common: topic, proof source, hook type, hook
     wording, length, first picture, format version (overlay format since 9 Nov, smart loop since 9 Nov evening,
     quick cuts since 12 Nov). Use the `test` field in ops/hook-log.md to attribute a change to a result. With fewer
     than ~5 Shorts per variant it is an indication, not a conclusion: say so.
   - Whether the proven-topic rule is followed and whether proven topics really do better for us.
3. Write ops/daily-review.md (replace it), at most ~60 lines:
   `# Daily review <date>` / "## Numbers" (channel, yesterday's videos, last 7 days in one small table) /
   "## What works" and "## What does not" (each with the evidence) / "## Instructions for today" (at most 3 concrete,
   checkable instructions for the midday and evening tasks, e.g. a hook type to use, a length, a topic field from
   the proven list) / "## Test of the day" (the ONE variable to change today and how we will judge it) /
   "## Open problems". Append one dated line with the main conclusion to ops/review-log.md.
4. Commit and push (ops/daily-review.md, ops/review-log.md, ops/health.md) with
   `git -c user.name="tbeugelink" -c user.email="345708345+tbeugelink@users.noreply.github.com"`, message "Daily review <date>".
   Do not change code, workflows, tools, README.md or articles.
5. Finish with a short message for William in Dutch (max 8 lines, plain language): yesterday's numbers, the main
   finding, today's instructions and test, and any problem (start that line with "PROBLEEM:").
