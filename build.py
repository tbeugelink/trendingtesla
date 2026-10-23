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
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from covers import make_cover
from model_info import INFO

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
        "switch": "NL", "switch_full": "Nederlands", "i_specs": "Specifications", "i_watch": "Points to watch", "i_special": "What makes it special", "i_acc": "Accessories", "i_acc_soon": "Coming soon: accessories that fit this version, tested and explained.", "slogan": "Daily Tesla news &amp; trends", "search": "Search Tesla news", "none": "Nothing found", "home": "Home", "collapse": "Close menu", "like": "Like", "save": "Save", "saved_btn": "Saved", "saved": "Saved articles", "saved_empty": "You have not saved any articles yet. Tap Save under an article title to keep it here. Saved articles stay in this browser on this device.", "archive": "All news", "newer": "Newer", "older": "Older", "page": "Page", "d_topics": "Topics", "d_models": "Models", "d_more": "More", "menu": "Menu", "tip_h": "A 22 kW charger won't charge your Tesla any faster", "tip_p": "Most Tesla models charge at home at up to 11 kW AC.", "tip_btn": "Read why", "tips": [("HW4", "Buying a used Model 3? Check the hardware first", "The Highland has HW4, older cars HW3. It decides what FSD can do.", "How to check", "used-model-3-highland-vs-classic-hw3-hw4-buying-guide"), ("−20%", "Losing range in winter? It doesn't have to be", "Preconditioning and the right settings save you kilometers.", "9 winter tips", "tesla-winter-range-tips-cold-weather")],
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
        "switch": "EN", "switch_full": "English", "i_specs": "Specificaties", "i_watch": "Aandachtspunten", "i_special": "Bijzonderheden", "i_acc": "Accessoires", "i_acc_soon": "Binnenkort: accessoires die op deze uitvoering passen, getest en uitgelegd.", "slogan": "Iedere dag het laatste nieuws &amp; trends", "search": "Zoek in Tesla-nieuws", "none": "Niets gevonden", "home": "Home", "collapse": "Inklappen", "like": "Vind ik leuk", "save": "Bewaren", "saved_btn": "Bewaard", "saved": "Bewaarde artikelen", "saved_empty": "Je hebt nog geen artikelen bewaard. Tik op Bewaren onder de titel van een artikel om het hier terug te vinden. Bewaarde artikelen blijven in deze browser op dit apparaat.", "archive": "Alle nieuws", "newer": "Nieuwer", "older": "Ouder", "page": "Pagina", "d_topics": "Onderwerpen", "d_models": "Modellen", "d_more": "Meer", "menu": "Menu", "tip_h": "Een 22 kW-laadpaal laadt je Tesla niet sneller", "tip_p": "Veel Tesla-modellen laden thuis met maximaal 11 kW AC.", "tip_btn": "Lees waarom", "tips": [("HW4", "Tweedehands Model 3 kopen? Check eerst de hardware", "De Highland heeft HW4, oudere Model 3's HW3. Dat bepaalt wat FSD kan.", "Zo check je het", "used-model-3-highland-vs-classic-hw3-hw4-buying-guide"), ("−20%", "Minder bereik in de winter? Dat hoeft niet", "Met voorverwarmen en de juiste instellingen houd je meer kilometers over.", "9 wintertips", "tesla-winter-range-tips-cold-weather")],
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
    "models":   {"en": "Model",    "nl": "Model", "menu": True, "tag": "Model"},
    "charging": {"en": "Charging", "nl": "Laden",    "menu": True},
    "software": {"en": "Software", "nl": "Software", "menu": True},
    "fsd":      {"en": "FSD",      "nl": "FSD",      "menu": True},
    "robotaxi": {"en": "Robotaxi", "nl": "Robotaxi", "menu": True},
    "optimus":  {"en": "Optimus",  "nl": "Optimus",  "menu": True},
    "factories": {"en": "Factories", "nl": "Fabrieken", "menu": True},
    "xai":      {"en": "xAI / Grok", "nl": "xAI / Grok", "menu": True},
    "energy":   {"en": "Energy",   "nl": "Energie",  "menu": True},
    "spacex":   {"en": "SpaceX",   "nl": "SpaceX",   "menu": True},
    "starlink": {"en": "Starlink", "nl": "Starlink", "menu": True},
    "boring":   {"en": "Boring Co.", "nl": "Boring Co.", "menu": True},
    "musk":     {"en": "Elon Musk", "nl": "Elon Musk", "menu": True},
    "earnings": {"en": "Earnings", "nl": "Cijfers",  "menu": True},
    "guides":   {"en": "Tips",     "nl": "Tips",     "menu": True, "btn": "Tips!"},
    "ecosystem": {"en": "Ecosystem", "nl": "Ecosysteem", "menu": False},
}

