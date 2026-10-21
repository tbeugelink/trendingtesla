#!/usr/bin/env python3
"""Static site generator for trendingtesla.com.

Reads articles from content/articles/*.json and writes the complete site to public/.
English lives at the site root, Dutch under /nl/. Every article automatically gets an
original cover image per language (see covers.py), used on the site and for social sharing.

Article JSON format:
{
  "slug": "tesla-q3-2026-earnings-preview",      # URL part, same for both languages
  "date": "2026-10-21",                            # publication date (YYYY-MM-DD, Europe/Amsterdam)
  "time": "07:00",                                 # publication time (HH:MM, Europe/Amsterdam); optional
  "category": "earnings",                          # key from CATEGORIES below
  "sources": [{"title": "...", "url": "https://..."}],
  "en": {"title": "...", "description": "...", "body": "<p>...</p>"},
  "nl": {"title": "...", "description": "...", "body": "<p>...</p>"}
}

Run: python3 build.py   (needs Pillow: pip install --break-system-packages pillow)
"""
import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from covers import make_cover

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content" / "articles"
OUT = ROOT / "public"
SITE = "https://trendingtesla.com"
NAME = "TrendingTesla"
TZ = ZoneInfo("Europe/Amsterdam")

LANGS = {
    "en": {
        "prefix": "",
        "locale": "en_US",
        "tagline": "Tesla news, explained. Every day.",
        "latest": "Latest news",
        "top": "Top story",
        "related": "Read next",
        "sources": "Sources",
        "about": "About",
        "privacy": "Privacy",
        "home": "Home",
        "switch": "NL",
        "switch_full": "Nederlands",
        "empty": "No articles in this category yet. New stories are published several times a day.",
        "cat_intro": "All TrendingTesla articles about {}.",
        "notfound": "Page not found",
        "notfound_text": "This page does not exist (anymore).",
        "back": "Back to the homepage",
        "min": "min read",
        "disclaimer": "TrendingTesla is an independent news site and is not affiliated with Tesla, Inc. Nothing on this site is financial advice.",
        "months": ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"],
    },
    "nl": {
        "prefix": "/nl",
        "locale": "nl_NL",
        "tagline": "Tesla-nieuws, helder uitgelegd. Elke dag.",
        "latest": "Laatste nieuws",
        "top": "Hoofdverhaal",
        "related": "Lees ook",
        "sources": "Bronnen",
        "about": "Over ons",
        "privacy": "Privacy",
        "home": "Home",
        "switch": "EN",
        "switch_full": "English",
        "empty": "Nog geen artikelen in deze categorie. Er verschijnen meerdere keren per dag nieuwe verhalen.",
        "cat_intro": "Alle artikelen van TrendingTesla over {}.",
        "notfound": "Pagina niet gevonden",
        "notfound_text": "Deze pagina bestaat niet (meer).",
        "back": "Terug naar de homepagina",
        "min": "min lezen",
        "disclaimer": "TrendingTesla is een onafhankelijke nieuwssite en is niet verbonden aan Tesla, Inc. Niets op deze site is financieel advies.",
        "months": ["januari", "februari", "maart", "april", "mei", "juni", "juli",
                   "augustus", "september", "oktober", "november", "december"],
    },
}

# key: labels, colour, shown in the main menu
CATEGORIES = {
    "news":     {"en": "News",           "nl": "Nieuws",            "color": "#e31937", "menu": True},
    "robotaxi": {"en": "Robotaxi",       "nl": "Robotaxi",          "color": "#f59e0b", "menu": True},
    "fsd":      {"en": "FSD",            "nl": "FSD",               "color": "#3b82f6", "menu": True},
    "models":   {"en": "Models",         "nl": "Modellen",          "color": "#a855f7", "menu": True},
    "earnings": {"en": "Earnings",       "nl": "Cijfers",           "color": "#10b981", "menu": True},
    "energy":   {"en": "Energy",         "nl": "Energie",           "color": "#eab308", "menu": True},
    "optimus":  {"en": "Optimus",        "nl": "Optimus",           "color": "#06b6d4", "menu": True},
    "software": {"en": "Software",       "nl": "Software",          "color": "#6366f1", "menu": False},
    "charging": {"en": "Charging",       "nl": "Laden",             "color": "#22c55e", "menu": False},
    "guides":   {"en": "Guides",         "nl": "Gidsen",            "color": "#ec4899", "menu": False},
}

