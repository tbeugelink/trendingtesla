#!/usr/bin/env python3
"""Refresh Amazon and AliExpress prices, the ECB dollar rate, and Amazon galleries.

Prices that cannot be read are left out, so the site hides them instead of
keeping a stale figure. Amazon photos stay hotlinked from m.media-amazon.com.
A gallery that cannot be read keeps the previous list.

Run from the repo root: python3 tools/refresh-product-prices.py
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Europe/Amsterdam")
GIFT = "41qAawoik5L"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
US40 = re.compile(r"m\.media-amazon\.com/images/I/([A-Za-z0-9+\-]{6,})\._AC_US40_\.jpg")
MAIN = re.compile(r"m\.media-amazon\.com/images/I/([A-Za-z0-9+\-]{6,})\._AC_SX(?:679|425)_\.jpg")
BUY = re.compile(
    r'"desktop_buybox_group_1":\[\{"displayPrice":"[^"]*","priceAmount":([0-9]+(?:\.[0-9]+)?)'
)


def now_stamp():
    return datetime.now(TZ).isoformat(timespec="seconds")


def fetch(url, timeout=40, cookie=""):
    headers = {"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.5"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.status, res.read()


def fetch_text(url, timeout=40, cookie=""):
    try:
        status, body = fetch(url, timeout=timeout, cookie=cookie)
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""
    if status != 200:
        return status, ""
    return status, body.decode("utf-8", "replace")


def amazon_page(asin):
    direct = f"https://www.amazon.nl/dp/{asin}"
    status, text = fetch_text(direct, timeout=25)
    if status == 200 and len(text) > 20000 and "priceAmount" in text:
        return text
    for attempt in range(3):
        status, text = fetch_text(f"https://r.jina.ai/{direct}", timeout=50)
        if status == 200 and ("priceAmount" in text or "media-amazon.com/images/I/" in text):
            return text
        time.sleep(1.5 * (attempt + 1))
    return ""


def gallery_urls(text, fallback):
    ids = []
    for match in US40.finditer(text or ""):
        image_id = match.group(1)
        if image_id == GIFT or image_id in ids:
            continue
        ids.append(image_id)
        if len(ids) == 5:
            break
    if not ids:
        for match in MAIN.finditer(text or ""):
            image_id = match.group(1)
            if image_id != GIFT:
                ids.append(image_id)
                break
    urls = [f"https://m.media-amazon.com/images/I/{image_id}._AC_SX679_.jpg" for image_id in ids]
    if urls:
        return urls
    if isinstance(fallback, list) and fallback:
        return [str(item) for item in fallback if str(item).startswith("https://m.media-amazon.com/images/I/")]
    if isinstance(fallback, str) and fallback.startswith("https://m.media-amazon.com/images/I/"):
        return [fallback]
    return []


def euro_price(text):
    if not text or "captcha" in text.lower() and "priceAmount" not in text:
        return None
    match = BUY.search(text)
    if not match:
        return None
    value = float(match.group(1))
    if 1 <= value <= 5000:
        return round(value, 2)
    return None


def image_ok(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            kind = res.headers.get("content-type", "")
            length = int(res.headers.get("content-length") or 0)
            return res.status == 200 and kind.startswith("image/") and length > 2000
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def keep_live(urls):
    live = [url for url in urls if image_ok(url)]
    return live or urls


ALI_COOKIE = "aep_usuc_f=site=nld&c_tp=EUR&region=NL&b_locale=nl_NL"
ALI_IMG = re.compile(r"https://ae-pic-a1\.aliexpress-media\.com/kf/([A-Za-z0-9]+)\.(jpg|png)")


def ali_page(item):
    """Item HTML. A euro price is kept only when the page itself is priced in euros."""
    direct = f"https://nl.aliexpress.com/item/{item}.html"
    status, text = fetch_text(direct, timeout=25, cookie=ALI_COOKIE)
    if status == 200 and "imagePathList" in text and "punish" not in text:
        return text
    for attempt in range(3):
        headers_url = f"https://r.jina.ai/{direct}"
        try:
            req = urllib.request.Request(headers_url, headers={
                "User-Agent": UA,
                "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
                "X-Return-Format": "html",
                "X-No-Cache": "true",
                "Cookie": ALI_COOKIE,
            })
            with urllib.request.urlopen(req, timeout=70) as res:
                text = res.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError):
            text = ""
        if "imagePathList" in text or "ae-pic-a1.aliexpress-media.com/kf/" in text:
            if "Captcha" not in text[:400] and "slide to verify" not in text.lower():
                return text
        time.sleep(2 * (attempt + 1))
    return ""


def ali_euro(text):
    if not text or "punish" in text or "slide to verify" in text.lower():
        return None
    patterns = [
        r'"priceCurrency":"EUR","price":"([0-9]+(?:\.[0-9]+)?)"',
        r'"price":"([0-9]+(?:\.[0-9]+)?)","priceCurrency":"EUR"',
        r'"minActivityAmount"\s*:\s*\{\s*"value"\s*:\s*([0-9]+(?:\.[0-9]+)?)[^}]*"currency"\s*:\s*"EUR"',
        r'"currency"\s*:\s*"EUR"[^}]{0,80}"value"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = float(match.group(1))
        if 0.5 <= value <= 5000:
            return round(value, 2)
    return None


def ali_gallery(text):
    urls = []
    match = re.search(r'"imagePathList":(\[[^\]]+\])', text or "")
    if match:
        try:
            raw = json.loads(match.group(1))
        except ValueError:
            raw = []
        for src in raw:
            src = str(src or "").split("?")[0]
            if src.startswith("https://ae-pic-a1.aliexpress-media.com/kf/") and src.endswith((".jpg", ".png")) and src not in urls:
                urls.append(src)
    if not urls:
        for image_id, ext in ALI_IMG.findall(text or ""):
            src = f"https://ae-pic-a1.aliexpress-media.com/kf/{image_id}.{ext}"
            if src not in urls:
                urls.append(src)
            if len(urls) == 6:
                break
    return urls[:6]


def ecb_rate():
    status, text = fetch_text("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=25)
    if status != 200:
        return None
    day = re.search(r"<Cube time='(\d{4}-\d{2}-\d{2})'>", text)
    usd = re.search(r"currency='USD' rate='([0-9.]+)'", text)
    if not day or not usd:
        return None
    rate = float(usd.group(1))
    if not (0.5 <= rate <= 2.5):
        return None
    return {"usd_per_eur": rate, "date": day.group(1), "fetched": now_stamp()}


def _count(raw):
    digits = re.sub(r"[^\d]", "", str(raw or ""))
    return int(digits) if digits else 0


def amazon_rating(text, asin):
    if not text or not asin:
        return None
    score = count = None
    paired = re.search(
        rf"([0-9]\.[0-9]) out of 5 stars.{{0,80}}\(([0-9][0-9,]*)\).{{0,120}}(?:/dp/|product-reviews/){asin}",
        text, re.I)
    if paired:
        score = float(paired.group(1))
        count = _count(paired.group(2))
    if score is None or not 1 <= score <= 5:
        return None
    return {"score": round(score, 1), "count": count or 0}


def ali_rating(text):
    if not text or "punish" in text or "slide to verify" in text.lower():
        return None
    score = count = None
    star = re.search(r'"averageStar(?:Rate)?"\s*:\s*"?([0-9.]+)"?', text)
    reviews = re.search(r'"(?:totalValidNum|reviewCount)"\s*:\s*"?([0-9]+)"?', text)
    if star:
        score = float(star.group(1))
    if reviews:
        count = int(reviews.group(1))
    if score is None:
        marked = re.search(r"\*\*([0-9]\.[0-9])\*\*.{0,60}([0-9][0-9,]*)\s+Reviews", text, re.I)
        if marked:
            score = float(marked.group(1))
            count = _count(marked.group(2))
    if score is None or not 1 <= score <= 5:
        return None
    return {"score": round(score, 1), "count": count or 0}


def one_amazon(asin, fallback):
    text = amazon_page(asin)
    price = euro_price(text)
    urls = keep_live(gallery_urls(text, fallback))
    return asin, price, urls, amazon_rating(text, asin)


def main():
    images_path = ROOT / "content" / "amazon-images.json"
    prices_path = ROOT / "content" / "product-prices.json"
    ali_path = ROOT / "content" / "ali-images.json"
    licences_path = ROOT / "content" / "image-licences.json"
    try:
        previous = json.loads(prices_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    previous_prices = previous.get("prices") if isinstance(previous, dict) else {}
    if not isinstance(previous_prices, dict):
        previous_prices = {}
    previous_ratings = previous.get("ratings") if isinstance(previous, dict) else {}
    if not isinstance(previous_ratings, dict):
        previous_ratings = {}
    try:
        previous_ali = json.loads(ali_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous_ali = {}
    previous_galleries = previous_ali.get("images") if isinstance(previous_ali, dict) else {}
    if not isinstance(previous_galleries, dict):
        previous_galleries = {}
    images = json.loads(images_path.read_text(encoding="utf-8"))
    current = images.get("images") if isinstance(images, dict) else {}
    if not isinstance(current, dict):
        current = {}
    licences = json.loads(licences_path.read_text(encoding="utf-8"))
    ali_items = []
    for row in licences.get("aliexpress_promo") or []:
        item = str(row.get("item") or "").strip()
        if item.isdigit() and item not in ali_items:
            ali_items.append(item)
    for folder, pattern in (("guides", r"(?:^item:\s*|ali-)(\d{10,})"), ("articles", r'"ali_item"\s*:\s*"(\d{10,})"')):
        directory = ROOT / "content" / folder
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            for item in re.findall(pattern, text, re.M):
                if item not in ali_items:
                    ali_items.append(item)

    stamp = now_stamp()
    rate = ecb_rate()
    prices = {}
    ratings = {}
    galleries = {}
    asins = [key for key in current if re.fullmatch(r"[A-Z0-9]{10}", str(key).upper())]

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(one_amazon, asin.upper(), current.get(asin)) for asin in asins]
        for future in as_completed(futures):
            asin, price, urls, rating = future.result()
            if urls:
                galleries[asin] = urls
            elif isinstance(current.get(asin), list):
                galleries[asin] = current[asin]
            elif isinstance(current.get(asin), str):
                galleries[asin] = [current[asin]]
            if price is not None:
                prices[asin] = {"eur": price, "fetched": stamp, "source": "amazon.nl"}
            if rating:
                ratings[asin] = {**rating, "fetched": stamp, "source": "amazon.nl"}
            elif isinstance(previous_ratings.get(asin), dict):
                ratings[asin] = previous_ratings[asin]
            print(f"{asin} price={price} photos={len(galleries.get(asin) or [])} rating={rating}", flush=True)

    ali_galleries = {}
    for item in ali_items:
        text = ali_page(item)
        price = ali_euro(text)
        photos = ali_gallery(text)
        rating = ali_rating(text)
        key = f"ali:{item}"
        previous_row = previous_galleries.get(item)
        kept_local = isinstance(previous_row, list) and previous_row and all(
            str(src).startswith("/img/guides/") for src in previous_row)
        if kept_local:
            ali_galleries[item] = previous_row
        elif photos:
            ali_galleries[item] = photos
        elif isinstance(previous_row, list):
            ali_galleries[item] = previous_row
        if price is not None:
            prices[key] = {"eur": price, "fetched": stamp, "source": "aliexpress", "fresh_days": 1}
        elif isinstance(previous_prices.get(key), dict):
            prices[key] = previous_prices[key]
        if rating:
            ratings[key] = {**rating, "fetched": stamp, "source": "aliexpress"}
        elif isinstance(previous_ratings.get(key), dict):
            ratings[key] = previous_ratings[key]
        print(f"ali:{item} price={price or 'kept' if key in prices else None} photos={len(ali_galleries.get(item) or [])} rating={rating}", flush=True)

    images_path.write_text(
        json.dumps({"fetched": stamp[:10], "images": galleries}, indent=2) + "\n",
        encoding="utf-8",
    )
    ali_path.write_text(
        json.dumps({"fetched": stamp, "images": ali_galleries}, indent=2) + "\n",
        encoding="utf-8",
    )
    payload = {"fetched": stamp, "rate": rate or previous.get("rate") or {}, "prices": prices, "ratings": ratings}
    prices_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    multi = sum(1 for urls in galleries.values() if len(urls) > 1)
    print(f"prices {len(prices)} galleries {len(galleries)} with more than one photo {multi} rate {rate}", flush=True)


def refresh_ratings():
    """Fill ratings only. A missed page keeps the rating already stored."""
    prices_path = ROOT / "content" / "product-prices.json"
    images_path = ROOT / "content" / "amazon-images.json"
    data = json.loads(prices_path.read_text(encoding="utf-8"))
    images = json.loads(images_path.read_text(encoding="utf-8")).get("images") or {}
    ratings = data.get("ratings") if isinstance(data.get("ratings"), dict) else {}
    stamp = now_stamp()
    asins = [key for key in images if re.fullmatch(r"[A-Z0-9]{10}", str(key).upper())]

    def one(asin):
        text = amazon_page(asin)
        return asin, amazon_rating(text, asin)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed(pool.submit(one, asin.upper()) for asin in asins):
            asin, rating = future.result()
            if rating:
                ratings[asin] = {**rating, "fetched": stamp, "source": "amazon.nl"}
            print(f"{asin} rating={rating}", flush=True)
    data["ratings"] = ratings
    prices_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"ratings {sum(1 for key in ratings if not str(key).startswith('ali:'))}", flush=True)


if __name__ == "__main__":
    if "--ratings" in sys.argv:
        refresh_ratings()
    else:
        main()