# Model pages. "photo" is a file in static/img/models/ (optional until uploaded).
# "article_photo": photo used on articles tagged with this model (current generation).
# "parent": this is a version/generation of the parent model. Its page also lists the parent's
#   articles, the parent page lists its articles, and both show a row of version buttons.
# "label": text on the version button (years are the same in both languages).
MODELS = {
    "model-s":           {"name": "Model S", "menu": "menu-ms21.jpg",            "photo": "ms-1.jpg", "gallery": ["ms-4.jpg", "ms-1.jpg", "ms-3.jpg", "ms-2.jpg"]},
    "model-s-classic":   {"name": "Model S 2012–2020", "menu": "menu-msc.jpg",  "photo": "msc-2.jpg", "parent": "model-s", "gallery": ["msc-2.jpg", "msc-1.jpg", "msc-4.jpg", "msc-3.jpg"], "label": "2012–2020"},
    "model-s-2021":      {"name": "Model S 2021+", "menu": "menu-ms21.jpg",      "photo": "ms-3.jpg", "parent": "model-s", "gallery": ["ms-1.jpg", "ms-3.jpg", "ms-2.jpg", "ms-4.jpg"], "label": "2021+"},
    "model-s-plaid":     {"name": "Model S Plaid", "menu": "menu-msp.jpg",      "photo": "ms-4.jpg", "parent": "model-s", "gallery": ["ms-4.jpg", "ms-3.jpg", "ms-2.jpg"], "label": "Plaid"},
    "model-3":           {"name": "Model 3", "menu": "menu-m3h.jpg",            "photo": "m3h-1.jpg", "gallery": ["m3h-1.jpg", "m3h-4.jpg", "m3h-2.jpg", "m3h-3.jpg", "m3h-5.jpg"]},
    "model-3-classic":   {"name": "Model 3 2017–2023", "menu": "menu-m3c.jpg",  "photo": "m3c-1.jpg", "parent": "model-3", "label": "2017–2023", "gallery": ["m3c-1.jpg", "m3c-5.jpg", "m3c-9.jpg", "m3c-2.jpg", "m3c-6.jpg", "m3c-10.jpg", "m3c-3.jpg", "m3c-7.jpg", "m3c-11.jpg", "m3c-4.jpg", "m3c-8.jpg"]},
    "model-3-highland":  {"name": "Model 3 Highland", "menu": "menu-m3h.jpg",   "photo": "m3h-4.jpg", "parent": "model-3", "label": "Highland · 2023+"},
    "model-3-standard":  {"name": "Model 3 Standard", "menu": "menu-m3s.jpg",   "photo": "m3s-1.jpg", "gallery": ["m3s-1.jpg"], "parent": "model-3", "label": "Standard · 2025+"},
    "model-3-performance": {"name": "Model 3 Performance", "menu": "menu-m3p.jpg", "photo": "m3p-1.jpg", "gallery": ["m3p-1.jpg", "m3p-2.jpg"], "parent": "model-3", "label": "Performance"},
    "model-x":           {"name": "Model X", "menu": "menu-mx21.jpg",            "photo": "mx-2.jpg", "gallery": ["mx-1.jpg", "mx-4.jpg", "mx-5.jpg", "mx-2.jpg", "mx-3.jpg"]},
    "model-x-classic":   {"name": "Model X 2015–2020", "menu": "menu-mxc.jpg",  "photo": "mxc-1.jpg", "gallery": ["mxc-1.jpg"], "parent": "model-x", "label": "2015–2020"},
    "model-x-2021":      {"name": "Model X 2021+", "menu": "menu-mx21.jpg",      "photo": "mx-1.jpg", "parent": "model-x", "label": "2021+"},
    "model-x-plaid":     {"name": "Model X Plaid",      "photo": "mx-5.jpg", "parent": "model-x", "label": "Plaid"},
    "model-y":           {"name": "Model Y", "menu": "menu-myj.jpg",            "photo": "myj-9.jpg", "gallery": ["myj-1.jpg", "myj-9.jpg", "myj-12.jpg", "myj-5.jpg", "myj-2.jpg", "myj-10.jpg", "myj-7.jpg", "myj-3.jpg", "myj-11.jpg", "myj-6.jpg", "myj-8.jpg", "myj-4.jpg"]},
    "model-y-classic":   {"name": "Model Y 2020–2024", "menu": "menu-myc.jpg",  "photo": "myc-1.jpg", "gallery": ["myc-1.jpg", "myc-2.jpg"], "parent": "model-y", "label": "2020–2024"},
    "model-y-juniper":   {"name": "Model Y Juniper", "menu": "menu-myj.jpg",    "photo": "myj-12.jpg", "parent": "model-y", "label": "Juniper · 2025+", "gallery": ["myj-1.jpg", "myj-9.jpg", "myj-12.jpg", "myj-5.jpg", "myj-2.jpg", "myj-10.jpg", "myj-7.jpg", "myj-3.jpg", "myj-11.jpg", "myj-6.jpg", "myj-8.jpg", "myj-4.jpg"]},
    "model-y-standard":  {"name": "Model Y Standard", "menu": "menu-mys.jpg",   "photo": "mys-1.jpg", "gallery": ["mys-1.jpg"], "parent": "model-y", "label": "Standard · 2025+"},
    "model-y-performance": {"name": "Model Y Performance", "menu": "menu-myp.jpg", "photo": "myp-1.jpg", "gallery": ["myp-1.jpg"], "parent": "model-y", "label": "Performance"},
    "model-y-l":         {"name": "Model Y L",          "photo": "myl-1.jpg", "parent": "model-y", "label": {"en": "Model Y L · 6 seats", "nl": "Model Y L · 6 zitplaatsen"}},
    "cybertruck":        {"name": "Cybertruck", "menu": "menu-cybertruck.jpg",         "photo": "ct-3.jpg", "gallery": ["ct-1.jpg", "ct-3.jpg", "ct-2.jpg", "ct-4.jpg", "ct-5.jpg"]},
    "cybertruck-awd":    {"name": "Cybertruck AWD", "menu": "menu-cybertruck.jpg",     "photo": "ct-1.jpg", "parent": "cybertruck", "label": "AWD"},
    "cybertruck-cyberbeast": {"name": "Cyberbeast",     "photo": "cb-1.jpg", "gallery": ["cb-1.jpg", "ct-5.jpg"], "parent": "cybertruck", "label": "Cyberbeast"},
    "cybertruck-foundation": {"name": "Cybertruck Foundation Series", "parent": "cybertruck", "label": "Foundation Series"},
    "cybercab":          {"name": "Cybercab", "menu": "menu-cybercab.jpg",           "photo": "cybercab.jpg", "gallery": ["cybercab.jpg", "cc-1.jpg", "cc-3.jpg", "cc-2.jpg"]},
    "roadster":          {"name": "Roadster",           "photo": "rd-2.jpg", "menu": "menu-roadster.jpg", "gallery": ["rd-1.jpg", "rd-2.jpg", "rd-3.jpg"]},
    "semi":              {"name": "Semi",               "photo": "semi.jpg", "menu": "menu-semi.jpg", "gallery": ["semi.jpg", "semi-4.jpg", "semi-2.jpg", "semi-5.jpg", "semi-3.jpg"]},
}
# Fallback photo per category: a file in static/img/topics/, or a list of files to vary between
# (each article always gets the same one, picked from its slug). Missing files are skipped.
TOPIC_PHOTOS = {
    "robotaxi": ["cybercab-fleet.jpg", "robotaxi-my-1.jpg", "cybercab-street.jpg", "cybercab-interior.jpg", "robotaxi-my-2.jpg", "models/cc-3.jpg", "models/cybercab.jpg"], "fsd": ["fsd.jpg", "models/myj-3.jpg", "fsd-2.jpg", "models/m3c-1.jpg", "fsd-3.jpg", "models/myj-1.jpg", "fsd-4.jpg"], "software": ["interior-2.jpg", "grok-2.jpg", "interior-1.jpg", "fsd.jpg", "grok-1.jpg", "fsd-2.jpg", "fsd-3.jpg", "fsd-4.jpg"], "optimus": ["optimus-army.jpg", "optimus-line.jpg", "optimus.jpg", "optimus-store.jpg", "optimus-factory.jpg", "optimus-full.jpg", "optimus-kitchen.jpg", "optimus-office.jpg", "optimus-garden.jpg"],
    "energy": ["megapack-1.jpg", "energy-3.jpg", "energy.jpg", "energy-5.jpg", "megapack-2.jpg", "energy-2.jpg", "energy-6.jpg", "megapack-3.jpg", "energy-4.jpg"], "charging": ["supercharger.jpg", "supercharger-5.jpg", "supercharger-2.jpg", "supercharger-7.jpg", "charge-port.jpg", "supercharger-3.jpg", "supercharger-4.jpg", "winter-1.jpg", "supercharger-6.jpg"], "ecosystem": ["spacex-1.jpg", "starlink-car-1.jpg", "spacex-2.jpg", "starlink-1.jpg", "spacex-4.jpg", "starlink-car-3.jpg", "spacex-3.jpg", "starlink-2.jpg", "spacex-5.jpg", "starlink-car-2.jpg", "tunnel-2.jpg", "tunnel-3.jpg", "tunnel-4.jpg"], "spacex": ["spacex-1.jpg", "spacex-2.jpg", "spacex-4.jpg", "spacex-3.jpg", "spacex-5.jpg"], "starlink": ["starlink-car-1.jpg", "starlink-1.jpg", "starlink-car-3.jpg", "starlink-2.jpg", "starlink-car-2.jpg"], "xai": ["grok-2.jpg", "grok-1.jpg", "interior-1.jpg"], "boring": ["tunnel-2.jpg", "tunnel-3.jpg", "tunnel-4.jpg", "tunnel-1.jpg"], "earnings": ["earnings-1.jpg", "gigafactory.jpg", "earnings-5.jpg", "earnings-2.jpg", "earnings-6.jpg", "earnings-4.jpg", "earnings-7.jpg", "earnings-3.jpg", "earnings-8.jpg", "models/myj-4.jpg", "gigafactory-3.jpg", "gigafactory-5.jpg", "gigafactory-2.jpg", "models/model-3.jpg", "gigafactory-4.jpg", "models/myj-6.jpg", "gigafactory-6.jpg"], "factories": ["gigafactory-2.jpg", "gigafactory-5.jpg", "gigafactory-3.jpg", "gigafactory-6.jpg", "gigafactory-4.jpg", "gigafactory.jpg", "optimus-factory.jpg", "semi-2.jpg"], "musk": ["earnings-1.jpg", "spacex-2.jpg", "earnings-6.jpg", "gigafactory-4.jpg", "spacex-4.jpg", "earnings-3.jpg", "models/rd-2.jpg"], "news": ["gigafactory.jpg", "models/myj-2.jpg", "gigafactory-4.jpg", "gigafactory-2.jpg", "models/m3c-10.jpg", "gigafactory-6.jpg", "models/myj-5.jpg", "gigafactory-3.jpg", "gigafactory-5.jpg"],
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
               "first and you will be asked for consent where the law requires it.</p>"
               "<p>Saved articles and the articles you liked are stored only in your own browser (local storage), "
               "not on our servers. The like counter itself only keeps a total number per article, without any "
               "information about who liked it.</p>"),
        "nl": ("Privacybeleid", "Hoe TrendingTesla met je gegevens omgaat.",
               "<p>TrendingTesla vraagt je niet om een account aan te maken en verzamelt geen "
               "persoonsgegevens via formulieren.</p>"
               "<p>De site wordt geleverd via Cloudflare, dat technische gegevens zoals "
               "IP-adressen verwerkt om de site te leveren en te beveiligen. Lettertypen komen "
               "van ons eigen domein, niet van derden. We gebruiken op dit moment geen "
               "trackingcookies.</p>"
               "<p>Als we in de toekomst advertenties of statistieken toevoegen, passen we "
               "deze pagina eerst aan en vragen we waar de wet dat vereist om toestemming.</p>" "<p>Bewaarde artikelen en de artikelen die je leuk vond, worden alleen in je eigen browser opgeslagen "
               "(local storage), niet op onze servers. De teller van de vind-ik-leuks houdt alleen een totaal per artikel bij, "
               "zonder gegevens over wie het leuk vond.</p>"),
    },
}

