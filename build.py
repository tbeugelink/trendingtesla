#!/usr/bin/env python3
"""Static site generator for trendingtesla.com.

Reads articles from content/articles/*.json and writes the complete site to public/.
English lives at the site root, Dutch under /nl/. Files in static/ (fonts, photos) are
copied as-is. Every article gets generated images (see covers.py): a clean visual for the
site (or the model photo when the article is about one model) and a titled image per
language for social sharing.

Article JSON format:
{
  "slug": "tesla-q3-2026-earnings-preview",      # URL part, same for both languages
  "date": "2026-10-21",                            # publication date (YYYY-MM-DD, Europe/Amsterdam)
  "time": "07:00",                                 # publication time (HH:MM, Europe/Amsterdam); optional
  "category": "earnings",                          # key from CATEGORIES below
  "models": ["model-y"],                           # optional: keys from MODELS below the article is about
  "image": "topics/optimus.jpg",                   # optional: specific photo (path inside static/img/)
  "sources": [{"title": "...", "url": "https://..."}],
  "en": {"title": "...", "description": "...", "body": "<p>...</p>"},
  "nl": {"title": "...", "description": "...", "body": "<p>...</p>"}
}
Guides (buying advice) use category "guides"; they appear in the "Best picks" section
and on the model pages they are tagged with.

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
STATIC = ROOT / "static"
OUT = ROOT / "public"
SITE = "https://trendingtesla.com"
NAME = "TrendingTesla"
TZ = ZoneInfo("Europe/Amsterdam")

LANGS = {
    "en": {
        "prefix": "", "locale": "en_US",
        "tagline": "Tesla news, explained. Every day.",
        "eyebrow": "Tesla news & honest advice",
        "hero_h": "Everything about your Tesla", "hero_span": "Without the hype",
        "hero_p": "The most important Tesla news several times a day, explained in plain language. Plus honest buying advice for your model.",
        "btn_news": "Latest news", "btn_model": "Choose your model",
        "latest": "Latest news", "more": "More news", "top": "Top story",
        "models_h": "News and advice for your model", "guides_h": "Best picks for your Tesla",
        "guides_sub": "Researched per model and year, with pros and cons.",
        "related": "Read next", "sources": "Sources", "about": "About", "privacy": "Privacy",
        "switch": "NL", "switch_full": "Nederlands",
        "empty": "No articles here yet. New stories are published several times a day.",
        "cat_intro": "All TrendingTesla articles about {}.",
        "eco_intro": "SpaceX, Starlink, The Boring Company and xAI/Grok: the companies around Tesla, and how they connect.",
        "model_intro": "News, updates and advice for the Tesla {}.",
        "model_guides": "Advice for the {}", "model_news": "{} news",
        "all_versions": "All versions", "your_version": "Your version:",
        "notfound": "Page not found", "notfound_text": "This page does not exist (anymore).",
        "back": "Back to the homepage", "min": "min read", "all": "All news",
        "why_h": "Honest news, no sales talk",
        "why": [("Several times a day", "We follow Tesla news around the clock and publish when something really happens."),
                ("Explained, not copied", "Our own articles: what happened, why it matters and what to watch."),
                ("Sources included", "Every article links to the sources we used, so you can check them."),
                ("Always free", "If you buy through our links we may earn a small commission, at no extra cost to you.")],
        "disclaimer": "TrendingTesla is an independent site and is not affiliated with Tesla, Inc. Nothing on this site is financial advice.",
        "months": ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"],
    },
    "nl": {
        "prefix": "/nl", "locale": "nl_NL",
        "tagline": "Tesla-nieuws, helder uitgelegd. Elke dag.",
        "eyebrow": "Tesla-nieuws & eerlijk advies",
        "hero_h": "Alles over jouw Tesla", "hero_span": "Zonder de hype",
        "hero_p": "Het belangrijkste Tesla-nieuws, meerdere keren per dag helder uitgelegd. Plus eerlijk koopadvies voor jouw model.",
        "btn_news": "Laatste nieuws", "btn_model": "Kies je model",
        "latest": "Laatste nieuws", "more": "Meer nieuws", "top": "Hoofdverhaal",
        "models_h": "Nieuws en advies voor jouw model", "guides_h": "De beste keuzes voor je Tesla",
        "guides_sub": "Uitgezocht per model en bouwjaar, met plus- en minpunten.",
        "related": "Lees ook", "sources": "Bronnen", "about": "Over ons", "privacy": "Privacy",
        "switch": "EN", "switch_full": "English",
        "empty": "Hier staan nog geen artikelen. Er verschijnen meerdere keren per dag nieuwe verhalen.",
        "cat_intro": "Alle artikelen van TrendingTesla over {}.",
        "eco_intro": "SpaceX, Starlink, The Boring Company en xAI/Grok: de bedrijven rond Tesla, en hoe ze met elkaar verbonden zijn.",
        "model_intro": "Nieuws, updates en advies voor de Tesla {}.",
        "model_guides": "Advies voor de {}", "model_news": "Nieuws over de {}",
        "all_versions": "Alle versies", "your_version": "Jouw versie:",
        "notfound": "Pagina niet gevonden", "notfound_text": "Deze pagina bestaat niet (meer).",
        "back": "Terug naar de homepagina", "min": "min lezen", "all": "Al het nieuws",
        "why_h": "Eerlijk nieuws, geen verkooppraatjes",
        "why": [("Meerdere keren per dag", "We volgen het Tesla-nieuws de klok rond en publiceren als er echt iets gebeurt."),
                ("Uitgelegd, niet overgeschreven", "Eigen artikelen: wat er gebeurde, waarom het ertoe doet en waar je op moet letten."),
                ("Met bronnen", "Elk artikel linkt naar de bronnen die we gebruikten, zodat je ze kunt controleren."),
                ("Altijd gratis", "Koop je via onze links, dan krijgen wij mogelijk een kleine commissie. Jij betaalt niets extra.")],
        "disclaimer": "TrendingTesla is een onafhankelijke site en is niet verbonden aan Tesla, Inc. Niets op deze site is financieel advies.",
        "months": ["januari", "februari", "maart", "april", "mei", "juni", "juli",
                   "augustus", "september", "oktober", "november", "december"],
    },
}

CATEGORIES = {
    "news":     {"en": "News",     "nl": "Nieuws",   "menu": True},
    "robotaxi": {"en": "Robotaxi", "nl": "Robotaxi", "menu": True},
    "fsd":      {"en": "FSD",      "nl": "FSD",      "menu": True},
    "models":   {"en": "Models",   "nl": "Modellen", "menu": True},
    "earnings": {"en": "Earnings", "nl": "Cijfers",  "menu": True},
    "energy":   {"en": "Energy",   "nl": "Energie",  "menu": True},
    "optimus":  {"en": "Optimus",  "nl": "Optimus",  "menu": True},
    "software": {"en": "Software", "nl": "Software", "menu": False},
    "charging": {"en": "Charging", "nl": "Laden",    "menu": False},
    "guides":   {"en": "Guides",   "nl": "Gidsen",   "menu": True},
    # SpaceX, Starlink, The Boring Company, xAI/Grok: only stories with a clear link to Tesla.
    "ecosystem": {"en": "Ecosystem", "nl": "Ecosysteem", "menu": True},
}

# Model pages. "photo" is a file in static/img/models/ (optional until uploaded).
# "article_photo": photo used on articles tagged with this model (current generation).
# "parent": this is a version/generation of the parent model. Its page also lists the parent's
#   articles, the parent page lists its articles, and both show a row of version buttons.
# "label": text on the version button (years are the same in both languages).
MODELS = {
    "model-s":           {"name": "Model S",            "photo": "model-s.jpg"},
    "model-s-classic":   {"name": "Model S 2012–2020",  "parent": "model-s", "label": "2012–2020"},
    "model-s-2021":      {"name": "Model S 2021+",      "parent": "model-s", "label": "2021+"},
    "model-s-plaid":     {"name": "Model S Plaid",      "parent": "model-s", "label": "Plaid"},
    "model-3":           {"name": "Model 3",            "photo": "model-3-classic.jpg", "article_photo": "model-3.jpg"},
    "model-3-classic":   {"name": "Model 3 2017–2023",  "photo": "model-3-classic.jpg", "parent": "model-3", "label": "2017–2023"},
    "model-3-highland":  {"name": "Model 3 Highland",   "photo": "model-3.jpg", "parent": "model-3", "label": "Highland · 2023+"},
    "model-3-standard":  {"name": "Model 3 Standard",   "photo": "model-3.jpg", "parent": "model-3", "label": "Standard · 2025+"},
    "model-3-performance": {"name": "Model 3 Performance", "photo": "model-3.jpg", "parent": "model-3", "label": "Performance"},
    "model-x":           {"name": "Model X",            "photo": "model-x.jpg"},
    "model-x-classic":   {"name": "Model X 2015–2020",  "parent": "model-x", "label": "2015–2020"},
    "model-x-2021":      {"name": "Model X 2021+",      "parent": "model-x", "label": "2021+"},
    "model-x-plaid":     {"name": "Model X Plaid",      "parent": "model-x", "label": "Plaid"},
    "model-y":           {"name": "Model Y",            "photo": "model-y-classic.jpg", "article_photo": "model-y.jpg"},
    "model-y-classic":   {"name": "Model Y 2020–2024",  "photo": "model-y-classic.jpg", "parent": "model-y", "label": "2020–2024"},
    "model-y-juniper":   {"name": "Model Y Juniper",    "photo": "model-y.jpg", "parent": "model-y", "label": "Juniper · 2025+"},
    "model-y-standard":  {"name": "Model Y Standard",   "photo": "model-y.jpg", "parent": "model-y", "label": "Standard · 2025+"},
    "model-y-performance": {"name": "Model Y Performance", "photo": "model-y.jpg", "parent": "model-y", "label": "Performance"},
    "model-y-l":         {"name": "Model Y L",          "photo": "model-y.jpg", "parent": "model-y", "label": {"en": "Model Y L · 6 seats", "nl": "Model Y L · 6 zitplaatsen"}},
    "cybertruck":        {"name": "Cybertruck",         "photo": "cybertruck.jpg"},
    "cybertruck-awd":    {"name": "Cybertruck AWD",     "parent": "cybertruck", "label": "AWD"},
    "cybertruck-cyberbeast": {"name": "Cyberbeast",     "parent": "cybertruck", "label": "Cyberbeast"},
    "cybercab":          {"name": "Cybercab",           "photo": "cybercab.jpg"},
    "roadster":          {"name": "Roadster",           "photo": "roadster.jpg"},
    "semi":              {"name": "Semi",               "photo": "semi.jpg"},
}
# Fallback photo per category: a file in static/img/topics/, or a list of files to vary between
# (each article always gets the same one, picked from its slug). Missing files are skipped.
TOPIC_PHOTOS = {
    "robotaxi": "cybercab.jpg", "fsd": ["fsd.jpg", "fsd-2.jpg", "fsd-3.jpg", "fsd-4.jpg"], "software": ["fsd.jpg", "fsd-2.jpg", "fsd-3.jpg", "fsd-4.jpg"], "optimus": ["optimus.jpg", "optimus-full.jpg"],
    "energy": ["energy.jpg", "energy-2.jpg"], "charging": ["supercharger.jpg", "supercharger-2.jpg", "supercharger-3.jpg"], "ecosystem": ["spacex-1.jpg", "starlink-car-1.jpg", "spacex-2.jpg", "starlink-1.jpg", "spacex-4.jpg", "starlink-car-3.jpg", "spacex-3.jpg", "starlink-2.jpg", "spacex-5.jpg", "starlink-car-2.jpg", "tunnel-2.jpg", "tunnel-3.jpg", "tunnel-4.jpg"], "earnings": ["gigafactory.jpg", "gigafactory-2.jpg"], "news": ["gigafactory.jpg", "gigafactory-2.jpg"],
}
MODEL_STRIP = ["model-s", "model-3", "model-3-highland", "model-x", "model-y", "model-y-juniper", "cybertruck"]

PAGES = {
    "about": {
        "en": ("About TrendingTesla", "What TrendingTesla is and how we write.",
               "<p>TrendingTesla follows everything that moves at Tesla: vehicles, software, "
               "self-driving, robotaxi, Optimus, energy and the company's results, the wider ecosystem of SpaceX, Starlink, The Boring Company and xAI where it touches Tesla, plus honest "
               "buying advice for Tesla owners.</p>"
               "<p>Several times a day we pick the stories that matter most and explain them in "
               "plain language: what happened, why it matters and what to watch next. We write "
               "our own articles and always link to the sources we used, so you can check them.</p>"
               "<p>Articles are researched and written with the help of AI and published "
               "under editorial supervision. Spotted a mistake? We correct it as soon as we "
               "know about it.</p>"
               "<p>Some links on this site may be affiliate links: if you buy through them we may "
               "earn a small commission, at no extra cost to you. This never affects our opinion.</p>"
               "<p>TrendingTesla is an independent site. We are not affiliated with, "
               "sponsored by or endorsed by Tesla, Inc. Nothing on this site is financial advice.</p>"),
        "nl": ("Over TrendingTesla", "Wat TrendingTesla is en hoe we schrijven.",
               "<p>TrendingTesla volgt alles wat er bij Tesla in beweging is: auto's, software, "
               "zelfrijden, robotaxi, Optimus, energie en de bedrijfscijfers, het bredere ecosysteem van SpaceX, Starlink, The Boring Company en xAI waar het Tesla raakt, plus eerlijk "
               "koopadvies voor Tesla-rijders.</p>"
               "<p>Meerdere keren per dag kiezen we de belangrijkste verhalen en leggen we ze "
               "helder uit: wat er gebeurde, waarom het ertoe doet en waar je op moet letten. We "
               "schrijven onze eigen artikelen en linken altijd naar de bronnen die we gebruikten, "
               "zodat je ze kunt controleren.</p>"
               "<p>Artikelen worden met hulp van AI onderzocht en geschreven en onder "
               "redactioneel toezicht gepubliceerd. Een fout gezien? We verbeteren hem zodra "
               "we ervan weten.</p>"
               "<p>Sommige links op deze site kunnen affiliate-links zijn: koop je via zo'n link, "
               "dan krijgen wij mogelijk een kleine commissie. Jij betaalt niets extra en het "
               "verandert nooit ons oordeel.</p>"
               "<p>TrendingTesla is een onafhankelijke site. We zijn niet verbonden aan, "
               "gesponsord door of goedgekeurd door Tesla, Inc. Niets op deze site is "
               "financieel advies.</p>"),
    },
    "privacy": {
        "en": ("Privacy policy", "How TrendingTesla handles your data.",
               "<p>TrendingTesla does not ask you to create an account and does not collect "
               "personal data through forms.</p>"
               "<p>The site is served through Cloudflare, which processes technical data such "
               "as IP addresses to deliver and protect the site. Fonts are served from our own "
               "domain, not from third parties. We do not use tracking cookies at this moment.</p>"
               "<p>If we add advertising or analytics in the future, this page will be updated "
               "first and you will be asked for consent where the law requires it.</p>"),
        "nl": ("Privacybeleid", "Hoe TrendingTesla met je gegevens omgaat.",
               "<p>TrendingTesla vraagt je niet om een account aan te maken en verzamelt geen "
               "persoonsgegevens via formulieren.</p>"
               "<p>De site wordt geleverd via Cloudflare, dat technische gegevens zoals "
               "IP-adressen verwerkt om de site te leveren en te beveiligen. Lettertypen komen "
               "van ons eigen domein, niet van derden. We gebruiken op dit moment geen "
               "trackingcookies.</p>"
               "<p>Als we in de toekomst advertenties of statistieken toevoegen, passen we "
               "deze pagina eerst aan en vragen we waar de wet dat vereist om toestemming.</p>"),
    },
}

CSS = """
@font-face{font-family:Manrope;font-weight:400;font-display:swap;src:url(/fonts/manrope-latin-400-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:600;font-display:swap;src:url(/fonts/manrope-latin-600-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:700;font-display:swap;src:url(/fonts/manrope-latin-700-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:800;font-display:swap;src:url(/fonts/manrope-latin-800-normal.woff2) format("woff2")}
:root{--bg:#04060a;--surface:rgba(11,15,23,.92);--surface2:#111827;--border:#172130;--border2:#223044;--fg:#e8eef5;--head:#fff;--muted:#b9c4d2;--dim:#8f9db0;--red:#e22822;--red2:#b81e19;--blue:#00d4ff;--edge:#3a4a60;--blue2:#5fe3ff;--max:1200px;color-scheme:dark}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:150px;background:#04060a}
body{background:radial-gradient(1400px 800px at 90% -15%,rgba(0,212,255,.065),transparent 60%),radial-gradient(1000px 700px at -15% 35%,rgba(56,96,255,.08),transparent 60%),radial-gradient(900px 600px at 70% 75%,rgba(0,150,255,.05),transparent 60%) #03050a;min-height:100vh;color:var(--fg);font:17px/1.65 Manrope,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
body::before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.12;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='260' height='260'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.65' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  2.6 0 0 0 -1.3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
main,footer{position:relative;z-index:1}
a{color:var(--head)}
img{display:block;max-width:100%;height:auto}
h1,h2,h3{color:var(--head);font-weight:800}
.wrap{max-width:var(--max);margin:0 auto;padding:0 24px}
.narrow{max-width:740px;margin:0 auto}
.sr{position:absolute;left:-9999px}
/* header */
.top{position:sticky;top:0;z-index:10;background:rgba(6,10,18,.55);backdrop-filter:blur(16px) saturate(1.3);-webkit-backdrop-filter:blur(16px) saturate(1.3);border-bottom:1px solid var(--border)}
.bar{display:flex;align-items:center;justify-content:space-between;gap:16px;height:60px}
.logo{font-weight:800;font-size:1.4rem;letter-spacing:-.02em;color:var(--head);text-decoration:none;white-space:nowrap}
.logo span{color:var(--red)}
.lang{font-size:.78rem;font-weight:800;letter-spacing:.05em;color:var(--muted);text-decoration:none;border:1px solid var(--border2);border-radius:999px;padding:4px 11px}
.lang:hover{color:var(--head);border-color:var(--head)}
.menu{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;padding-bottom:10px;margin-top:-4px}
.menu::-webkit-scrollbar{display:none}
.menu a{flex:none;font-size:.86rem;font-weight:700;color:var(--muted);text-decoration:none;padding:6px 12px;border-radius:999px}
.menu a:hover{color:var(--head);background:var(--surface)}
.menu a.on{color:var(--head);background:var(--surface2);box-shadow:inset 0 -2px 0 var(--blue)}
/* buttons, labels */
.btn{display:inline-flex;align-items:center;justify-content:center;background:var(--red);color:#fff;font-weight:800;font-size:.9rem;padding:11px 20px;border-radius:10px;text-decoration:none;transition:background .2s}
.btn:hover{background:var(--red2)}
.btn.ghost{background:transparent;border:1px solid var(--border2);color:var(--head)}
.btn.ghost:hover{border-color:var(--head);background:transparent}
.tag{display:inline-block;font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;text-decoration:none;color:var(--blue)}
.meta{font-size:.8rem;color:var(--dim)}
.h2{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:48px 0 22px}
.h2 h2{font-size:clamp(1.3rem,2.6vw,1.75rem);letter-spacing:-.02em;line-height:1.2}
.h2 a{font-size:.86rem;font-weight:700;color:var(--muted);text-decoration:none;white-space:nowrap}
.h2 a:hover{color:var(--head)}
.sub{color:var(--muted);font-size:.92rem;margin:-8px 0 16px}
/* hero */
.hero{position:relative;overflow:hidden;border-radius:18px;background:radial-gradient(ellipse at 85% 40%,rgba(0,212,255,.14),transparent 60%),linear-gradient(135deg,#0b1320,#04060a);min-height:340px;margin-top:24px;display:flex;align-items:center}
.hero img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center right}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(4,6,10,.96) 0%,rgba(4,6,10,.7) 45%,rgba(4,6,10,.12) 100%)}
.hero .in{position:relative;z-index:2;max-width:520px;padding:36px 32px}
.eyebrow{display:inline-block;font-size:.7rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--blue);border:1px solid rgba(0,212,255,.35);background:rgba(0,212,255,.1);padding:4px 11px;border-radius:999px;margin-bottom:14px}
.hero h1{font-size:clamp(1.8rem,4vw,2.7rem);line-height:1.08;letter-spacing:-.025em;margin-bottom:12px}
.hero h1 span{color:var(--red)}
.hero p{color:#c9ced3;font-size:1rem;margin-bottom:20px}
#news .h2{margin-top:36px}
.hero .btns{display:flex;gap:10px;flex-wrap:wrap}
/* top stories */
.tops{display:grid;grid-template-columns:1.6fr 1fr;gap:44px}
.feature{text-decoration:none;color:var(--fg);display:block}
.feature .im,.card .im{overflow:hidden;border-radius:14px;border:1px solid var(--edge);background:var(--surface);transition:border-color .2s}
.feature:hover .im,.card:hover .im{border-color:var(--blue)}
.feature img,.card img{width:100%;aspect-ratio:1200/630;object-fit:cover;transition:transform .4s}
.feature:hover img,.card:hover img{transform:scale(1.03)}
.feature h3{font-size:clamp(1.4rem,2.8vw,2rem);line-height:1.15;letter-spacing:-.02em;margin:14px 0 8px}
.feature p{color:var(--muted);margin-bottom:8px}
.side{display:flex;flex-direction:column;gap:28px}
.mini{display:grid;grid-template-columns:180px 1fr;gap:18px;text-decoration:none;color:var(--fg);align-items:start}
.mini img{width:180px;aspect-ratio:1200/630;object-fit:cover;border-radius:10px;border:1px solid var(--edge);transition:border-color .2s,box-shadow .2s}
.mini:hover img{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue)}
.mini h3{font-size:.98rem;line-height:1.3;margin:6px 0 4px}
.mini .tag{display:block;line-height:1;margin-top:0}
.feature:hover h3,.card:hover h3,.mini:hover h3{color:var(--blue2)}
/* grid */
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:56px 64px}
.card{text-decoration:none;color:var(--fg);display:flex;flex-direction:column}
.card .body{padding:18px 4px 0}
.card h3{font-size:1.08rem;line-height:1.3;margin:6px 0 6px}
.card p{color:var(--muted);font-size:.9rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.empty{color:var(--muted);background:var(--surface);border:1px dashed var(--border2);border-radius:14px;padding:28px;text-align:center}
/* models */
.models{display:grid;grid-template-columns:repeat(7,1fr);gap:24px}
.model{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--edge);border-radius:14px;overflow:hidden;text-decoration:none;color:var(--head);transition:border-color .2s,transform .2s}
.model:hover{border-color:var(--blue);transform:translateY(-3px)}
.model .ph{aspect-ratio:3/2;background:#000;display:flex;align-items:center;justify-content:center}
.model img{width:100%;height:100%;object-fit:contain}
.model .ph b{font-size:1.5rem;color:#2a3544;letter-spacing:-.02em}
.model span{padding:10px 8px;font-size:.82rem;line-height:1.3;font-weight:800;text-align:center}
/* why */
.why{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.why div{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px}
.why i{display:inline-flex;width:32px;height:32px;border-radius:8px;background:rgba(0,212,255,.12);align-items:center;justify-content:center;color:var(--blue);font-weight:800;font-style:normal;margin-bottom:10px}
.why b{display:block;color:var(--head);font-size:.98rem;margin-bottom:4px}
.why p{font-size:.86rem;color:var(--muted)}
/* page heads */
.phead{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:36px 0 22px;border-bottom:1px solid var(--border);margin-bottom:28px}
.versions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:18px}
.versions span{font-size:.8rem;font-weight:700;color:var(--dim);margin-right:4px}
.versions a{font-size:.84rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid var(--border2);border-radius:999px;padding:6px 13px;transition:border-color .2s,color .2s}
.versions a:hover{color:var(--head);border-color:var(--blue)}
.versions a.on{color:#03131a;background:var(--blue);border-color:var(--blue)}
.phead h1{font-size:clamp(2rem,5vw,3rem);letter-spacing:-.03em;line-height:1.05}
.phead p{color:var(--muted);margin-top:6px}
.phead img{width:min(420px,45%);flex:none;border-radius:14px;border:1px solid var(--edge)}
/* article */
article{padding:36px 0 8px}
article h1{font-size:clamp(1.8rem,4.6vw,2.6rem);line-height:1.12;letter-spacing:-.025em;margin:10px 0 14px}
article .lead{font-size:1.18rem;line-height:1.55;color:var(--muted);margin:0 0 18px}
article .hero-img{border-radius:16px;margin:0 0 26px;aspect-ratio:1200/630;width:100%;object-fit:cover;border:1px solid var(--edge)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.chips a{font-size:.78rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid var(--border2);border-radius:999px;padding:3px 10px}
.chips a:hover{color:var(--head);border-color:var(--head)}
.prose h2{font-size:1.35rem;line-height:1.3;letter-spacing:-.015em;margin:34px 0 10px}
.prose p,.prose ul,.prose ol{margin-bottom:18px}
.prose ul,.prose ol{padding-left:22px}
.prose li{margin-bottom:8px}
.prose li::marker{color:var(--blue)}
.prose a{color:var(--blue2)}
.prose em{color:var(--muted)}
.prose strong{color:var(--head)}
.sources{background:var(--surface);border:1px solid var(--border);border-radius:14px;margin-top:34px;padding:18px 22px;font-size:.88rem}
.sources h2{font-size:.74rem;text-transform:uppercase;letter-spacing:.12em;color:var(--dim);margin:0 0 8px}
.sources ul{padding-left:18px}
.sources li{margin-bottom:4px}
.sources a{color:var(--muted)}
/* footer */
footer{border-top:1px solid var(--border);margin-top:72px;padding:36px 0 48px;font-size:.85rem;color:var(--dim)}
footer .cols{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap}
footer a{color:var(--muted);text-decoration:none}
footer a:hover{color:var(--head)}
footer .links{display:flex;gap:18px;flex-wrap:wrap}
footer p{max-width:560px;margin-top:10px}
@media (max-width:1000px){.grid{grid-template-columns:repeat(2,1fr);gap:48px 40px}.tops{grid-template-columns:1fr}.why{grid-template-columns:repeat(2,1fr)}.models{grid-template-columns:repeat(4,1fr);gap:20px}}
@media (max-width:600px){.wrap{padding:0 20px}.mini{grid-template-columns:1fr;gap:12px}.mini img{width:100%}#news .h2{margin-top:32px}.grid{grid-template-columns:1fr;gap:40px}.why{grid-template-columns:1fr 1fr;gap:10px}.why div{padding:14px}.why p{font-size:.8rem}
 .models{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;margin:0 -24px;padding:0 24px 4px}.models::-webkit-scrollbar{display:none}.models{gap:14px}.model{flex:0 0 46%;scroll-snap-align:start}
 body{font-size:16.5px}.h2{margin-top:40px}.hero{min-height:0}.hero .in{padding:26px 20px}.hero .btn{flex:1;white-space:nowrap;padding:11px 12px}
 .phead{flex-direction:column-reverse;align-items:flex-start}.phead img{width:100%}}
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
    return f"{LANGS[lang]['prefix']}/{path}"


def other(lang):
    return "nl" if lang == "en" else "en"


def model_photo(key, for_article=False):
    m = MODELS[key]
    p = m.get("article_photo", m.get("photo")) if for_article else m.get("photo")
    if p and (STATIC / "img" / "models" / p).exists():
        return f"/img/models/{p}"
    return model_photo(m["parent"], for_article) if m.get("parent") else None


def social_img(a, lang):
    return f"/img/{a['slug']}-{lang}.jpg"


PHOTO_ORDER = {}  # slug -> position among articles of its category, oldest first (set in build)


def topic_photo(category, slug=""):
    f = TOPIC_PHOTOS.get(category)
    files = [x for x in ([f] if isinstance(f, str) else (f or [])) if (STATIC / "img" / "topics" / x).exists()]
    if not files:
        return None
    # Round-robin in publication order, so neighbouring articles get different photos and
    # existing articles keep their photo when new ones are added.
    pick = PHOTO_ORDER.get(slug, 0) % len(files)
    return f"/img/topics/{files[pick]}"


def site_img(a):
    """Image shown on the site: an explicit "image" (file in static/img/), else the model photo for
    single-model articles, else the category photo, else the generated visual."""
    if a.get("image") and (STATIC / "img" / a["image"]).exists():
        return f"/img/{a['image']}"
    ms = a.get("models", [])
    if ms and model_photo(ms[0], True):
        return model_photo(ms[0], True)
    if len(ms) == 1 and MODELS[ms[0]].get("photo") and (STATIC / "img" / "topics" / MODELS[ms[0]]["photo"]).exists():
        return f"/img/topics/{MODELS[ms[0]]['photo']}"
    return topic_photo(a["category"], a["slug"]) or f"/img/v/{a['slug']}.jpg"


def read_time(a, lang):
    return max(1, round(len(html.unescape(a[lang]["body"]).split()) / 220))


def page(lang, path, title, description, body, og_type="website", extra_head="", image=None, active=None):
    L = LANGS[lang]
    alt = other(lang)
    full_title = f"{title} | {NAME}" if title != NAME else f"{NAME} — {L['tagline']}"
    canonical = SITE + url(lang, path)
    img = SITE + (image or f"/img/default-{lang}.jpg")
    menu = "".join(
        f'<a href="{url(lang, "category/" + k + "/")}"{" class=\"on\"" if k == active else ""}>{c[lang]}</a>'
        for k, c in CATEGORIES.items() if c["menu"])
    cats = " · ".join(f'<a href="{url(lang, "category/" + k + "/")}">{c[lang]}</a>' for k, c in CATEGORIES.items())
    mods = " · ".join(f'<a href="{url(lang, "model/" + k + "/")}">{m["name"]}</a>' for k, m in MODELS.items() if not m.get("parent") or k in MODEL_STRIP)
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
<link rel="preload" href="/fonts/manrope-latin-800-normal.woff2" as="font" type="font/woff2" crossorigin>
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
<meta name="theme-color" content="#03050a">
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
<p>{cats}</p><p>{mods}</p><p>&copy; {datetime.now().year} {NAME}</p></div>
</div></div></footer>
</body>
</html>
"""


def label(a, lang):
    return f'<span class="tag">{CATEGORIES[a["category"]][lang]}</span>'


def card(a, lang):
    t = a[lang]
    return (f'<a class="card" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="im"><img src="{site_img(a)}" alt="" width="1200" height="630" loading="lazy" decoding="async"></div>'
            f'<div class="body">{label(a, lang)} <span class="meta">· {fmt_date(a["date"], lang)}</span>'
            f'<h3>{esc(t["title"])}</h3><p>{esc(t["description"])}</p></div></a>')


def mini(a, lang):
    t = a[lang]
    return (f'<a class="mini" href="{url(lang, a["slug"] + "/")}">'
            f'<img src="{site_img(a)}" alt="" width="1200" height="630" loading="lazy" decoding="async">'
            f'<div>{label(a, lang)}<h3>{esc(t["title"])}</h3><span class="meta">{fmt_date(a["date"], lang)}</span></div></a>')


def grid(items, lang):
    return f'<div class="grid">{"".join(card(a, lang) for a in items)}</div>'


def section(title, body, link=None, sub=None, anchor=None):
    a = f' id="{anchor}"' if anchor else ""
    l = f'<a href="{link[0]}">{link[1]} →</a>' if link else ""
    s = f'<p class="sub">{sub}</p>' if sub else ""
    return f'<section{a}><div class="h2"><h2>{title}</h2>{l}</div>{s}{body}</section>'


def model_tiles(lang):
    tiles = ""
    for k in MODEL_STRIP:
        m = MODELS[k]
        ph = model_photo(k)
        inner = f'<img src="{ph}" alt="Tesla {m["name"]}" loading="lazy">' if ph else f'<b>{m["name"].replace("Model ", "")}</b>'
        tiles += f'<a class="model" href="{url(lang, "model/" + k + "/")}"><div class="ph">{inner}</div><span>{m["name"]}</span></a>'
    return f'<div class="models">{tiles}</div>'


def why(lang):
    return '<div class="why">' + "".join(
        f"<div><i>{i}</i><b>{h}</b><p>{p}</p></div>" for i, (h, p) in enumerate(LANGS[lang]["why"], 1)) + "</div>"


def load_articles():
    arts = []
    for f in sorted(CONTENT.glob("*.json")):
        a = json.loads(f.read_text(encoding="utf-8"))
        for key in ("slug", "date", "category", "en", "nl"):
            if key not in a:
                raise SystemExit(f"{f.name}: missing '{key}'")
        if a["category"] not in CATEGORIES:
            raise SystemExit(f"{f.name}: unknown category '{a['category']}'")
        for m in a.get("models", []):
            if m not in MODELS:
                raise SystemExit(f"{f.name}: unknown model '{m}' (use a key from MODELS)")
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
    ms = set(a.get("models", []))
    def score(x):
        return (len(ms & set(x.get("models", []))) * 2 + (x["category"] == a["category"]), published(x))
    return sorted((x for x in arts if x is not a), key=score, reverse=True)[:n]


def build():
    arts = load_articles()
    seen = {}
    for x in sorted(arts, key=published):
        PHOTO_ORDER[x["slug"]] = seen.get(x["category"], 0)
        seen[x["category"]] = PHOTO_ORDER[x["slug"]] + 1
    news = [a for a in arts if a["category"] != "guides"]
    guides = [a for a in arts if a["category"] == "guides"]
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT)

    # Images
    for a in arts:
        make_cover(OUT / "img" / "v" / f"{a['slug']}.jpg", "", "", a["category"], "", "", with_text=False)
        for lang in LANGS:
            make_cover(OUT / social_img(a, lang).lstrip("/"), a[lang]["title"], CATEGORIES[a["category"]][lang],
                       a["category"], "", fmt_date(a["date"], lang))
    for lang in LANGS:
        make_cover(OUT / "img" / f"default-{lang}.jpg", LANGS[lang]["tagline"], NAME, "news", "", "trendingtesla.com")
    hero_photo = "/img/hero.jpg" if (STATIC / "img" / "hero.jpg").exists() else None

    for lang in LANGS:
        L = LANGS[lang]

        # ---------- Home ----------
        hero = (f'<div class="hero">{f"<img src={chr(34)}{hero_photo}{chr(34)} alt={chr(34)}{chr(34)} fetchpriority={chr(34)}high{chr(34)}>" if hero_photo else ""}'
                f'<div class="in"><span class="eyebrow">{L["eyebrow"]}</span>'
                f'<h1>{L["hero_h"]}<br><span>{L["hero_span"]}</span></h1><p>{L["hero_p"]}</p>'
                f'<div class="btns"><a class="btn" href="#models">{L["btn_model"]} →</a></div></div></div>')
        body = hero
        if news:
            top = news[0]
            t = top[lang]
            feature = (f'<a class="feature" href="{url(lang, top["slug"] + "/")}">'
                       f'<div class="im"><img src="{site_img(top)}" alt="" width="1200" height="630"></div>'
                       f'<span class="tag" style="margin-top:14px">{L["top"]} · {CATEGORIES[top["category"]][lang]}</span>'
                       f'<h3>{esc(t["title"])}</h3><p>{esc(t["description"])}</p>'
                       f'<span class="meta">{fmt_date(top["date"], lang)} · {read_time(top, lang)} {L["min"]}</span></a>')
            side = "".join(mini(a, lang) for a in news[1:5])
            tops = f'<div class="tops">{feature}<div class="side">{side}</div></div>'
            body += section(L["latest"], tops, (url(lang, "category/news/"), L["all"]), anchor="news")
        else:
            body += section(L["latest"], f'<p class="empty">{L["empty"]}</p>', anchor="news")
        body += section(L["models_h"], model_tiles(lang), anchor="models")
        if guides:
            body += section(L["guides_h"], grid(guides[:6], lang), (url(lang, "category/guides/"), CATEGORIES["guides"][lang]),
                            sub=L["guides_sub"])
        if len(news) > 5:
            body += section(L["more"], grid(news[5:20], lang))
        body += section(L["why_h"], why(lang))
        write(url(lang), page(lang, "", NAME, L["tagline"], body))

        # ---------- Category pages ----------
        for key, c in CATEGORIES.items():
            items = arts if key == "news" else [a for a in arts if a["category"] == key]
            if key == "news":
                items = news
            intro = L["eco_intro"] if key == "ecosystem" else L["cat_intro"].format(c[lang])
            head = f'<div class="phead"><div><span class="tag">{NAME}</span><h1>{c[lang]}</h1><p>{intro}</p></div></div>'
            content = grid(items, lang) if items else f'<p class="empty">{L["empty"]}</p>'
            write(url(lang, f"category/{key}/"),
                  page(lang, f"category/{key}/", c[lang], intro, head + content, active=key))

        # ---------- Model pages ----------
        for key, m in MODELS.items():
            family = {key} | ({m["parent"]} if m.get("parent") else set()) \
                | {k for k, v in MODELS.items() if v.get("parent") == key}
            items = [a for a in arts if family & set(a.get("models", []))]
            mg = [a for a in items if a["category"] == "guides"]
            mn = [a for a in items if a["category"] != "guides"]
            ph = model_photo(key)
            root = m.get("parent", key)
            versions = [k for k, v in MODELS.items() if v.get("parent") == root]
            chips_v = ""
            if versions:
                btns = [(root, L["all_versions"])] + [(k, MODELS[k]["label"][lang] if isinstance(MODELS[k]["label"], dict) else MODELS[k]["label"]) for k in versions]
                chips_v = '<div class="versions"><span>' + L["your_version"] + '</span>' + "".join(
                    f'<a href="{url(lang, "model/" + k + "/")}"{" class=\"on\"" if k == key else ""}>{esc(lbl)}</a>'
                    for k, lbl in btns) + '</div>'
            head = (f'<div class="phead"><div><span class="tag">Tesla</span><h1>{m["name"]}</h1>'
                    f'<p>{L["model_intro"].format(m["name"])}</p>{chips_v}</div>'
                    f'{f"<img src={chr(34)}{ph}{chr(34)} alt={chr(34)}Tesla {m[chr(110)+chr(97)+chr(109)+chr(101)]}{chr(34)}>" if ph else ""}</div>')
            content = ""
            if mg:
                content += section(L["model_guides"].format(m["name"]), grid(mg, lang))
            content += section(L["model_news"].format(m["name"]), grid(mn, lang) if mn else f'<p class="empty">{L["empty"]}</p>')
            write(url(lang, f"model/{key}/"),
                  page(lang, f"model/{key}/", f"Tesla {m['name']}", L["model_intro"].format(m["name"]), head + content,
                       image=ph))

        # ---------- Articles ----------
        for a in arts:
            t = a[lang]
            c = CATEGORIES[a["category"]]
            src = ""
            if a.get("sources"):
                items = "".join(f'<li><a href="{esc(s["url"])}" rel="nofollow noopener" target="_blank">{esc(s["title"])}</a></li>'
                                for s in a["sources"])
                src = f'<div class="sources"><h2>{L["sources"]}</h2><ul>{items}</ul></div>'
            chips = ""
            if a.get("models"):
                chips = '<div class="chips">' + "".join(
                    f'<a href="{url(lang, "model/" + k + "/")}">Tesla {MODELS[k]["name"]}</a>' for k in a["models"]) + "</div>"
            ld = {
                "@context": "https://schema.org", "@type": "NewsArticle",
                "headline": t["title"], "description": t["description"],
                "image": [SITE + social_img(a, lang)],
                "datePublished": published(a).isoformat(),
                "dateModified": a.get("updated", published(a).isoformat()),
                "inLanguage": lang, "articleSection": c[lang],
                "mainEntityOfPage": SITE + url(lang, a["slug"] + "/"),
                "publisher": {"@type": "Organization", "name": NAME, "url": SITE,
                              "logo": {"@type": "ImageObject", "url": SITE + "/favicon.svg"}},
                "author": {"@type": "Organization", "name": NAME, "url": SITE},
            }
            head = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
            rel = related(a, arts)
            rel_html = section(L["related"], grid(rel, lang)) if rel else ""
            body = (f'<article class="narrow">'
                    f'<img class="hero-img" src="{site_img(a)}" alt="{esc(t["title"])}" width="1200" height="630" fetchpriority="high">'
                    f'<a class="tag" href="{url(lang, "category/" + a["category"] + "/")}">{c[lang]}</a>'
                    f'<h1>{esc(t["title"])}</h1><p class="lead">{esc(t["description"])}</p>'
                    f'<p class="meta" style="margin-bottom:26px">{NAME} · {fmt_date(a["date"], lang)} · {read_time(a, lang)} {L["min"]}</p>{chips}'
                    f'<div class="prose">{t["body"]}</div>{src}</article>{rel_html}')
            write(url(lang, a["slug"] + "/"),
                  page(lang, a["slug"] + "/", t["title"], t["description"], body, "article", head,
                       image=social_img(a, lang), active=a["category"]))

        # ---------- Static pages ----------
        for key, p in PAGES.items():
            title, desc, content = p[lang]
            write(url(lang, key + "/"), page(lang, key + "/", title, desc,
                  f'<article class="narrow"><h1>{esc(title)}</h1><div class="prose">{content}</div></article>'))

        # ---------- RSS ----------
        items = "".join(
            f"<item><title>{esc(a[lang]['title'])}</title>"
            f"<link>{SITE + url(lang, a['slug'] + '/')}</link><guid>{SITE + url(lang, a['slug'] + '/')}</guid>"
            f"<pubDate>{published(a).astimezone(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
            f"<description>{esc(a[lang]['description'])}</description>"
            f'<enclosure url="{SITE + social_img(a, lang)}" type="image/jpeg" length="0"/></item>'
            for a in arts[:30])
        write(url(lang, "feed.xml"),
              f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
              f"<title>{NAME}</title><link>{SITE + url(lang)}</link>"
              f"<description>{esc(L['tagline'])}</description><language>{lang}</language>{items}</channel></rss>")

    # 404
    L = LANGS["en"]
    write("/404.html", page("en", "", L["notfound"], L["notfound_text"],
          f'<article class="narrow"><h1>{L["notfound"]}</h1><p class="lead">{L["notfound_text"]}</p>'
          f'<p><a href="/">{L["back"]}</a> · <a href="/nl/">{LANGS["nl"]["back"]}</a></p></article>'))

    # Sitemap
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = ([("", today)] + [(a["slug"] + "/", a.get("updated", a["date"])[:10]) for a in arts]
               + [(f"category/{k}/", today) for k in CATEGORIES] + [(f"model/{k}/", today) for k in MODELS]
               + [(k + "/", today) for k in PAGES])
    urls = ""
    for path, mod in entries:
        for lang in LANGS:
            alts = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{SITE + url(l, path)}"/>' for l in LANGS)
            urls += f"<url><loc>{SITE + url(lang, path)}</loc><lastmod>{mod}</lastmod>{alts}</url>"
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
          f"{urls}</urlset>")
    write("/robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    write("/favicon.svg",
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#e22822"/>'
          '<text x="32" y="45" font-family="system-ui,sans-serif" font-size="38" font-weight="800" fill="#fff" text-anchor="middle">T</text></svg>')
    print(f"Built {len(arts)} article(s) in {len(LANGS)} languages -> {OUT}")


if __name__ == "__main__":
    build()
