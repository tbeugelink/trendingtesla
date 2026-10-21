#!/usr/bin/env python3
"""Static site generator for trendingtesla.com.

Reads articles from content/articles/*.json and writes the complete site to public/.
English lives at the site root, Dutch under /nl/.

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

Run: python3 build.py
"""
import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content" / "articles"
OUT = ROOT / "public"
SITE = "https://trendingtesla.com"
NAME = "TrendingTesla"

LANGS = {
    "en": {
        "prefix": "",
        "locale": "en_US",
        "tagline": "Tesla news, explained. Every day.",
        "latest": "Latest",
        "read": "Read article",
        "sources": "Sources",
        "about": "About",
        "privacy": "Privacy",
        "home": "Home",
        "switch": "Nederlands",
        "published": "Published",
        "empty": "The first articles are on their way.",
        "notfound": "Page not found",
        "notfound_text": "This page does not exist (anymore).",
        "back": "Back to the homepage",
        "disclaimer": "TrendingTesla is an independent news site and is not affiliated with Tesla, Inc.",
        "months": ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"],
    },
    "nl": {
        "prefix": "/nl",
        "locale": "nl_NL",
        "tagline": "Tesla-nieuws, helder uitgelegd. Elke dag.",
        "latest": "Nieuwste",
        "read": "Lees artikel",
        "sources": "Bronnen",
        "about": "Over ons",
        "privacy": "Privacy",
        "home": "Home",
        "switch": "English",
        "published": "Gepubliceerd",
        "empty": "De eerste artikelen komen eraan.",
        "notfound": "Pagina niet gevonden",
        "notfound_text": "Deze pagina bestaat niet (meer).",
        "back": "Terug naar de homepagina",
        "disclaimer": "TrendingTesla is een onafhankelijke nieuwssite en is niet verbonden aan Tesla, Inc.",
        "months": ["januari", "februari", "maart", "april", "mei", "juni", "juli",
                   "augustus", "september", "oktober", "november", "december"],
    },
}

CATEGORIES = {
    "news": {"en": "News", "nl": "Nieuws"},
    "earnings": {"en": "Earnings", "nl": "Cijfers"},
    "fsd": {"en": "FSD & Autonomy", "nl": "FSD & Zelfrijdend"},
    "robotaxi": {"en": "Robotaxi", "nl": "Robotaxi"},
    "optimus": {"en": "Optimus", "nl": "Optimus"},
    "models": {"en": "Models", "nl": "Modellen"},
    "energy": {"en": "Energy", "nl": "Energie"},
    "software": {"en": "Software", "nl": "Software"},
    "charging": {"en": "Charging", "nl": "Laden"},
    "guides": {"en": "Guides", "nl": "Gidsen"},
}