CSS = """
@font-face{font-family:Manrope;font-weight:400;font-display:swap;src:url(/fonts/manrope-latin-400-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:600;font-display:swap;src:url(/fonts/manrope-latin-600-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:700;font-display:swap;src:url(/fonts/manrope-latin-700-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:800;font-display:swap;src:url(/fonts/manrope-latin-800-normal.woff2) format("woff2")}
:root{--bg:#04060a;--surface:#212121;--surface2:#272727;--border:#272727;--border2:#3f3f3f;--fg:#e8eef5;--head:#fff;--muted:#b9c4d2;--dim:#8f9db0;--red:#e22822;--red2:#b81e19;--blue:#00d4ff;--edge:#3a4a60;--blue2:#5fe3ff;--max:1200px;color-scheme:dark}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:150px;background:#04060a}
html,body{overflow-x:clip;max-width:100%}
body{background:linear-gradient(160deg,#2b2b2b 0%,#1d1d1d 35%,#141414 70%,#0f0f0f 100%) top left/100% 520px no-repeat,#0f0f0f;min-height:100vh;color:var(--fg);font:17px/1.42 Manrope,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main,footer{position:relative;z-index:1}
a{color:var(--head)}
img{display:block;max-width:100%;height:auto}
h1,h2,h3{color:#ebebeb;font-weight:800}
.wrap{max-width:var(--max);margin:0 auto;padding:0 12px}
.narrow{max-width:740px;margin:0 auto}
.read{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:13px;align-items:start;margin-top:0}
.grid2{display:grid;grid-template-columns:1fr;gap:13px;margin-top:20px}
.grid2>.card{display:grid;grid-template-columns:254px 1fr;gap:11px;align-items:start}.grid2>.card .body{padding:0;line-height:1}.grid2>.card .body .tag,.grid2>.card .body .meta{line-height:1;vertical-align:top}.grid2>.card h3{font-size:1.12rem;line-height:1.3;margin:8px 0 6px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.grid2>.card p{-webkit-line-clamp:2;line-height:1.42}.grid2>.card .im{height:142px;width:254px}.grid2>.card .im img{height:100%;aspect-ratio:auto}
.grid2 .card{padding:8px;margin:-8px;border-radius:7px;transition:background .15s}
.grid2 .card:hover{background:#272727}.below{margin-top:17px}.below>.tip{margin-top:0}.grid2.gall.wide{grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:22px 16px;margin-top:14px}.wide .empty{grid-column:1/-1}.grid2.gall{grid-template-columns:repeat(3,minmax(0,1fr));gap:18px 14px}.gall>.card{grid-template-columns:1fr;gap:0}.gall>.card .im{width:auto;height:auto}.gall>.card .im img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}.gall>.card .body{padding:8px 0 0;line-height:1.3}.gall>.card h3{font-size:.92rem;margin:0 0 5px;-webkit-line-clamp:3}.gall>.card p{font-size:.8rem;line-height:1.35;-webkit-line-clamp:2;margin-bottom:5px}.gall>.card .meta{font-size:.74rem}
.span2{grid-column:1/-1}.span2 .tip{margin:0}
.read article{padding-top:0}
.rside .rh{font-size:1.15rem;margin:0 0 22px;padding-bottom:12px;border-bottom:1px solid var(--border)}
.sr{position:absolute;left:-9999px}
/* header */
.top{position:sticky;top:0;z-index:40;background:#161616}
.bar{display:flex;align-items:center;gap:14px;height:66px}
.brand{display:flex;align-items:baseline;gap:14px;min-width:0}
.logo{font-weight:800;font-size:1.4rem;letter-spacing:-.02em;color:#ebebeb;text-decoration:none;white-space:nowrap}
.logo span{color:var(--red);font-size:calc(1em + 1px);position:relative;top:1px}
.slogan{font-size:.86rem;font-weight:600;color:var(--muted);white-space:nowrap}
.burger{flex:none;width:40px;height:40px;margin-left:-8px;border-radius:7px;border:0;background:transparent;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;cursor:pointer}
.burger span{width:18px;height:2px;border-radius:2px;background:#ebebeb}
.burger:hover{background:var(--surface2)}
.search{position:relative;flex:1;max-width:520px;margin-left:auto;display:flex}
.search input{flex:1;min-width:0;background:#121212;border:1px solid #303030;border-right:0;border-radius:7px 0 0 7px;color:var(--head);font:inherit;font-size:.92rem;padding:9px 18px;outline:none}
.search input::placeholder{color:var(--dim)}
.search input:focus{border-color:#1c62b9}
.search>button,.sbtn{border:1px solid #303030;background:#222;color:#ebebeb;cursor:pointer;display:grid;place-items:center}
.search>button{border-radius:0 7px 7px 0;width:58px}
.sbtn{display:none;width:40px;height:40px;border-radius:7px;margin-left:auto}
.res{position:absolute;top:calc(100% + 8px);left:0;right:0;background:#212121;border:1px solid var(--border2);border-radius:7px;padding:6px;box-shadow:0 24px 48px rgba(0,0,0,.55);max-height:70vh;overflow:auto;z-index:40}
.res a{display:flex;gap:12px;align-items:center;padding:8px;border-radius:7px;text-decoration:none}
.res a:hover{background:var(--surface2)}
.res img{width:76px;aspect-ratio:1200/630;object-fit:cover;border-radius:7px;flex:none}
.res b{display:block;font-size:.88rem;line-height:1.3;color:var(--head)}
.res small{color:var(--dim);font-size:.74rem}
.res p{padding:10px;color:var(--muted);font-size:.88rem}
.lang{flex:none;font-size:.78rem;font-weight:800;letter-spacing:.05em;color:#ebebeb;text-decoration:none;border:1px solid var(--border2);border-radius:7px;padding:4px 11px;margin-left:6px}
.lang:hover{color:#ebebeb;border-color:#ebebeb}
.scrim{position:fixed;inset:0;z-index:25;background:rgba(0,0,0,.55);opacity:0;pointer-events:none;transition:opacity .25s}
.dopen .scrim{opacity:1;pointer-events:auto}.drawer,.scrim{top:66px}nav.drawer .dh,nav.drawer .dclose{display:none}nav.drawer{padding-top:19px}
.drawer{position:fixed;top:0;bottom:0;left:0;z-index:30;width:290px;max-width:86vw;overflow-y:auto;background:#0f0f0f;border-right:1px solid var(--border);padding:13px 12px 32px;transform:translateX(-102%);transition:transform .25s ease}
.dopen .drawer{transform:none}.dnoanim .drawer,.dnoanim .scrim{transition:none!important}
.drawer{overscroll-behavior:contain}html.dopen,html.dopen body{overflow:hidden}
.drawer .dh{display:flex;align-items:center;gap:12px;padding:0 4px 13px 12px;margin:0 -12px 10px;border-bottom:1px solid var(--border)}
@media (min-width:861px){.drawer,.scrim,.bar .burger{display:none}}
@media (max-width:860px){.rside .cats9,.rside .mnav{display:none}.read.topic .rside{display:none}}
.arch{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:13px;align-items:start}
.archh{margin:6px 0 0}.arch .rside{position:sticky;top:82px}
.pager{display:flex;justify-content:space-between;align-items:center;margin:34px 0 0;font-size:.9rem;color:var(--dim)}
.pager a,.morelink{color:var(--head);text-decoration:none;font-weight:700;background:#272727;border-radius:7px;padding:9px 14px 7px}
.pager a:hover,.morelink:hover{background:#3f3f3f}
.morelink{display:block;text-align:center;margin-top:12px;font-size:.88rem}
.srow{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 14px}.srow .smeta{margin:0;white-space:nowrap}
.acts{display:flex;gap:8px;flex:none}
.act{display:inline-flex;align-items:center;gap:6px;border:0;border-radius:7px;background:#272727;color:#ebebeb;font:inherit;font-size:.82rem;font-weight:700;padding:7px 13px 6px;cursor:pointer;transition:background .15s}
.act:hover{background:#3f3f3f}.act svg{flex:none}
.act.like[aria-pressed=true] svg{fill:#e22822;stroke:#e22822}
.act.save[aria-pressed=true] svg{fill:#ebebeb;stroke:#ebebeb}
.savedlink{position:relative;flex:none;display:grid;place-items:center;width:36px;height:36px;border-radius:7px;color:#ebebeb;margin-left:6px}
.savedlink:hover{background:#272727}
@media (min-width:601px){.brand{transform:translateX(4px)}.savedlink{transform:translateX(16px)}.search{transform:translateX(20px)}}
@media (max-width:600px){.brand{transform:translateX(-8px)}.savedlink{transform:translateX(8px)}.bar .savedlink i{line-height:13px}.sbtn{transform:translateX(16px)}}
.savedlink i{position:absolute;top:3px;right:2px;min-width:14px;height:14px;border-radius:7px;background:var(--red);color:#fff;font:800 .58rem/14px Manrope,sans-serif;font-style:normal;text-align:center;padding:0 3px}
.dtopics{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:0 4px}
.dtopics a{text-align:center;font-size:.84rem;font-weight:700;color:var(--fg);text-decoration:none;background:#272727;border:1px solid #272727;border-radius:7px;padding:10px 6px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dtopics a:hover{background:#3f3f3f;border-color:#3f3f3f;color:var(--head)}
.dtopics a.on{background:#474747;border-color:#5e5e5e;color:#fff}
.dsep{border:0;border-top:1px solid var(--border2);margin:16px 4px}
.dclose{margin-bottom:10px}
.dmodels{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 4px}
.dm{display:flex;flex-direction:column;border:1px solid var(--edge);border-radius:7px;overflow:hidden;text-decoration:none;color:var(--head);background:#0b0b0b;transition:border-color .15s,background .15s}
.dm:hover{border-color:#6b7d95;background:#1a1a1a}
.dm .ph{aspect-ratio:3/2;background:#000;display:flex;align-items:center;justify-content:center}
.dm .ph img{width:100%;height:100%;object-fit:contain}
.dm span{padding:7px 6px 8px;font-size:.78rem;line-height:1.25;font-weight:800;text-align:center}
.drawer h4{font-size:.7rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);margin:20px 10px 6px}
.drawer .di{display:flex;align-items:center;gap:12px;padding:9px 10px;border-radius:7px;color:var(--fg);text-decoration:none;font-weight:700;font-size:.92rem}
.drawer button.di{width:100%;border:0;background:transparent;font:inherit;font-weight:700;font-size:.92rem;text-align:left;cursor:pointer}
.drawer .di:hover{background:var(--surface2);color:var(--head)}
.drawer .di.on{background:var(--surface2);color:var(--head);font-weight:800}
.drawer .di img,.drawer .di i{width:56px;aspect-ratio:1200/630;object-fit:cover;border-radius:7px;border:1px solid var(--edge);flex:none;background:var(--surface)}
.cats9{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:14px}
.cats9 a{text-align:center;font-size:.8rem;font-weight:700;color:var(--fg);text-decoration:none;background:#272727;border:1px solid #272727;border-radius:7px;padding:9px 6px 7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:border-color .2s,color .2s}
.cats9 a:hover{background:#3f3f3f;border-color:#3f3f3f;color:var(--head)}
.cats9 a b,.dtopics a b{font-weight:900}
.cats9 a.on{background:#474747;border-color:#5e5e5e;color:#fff}
.mnav{display:flex;flex-direction:column;gap:14px;margin:16px 0 14px}.mgrp{display:flex;flex-direction:column;gap:6px}.mh{font-size:.74rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--blue);text-decoration:none;padding:0 12px;margin-top:4px}.mh:hover,.mh.on{text-decoration:underline;text-underline-offset:3px}.drawer .mnav{margin:23px 4px 0}
.mcell{display:grid;grid-template-columns:1fr 1fr;gap:7px;align-items:start}
.mopts{display:flex;flex-direction:column;gap:6px}
.mopts a{font-size:.8rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid #3f3f3f;border-radius:7px;padding:5px 6px 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center;transition:background .15s}
.mopts a:hover{background:#3f3f3f;color:var(--head)}.mgrp .mopts{gap:0}.mopts a.vt:nth-child(odd){background:rgba(255,255,255,.025)}.mopts a.vt:nth-child(even){background:transparent}.mopts a.vt:hover{background:rgba(255,255,255,.07)}.mopts a.vt.on{background:#333;border-color:var(--border2)}.mopts a.vt b{border-radius:7px}
.mopts a.on,.mopts a.vt.on{background:#333;border-color:#5a5a5a;color:#fff;font-weight:500}.mopts a.vt{display:flex;align-items:center;gap:14px;padding:5px 12px;text-align:left;font-size:.9rem;font-weight:400;color:var(--fg);border-radius:0;border:0;border-bottom:1px solid var(--border2)}.mopts a.vt b{flex:none;width:74px;height:50px;border-radius:7px;overflow:hidden;background:#000}.mopts a.vt b img{width:100%;height:100%;object-fit:cover;display:block}.mopts a span{overflow:hidden;text-overflow:ellipsis}
.dm.on,.dm.in{border-color:var(--head)}
.specs{width:100%;border-collapse:collapse;margin:6px 0 10px;font-size:.92rem}
.specs th,.specs td{padding:9px 12px;border-bottom:1px solid var(--border2);text-align:left;vertical-align:top}
.specs th{width:38%;color:var(--muted);font-weight:700}
.specs td{color:var(--head)}
.specs tr:nth-child(odd){background:rgba(255,255,255,.025)}
.soon{color:var(--muted);background:var(--surface);border:1px dashed var(--border2);border-radius:7px;padding:14px 16px}
.tip{display:flex;align-items:center;gap:26px;margin-top:17px;padding:22px 26px;border-radius:7px;border:1px solid var(--border2);background:linear-gradient(120deg,rgba(0,212,255,.09),rgba(56,96,255,.05) 55%,rgba(255,255,255,.01))}
.tip .big{font-size:2.6rem;font-weight:800;letter-spacing:-.03em;line-height:1;color:var(--blue);white-space:nowrap}
.tip h2{font-size:1.12rem;line-height:1.25;margin-bottom:4px}
.tip p{color:var(--muted);font-size:.9rem}
.tip .btn{margin-left:auto;flex:none}
.tip{text-decoration:none;color:var(--fg);transition:background .15s,border-color .15s}.tip:hover{background:linear-gradient(120deg,rgba(0,212,255,.16),rgba(56,96,255,.09) 55%,rgba(255,255,255,.04));border-color:#4a5a70}.tip:hover .btn{background:var(--red2)}
.home{margin-top:0}
article .st{font-size:clamp(1.05rem,2vw,1.3rem);line-height:1.22;letter-spacing:-.015em;margin:0 0 6px}
.st a{color:inherit;text-decoration:none}
.smeta{margin:0 0 14px;font-size:.88rem}.smeta a.tag{color:var(--blue)}.smeta a.tag:hover{color:var(--blue2)}
.sideh{font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:var(--blue);margin:11px 0 -2px;padding-top:9px;border-top:1px solid var(--border2)}
.hi,.th,.im{position:relative}.hi{margin:0 0 8px}.hi .hero-img{margin:0}
.dur{display:inline-flex;align-items:center;gap:4px;position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.8);color:#fff;font-size:.74rem;font-weight:700;line-height:1;padding:4px 6px;border-radius:7px;cursor:help}.th .dur{right:6px;bottom:6px;font-size:.68rem;padding:3px 5px}.th .dur svg{width:12px;height:12px}
/* buttons, labels */
.btn{display:inline-flex;align-items:center;justify-content:center;background:var(--red);color:#fff;font-weight:800;font-size:.9rem;padding:11px 20px;border-radius:7px;text-decoration:none;transition:background .2s}
.btn:hover{background:var(--red2)}
.btn.ghost{background:transparent;border:1px solid var(--border2);color:var(--head)}
.btn.ghost:hover{border-color:var(--head);background:transparent}
.tag{display:inline-block;font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;text-decoration:none;color:var(--blue)}
.meta{font-size:.8rem;color:var(--dim)}
.h2{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:24px 0 11px}
.h2 h2{font-size:clamp(1.3rem,2.6vw,1.75rem);letter-spacing:-.02em;line-height:1.2}
.h2 a{font-size:.86rem;font-weight:700;color:var(--muted);text-decoration:none;white-space:nowrap}
.h2 a:hover{color:var(--head)}
.sub{color:var(--muted);font-size:.92rem;margin:-8px 0 16px}
/* hero */
.hero{position:relative;overflow:hidden;border-radius:7px;background:radial-gradient(ellipse at 85% 40%,rgba(0,212,255,.14),transparent 60%),linear-gradient(135deg,#0b1320,#04060a);min-height:340px;margin-top:24px;display:flex;align-items:center}
.hero img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center right}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(4,6,10,.96) 0%,rgba(4,6,10,.7) 45%,rgba(4,6,10,.12) 100%)}
.hero .in{position:relative;z-index:2;max-width:520px;padding:36px 32px}
.eyebrow{display:inline-block;font-size:.7rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--blue);border:1px solid rgba(0,212,255,.35);background:rgba(0,212,255,.1);padding:4px 11px;border-radius:7px;margin-bottom:14px}
.hero h1{font-size:clamp(1.8rem,4vw,2.7rem);line-height:1.08;letter-spacing:-.025em;margin-bottom:12px}
.hero h1 span{color:var(--red)}
.hero p{color:#c9ced3;font-size:1rem;margin-bottom:20px}
#news .h2{margin-top:18px}
.hero .btns{display:flex;gap:10px;flex-wrap:wrap}
/* top stories */
.tops{display:grid;grid-template-columns:1.6fr 1fr;gap:44px}
.feature{text-decoration:none;color:var(--fg);display:block}
.feature .im,.card .im{overflow:hidden;border-radius:7px;border:1px solid var(--edge);background:var(--surface);transition:border-color .2s}

.feature img,.card img{width:100%;aspect-ratio:1200/630;object-fit:cover;transition:transform .4s}

.feature h3{font-size:clamp(1.4rem,2.8vw,2rem);line-height:1.15;letter-spacing:-.02em;margin:14px 0 8px}
.feature p{color:var(--muted);margin-bottom:8px}
.side{display:flex;flex-direction:column;gap:10px}
.mini{display:grid;grid-template-columns:calc((100% - 26px) * 2 / 3 + 7px) 1fr;gap:8px;text-decoration:none;color:var(--fg);align-items:start;box-sizing:border-box}.mini>div{overflow:hidden}
.th{width:100%}.mini img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:7px;border:1px solid var(--edge)}
.mini{padding:6px;margin:-6px;border-radius:7px;transition:background .15s}.mini:hover{background:#272727}.mini>div{padding:2px 4px 2px 0}
.mini h3{font-size:.98rem;line-height:1.3;margin:6px 0 4px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.mini .tag{display:block;line-height:1;margin-top:0}

/* grid */
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:56px 64px}
.card{text-decoration:none;color:var(--fg);display:flex;flex-direction:column}
.card.lead{grid-column:span 2}
.leadside{display:flex;flex-direction:column;justify-content:space-between;gap:28px}
.leadside .card p{display:none}
.leadside .card .body{padding-top:12px}
.leadside .card h3{font-size:1rem;margin-bottom:0}
.card.lead h3{font-size:clamp(1.35rem,2.4vw,1.85rem);line-height:1.2;letter-spacing:-.02em}
.card.lead p{font-size:1rem;-webkit-line-clamp:2}
.card .body{padding:18px 4px 0}
.card h3{font-size:1.08rem;line-height:1.3;margin:6px 0 6px}.card h3{font-weight:700;color:#ebebeb}.grid2>.card h3{font-size:1rem}.mini h3{font-weight:700;font-size:.9rem;color:#ebebeb}.mini h3{margin-top:0}.mdesc{color:var(--muted);font-size:.8rem;line-height:1.35;margin:0 0 4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.mini .meta{font-size:.74rem}
.card p{color:var(--muted);font-size:.9rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.empty{color:var(--muted);background:var(--surface);border:1px dashed var(--border2);border-radius:7px;padding:28px;text-align:center}
/* models */
.models{display:grid;grid-template-columns:repeat(7,1fr);gap:24px}
.model{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--edge);border-radius:7px;overflow:hidden;text-decoration:none;color:var(--head);transition:border-color .2s,transform .2s}
.model:hover{border-color:var(--blue);transform:translateY(-3px)}
.model .ph{aspect-ratio:3/2;background:#000;display:flex;align-items:center;justify-content:center}
.model img{width:100%;height:100%;object-fit:contain}
.model .ph b{font-size:1.5rem;color:#2a3544;letter-spacing:-.02em}
.model span{padding:10px 8px;font-size:.82rem;line-height:1.3;font-weight:800;text-align:center}
/* why */
.why{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.why div{background:var(--surface);border:1px solid var(--border);border-radius:7px;padding:20px}
.why i{display:inline-flex;width:32px;height:32px;border-radius:7px;background:rgba(0,212,255,.12);align-items:center;justify-content:center;color:var(--blue);font-weight:800;font-style:normal;margin-bottom:10px}
.why b{display:block;color:var(--head);font-size:.98rem;margin-bottom:4px}
.why p{font-size:.86rem;color:var(--muted)}
/* page heads */
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.ptop{height:36px}
.phead{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:36px 0 22px;border-bottom:1px solid var(--border);margin-bottom:28px}
.versions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:30px}
.versions span{font-size:.8rem;font-weight:700;color:var(--dim);margin-right:4px}
.versions a{font-size:.84rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid var(--border2);border-radius:7px;padding:6px 13px;transition:border-color .2s,color .2s}
.versions a:hover{color:var(--head);border-color:var(--blue)}
.versions a.on{color:#03131a;background:var(--blue);border-color:var(--blue)}
.phead h1{font-size:clamp(2rem,5vw,3rem);letter-spacing:-.03em;line-height:1.05}
.phead p{color:var(--muted);margin-top:6px}
.phead img{width:min(420px,45%);flex:none;border-radius:7px;border:1px solid var(--edge)}
/* article */
article{padding:36px 0 8px}
article h1{font-size:clamp(1.8rem,4.6vw,2.6rem);line-height:1.12;letter-spacing:-.025em;margin:10px 0 14px}
article .lead{font-size:1.02rem;line-height:1.38;color:var(--muted);margin:0 0 22px}
article .hero-img{border-radius:7px;margin:0 0 26px;aspect-ratio:1200/630;width:100%;object-fit:cover;border:1px solid var(--edge)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:-8px 0 24px}
.chips a{font-size:.78rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid var(--border2);border-radius:7px;padding:3px 10px}
.chips a:hover{color:var(--head);border-color:var(--head)}
.prose h2{font-size:1.15rem;line-height:1.3;letter-spacing:-.015em;margin:40px 0 12px}
article .prose{font-size:15px}article .prose,article .lead{max-width:680px}article .prose{line-height:1.65}.prose p,.prose ul,.prose ol{margin-bottom:22px}
.prose ul,.prose ol{padding-left:22px}
.prose li{margin-bottom:8px}
.prose li::marker{color:var(--blue)}
.prose a{color:var(--blue2)}
.prose em{color:var(--muted)}
.prose strong{color:var(--head)}
.sources{margin-top:13px;font-size:.88rem}
.sources summary{display:inline-flex;align-items:center;gap:6px;cursor:pointer;list-style:none;font-size:.74rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--blue);user-select:none}
.sources summary::-webkit-details-marker{display:none}
.sources summary::after{content:"▾";font-size:.9rem;transition:transform .2s}
.sources[open] summary::after{transform:rotate(180deg)}
.sources summary:hover{color:var(--blue2)}
.sources ul{margin-top:10px;padding:12px 16px 12px 32px;background:var(--surface);border-radius:7px}
.sources li{margin-bottom:4px}
.sources a{color:var(--muted)}
/* footer */
footer{border-top:1px solid var(--border);margin-top:14px;padding:15px 0 40px;font-size:.85rem;color:var(--dim)}
footer .fgrid{display:grid;grid-template-columns:1.4fr 1.3fr 1.3fr .8fr;gap:40px}
footer a{color:var(--muted);text-decoration:none}
footer a:hover{color:var(--head)}
footer h4{font-size:.7rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--blue);margin:6px 0 12px}
footer .flist{display:grid;gap:7px 18px}footer .flist.two{grid-template-columns:1fr 1fr}
footer .fbrand p{margin-top:12px;max-width:340px;line-height:1.5}
footer .fcopy{margin-top:32px;padding-top:18px;border-top:1px solid var(--border)}
@media (max-width:1000px){.grid{grid-template-columns:repeat(2,1fr);gap:48px 40px}.leadside{grid-column:span 2;flex-direction:row}.leadside .card{flex:1}.tops{grid-template-columns:1fr}.read,.arch{grid-template-columns:1fr;gap:36px}.why{grid-template-columns:repeat(2,1fr)}.models{grid-template-columns:repeat(4,1fr);gap:20px}}
@media (max-width:860px){.search{display:none}.sbtn{display:grid}.sopen .search{display:flex;position:absolute;left:16px;right:16px;top:12px;max-width:none;z-index:41}.sopen .search input{background:#121212}.tip{flex-wrap:wrap;gap:14px 20px}.tip .btn{margin-left:0}}
@media (max-width:860px){footer .fgrid{grid-template-columns:1fr 1fr;gap:28px}footer .fbrand{grid-column:1/-1}}
@media (max-width:600px){.wrap{padding:0 12px}
.bar{gap:4px;height:56px}.drawer,.scrim{top:56px}.burger{margin-left:-14px}.logo{font-size:1.15rem}.brand{margin-left:2px}
.sbtn{margin-left:auto;width:36px;height:36px;border:0;background:transparent}.savedlink{margin-left:-2px;width:34px;height:34px}.lang{margin-left:0;margin-right:-10px;font-size:.7rem;padding:3px 9px}
.read .hi{margin:0 -12px 6px}.read .hi .hero-img{border-radius:0;border:0}.hi .dur{right:12px}
article .st{font-size:1rem;line-height:1.25}.srow{flex-wrap:wrap;gap:8px}.srow .acts{display:contents}.srow .smeta{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}article .lead{font-size:.95rem}.smeta{font-size:.82rem}
article .prose{font-size:15px}article .prose h2{font-size:.98rem}.grid2{grid-template-columns:1fr;gap:59px}.grid2.gall{grid-template-columns:1fr;gap:40px}.gall>.card h3{font-size:1rem}.gall>.card p{font-size:.9rem}.side{gap:29px}.grid2>.card{grid-template-columns:1fr;gap:0}.grid2>.card .im{height:auto;width:auto}.grid2>.card .im img{aspect-ratio:1200/630}.grid2>.card .body{padding:7px 0 0}.card.lead{grid-column:auto}.leadside{grid-column:auto;flex-direction:column;gap:40px}.leadside .card p{display:-webkit-box}.mini{grid-template-columns:1fr;gap:6px;height:auto}.mini>div{height:auto}.th{width:100%;height:auto}.mini img{width:100%;height:auto;aspect-ratio:1200/630}#news .h2{margin-top:16px}.grid{grid-template-columns:1fr;gap:40px}.why{grid-template-columns:1fr 1fr;gap:10px}.why div{padding:14px}.why p{font-size:.8rem}
 .models{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;margin:0 -24px;padding:0 24px 4px}.models::-webkit-scrollbar{display:none}.models{gap:14px}.model{flex:0 0 46%;scroll-snap-align:start}
 body{font-size:16.5px}.h2{margin-top:20px}.hero{min-height:0}.hero .in{padding:26px 20px}.hero .btn{flex:1;white-space:nowrap;padding:11px 12px}
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


# Coarse scene per photo, so neighbouring articles never show the same kind of background.
SCENES = [
    (r"^models/m3c-([1-4])\.jpg$", "highway"), (r"^models/m3c-([5-8])\.jpg$", "city"), (r"^models/m3c-(9|10|11)\.jpg$", "sunset"),
    (r"^models/myj-[126]\.jpg$", "city"), (r"^models/myj-[345]\.jpg$", "sunset"),
    (r"^models/ct-[14]\.jpg$", "city"), (r"^models/ct-2\.jpg$", "sunset"), (r"^models/ct-[35]\.jpg$", "desert"),
    (r"^models/cc-\d\.jpg$", "city"), (r"^models/rd-1\.jpg$", "sky"), (r"^models/rd-[23]\.jpg$", "sunset"),
    (r"^models/mx-[12]", "sunset"), (r"^models/mx-3", "trees"), (r"^models/mx-4", "countryside"), (r"^models/mx-5", "night"), (r"^models/msc-1", "village"), (r"^models/msc-2", "hills"), (r"^models/msc-3", "beach"), (r"^models/msc-4", "sunset"), (r"^models/ms-1", "village"), (r"^models/ms-2", "trees"), (r"^models/ms-3", "night"), (r"^models/ms-4", "sunset"), (r"^models/m3h-1", "night"), (r"^models/m3h-2", "street"), (r"^models/m3h-3", "autumn"), (r"^models/m3h-[45]", "coast"), (r"^models/m3p", "track"), (r"^models/myc-1", "polder"), (r"^models/myj-10", "street"), (r"^models/myj-11", "mountain"), (r"^models/myj-12", "rain"), (r"^models/myl", "street"), (r"^models/myj-7", "forest"), (r"^models/myj-8", "spring"), (r"^models/myj-9", "polder"), (r"^models/cc-3", "sunset"), (r"^models/semi", "sunset"), (r"^models/", "studio"),
    (r"^topics/gigafactory-[56]", "aerial"), (r"^topics/gigafactory-4", "sunset"), (r"^topics/earnings-[5-8]", "dashboard"), (r"^topics/earnings-1", "screen-dark"), (r"^topics/earnings", "stage"), (r"^topics/(gigafactory)", "factory"), (r"^topics/(fsd|grok)", "interior"), (r"^topics/(spacex|starlink-\d)", "space"),
    (r"^topics/starlink-car", "nightsky"), (r"^topics/tunnel", "tunnel"), (r"^topics/wallbox-[23]", "homecar"), (r"^topics/wallbox", "wallbox"), (r"^topics/supercharger-[456]", "charging-night"), (r"^topics/(winter|charge-port)", "winter"), (r"^topics/interior", "cabin"), (r"^topics/robotaxi-my", "city"), (r"^topics/cybercab-interior", "cabin"), (r"^topics/supercharger", "charging"),
    (r"^topics/megapack-1", "hills"), (r"^topics/megapack-2", "desert"), (r"^topics/megapack-3", "studio"), (r"^topics/energy-[34]", "sunset"), (r"^topics/energy-6", "desert"), (r"^topics/energy", "energy"), (r"^topics/optimus-(store|kitchen|office|garden)", "optimus-place"), (r"^topics/optimus-factory", "optimus-factory"), (r"^topics/optimus", "optimus"), (r"^topics/cybercab", "robotaxi"),
    (r"^topics/roadster", "sky"),
]
CHOSEN = {}  # slug -> chosen image path (set in build)


def scene_of(path):
    rel = path.split("/img/", 1)[-1]
    for pat, sc in SCENES:
        if re.search(pat, rel):
            return sc
    return rel


def candidates(a):
    """All suitable photos for an article, preferred first, rotated per article."""
    out = []
    if a.get("image") and (STATIC / "img" / a["image"]).exists():
        out.append(f"/img/{a['image']}")
    for k in a.get("models", []):
        m = MODELS[k]
        gal = m.get("gallery") or MODELS.get(m.get("parent", ""), {}).get("gallery") or []
        gal = [f"/img/models/{g}" for g in gal if (STATIC / "img" / "models" / g).exists()]
        if gal:
            r = GALLERY_ORDER.get(a["slug"], 0) % len(gal)
            out += gal[r:] + gal[:r]
        elif model_photo(k, True):
            out.append(model_photo(k, True))
        if out:
            break
    f = TOPIC_PHOTOS.get(a["category"])
    files = [x if "/" in x else f"topics/{x}" for x in ([f] if isinstance(f, str) else (f or []))]
    files = [x for x in files if (STATIC / "img" / x).exists()]
    if files:
        r = PHOTO_ORDER.get(a["slug"], 0) % len(files)
        out += [f"/img/{x}" for x in files[r:] + files[:r]]
    out.append(f"/img/v/{a['slug']}.jpg")
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def assign_photos(arts):
    """Oldest first: each article avoids the photo and the scene of the 3 articles before it, so on
    the site (newest first, 3 per row) no photo or background repeats next to or directly above another."""
    hist, cat_hist = [], {}
    for a in sorted(arts, key=published):
        cands = candidates(a)
        photos = [c for c in cands if not c.startswith("/img/v/")]
        # neighbours on the homepage (all articles) and on the category / model pages
        groups = [a["category"]] + [MODELS[k].get("parent") or k for k in a.get("models", [])]
        local = [h for g in groups for h in cat_hist.get(g, [])[-3:]]
        recent_files = [h[0] for h in hist[-4:]] + [h[0] for h in local]
        recent_scenes = [h[1] for h in hist[-3:]] + [h[1] for h in local]
        own = f"/img/{a['image']}" if a.get("image") and (STATIC / "img" / a["image"]).exists() else None
        pick = (own if own and own not in recent_files else None) \
            or next((c for c in photos if c not in recent_files and scene_of(c) not in recent_scenes), None) \
            or next((c for c in photos if c not in recent_files), None) \
            or (photos[0] if photos else cands[-1])
        CHOSEN[a["slug"]] = pick
        hist.append((pick, scene_of(pick)))
        for g in groups:
            cat_hist.setdefault(g, []).append((pick, scene_of(pick)))


GALLERY_ORDER = {}  # slug -> position among articles sharing the same first model (set in build)
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
    """Photo shown for an article on the site (chosen in assign_photos)."""
    return CHOSEN.get(a["slug"]) or candidates(a)[0]


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
    fcats = "".join(f'<a href="{url(lang, "category/" + k + "/")}">{c[lang]}</a>' for k, c in CATEGORIES.items() if c["menu"])
    fmods = "".join(f'<a href="{url(lang, "model/" + k + "/")}">{MODELS[k]["name"]}</a>' for k in MODEL_ROOTS)
    cats = " · ".join(f'<a href="{url(lang, "category/" + k + "/")}">{c[lang]}</a>' for k, c in CATEGORIES.items() if c["menu"])
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
<div class="bar"><button class="burger" type="button" aria-label="{L['menu']}" aria-expanded="false" aria-controls="drawer"><span></span><span></span><span></span></button>
<div class="brand"><a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a></div>
<form class="search" role="search" action="{url(lang)}" data-idx="/search-{lang}.json" data-none="{L['none']}"><input type="search" name="q" placeholder="{L['search']}" aria-label="{L['search']}" autocomplete="off"><button type="submit" aria-label="{L['search']}">{SEARCH_SVG}</button><div class="res" hidden></div></form>
<button class="sbtn" type="button" aria-label="{L['search']}">{SEARCH_SVG}</button>
<a class="savedlink" href="{url(lang, 'saved/')}" title="{L['saved']}" aria-label="{L['saved']}">{BOOK_SVG}<i hidden></i></a>
<a class="lang" href="{url(alt, path)}" hreflang="{alt}" lang="{alt}" title="{L['switch_full']}">{L['switch']}</a></div>
</div></header>
<div class="scrim"></div>
<nav id="drawer" class="drawer" aria-label="{L['menu']}">{drawer(lang, active, path.strip("/").split("/")[1] if path.strip("/").startswith("model/") else None)}</nav>
<main class="wrap">
{body}
</main>
<footer><div class="wrap"><div class="fgrid">
<div class="fbrand"><a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a><p>{L['tagline']} {L['disclaimer']}</p></div>
<div><h4>{L['d_topics']}</h4><div class="flist two">{fcats}</div></div>
<div><h4>{L['d_models']}</h4><div class="flist two">{fmods}</div></div>
<div><h4>{L['d_more']}</h4><div class="flist"><a href="{url(lang, 'archive/')}">{L['archive']}</a><a href="{url(lang, 'about/')}">{L['about']}</a><a href="{url(lang, 'privacy/')}">{L['privacy']}</a><a href="{url(lang, 'feed.xml')}">RSS</a><a href="{url(alt, path)}">{L['switch_full']}</a></div></div>
</div><p class="fcopy">&copy; {datetime.now().year} {NAME}</p></div></footer>
<script>{JS}</script>
</body>
</html>
"""


