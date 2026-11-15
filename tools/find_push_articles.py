#!/usr/bin/env python3
"""Which new articles in a push should get a Short or a long video.

Used by .github/workflows/shorts.yml. The workflow file cannot embed this
script: a line at column 0 ends the YAML block and the run fails before it starts.

Usage (GitHub Actions sets GITHUB_EVENT_PATH and GITHUB_SHA):
  python3 tools/find_push_articles.py >> "$GITHUB_OUTPUT"

Prints:
  slugs=<new Shorts>
  longs=<new long videos, only articles with video.en>
  story=<those Shorts whose script is short.story>
  queue_in_push=1   when video/queue.txt changed in the same push

A Short already listed by slug or English title (content/shorts.json,
ops/story-pending.json, ops/short-uploads.json) is left out, so a second
upload is not requested. A long video whose slug is already in
content/videos.json is left out too.

The push base is github.event.before. When that is all zeros (a new ref) or
the old commit is not in this checkout (a force-push that dropped it), the
files come from the commits in the push event, not from the whole history
and not from HEAD~1 alone.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZERO = "0" * 40


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def is_commit(sha):
    if not sha or set(sha) <= {"0"}:
        return False
    return git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def event():
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def push_commits(ev):
    ids = []
    for item in ev.get("commits") or []:
        sha = item.get("id") if isinstance(item, dict) else item
        if sha:
            ids.append(sha)
    return ids


def names_from(args):
    result = git(*args)
    if result.returncode != 0:
        print(f"::warning::git {' '.join(args)} failed: {result.stderr.strip()[:200]}", file=sys.stderr)
        return []
    return [line for line in result.stdout.splitlines() if line]


def changed_in_commit(sha):
    """Files added or changed by one commit, including a root commit and a merge."""
    return names_from(
        ["diff-tree", "--root", "-m", "--no-commit-id", "--name-only", "-r", sha])


def added_in_commit(sha):
    return [p for p in names_from(
        ["diff-tree", "--root", "-m", "--diff-filter=A", "--no-commit-id", "--name-only", "-r", sha, "--", "content/articles"])
            if p.endswith(".json")]


def push_span(before, head, commits):
    """(added article paths, every path changed in the push)."""
    if is_commit(before) and is_commit(head):
        added = [p for p in names_from(
            ["diff", "--name-only", "--diff-filter=A", before, head, "--", "content/articles"]) if p.endswith(".json")]
        changed = names_from(["diff", "--name-only", before, head])
        return added, changed
    print("::warning::Push base is missing or not in this checkout; using the commits in the push", file=sys.stderr)
    shas = [sha for sha in commits if is_commit(sha)]
    if not shas and is_commit(head):
        shas = [head]
        print("::warning::No commit list on the push event; looking at the tip commit only", file=sys.stderr)
    added, changed = [], []
    for sha in shas:
        added.extend(added_in_commit(sha))
        changed.extend(changed_in_commit(sha))
    return list(dict.fromkeys(added)), list(dict.fromkeys(changed))


def known():
    sys.path.insert(0, str(ROOT / "video"))
    import upload  # noqa: E402
    return upload


def select(files):
    up = known()
    videos = up.load_json(ROOT / "content" / "videos.json", [])
    have_long = {row.get("slug") for row in videos if isinstance(row, dict) and row.get("slug")}
    slugs, longs, story = [], [], []
    for path in files:
        try:
            article = json.loads((ROOT / path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"::warning::skip {path}: {exc}", file=sys.stderr)
            continue
        slug = article.get("slug") or ""
        short = article.get("short") or {}
        if short:
            title = short.get("yt_title_en") or ""
            if up.local_duplicate(slug, title):
                print(f"::notice::skip Short for {slug}: already uploaded", file=sys.stderr)
            else:
                slugs.append(slug)
                if short.get("story"):
                    story.append(slug)
        video = article.get("video") or {}
        if video.get("en"):
            if slug in have_long:
                print(f"::notice::skip long video for {slug}: already uploaded", file=sys.stderr)
            else:
                longs.append(slug)
    return slugs, longs, story


def outputs(before, head, commits):
    added, changed = push_span(before, head, commits)
    slugs, longs, story = select(added)
    lines = [
        "slugs=" + " ".join(slugs),
        "longs=" + " ".join(longs),
        "story=" + " ".join(story),
    ]
    if "video/queue.txt" in changed:
        lines.append("queue_in_push=1")
    return lines


def main():
    ev = event()
    before = ev.get("before") or os.environ.get("GITHUB_EVENT_BEFORE") or ""
    head = os.environ.get("GITHUB_SHA") or ev.get("after") or "HEAD"
    for line in outputs(before, head, push_commits(ev)):
        print(line)


if __name__ == "__main__":
    main()
