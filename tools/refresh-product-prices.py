#!/usr/bin/env python3
"""Refresh Amazon and AliExpress prices, the ECB dollar rate, and Amazon galleries.

Prices that cannot be read are left out, so the site hides them instead of
keeping a stale figure. Amazon photos stay hotlinked from m.media-amazon.com.
A gallery that cannot be read keeps the previous list.

Run from the repo root: python3 tools/refresh-product-prices.py
"""

import json
import re
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


def ali_price(item):
    cookie = "aep_usuc_f=site=nld&c_tp=EUR&region=NL&b_locale=nl_NL"
    pages = [
        f"https://nl.aliexpress.com/item/{item}.html",
        f"https://www.aliexpress.com/item/{item}.html",
    ]
    for url in pages:
        status, text = fetch_text(url, timeout=25, cookie=cookie)
        price = ali_euro(text) if status == 200 else None
        if price:
            return price
        status, text = fetch_text(f"https://r.jina.ai/{url}", timeout=40)
        price = ali_euro(text) if status == 200 else None
        if price:
            return price
    return None


def ali_euro(text):
    if not text or "punish" in text or "slide to verify" in text.lower():
        return None
    patterns = [
        r'"minActivityAmount"\s*:\s*\{\s*"value"\s*:\s*([0-9]+(?:\.[0-9]+)?)[^}]*"currency"\s*:\s*"EUR"',
        r'"currency"\s*:\s*"EUR"[^}]{0,80}"value"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        r'"formatedActivityPrice"\s*:\s*"€\s*([0-9]+(?:[.,][0-9]{2})?)"',
        r'"formattedPrice"\s*:\s*"€\s*([0-9]+(?:[.,][0-9]{2})?)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = float(match.group(1).replace(",", "."))
        if 0.5 <= value <= 5000:
            return round(value, 2)
    return None


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


def one_amazon(asin, fallback):
    text = amazon_page(asin)
    price = euro_price(text)
    urls = keep_live(gallery_urls(text, fallback))
    return asin, price, urls


def main():
    images_path = ROOT / "content" / "amazon-images.json"
    prices_path = ROOT / "content" / "product-prices.json"
    licences_path = ROOT / "content" / "image-licences.json"
    images = json.loads(images_path.read_text(encoding="utf-8"))
    current = images.get("images") if isinstance(images, dict) else {}
    if not isinstance(current, dict):
        current = {}
    licences = json.loads(licences_path.read_text(encoding="utf-8"))
    ali_items = []
    for row in licences.get("aliexpress_promo") or []:
        item = str(row.get("item") or "").strip()
        if item.isdigit():
            ali_items.append(item)

    stamp = now_stamp()
    rate = ecb_rate()
    prices = {}
    galleries = {}
    asins = [key for key in current if re.fullmatch(r"[A-Z0-9]{10}", str(key).upper())]

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(one_amazon, asin.upper(), current.get(asin)) for asin in asins]
        for future in as_completed(futures):
            asin, price, urls = future.result()
            if urls:
                galleries[asin] = urls
            elif isinstance(current.get(asin), list):
                galleries[asin] = current[asin]
            elif isinstance(current.get(asin), str):
                galleries[asin] = [current[asin]]
            if price is not None:
                prices[asin] = {"eur": price, "fetched": stamp, "source": "amazon.nl"}
            print(f"{asin} price={price} photos={len(galleries.get(asin) or [])}", flush=True)

    for item in ali_items:
        price = ali_price(item)
        if price is not None:
            prices[f"ali:{item}"] = {"eur": price, "fetched": stamp, "source": "aliexpress"}
        print(f"ali:{item} price={price}", flush=True)

    images_path.write_text(
        json.dumps({"fetched": stamp[:10], "images": galleries}, indent=2) + "\n",
        encoding="utf-8",
    )
    payload = {"fetched": stamp, "rate": rate or {}, "prices": prices}
    prices_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    multi = sum(1 for urls in galleries.values() if len(urls) > 1)
    print(f"prices {len(prices)} galleries {len(galleries)} with more than one photo {multi} rate {rate}", flush=True)


if __name__ == "__main__":
    main()