SEARCH_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/></svg>'
HEART_SVG = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.4 4.5 7 4.5c2 0 3.6 1.1 5 2.9 1.4-1.8 3-2.9 5-2.9 3.6 0 5.6 3.5 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z"/></svg>'
BOOK_SVG = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"><path d="M6 3.5h12v17l-6-4.2-6 4.2z"/></svg>'
DRAWER_MODELS = MODEL_STRIP + ["cybercab", "semi", "roadster"]


def drawer(lang, active=None, model=None):
    active = menu_key(active)
    L = LANGS[lang]
    out = (f'<div class="dh"><button class="burger" type="button" aria-label="{L["menu"]}"><span></span><span></span><span></span></button>'
           f'<a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a></div>'
           f'<button class="di dclose" type="button">‹ {L["collapse"]}</button><div class="mobonly"><div class="dtopics">')
    out += "".join(f'<a class="{"on" if k == active else ""}" href="{url(lang, "category/" + k + "/")}">{btn_label(c, lang)}</a>'
                   for k, c in CATEGORIES.items() if c["menu"])
    out += f'</div><hr class="dsep"></div>'
    out += modelnav(lang, model if model in MODELS else None)
    return out


def story(a, lang, tag="h1"):
    """Full article block: photo, title, intro, meta, model chips, body and sources."""
    L = LANGS[lang]
    t = a[lang]
    c = CATEGORIES[a["category"]]
    src = ""
    if a.get("sources"):
        items = "".join(f'<li><a href="{esc(s["url"])}" rel="nofollow noopener" target="_blank">{esc(s["title"])}</a></li>'
                        for s in a["sources"])
        src = f'<details class="sources"><summary>{L["sources"]} ({len(a["sources"])})</summary><ul>{items}</ul></details>'
    chips = ""
    if a.get("models"):
        chips = '<div class="chips">' + "".join(
            f'<a href="{url(lang, "model/" + k + "/")}">Tesla {MODELS[k]["name"]}</a>' for k in a["models"]) + "</div>"
    title = esc(t["title"]) if tag == "h1" else f'<a href="{url(lang, a["slug"] + "/")}">{esc(t["title"])}</a>'
    return (f'<article>'
            f'<div class="hi"><img class="hero-img" src="{site_img(a)}" alt="{esc(t["title"])}" width="1200" height="630" fetchpriority="high">{dur(a, lang)}</div>'
            f'<{tag} class="st">{title}</{tag}>'
            f'<div class="srow"><p class="meta smeta"><a class="tag" href="{url(lang, "category/" + a["category"] + "/")}">{c.get("tag", c[lang])}</a> · {fmt_date(a["date"], lang)}</p>'
            f'<div class="acts"><button class="act like" type="button" data-like="{a["slug"]}" aria-pressed="false" title="{L["like"]}">{HEART_SVG}<span>0</span></button>'
            f'<button class="act save" type="button" data-save="{a["slug"]}" aria-pressed="false" title="{L["save"]}" aria-label="{L["save"]}">{BOOK_SVG}</button></div></div>'
            f'<p class="lead">{esc(t["description"])}</p>'
            f'<div class="prose">{t["body"]}</div>{src}</article>')


