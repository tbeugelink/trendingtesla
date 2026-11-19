"""Set one YouTube video to private. Does not delete it.

Uses the same OAuth client as video/upload.py. Prints only the video id and privacyStatus.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

VIDEO_ID = (os.environ.get("VIDEO_ID") or (sys.argv[1] if len(sys.argv) > 1 else "")).strip()
if not VIDEO_ID:
    raise SystemExit("VIDEO_ID is missing")


def token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"].strip(),
        "client_secret": os.environ["YT_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["YT_REFRESH_TOKEN"].strip(),
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=60) as response:
        return json.load(response)["access_token"]


def call(url, method, access, body=None):
    req = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(), method=method,
        headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def main():
    access = token()
    call(
        "https://www.googleapis.com/youtube/v3/videos?part=status",
        "PUT",
        access,
        {"id": VIDEO_ID, "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}},
    )
    checked = call(
        f"https://www.googleapis.com/youtube/v3/videos?part=status,snippet&id={VIDEO_ID}",
        "GET",
        access,
    )
    items = checked.get("items") or []
    if not items:
        raise SystemExit(f"video {VIDEO_ID} was not returned after the update")
    status = items[0]["status"]["privacyStatus"]
    title = items[0].get("snippet", {}).get("title", "")
    print(json.dumps({"id": VIDEO_ID, "privacyStatus": status, "title": title}))
    if status != "private":
        raise SystemExit(f"privacyStatus is {status}")


if __name__ == "__main__":
    main()