PAGES = {
    "about": {
        "en": ("About TrendingTesla",
               "What TrendingTesla is and how we write.",
               "<p>TrendingTesla follows everything that moves at Tesla: vehicles, software, "
               "self-driving, robotaxi, Optimus, energy and the company's results.</p>"
               "<p>Several times a day we pick the stories that matter most and explain them in "
               "plain language: what happened, why it matters and what to watch next. We write "
               "our own articles and always link to the sources we used, so you can check them.</p>"
               "<p>Articles are researched and written with the help of AI and published "
               "under editorial supervision. Spotted a mistake? We correct it as soon as we "
               "know about it.</p>"
               "<p>TrendingTesla is an independent site. We are not affiliated with, "
               "sponsored by or endorsed by Tesla, Inc. Nothing on this site is financial "
               "advice.</p>"),
        "nl": ("Over TrendingTesla",
               "Wat TrendingTesla is en hoe we schrijven.",
               "<p>TrendingTesla volgt alles wat er bij Tesla in beweging is: auto's, software, "
               "zelfrijden, robotaxi, Optimus, energie en de bedrijfscijfers.</p>"
               "<p>Meerdere keren per dag kiezen we de belangrijkste verhalen en leggen we ze "
               "helder uit: wat er gebeurde, waarom het ertoe doet en waar je op moet letten. We "
               "schrijven onze eigen artikelen en linken altijd naar de bronnen die we gebruikten, "
               "zodat je ze kunt controleren.</p>"
               "<p>Artikelen worden met hulp van AI onderzocht en geschreven en onder "
               "redactioneel toezicht gepubliceerd. Een fout gezien? We verbeteren hem zodra "
               "we ervan weten.</p>"
               "<p>TrendingTesla is een onafhankelijke site. We zijn niet verbonden aan, "
               "gesponsord door of goedgekeurd door Tesla, Inc. Niets op deze site is "
               "financieel advies.</p>"),
    },
    "privacy": {
        "en": ("Privacy policy",
               "How TrendingTesla handles your data.",
               "<p>TrendingTesla does not ask you to create an account and does not collect "
               "personal data through forms.</p>"
               "<p>The site is served through Cloudflare, which processes technical data such "
               "as IP addresses to deliver and protect the site. We do not use tracking "
               "cookies at this moment.</p>"
               "<p>If we add advertising or analytics in the future, this page will be updated "
               "first and you will be asked for consent where the law requires it.</p>"),
        "nl": ("Privacybeleid",
               "Hoe TrendingTesla met je gegevens omgaat.",
               "<p>TrendingTesla vraagt je niet om een account aan te maken en verzamelt geen "
               "persoonsgegevens via formulieren.</p>"
               "<p>De site wordt geleverd via Cloudflare, dat technische gegevens zoals "
               "IP-adressen verwerkt om de site te leveren en te beveiligen. We gebruiken op "
               "dit moment geen trackingcookies.</p>"
               "<p>Als we in de toekomst advertenties of statistieken toevoegen, passen we "
               "deze pagina eerst aan en vragen we waar de wet dat vereist om toestemming.</p>"),
    },
}