ALL_ARTS = []
ARCH_PAGES = [1]


MODEL_ROOTS = ["model-s", "model-3", "model-x", "model-y", "cybertruck", "cybercab", "semi", "roadster"]


def modelnav(lang, current=None):
    """Models with their versions: a model header with a bar (photo + type/year) per version."""
    cur_root = (MODELS[current].get("parent") or current) if current else None
    ov = {"en": "Overview", "nl": "Overzicht"}[lang]
    rows = ""
    for r in MODEL_ROOTS:
        kids = [(k, v) for k, v in MODELS.items() if v.get("parent") == r]
        items = []
        for k, v in kids:
            lbl = v["label"][lang] if isinstance(v["label"], dict) else v["label"]
            items.append((k, lbl.split(" · ")[0], v.get("menu")))
        if not items:
            items = [(r, ov, MODELS[r].get("menu"))]
        bars = ""
        for k, lbl, img in items:
            th = f'<img src="/img/models/{img}" alt="" loading="lazy">' if img else ""
            bars += f'<a href="{url(lang, "model/" + k + "/")}" class="vt{" on" if k == current else ""}"><b>{th}</b><span>{esc(lbl)}</span></a>'
        st = " on" if current == r else (" in" if cur_root == r else "")
        rows += (f'<div class="mgrp"><a class="mh{st}" href="{url(lang, "model/" + r + "/")}">{MODELS[r]["name"]}</a>'
                 f'<div class="mopts">{bars}</div></div>')
    return f'<nav class="mnav" aria-label="Models">{rows}</nav>'


