# Monitor task (twice a day, after each publication) - find problems, repair what is safe, tell William

William's rule (11 Nov 2026): no more lost days. A Short that crashed, a video run GitHub never started and social
posts that failed for 11 days all went unnoticed. You are the check that this never happens again. Work unattended.

1. Run `python3 tools/health.py` in the repo (it writes ops/health.md and prints the report). Read every PROBLEM and
   every note. Also look yourself: `gh run list -R tbeugelink/trendingtesla -L 15` (failed or long-queued runs) and,
   for a failed run, `gh run view <id> -R tbeugelink/trendingtesla --log-failed | tail -40` to find the real cause.
2. Repair ONLY in these safe ways, each at most once per video (ops/video-retries.json shows what the watchdog tried):
   - Short or long video missing and no video run is in progress: write the first line of video/queue.txt as
     `<slug> en --upload` (Short) or `<slug> en --full --upload` (long video) plus a line `# monitor <UTC time>`,
     commit ("Monitor: make missing video") and push; one video per push; wait for the run and check the result.
     Before that, make sure the script passes `python3 tools/check_article.py <article file>`; if the script itself
     is wrong (for example a part that is not hook/tension/payoff, a missing overlay), fix ONLY that field in the
     article JSON, run build.py, commit and push, then queue the video.
   - Short not posted to TikTok/Instagram/Facebook: add `{"slug": "<slug>", "after": "<now, UTC ISO>"}` to
     ops/social-queue.json (commit, push); the hourly workflow posts it.
   - Never upload a video that already exists on YouTube, never delete anything, never change code, workflows or
     tools, never cancel runs. Commit with `git -c user.name="tbeugelink" -c user.email="345708345+tbeugelink@users.noreply.github.com"`.
3. Quality check of today's Short and video (the notes in the report): script rule breaks, beats outside 2.5-4 s,
   overlays that were split, a loop that repeats the hook. Write these as one line each in ops/health.md under
   "## Quality notes for the next run" (the morning review and the article tasks read it), commit and push ops/health.md.
4. Finish with a message for William in Dutch, plain language, no jargon:
   - Nothing wrong: exactly one line, e.g. "Alles in orde: <titel> - Short, video en TikTok/Instagram/Facebook staan online."
   - Something wrong: start with "PROBLEEM:" and say per problem what happened, what you repaired, whether it is solved
     now, and what William must do himself (only if needed). Never write that something is solved without having
     checked it (YouTube link opens, the run succeeded).