CSS = """
:root{--bg:#0b0d10;--surface:#14171c;--surface2:#1b1f26;--border:#262b33;--fg:#eef0f2;--muted:#9aa1a9;--accent:#e31937;--link:#ff5a6e;--max:1180px}
@media (prefers-color-scheme: light){:root{--bg:#ffffff;--surface:#f4f5f7;--surface2:#eceef1;--border:#e2e5e9;--fg:#111418;--muted:#5d6570;--accent:#d0102e;--link:#b00d26}}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--fg);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--link)}
img{display:block;max-width:100%;height:auto}
.wrap{max-width:var(--max);margin:0 auto;padding:0 16px}
.narrow{max-width:740px;margin:0 auto}
/* header */
.top{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
.bar{display:flex;align-items:center;justify-content:space-between;gap:16px;height:60px}
.logo{font-weight:850;font-size:1.4rem;letter-spacing:-.03em;color:var(--fg);text-decoration:none;white-space:nowrap}
.logo span{color:var(--accent)}
.lang{font-size:.8rem;font-weight:700;letter-spacing:.05em;color:var(--muted);text-decoration:none;border:1px solid var(--border);border-radius:999px;padding:4px 10px}
.lang:hover{color:var(--fg);border-color:var(--fg)}
.menu{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;padding-bottom:10px;margin-top:-4px}
.menu::-webkit-scrollbar{display:none}
.menu a{flex:none;font-size:.88rem;font-weight:600;color:var(--muted);text-decoration:none;padding:6px 12px;border-radius:999px}
.menu a:hover{color:var(--fg);background:var(--surface)}
.menu a.on{color:var(--fg);background:var(--surface2)}
/* labels */
.tag{display:inline-block;font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;text-decoration:none;color:var(--c,var(--accent))}
.meta{font-size:.82rem;color:var(--muted)}
.section{display:flex;align-items:center;gap:12px;font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:44px 0 18px}
.section::after{content:"";flex:1;height:1px;background:var(--border)}
/* featured */
.feature{display:grid;grid-template-columns:1.35fr 1fr;gap:28px;align-items:center;margin-top:28px;text-decoration:none;color:var(--fg)}
.feature img,.card img{border-radius:14px;aspect-ratio:1200/630;object-fit:cover;width:100%;background:var(--surface)}
.feature h2{font-size:clamp(1.6rem,3.2vw,2.5rem);line-height:1.15;letter-spacing:-.025em;margin:10px 0 12px}
.feature p{color:var(--muted);font-size:1.05rem;margin-bottom:12px}
.feature:hover h2,.card:hover h3{color:var(--link)}
/* grid */
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:28px 24px}
.card{text-decoration:none;color:var(--fg);display:flex;flex-direction:column}
.card .body{padding-top:12px}
.card h3{font-size:1.12rem;line-height:1.3;letter-spacing:-.01em;margin:6px 0 6px}
.card p{color:var(--muted);font-size:.93rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.empty{color:var(--muted);background:var(--surface);border:1px dashed var(--border);border-radius:14px;padding:28px;text-align:center}
/* category head */
.cathead{padding:36px 0 4px;border-bottom:3px solid var(--c);margin-bottom:8px}
.cathead h1{font-size:clamp(2rem,5vw,3rem);letter-spacing:-.03em;line-height:1.1}
.cathead p{color:var(--muted);margin:6px 0 18px}
/* article */
article{padding:36px 0 8px}
article h1{font-size:clamp(1.8rem,4.6vw,2.7rem);line-height:1.15;letter-spacing:-.03em;margin:10px 0 14px}
article .lead{font-size:1.2rem;line-height:1.55;color:var(--muted);margin:0 0 22px}
article .hero{border-radius:16px;margin:22px 0 28px;aspect-ratio:1200/630;width:100%;object-fit:cover}
.prose h2{font-size:1.4rem;line-height:1.3;letter-spacing:-.015em;margin:34px 0 10px}
.prose p,.prose ul,.prose ol{margin-bottom:18px}
.prose ul,.prose ol{padding-left:22px}
.prose li{margin-bottom:8px}
.prose li::marker{color:var(--accent)}
.prose em{color:var(--muted)}
.sources{background:var(--surface);border-radius:14px;margin-top:34px;padding:18px 22px;font-size:.9rem}
.sources h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:0 0 8px}
.sources ul{padding-left:18px}
.sources li{margin-bottom:4px}
/* footer */
footer{border-top:1px solid var(--border);margin-top:64px;padding:32px 0 48px;font-size:.86rem;color:var(--muted)}
footer .cols{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap}
footer a{color:var(--muted);text-decoration:none}
footer a:hover{color:var(--fg)}
footer .links{display:flex;gap:18px;flex-wrap:wrap}
footer p{max-width:560px;margin-top:10px}
@media (max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}.feature{grid-template-columns:1fr;gap:16px}}
@media (max-width:600px){.grid{grid-template-columns:1fr}body{font-size:16.5px}.section{margin-top:34px}}
"""