def modelinfo(key, lang):
    L = LANGS[lang]
    inf = INFO.get(key)
    if not inf:
        return ""
    t = inf[lang]
    ph = model_photo(key)
    img = f'<div class="hi"><img class="hero-img" src="{ph}" alt="Tesla {MODELS[key]["name"]}" width="1200" height="630" fetchpriority="high"></div>' if ph else ""
    rows = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in t["specs"])
    li = lambda xs: "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in xs) + "</ul>"
    src = "".join(f'<li><a href="{esc(u)}"{"" if u.startswith("/") else " rel=nofollow target=_blank"}>{esc(ti)}</a></li>'
                  for ti, u in inf["sources"])
    return (f'<article class="minfo">{img}<h1 class="st">Tesla {MODELS[key]["name"]}</h1><p class="lead">{esc(t["intro"])}</p>'
            f'<div class="prose"><h2>{L["i_specs"]}</h2><table class="specs">{rows}</table>'
            f'<h2>{L["i_watch"]}</h2>{li(t["watch"])}<h2>{L["i_special"]}</h2>{li(t["special"])}'
            f'<h2>{L["i_acc"]}</h2><p class="soon">{L["i_acc_soon"]}</p></div>'
            f'<details class="sources"><summary>{L["sources"]} ({len(inf["sources"])})</summary><ul>{src}</ul></details></article>')


NEAR_CATS = {"robotaxi": ["fsd", "models"], "fsd": ["robotaxi", "software"], "software": ["fsd", "guides"],
             "charging": ["energy", "guides"], "energy": ["charging", "earnings"], "earnings": ["news", "energy"],
             "news": ["earnings", "models"], "models": ["guides", "news"], "guides": ["models", "charging"],
             "optimus": ["spacex", "earnings"], "ecosystem": ["spacex", "starlink"],
             "spacex": ["starlink", "earnings"], "starlink": ["spacex", "robotaxi"], "xai": ["software", "fsd"], "boring": ["robotaxi", "spacex"], "factories": ["news", "earnings"], "musk": ["earnings", "spacex"]}
ECO = ("spacex", "starlink", "xai", "boring", "ecosystem")


def rank_for(items, cat=None, model=None):
    """Other articles ranked by relevance to a topic page or model page (not already in `items`)."""
    own = set(id(x) for x in items)
    fam = lambda x: {MODELS[k].get("parent") or k for k in x.get("models", [])}
    mods = set().union(*(fam(x) for x in items)) if items else set()
    root = (MODELS[model].get("parent") or model) if model else None
    terms = set().union(*(_terms(x) for x in items[:12])) if items else set()
    near = NEAR_CATS.get(cat or "models", [])
    def score(x):
        sc = 0
        if root and root in fam(x):
            sc += 6
        if model and model in x.get("models", []):
            sc += 4
        sc += 2 * len(mods & fam(x))
        if x["category"] in near:
            sc += (1 if root else 3 - near.index(x["category"]))
        if root and MODELS[root]["name"].lower() in (x["en"]["title"] + " " + x["en"]["description"]).lower():
            sc += 5
        sc += min(len(terms & _terms(x)), 4)
        return (sc, published(x))
    return sorted((x for x in ALL_ARTS if id(x) not in own), key=score, reverse=True)


def listing(items, lang, active=None, model=None):
    """Topic/model page: lead (newest article, or the model info) on the left, all articles of this topic or
    model in the two columns below it, then related ones; the right column is the general newest news."""
    L = LANGS[lang]
    if not items and not (model and INFO.get(model)):
        return f'<p class="empty">{L["empty"]}</p>'
    extra = modelnav(lang, model) if (active == "models" or model) else ""
    info = model and INFO.get(model)
    lead = None if info else items[0]
    own = items if info else items[1:]
    if active == "news":
        return feed(lead, story(lead, lang, "h2"), own, lang, active, L["latest"], extra_side=extra)
    rest = [x for x in ALL_ARTS if x is not lead]
    own = sorted(own, key=published, reverse=True)
    return feed(lead, modelinfo(model, lang) if info else story(lead, lang, "h2"), rest, lang,
                "models" if model else active, L["latest"], extra_side=extra, left_exact=own,
                lead_px=1500 if info else None)