PAGES = {
    "about": {
        "en": ("About TrendingTesla",
               "What TrendingTesla is and how we write.",
               "<p>TrendingTesla follows everything that moves at Tesla: vehicles, software, "
               "self-driving, robotaxi, Optimus, energy and the company's results.</p>"
               "<p>Every day we pick the story that matters most and explain it in plain "
               "language: what happened, why it matters and what to watch next. We write our "
               "own articles and always link to the sources we used, so you can check them.</p>"
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
               "<p>Elke dag kiezen we het belangrijkste verhaal en leggen we het helder uit: "
               "wat er gebeurde, waarom het ertoe doet en waar je op moet letten. We schrijven "
               "onze eigen artikelen en linken altijd naar de bronnen die we gebruikten, zodat "
               "je ze kunt controleren.</p>"
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
:root{--bg:#0b0d10;--surface:#14171c;--border:#252a31;--fg:#e8eaed;--muted:#9aa0a6;--accent:#e31937;--link:#ff5a6e}
@media (prefers-color-scheme: light){:root{--bg:#ffffff;--surface:#f5f6f7;--border:#e3e5e8;--fg:#14171c;--muted:#5f6670;--accent:#cc0f2c;--link:#b30d26}}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--fg);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--link)}
.wrap{max-width:760px;margin:0 auto;padding:0 16px}
header{border-bottom:1px solid var(--border)}
header .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-top:16px;padding-bottom:16px}
.logo{font-weight:800;font-size:1.35rem;letter-spacing:-.02em;color:var(--fg);text-decoration:none}
.logo span{color:var(--accent)}
nav{display:flex;gap:16px;font-size:.92rem}
nav a{color:var(--muted);text-decoration:none}
nav a:hover{color:var(--fg)}
.hero{padding:40px 0 8px}
.hero p{color:var(--muted);font-size:1.1rem}
h1{font-size:clamp(1.7rem,4.5vw,2.4rem);line-height:1.2;letter-spacing:-.02em;margin-bottom:12px}
h2{font-size:1.35rem;line-height:1.3;margin:32px 0 10px}
.section-title{font-size:.8rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:32px 0 12px}
.card{display:block;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:14px;text-decoration:none;color:var(--fg)}
.card:hover{border-color:var(--accent)}
.card h3{font-size:1.2rem;line-height:1.35;margin:6px 0 8px}
.card p{color:var(--muted);font-size:.98rem}
.meta{font-size:.82rem;color:var(--muted)}
.tag{color:var(--accent);font-weight:600;text-transform:uppercase;letter-spacing:.06em;font-size:.75rem}
article{padding:32px 0}
article .lead{font-size:1.15rem;color:var(--muted);margin-bottom:20px}
article p,article ul,article ol{margin-bottom:16px}
article ul,article ol{padding-left:22px}
article li{margin-bottom:6px}
.sources{border-top:1px solid var(--border);margin-top:32px;padding-top:16px;font-size:.92rem}
.sources h2{font-size:1rem;margin:0 0 8px}
.sources li{margin-bottom:4px}
footer{border-top:1px solid var(--border);margin-top:48px;padding:24px 0 40px;font-size:.85rem;color:var(--muted)}
footer a{color:var(--muted)}
footer .links{display:flex;gap:16px;margin-bottom:8px;flex-wrap:wrap}
"""


def esc(s):
    return html.escape(s, quote=True)


def fmt_date(d, lang):
    dt = datetime.strptime(d, "%Y-%m-%d")
    m = LANGS[lang]["months"][dt.month - 1]
    return f"{m} {dt.day}, {dt.year}" if lang == "en" else f"{dt.day} {m} {dt.year}"


TZ = ZoneInfo("Europe/Amsterdam")


def published(a):
    """Timezone-aware publication datetime (defaults to 08:00 local)."""
    return datetime.strptime(f"{a['date']} {a.get('time', '08:00')}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


def url(lang, path=""):
    """Absolute path for a page in a language. path like '' or 'slug/' or 'about/'."""
    return f"{LANGS[lang]['prefix']}/{path}"


def other(lang):
    return "nl" if lang == "en" else "en"


def page(lang, path, title, description, body, og_type="website", extra_head=""):
    L = LANGS[lang]
    alt = other(lang)
    full_title = f"{title} | {NAME}" if title != NAME else f"{NAME} — {L['tagline']}"
    canonical = SITE + url(lang, path)
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
<meta property="og:locale" content="{L['locale']}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>{CSS}</style>
{extra_head}
</head>
<body>
<header><div class="wrap">
<a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a>
<nav><a href="{url(lang)}">{L['home']}</a><a href="{url(lang, 'about/')}">{L['about']}</a><a href="{url(alt, path)}" hreflang="{alt}" lang="{alt}">{L['switch']}</a></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
<div class="links"><a href="{url(lang, 'about/')}">{L['about']}</a><a href="{url(lang, 'privacy/')}">{L['privacy']}</a><a href="{url(lang, 'feed.xml')}">RSS</a></div>
<p>{L['disclaimer']}</p>
<p>&copy; {datetime.now().year} {NAME}</p>
</div></footer>
</body>
</html>
"""


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
    arts.sort(key=lambda a: (a["date"], a.get("time", "")), reverse=True)
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


def build():
    arts = load_articles()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    for lang in LANGS:
        L = LANGS[lang]

        # Home
        if arts:
            cards = "".join(
                f'<a class="card" href="{url(lang, a["slug"] + "/")}">'
                f'<span class="tag">{CATEGORIES[a["category"]][lang]}</span> '
                f'<span class="meta">· {fmt_date(a["date"], lang)}</span>'
                f'<h3>{esc(a[lang]["title"])}</h3><p>{esc(a[lang]["description"])}</p></a>'
                for a in arts
            )
        else:
            cards = f"<p class=\"meta\">{L['empty']}</p>"
        body = (f'<section class="hero"><h1>Trending<span style="color:var(--accent)">Tesla</span></h1>'
                f"<p>{L['tagline']}</p></section>"
                f'<h2 class="section-title">{L["latest"]}</h2>{cards}')
        write(url(lang), page(lang, "", NAME, L["tagline"], body))

        # Articles
        for a in arts:
            t = a[lang]
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
                "datePublished": published(a).isoformat(),
                "dateModified": a.get("updated", published(a).isoformat()),
                "inLanguage": lang,
                "mainEntityOfPage": SITE + url(lang, a["slug"] + "/"),
                "publisher": {"@type": "Organization", "name": NAME, "url": SITE},
                "author": {"@type": "Organization", "name": NAME},
            }
            head = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
            body = (f'<article><span class="tag">{CATEGORIES[a["category"]][lang]}</span>'
                    f'<h1>{esc(t["title"])}</h1>'
                    f'<p class="meta">{L["published"]} {fmt_date(a["date"], lang)}</p>'
                    f'<p class="lead">{esc(t["description"])}</p>'
                    f'{t["body"]}{src}</article>')
            write(url(lang, a["slug"] + "/"),
                  page(lang, a["slug"] + "/", t["title"], t["description"], body, "article", head))

        # Static pages
        for key, p in PAGES.items():
            title, desc, content = p[lang]
            write(url(lang, key + "/"),
                  page(lang, key + "/", title, desc, f"<article><h1>{esc(title)}</h1>{content}</article>"))

        # RSS
        items = "".join(
            f"<item><title>{esc(a[lang]['title'])}</title>"
            f"<link>{SITE + url(lang, a['slug'] + '/')}</link>"
            f"<guid>{SITE + url(lang, a['slug'] + '/')}</guid>"
            f"<pubDate>{published(a).astimezone(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
            f"<description>{esc(a[lang]['description'])}</description></item>"
            for a in arts[:30]
        )
        write(url(lang, "feed.xml"),
              f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
              f"<title>{NAME}</title><link>{SITE + url(lang)}</link>"
              f"<description>{esc(L['tagline'])}</description><language>{lang}</language>"
              f"{items}</channel></rss>")

    # 404 (English with link to Dutch home)
    L = LANGS["en"]
    write("/404.html", page("en", "", L["notfound"], L["notfound_text"],
          f"<article><h1>{L['notfound']}</h1><p>{L['notfound_text']}</p>"
          f"<p><a href=\"/\">{L['back']}</a> · <a href=\"/nl/\">{LANGS['nl']['back']}</a></p></article>"))

    # Sitemap
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = [("", today)] + [(a["slug"] + "/", a.get("updated", a["date"])[:10]) for a in arts] \
        + [(k + "/", today) for k in PAGES]
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