def esc(s):
    return html.escape(s, quote=True)


def fmt_date(d, lang):
    dt = datetime.strptime(d, "%Y-%m-%d")
    m = LANGS[lang]["months"][dt.month - 1]
    return f"{m} {dt.day}, {dt.year}" if lang == "en" else f"{dt.day} {m} {dt.year}"


def published(a):
    """Timezone-aware publication datetime (defaults to 08:00 local)."""
    return datetime.strptime(f"{a['date']} {a.get('time', '08:00')}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


def url(lang, path=""):
    """Absolute path for a page in a language. path like '' or 'slug/' or 'about/'."""
    return f"{LANGS[lang]['prefix']}/{path}"


def other(lang):
    return "nl" if lang == "en" else "en"


def cover(a, lang):
    return f"/img/{a['slug']}-{lang}.jpg"


def read_time(a, lang):
    words = len(html.unescape(a[lang]["body"]).split())
    return max(1, round(words / 220))


def cat_style(key):
    return f'style="--c:{CATEGORIES[key]["color"]}"'


def page(lang, path, title, description, body, og_type="website", extra_head="", image=None, active=None):
    L = LANGS[lang]
    alt = other(lang)
    full_title = f"{title} | {NAME}" if title != NAME else f"{NAME} — {L['tagline']}"
    canonical = SITE + url(lang, path)
    img = SITE + (image or "/img/default.jpg")
    menu = "".join(
        f'<a href="{url(lang, "category/" + k + "/")}"{" class=\"on\"" if k == active else ""}>{c[lang]}</a>'
        for k, c in CATEGORIES.items() if c["menu"]
    )
    cats_footer = " · ".join(f'<a href="{url(lang, "category/" + k + "/")}">{c[lang]}</a>' for k, c in CATEGORIES.items())
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="en" href="{SITE + url('en', path)}">
<link rel="alternate" hreflang="nl" href="{SITE + url('nl', path)}">
<link rel="alternate" hreflang="x-default" href="{SITE + url('en', path)}">
<link rel="alternate" type="application/rss+xml" title="{NAME}" href="{url(lang, 'feed.xml')}">
<meta property="og:site_name" content="{NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{L['locale']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{img}">
<meta name="theme-color" content="#0b0d10">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>{CSS}</style>
{extra_head}
</head>
<body>
<header class="top"><div class="wrap">
<div class="bar"><a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a>
<a class="lang" href="{url(alt, path)}" hreflang="{alt}" lang="{alt}" title="{L['switch_full']}">{L['switch']}</a></div>
<nav class="menu" aria-label="Categories">{menu}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap"><div class="cols">
<div><a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a><p>{L['tagline']} {L['disclaimer']}</p></div>
<div><div class="links"><a href="{url(lang, 'about/')}">{L['about']}</a><a href="{url(lang, 'privacy/')}">{L['privacy']}</a><a href="{url(lang, 'feed.xml')}">RSS</a><a href="{url(alt, path)}">{L['switch_full']}</a></div>
<p>{cats_footer}</p><p>&copy; {datetime.now().year} {NAME}</p></div>
</div></div></footer>
</body>
</html>
"""


def card(a, lang, eager=False):
    t = a[lang]
    c = CATEGORIES[a["category"]]
    loading = "eager" if eager else "lazy"
    return (f'<a class="card" href="{url(lang, a["slug"] + "/")}">'
            f'<img src="{cover(a, lang)}" alt="" width="1200" height="630" loading="{loading}" decoding="async">'
            f'<div class="body"><span class="tag" {cat_style(a["category"])}>{c[lang]}</span> '
            f'<span class="meta">· {fmt_date(a["date"], lang)}</span>'
            f'<h3>{esc(t["title"])}</h3><p>{esc(t["description"])}</p></div></a>')


def grid(items, lang):
    return f'<div class="grid">{"".join(card(a, lang) for a in items)}</div>'


def load_articles():
    arts = []
    for f in sorted(CONTENT.glob("*.json")):
        a = json.loads(f.read_text(encoding="utf-8"))
        for key in ("slug", "date", "category", "en", "nl"):
            if key not in a:
                raise SystemExit(f"{f.name}: missing '{key}'")
        if a["category"] not in CATEGORIES:
            raise SystemExit(f"{f.name}: unknown category '{a['category']}'")
        arts.append(a)
    arts.sort(key=published, reverse=True)
    slugs = [a["slug"] for a in arts]
    if len(slugs) != len(set(slugs)):
        raise SystemExit("duplicate slugs found")
    return arts


def write(path, text):
    p = OUT / path.lstrip("/")
    if path.endswith("/"):
        p = p / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def related(a, arts, n=3):
    same = [x for x in arts if x is not a and x["category"] == a["category"]]
    rest = [x for x in arts if x is not a and x["category"] != a["category"]]
    return (same + rest)[:n]


def build():
    arts = load_articles()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    # Cover images
    for a in arts:
        for lang in LANGS:
            c = CATEGORIES[a["category"]]
            make_cover(OUT / cover(a, lang).lstrip("/"), a[lang]["title"], c[lang], a["category"],
                       c["color"], fmt_date(a["date"], lang))
    for lang in LANGS:
        make_cover(OUT / "img" / f"default-{lang}.jpg", LANGS[lang]["tagline"], CATEGORIES["news"][lang],
                   "news", CATEGORIES["news"]["color"], "trendingtesla.com")
    shutil.copy(OUT / "img" / "default-en.jpg", OUT / "img" / "default.jpg")

    for lang in LANGS:
        L = LANGS[lang]
        default_img = f"/img/default-{lang}.jpg"

        # Home
        if arts:
            top = arts[0]
            t = top[lang]
            c = CATEGORIES[top["category"]]
            feature = (f'<a class="feature" href="{url(lang, top["slug"] + "/")}">'
                       f'<img src="{cover(top, lang)}" alt="" width="1200" height="630" fetchpriority="high">'
                       f'<div><span class="tag" {cat_style(top["category"])}>{L["top"]} · {c[lang]}</span>'
                       f'<h2>{esc(t["title"])}</h2><p>{esc(t["description"])}</p>'
                       f'<span class="meta">{fmt_date(top["date"], lang)} · {read_time(top, lang)} {L["min"]}</span></div></a>')
            rest = arts[1:25]
            latest = f'<h2 class="section">{L["latest"]}</h2>{grid(rest, lang)}' if rest else ""
            body = f'<h1 style="position:absolute;left:-9999px">{NAME} — {L["tagline"]}</h1>{feature}{latest}'
        else:
            body = f'<p class="empty" style="margin-top:32px">{L["empty"]}</p>'
        write(url(lang), page(lang, "", NAME, L["tagline"], body, image=default_img))

        # Category pages
        for key, c in CATEGORIES.items():
            items = [a for a in arts if a["category"] == key]
            head = (f'<div class="cathead" {cat_style(key)}><span class="tag" {cat_style(key)}>{NAME}</span>'
                    f'<h1>{c[lang]}</h1><p>{L["cat_intro"].format(c[lang])}</p></div>')
            content = grid(items, lang) if items else f'<p class="empty">{L["empty"]}</p>'
            write(url(lang, f"category/{key}/"),
                  page(lang, f"category/{key}/", c[lang], L["cat_intro"].format(c[lang]),
                       head + '<div style="height:20px"></div>' + content, image=default_img, active=key))

        # Articles
        for a in arts:
            t = a[lang]
            c = CATEGORIES[a["category"]]
            src = ""
            if a.get("sources"):
                items = "".join(f'<li><a href="{esc(s["url"])}" rel="nofollow noopener" target="_blank">{esc(s["title"])}</a></li>'
                                for s in a["sources"])
                src = f'<div class="sources"><h2>{L["sources"]}</h2><ul>{items}</ul></div>'
            ld = {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": t["title"],
                "description": t["description"],
                "image": [SITE + cover(a, lang)],
                "datePublished": published(a).isoformat(),
                "dateModified": a.get("updated", published(a).isoformat()),
                "inLanguage": lang,
                "articleSection": c[lang],
                "mainEntityOfPage": SITE + url(lang, a["slug"] + "/"),
                "publisher": {"@type": "Organization", "name": NAME, "url": SITE,
                              "logo": {"@type": "ImageObject", "url": SITE + "/favicon.svg"}},
                "author": {"@type": "Organization", "name": NAME, "url": SITE},
            }
            head = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
            rel = related(a, arts)
            rel_html = f'<h2 class="section">{L["related"]}</h2>{grid(rel, lang)}' if rel else ""
            body = (f'<article class="narrow">'
                    f'<a class="tag" {cat_style(a["category"])} href="{url(lang, "category/" + a["category"] + "/")}">{c[lang]}</a>'
                    f'<h1>{esc(t["title"])}</h1>'
                    f'<p class="lead">{esc(t["description"])}</p>'
                    f'<p class="meta">{NAME} · {fmt_date(a["date"], lang)} · {read_time(a, lang)} {L["min"]}</p>'
                    f'<img class="hero" src="{cover(a, lang)}" alt="{esc(t["title"])}" width="1200" height="630" fetchpriority="high">'
                    f'<div class="prose">{t["body"]}</div>{src}</article>{rel_html}')
            write(url(lang, a["slug"] + "/"),
                  page(lang, a["slug"] + "/", t["title"], t["description"], body, "article", head,
                       image=cover(a, lang), active=a["category"]))

        # Static pages
        for key, p in PAGES.items():
            title, desc, content = p[lang]
            write(url(lang, key + "/"),
                  page(lang, key + "/", title, desc,
                       f'<article class="narrow"><h1>{esc(title)}</h1><div class="prose">{content}</div></article>',
                       image=default_img))

        # RSS
        items = "".join(
            f"<item><title>{esc(a[lang]['title'])}</title>"
            f"<link>{SITE + url(lang, a['slug'] + '/')}</link>"
            f"<guid>{SITE + url(lang, a['slug'] + '/')}</guid>"
            f"<pubDate>{published(a).astimezone(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
            f"<description>{esc(a[lang]['description'])}</description>"
            f'<enclosure url="{SITE + cover(a, lang)}" type="image/jpeg" length="0"/></item>'
            for a in arts[:30]
        )
        write(url(lang, "feed.xml"),
              f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
              f"<title>{NAME}</title><link>{SITE + url(lang)}</link>"
              f"<description>{esc(L['tagline'])}</description><language>{lang}</language>"
              f"{items}</channel></rss>")

    # 404
    L = LANGS["en"]
    write("/404.html", page("en", "", L["notfound"], L["notfound_text"],
          f'<article class="narrow"><h1>{L["notfound"]}</h1><p class="lead">{L["notfound_text"]}</p>'
          f'<p><a href="/">{L["back"]}</a> · <a href="/nl/">{LANGS["nl"]["back"]}</a></p></article>'))

    # Sitemap
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = [("", today)] + [(a["slug"] + "/", a.get("updated", a["date"])[:10]) for a in arts] \
        + [(f"category/{k}/", today) for k in CATEGORIES] + [(k + "/", today) for k in PAGES]
    urls = ""
    for path, mod in entries:
        for lang in LANGS:
            alts = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{SITE + url(l, path)}"/>' for l in LANGS)
            urls += f"<url><loc>{SITE + url(lang, path)}</loc><lastmod>{mod}</lastmod>{alts}</url>"
    write("/sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
          f"{urls}</urlset>")

    write("/robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    write("/favicon.svg",
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#e31937"/>'
          '<text x="32" y="45" font-family="system-ui,sans-serif" font-size="38" font-weight="800" fill="#fff" text-anchor="middle">T</text></svg>')

    print(f"Built {len(arts)} article(s) in {len(LANGS)} languages -> {OUT}")


if __name__ == "__main__":
    build()