def btn_label(c, lang):
    return f'<b>{c["btn"]}</b>' if c.get("btn") else c[lang]


def menu_key(active):
    """Every page highlights one topic button; pages outside the menu fall back to News."""
    return active if active in CATEGORIES and CATEGORIES[active]["menu"] else "news"


def cats9(lang, active=None):
    active = menu_key(active)
    return '<nav class="cats9" aria-label="Topics">' + "".join(
        f'<a href="{url(lang, "category/" + k + "/")}"{" class=\"on\"" if k == active else ""}>{btn_label(c, lang)}</a>'
        for k, c in CATEGORIES.items() if c["menu"]) + '</nav>'


def tips(lang):
    L = LANGS[lang]
    allt = [("11 kW", L["tip_h"], L["tip_p"], L["tip_btn"], "tesla-home-charging-guide-11-kw-wall-connector")] + L["tips"]
    return [f'<a class="tip" href="{url(lang, slug + "/")}"><div class="big">{b}</div><div><h2>{h}</h2><p>{t}</p></div>'
            f'<span class="btn">{btn} →</span></a>' for b, h, t, btn, slug in allt]


def tip(lang, i=0):
    return tips(lang)[i % len(tips(lang))]


def words(a, lang):
    return len(re.sub(r"<[^>]+>", " ", a[lang]["body"]).split())


ROW_PX = 168
MAX_LEFT = 24   # articles in the list under the lead
MAX_RIGHT = 50  # articles in the news column
PER_PAGE = 36   # articles per archive page


