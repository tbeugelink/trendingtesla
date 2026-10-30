#!/usr/bin/env bash
# Put each English Short on a GitHub release of this public repo (a stable public link for Buffer to fetch)
# and post it to TikTok through Buffer.   Usage: tools/tiktok_publish.sh video/out/<slug>-en-short.mp4 ...
# Needs GH_TOKEN (contents: write) and BUFFER_API_KEY. Never fails the workflow.
for f in "$@"; do
  [ -f "$f" ] || continue
  slug=$(basename "$f" | sed -E 's/-(en|nl)-short\.mp4$//')
  tag="tiktok-$(echo "$slug" | cut -c1-90)"
  cover="${f%.mp4}-cover.jpg"  # opening frame (photo + label) as the TikTok cover
  ffmpeg -loglevel error -y -ss 1 -i "$f" -frames:v 1 -q:v 2 "$cover" || cover=""
  if ! gh release view "$tag" >/dev/null 2>&1; then
    gh release create "$tag" "$f" $cover --title "TikTok: $slug" --notes "Video file for TikTok (via Buffer)." --latest=false \
      || { echo "::warning::release for $slug failed"; continue; }
  else
    gh release upload "$tag" "$f" $cover --clobber || { echo "::warning::upload for $slug failed"; continue; }
  fi
  url="https://github.com/${GITHUB_REPOSITORY}/releases/download/${tag}/$(basename "$f")"
  curl_cover=""
  [ -n "$cover" ] && curl_cover="https://github.com/${GITHUB_REPOSITORY}/releases/download/${tag}/$(basename "$cover")"
  python3 tools/tiktok_post.py "$f" "$url" $curl_cover
done
exit 0