def feed(lead, lead_html, rest, lang, active=None, side_title="", left_first=(), more=(), extra_side="", lead_px=None, left_pool=None, min_left=0, left_exact=None, no_left=False):
    """YouTube-style page: lead story open on the left with a two-column grid of further articles
    below it (an ad/tip bar every few rows); a long list of the newest articles on the right."""
    # balance column heights (pixel estimates measured on the live layout)
    left_first, more = list(left_first), list(more)
    n_own = len(rest)
    rest = list(rest) + more
    n = len(rest) + len(left_first)
    story_px = lead_px if lead_px else 960 + 2.6 * words(lead, lang) + 170
    best, diff = 0, None
    for left in range(0, n + 1):
        h_left = story_px + (40 + left * ROW_PX + ((left - 1) // 6) * 168 if left else 0)
        if (more and n - left < n_own) or left < min_left:
            continue
        h_right = 170 + (1450 if extra_side else 0) + (n - left) * 144 + (60 if more and n - left > n_own else 0)
        d = abs(h_left - h_right)
        if diff is None or d < diff:
            best, diff = left, d
    if left_exact is not None:
        left_items = list(left_exact)
        right_items = [x for x in rest if x not in left_items]
        need = (len(left_items) * ROW_PX + story_px) / 144
        if len(right_items) < need:  # long topic list: let the general news continue so both columns end together
            right_items += [x for x in rest if x in left_items][: int(need) - len(right_items) + 1]
    elif left_pool is not None:
        left_items = list(left_pool[:best])
        left_items.sort(key=published, reverse=True)  # always newest first
        right_items = [x for x in rest if x not in left_items][:n - best]
    else:
        best = max(best, len(left_first))
        right_items, left_items = rest[:n - best], left_first + rest[n - best:]
    if left_exact is not None and active != "news":
        # topic, model and article pages: the 6 most relevant articles open the right column,
        # followed without a heading by the general news
        rel = list(left_items[:6])
        right_items = rel + [x for x in right_items if x not in rel]
    if no_left:
        right_items, left_items = list(rest), []
    more_link = ""
    topic = left_exact is not None and active != "news"
    if len(left_items) > MAX_LEFT and not topic:
        left_items = left_items[:MAX_LEFT]
        more_link = f'<a class="morelink" href="{url(lang, "archive/")}">{LANGS[lang]["archive"]} →</a>'
    right_items = right_items[:MAX_RIGHT]
    tl = tips(lang)
    g, ti = "", 1
    for i, a in enumerate(left_items):
        if i and i % (12 if topic else 6) == 0:
            g += f'<div class="span2">{tl[ti % len(tl)]}</div>'
            ti += 1
        g += gcard(a, lang) if topic else card(a, lang)
    side = "".join(mini(a, lang) for a in right_items[:n_own] if more) if more else "".join(mini(a, lang) for a in right_items)
    if more and len(right_items) > n_own:
        side += f'<h2 class="sideh">{CATEGORIES["news"][lang]}</h2>' + "".join(mini(a, lang) for a in right_items[n_own:])
    grid = (f'<div class="grid2 gall wide">{g}</div>' if topic else f'<div class=grid2>{g}</div>') if g else ""
    return (f'<section class="read home{" topic" if topic else ""}"><div class="lcol">{lead_html}</div>'
            f'<aside class="rside">{cats9(lang, active)}{extra_side}<h2 class="sr">{side_title}</h2><div class="side">{side}</div>'
            f'<a class="morelink" href="{url(lang, "archive/")}">{LANGS[lang]["archive"]} →</a></aside></section>'
            f'<section class="below">{tl[0]}{grid}{more_link}</section>')


JS = r"""(function(){var d=document.documentElement,o=document.querySelector('.scrim');
function t(x){d.classList.toggle('dopen',x);document.querySelectorAll('.burger').forEach(function(b){b.setAttribute('aria-expanded',x)})}
document.querySelectorAll('.burger').forEach(function(b){b.onclick=function(){t(!d.classList.contains('dopen'))}});
o.onclick=function(){t(false)};(function(){var dr=document.querySelector('.drawer'),x0=null,y0=0;if(!dr)return;
dr.addEventListener('touchstart',function(e){x0=e.touches[0].clientX;y0=e.touches[0].clientY},{passive:true});
dr.addEventListener('touchend',function(e){if(x0===null)return;var dx=e.changedTouches[0].clientX-x0,dy=e.changedTouches[0].clientY-y0;x0=null;
if(dx<-60&&Math.abs(dx)>Math.abs(dy)*1.5)t(false)},{passive:true})})();document.querySelectorAll('.dclose').forEach(function(b){b.onclick=function(){t(false)}});
document.querySelectorAll('.drawer .dtopics a[href$="/category/models/"]').forEach(function(a){a.addEventListener('click',function(){try{sessionStorage.setItem('tt_dm','1')}catch(_){}})});
(function(){var k=null;try{k=sessionStorage.getItem('tt_dm');sessionStorage.removeItem('tt_dm')}catch(_){}
if(k&&window.matchMedia('(max-width:860px)').matches){d.classList.add('dnoanim');t(true);
requestAnimationFrame(function(){requestAnimationFrame(function(){d.classList.remove('dnoanim')})})}})();
document.addEventListener('keydown',function(e){if(e.key==='Escape'){t(false);d.classList.remove('sopen')}});
var f=document.querySelector('.search'),i=f.querySelector('input'),r=f.querySelector('.res'),idx=null;
function e(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function load(){return idx?Promise.resolve(idx):fetch(f.dataset.idx).then(function(x){return x.json()}).then(function(j){idx=j;return j})}
i.addEventListener('focus',load);
i.addEventListener('input',function(){var q=i.value.trim().toLowerCase();if(q.length<2){r.hidden=true;return}
load().then(function(){var w=q.split(/\s+/),h=idx.filter(function(a){var s=(a.t+' '+a.d+' '+a.c).toLowerCase();return w.every(function(x){return s.indexOf(x)>-1})}).slice(0,8);
r.innerHTML=h.length?h.map(function(a){return '<a href="'+a.u+'"><img src="'+a.i+'" alt=""><span><b>'+e(a.t)+'</b><small>'+e(a.c)+' · '+e(a.dt)+'</small></span></a>'}).join(''):'<p>'+e(f.dataset.none)+'</p>';r.hidden=false})});
f.addEventListener('submit',function(x){x.preventDefault();var a=r.querySelector('a');if(a)location.href=a.href});
document.addEventListener('click',function(x){if(!f.contains(x.target)&&!x.target.closest('.sbtn')){r.hidden=true;d.classList.remove('sopen')}});
document.querySelector('.sbtn').onclick=function(){d.classList.add('sopen');i.focus()};
function fill(){[].slice.call(document.querySelectorAll('.grid2>.card')).forEach(function(c){var h=c.querySelector('h3'),p=c.querySelector('p');if(!h||!p)return;p.style.webkitLineClamp='';var n=Math.round(h.getBoundingClientRect().height/parseFloat(getComputedStyle(h).lineHeight));if(getComputedStyle(c).gridTemplateColumns.split(' ').length>1)p.style.webkitLineClamp=Math.max(2,5-n)})}
function bal(){fill();var l=document.querySelector('.read .lcol'),r=document.querySelector('.read .rside');if(!l||!r)return;
var all=[].slice.call(document.querySelectorAll('.rside .side>*,.lcol .grid2>*'));all.forEach(function(x){x.style.display=''});
if(getComputedStyle(l.parentNode).gridTemplateColumns.split(' ').length<2)return;
var lb=l.getBoundingClientRect().bottom,rb=r.getBoundingClientRect().bottom;
if(rb>lb){[].slice.call(r.querySelectorAll('.side>*')).forEach(function(x){if(x.getBoundingClientRect().bottom>lb+4)x.style.display='none'})}
else if(!l.querySelector('.gall')){var g=[].slice.call(l.querySelectorAll('.grid2>*'));for(var k=g.length-1;k>=0;k--){if(g[k].getBoundingClientRect().top>rb)g[k].style.display='none'}
var v=g.filter(function(x){return x.style.display!=='none'&&!x.classList.contains('span2')});var last=v[v.length-1];
}}
window.addEventListener('load',bal);
var LS={get:function(k){try{return JSON.parse(localStorage.getItem(k)||'[]')}catch(e){return []}},set:function(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
var sv=document.querySelector('.savedlink i');function badge(){var n=LS.get('tt_saved').length;if(sv){sv.hidden=!n;sv.textContent=n}}badge();
var SAVE=document.documentElement.lang==='nl'?['Bewaren','Bewaard']:['Save','Saved'];
document.querySelectorAll('[data-save]').forEach(function(b){var s=b.dataset.save;function st(){var on=LS.get('tt_saved').indexOf(s)>-1;b.setAttribute('aria-pressed',on);b.title=SAVE[on?1:0];b.setAttribute('aria-label',SAVE[on?1:0])}st();
b.onclick=function(){var l=LS.get('tt_saved'),i=l.indexOf(s);if(i>-1)l.splice(i,1);else l.unshift(s);LS.set('tt_saved',l);st();badge()}});
var lb=[].slice.call(document.querySelectorAll('[data-like]'));if(lb.length){var liked=LS.get('tt_liked');
fetch('/api/likes?s='+lb.map(function(b){return b.dataset.like}).join(',')).then(function(r){return r.json()}).then(function(j){lb.forEach(function(b){var n=j[b.dataset.like]||0;b.querySelector('span').textContent=n})}).catch(function(){});
lb.forEach(function(b){var s=b.dataset.like;b.setAttribute('aria-pressed',liked.indexOf(s)>-1);b.onclick=function(){var l=LS.get('tt_liked'),i=l.indexOf(s),d=i>-1?-1:1;if(d>0)l.push(s);else l.splice(i,1);LS.set('tt_liked',l);b.setAttribute('aria-pressed',d>0);
var sp=b.querySelector('span');sp.textContent=Math.max(0,(+sp.textContent||0)+d);fetch('/api/likes',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({slug:s,d:d})}).then(function(r){return r.json()}).then(function(j){if(j.n!=null)sp.textContent=j.n}).catch(function(){})}})}
var sl=document.querySelector('.savedlist');if(sl){var keep=LS.get('tt_saved');if(!keep.length){sl.innerHTML='<p class="empty">'+e(sl.dataset.empty)+'</p>'}else{load().then(function(){var m={};idx.forEach(function(a){var k=a.u.replace(/\/$/,'').split('/').pop();m[k]=a});
sl.innerHTML=keep.filter(function(k){return m[k]}).map(function(k){var a=m[k];return '<a class="card" href="'+a.u+'"><div class="im"><img src="'+a.i+'" alt=""></div><div class="body"><h3>'+e(a.t)+'</h3><p>'+e(a.d)+'</p><span class="meta">'+e(a.dt)+'</span></div></a>'}).join('')})}}window.addEventListener('resize',bal);bal();
})();"""


def label(a, lang):
    return f'<span class="tag">{CATEGORIES[a["category"]].get("tag", CATEGORIES[a["category"]][lang])}</span>'


def card(a, lang, lead=False):
    t = a[lang]
    cls = "card lead" if lead else "card"
    return (f'<a class="{cls}" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="im"><img src="{site_img(a)}" alt="" width="1200" height="630" loading="lazy" decoding="async">{dur(a, lang)}</div>'
            f'<div class="body">{label(a, lang)} <span class="meta">· {fmt_date(a["date"], lang)}</span>'
            f'<h3>{esc(t["title"])}</h3><p>{esc(t["description"])}</p></div></a>')


def gcard(a, lang):
    """Topic list under the lead: photo on top, then title, summary and date."""
    t = a[lang]
    return (f'<a class="card" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="im"><img src="{site_img(a)}" alt="" width="1200" height="630" loading="lazy" decoding="async">{dur(a, lang)}</div>'
            f'<div class="body"><h3>{esc(t["title"])}</h3><p>{esc(t["description"])}</p>'
            f'<span class="meta">{fmt_date(a["date"], lang)}</span></div></a>')


def dur(a, lang):
    secs = max(10, round(len(html.unescape(re.sub(r"<[^>]+>", " ", a[lang]["body"])).split()) / 220 * 60))
    lbl = {"en": "Reading time", "nl": "Leestijd"}[lang]
    return (f'<span class="dur" title="{lbl}" aria-label="{lbl}: {-(-secs // 60)} min">'
            f'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<path d="M2 4h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7z"/></svg>'
            f'{-(-secs // 60)} min</span>')


def mini(a, lang):
    t = a[lang]
    return (f'<a class="mini" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="th"><img src="{site_img(a)}" alt="" width="1200" height="630" loading="lazy" decoding="async">{dur(a, lang)}</div>'
            f'<div><h3>{esc(t["title"])}</h3><p class="mdesc">{esc(t["description"])}</p><span class="meta">{fmt_date(a["date"], lang)}</span></div></a>')


def grid(items, lang, lead=False):
    """lead=True: the newest article spans the two left columns, top left of the page, with the next
    two articles stacked in the right column so it lines up with the lead."""
    if lead and len(items) >= 3:
        top = (f'<div class="grid leadrow">{card(items[0], lang, True)}'
               f'<div class="leadside">{card(items[1], lang)}{card(items[2], lang)}</div></div>')
        rest = items[3:]
        return top + (f'<div class="grid" style="margin-top:56px">{"".join(card(a, lang) for a in rest)}</div>' if rest else "")
    return f'<div class="grid">{"".join(card(a, lang, lead and i == 0) for i, a in enumerate(items))}</div>'


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


STOP = set("the a an and or of to in on for with is are be by at as from its it this that what how why new now tesla tesla's "
           "de het een en of van in op voor met is zijn bij als uit naar dit dat wat hoe waarom nieuwe nu model models".split())


def _terms(x):
    return {w for w in re.findall(r"[a-z0-9]+", (x["en"]["title"] + " " + x["en"]["description"]).lower())
            if len(w) > 2 and w not in STOP}


def related(a, arts, n=3):
    """Most relevant other articles: shared models (incl. model family), same topic, shared title words."""
    fam = lambda x: {MODELS[k].get("parent") or k for k in x.get("models", [])}
    ms, mf, ta = set(a.get("models", [])), fam(a), _terms(a)
    def score(x):
        sc = 4 * len(ms & set(x.get("models", []))) + 2 * len(mf & fam(x)) + 3 * (x["category"] == a["category"])
        sc += min(len(ta & _terms(x)), 5)
        return (sc, published(x))
    return sorted((x for x in arts if x is not a), key=score, reverse=True)[:n]


def build():
    arts = load_articles()
    ALL_ARTS[:] = arts
    seen = {}
    for x in sorted(arts, key=published):
        PHOTO_ORDER[x["slug"]] = seen.get(x["category"], 0)
        seen[x["category"]] = PHOTO_ORDER[x["slug"]] + 1
        if x.get("models"):
            gk = "g:" + (MODELS[x["models"][0]].get("parent") or x["models"][0])
            GALLERY_ORDER[x["slug"]] = seen.get(gk, 0)
            seen[gk] = GALLERY_ORDER[x["slug"]] + 1
    assign_photos(arts)
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
        body = f'<h1 class="sr">{NAME} — {L["tagline"]}</h1>'
        if news:
            top = news[0]
            body += feed(top, story(top, lang, "h2"), [a for a in arts if a is not top], lang, "news", L["latest"], no_left=True)
        else:
            body += section(L["latest"], f'<p class="empty">{L["empty"]}</p>', anchor="news")
        body += section(L["why_h"], why(lang))
        write(url(lang), page(lang, "", NAME, L["tagline"], body))

        # ---------- Category pages ----------
        for key, c in CATEGORIES.items():
            items = arts if key == "news" else [a for a in arts if a["category"] == key or (key == "ecosystem" and a["category"] in ECO)]
            if key == "news":
                items = news
            intro = L["eco_intro"] if key in ECO else L["cat_intro"].format(c[lang])
            head = f'<h1 class="sr">{c[lang]}</h1>'
            content = listing(items, lang, key)
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
            head = f'<h1 class="sr">Tesla {m["name"]}</h1>'
            content = listing(items, lang, model=key)
            write(url(lang, f"model/{key}/"),
                  page(lang, f"model/{key}/", f"Tesla {m['name']}", L["model_intro"].format(m["name"]), head + content,
                       image=ph, active="models"))

        # ---------- Articles ----------
        for a in arts:
            t = a[lang]
            c = CATEGORIES[a["category"]]
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
            same = sorted((x for x in arts if x is not a and x["category"] == a["category"]), key=published, reverse=True)
            others = [x for x in arts if x is not a]
            body = feed(a, story(a, lang), others, lang, a["category"], L["latest"], left_exact=same)
            write(url(lang, a["slug"] + "/"),
                  page(lang, a["slug"] + "/", t["title"], t["description"], body, "article", head,
                       image=social_img(a, lang), active=a["category"]))

        idx = [{"u": url(lang, x["slug"] + "/"), "t": x[lang]["title"], "d": x[lang]["description"],
                "c": CATEGORIES[x["category"]].get("tag", CATEGORIES[x["category"]][lang]), "dt": fmt_date(x["date"], lang), "i": site_img(x)} for x in arts]
        (OUT / f"search-{lang}.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        # ---------- Archive: all articles, newest first, paginated ----------
        pages = max(1, -(-len(arts) // PER_PAGE))
        for pi in range(pages):
            chunk = arts[pi * PER_PAGE:(pi + 1) * PER_PAGE]
            path = "archive/" if pi == 0 else f"archive/{pi + 1}/"
            prev = url(lang, "archive/" if pi == 1 else f"archive/{pi}/") if pi else ""
            nxt = url(lang, f"archive/{pi + 2}/") if pi + 1 < pages else ""
            left = f'<a href="{prev}">← {L["newer"]}</a>' if prev else "<span></span>"
            right = f'<a href="{nxt}">{L["older"]} →</a>' if nxt else "<span></span>"
            pager = f'<nav class="pager">{left}<span>{L["page"]} {pi + 1} / {pages}</span>{right}</nav>'
            title = L["archive"] + (f' · {L["page"]} {pi + 1}' if pi else "")
            body = (f'<section class="wide"><h1 class="st archh">{title}</h1><div class="grid2 gall wide">'
                    + "".join(gcard(a, lang) for a in chunk) + f'</div>{pager}</section>')
            write(url(lang, path), page(lang, path, title, L["tagline"], body, active="news"))
        ARCH_PAGES[0] = pages

        # ---------- Saved articles (filled in the browser from localStorage) ----------
        body = (f'<section class="wide"><h1 class="st archh">{L["saved"]}</h1>'
                f'<div class="grid2 gall wide savedlist" data-empty="{esc(L["saved_empty"])}"></div></section>')
        write(url(lang, "saved/"), page(lang, "saved/", L["saved"], L["saved"], body).replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1))

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
               + [(k + "/", today) for k in PAGES]
               + [("archive/" if i == 0 else f"archive/{i + 1}/", today) for i in range(ARCH_PAGES[0])])
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
