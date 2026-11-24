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
  "date": "2026-10-21",                            # real publication date (YYYY-MM-DD, Europe/Amsterdam); never backdate
  "time": "07:00",                                 # real publication time (HH:MM, Europe/Amsterdam); optional
  "updated": "2026-10-22T09:30:00+01:00",          # optional; only after a real edit of the body, not for a video or a rebuild
  "category": "earnings",                          # key from CATEGORIES below
  "models": ["model-y"],                           # optional: keys from MODELS below the article is about
  "also": ["optimus"],                             # optional: extra categories where the article also appears
  "also_topics": ["falcon"],                       # optional: extra topic hubs; the primary topic stays the breadcrumb
  "image": "topics/optimus.jpg",                   # optional: specific photo (path inside static/img/)
  "sources": [{"title": "...", "url": "https://..."}],
  "en": {"title": "...", "description": "...", "body": "<p>...</p>"},
  "nl": {"title": "...", "description": "...", "body": "<p>...</p>"},
  "products": [                                # optional; omit the key when there is nothing to link.
    {"name": {"en": "...", "nl": "..."}, "why": {"en": "...", "nl": "..."},
     "asin": "B0XXXXXXXX",                       # amazon.nl only. A full https://www.amazon.nl/dp/ URL also works.
     "ali_url": "https://s.click.aliexpress.com/e/example",  # optional. s.click.aliexpress.com or aliexpress.com only.
     "image": "/img/topics/example.jpg"}         # optional local photo. Never a hotlinked store image.
  ]                                               # A dated price is added from content/product-prices.json when it is under 24 hours old.
}
A string may be used instead of {"en", "nl"} when the text is the same in both languages.
tools/check_article.py ignores "products". Ads and affiliate tags come from
content/monetization.json and stay hidden while those values are empty. The optional
footer newsletter form uses that file too and stays hidden while its action
URL is empty. Article pages show a compact bar that posts to the MailerLite form
(double opt-in). The right rail uses that same form in place of the topic list.
That rail form is hidden while the rail stacks under the story (max-width 900px),
so a phone keeps only the bar. /newsletter/ (Dutch: /nl/nieuwsbrief/) keeps the
full embed and leaves that rail slot empty. Dutch pages keep Dutch headings.
The "Handy for your Tesla" box is separate: content/affiliate.json holds amazon_nl_tag,
amazon_com_tag and a search-link catalog. The live account is an amazon.nl Associates tag,
so both English and Dutch pages link to amazon.nl and use amazon_nl_tag. A .com tag would
not be credited on amazon.nl, and amazon_com_tag stays empty until that store has its own
account. An empty amazon_nl_tag omits the box and the Amazon section on About and Privacy.
Writing rule (articles and video scripts): the paragraph or spoken text right before a heading
states the next problem as a plain statement and never ends with a question; the <h2>/"head"
itself is the question. (The build also drops such a duplicate question automatically.)
Heading style: write "What to watch for next" / "What should we watch for next?", never "What should
we watch next?" (that sounds like the video is ending and suggesting another video). Start one or two
headings per article with "So" ("So how does ...?", NL "Dus ..." or "... dan?") so it sounds natural
when spoken; not every heading.
Generated photo (optional, see tools/gen_image.py): "gen_image": {"prompt", "subject", "refs", "describe"}.
Right after publishing, the video workflow makes a new photo with Nano Banana from 1-3 reference photos of the
REAL subject and uses it on the site and in the videos (falls back to the normal photos on any problem).
Rules: refs show exactly the same product and version (never mix e.g. Supercharger V3 and V4, or two car
generations); prefer real photos (Wikimedia Commons via {"commons": "search words"}, Tesla press photos via
{"src": "https://...", "page": "..."}) or our photos marked as real in PHOTOS.md, never ones marked AI-made;
describe how the subject is really built and placed (e.g. "one charger post at the head end of each bay, cars
reversed in"); the scene is illustrative, never a fake documentary photo of the news event itself (no crash,
fire, arrest or real person). Skip "gen_image" for news about one specific car model (its real photos are used).
Guides (buying advice) use category "guides"; they appear in the "Best picks" section
and on the model pages they are tagged with.

Weekly briefings are markdown files in content/briefings/. A file whose name starts with
_ is not published, including the layout sample. template: true is also left out of the build.
Promises are rows in content/data/promises.json. The _example object is not rendered.
Buying-guide markdown lives in content/guides/. A file whose name starts with _ is not
published unless TT_EXAMPLES=1, which is only for a local preview.
Ad slots render only when ADS_ENABLED is true. Leave it false. The AdSense loader stays
deferred. public/ads.txt is written from the publisher id in content/monetization.json.

Run: python3 build.py   (needs Pillow: pip install --break-system-packages pillow)
"""
import hashlib
import html
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from covers import make_cover
from model_info import INFO
from model_pages import PAGE_FACTS

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content" / "articles"
STATIC = ROOT / "static"
OUT = ROOT / "public"
SITE = "https://trendingtesla.com"
NAME = "TrendingTesla"
# Author shown on articles and in NewsArticle JSON-LD. An organization, never a named person.
EDITORIAL_ORG = {"en": "TrendingTesla editorial team", "nl": "Redactie TrendingTesla"}
TZ = ZoneInfo("Europe/Amsterdam")

LANGS = {
    "en": {
        "prefix": "", "locale": "en_US",
        "tagline": "The Tesla ecosystem and the AI race, explained.",
        "home_desc": "TrendingTesla follows Tesla, FSD, Robotaxi, Optimus, SpaceX, Starship, Starlink, SpaceXSI, Neuralink, The Boring Company and the global AI race.",
        "scope": "Tesla, FSD, Robotaxi, Optimus, SpaceX, Starlink, SpaceXSI, Neuralink and the AI race.",
        "eyebrow": "Tesla news & honest advice",
        "hero_h": "Everything about your Tesla", "hero_span": "Without the hype",
        "hero_p": "The most important Tesla news, once a day, explained in plain language. Plus honest buying advice for your model.",
        "btn_news": "Latest news", "btn_model": "Choose your model",
        "latest": "Latest news", "more": "More news", "top": "Top story",
        "models_h": "News and advice for your model", "guides_h": "Best picks for your Tesla",
        "guides_sub": "Researched per model and year, with pros and cons.",
        "related": "Read next", "sources": "Sources", "about": "About", "editorial": "Editorial policy",
        "byline": "By the TrendingTesla editorial team", "privacy": "Privacy",
        "switch": "NL", "switch_full": "Nederlands", "i_specs": "Specifications", "i_watch": "Points to watch", "i_special": "What makes it special", "i_acc": "Accessories", "i_acc_soon": "Coming soon: accessories that fit this version, tested and explained.", "slogan": "Daily Tesla news &amp; trends", "nav_eco": "Ecosystem", "nav_tesla": "Tesla", "search": "Search TrendingTesla", "none": "Nothing found", "home": "Home", "toc": "On this page", "prev": "Previous", "next": "Next", "ad": "Advertisement", "videos": "Shorts", "see_all": "See all", "read_story": "Read the story", "nav_models": "Tesla models", "nav_energy": "Energy", "nav_fsd": "FSD / Robotaxi", "nav_space": "SpaceX / Starlink", "nav_xai": "xAI", "nav_more": "More", "start_here": "Start here", "start_p": "Guides that stay useful: practical explainers for owning and buying a Tesla.", "all_guides": "All guides", "articles": "Articles", "cookie": "Cookie settings", "news_h": "One email a week with the best explainers", "news_p": "One email a week with the best explainers. Unsubscribe any time.", "news_btn": "Subscribe", "news_email": "Email address", "bar_h": "The weekly briefing, in one email", "bar_ok": "Check your inbox to confirm", "bar_err": "Could not subscribe. Please try again.", "bar_fine": "Unsubscribe any time.", "signup": "Newsletter", "signup_h": "Get the TrendingTesla newsletter", "signup_lead": "One email a week with the best explainers. Double opt-in, and you can unsubscribe from any email.", "signup_fallback": "Open the newsletter form", "signup_desc": "One email a week with the best explainers. Double opt-in, and you can unsubscribe from any email.", "aff": "Affiliate disclosure: if you buy through this link, TrendingTesla may earn a commission, at no extra cost to you.", "aff_btn": "More info Amazon", "handy_h": "Handy for your Tesla", "handy_p": "A few accessories owners look for. Each link opens an Amazon.nl search, not one specific product.", "handy_note": "As an Amazon Associate we earn from qualifying purchases.", "watch": "Watch the video", "watch_short": "Watch the Short", "consent_p": "Visit counts are cookieless and anonymous. Consent is only for ads. YouTube loads when you press play.", "consent_yes": "Accept", "consent_no": "Refuse", "consent_more": "Privacy policy", "collapse": "Close menu", "like": "Like", "save": "Save", "saved_btn": "Saved", "saved": "Saved articles", "saved_empty": "You have not saved any articles yet. Tap Save under an article title to keep it here. Saved articles stay in this browser on this device.", "archive": "All news", "newer": "Newer", "older": "Older", "page": "Page", "d_topics": "Topics", "d_models": "Models", "d_more": "More", "menu": "Menu", "tip_h": "A 22 kW charger won't charge your Tesla any faster", "tip_p": "Most Tesla models charge at home at up to 11 kW AC.", "tip_btn": "Read why", "tips": [("HW4", "Buying a used Model 3? Check the hardware first", "The Highland has HW4, older cars HW3. It decides what FSD can do.", "How to check", "used-model-3-highland-vs-classic-hw3-hw4-buying-guide"), ("−20%", "Losing range in winter? It doesn't have to be", "Preconditioning and the right settings save you kilometers.", "9 winter tips", "tesla-winter-range-tips-cold-weather")],
        "empty": "No articles here yet. A new story is published once a day.",
        "cat_intro": "All TrendingTesla articles about {}.",
        "eco_intro": "Tesla, SpaceX, Starlink, SpaceXSI, Neuralink, The Boring Company and the global AI race, on one map.",
        "model_intro": "News, updates and advice for the Tesla {}.",
        "model_guides": "Advice for the {}", "model_news": "{} news",
        "all_versions": "All versions", "your_version": "Your version:",
        "notfound": "Page not found", "notfound_text": "This page does not exist (anymore).",
        "back": "Back to the homepage", "min": "min read", "all": "All news",
        "why_h": "Honest news, no sales talk",
        "why": [("Once a day", "We follow Tesla news around the clock and publish one story a day."),
                ("Explained, not copied", "Our own articles: what happened, why it matters and what to watch."),
                ("Sources included", "Every article links to the sources we used, so you can check them."),
                ("Always free", "If you buy through our links we may earn a small commission, at no extra cost to you.")],
        "imgnote": "Images are illustrations; some are made with AI.", "photocredit": "Photos", "imgnote_other": "Other images are illustrations; some are made with AI.",
        "disclaimer": "TrendingTesla is an independent site and is not affiliated with Tesla, SpaceX, SpaceXSI, Neuralink or The Boring Company. Nothing on this site is financial advice.",
        "months": ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"],
    },
    "nl": {
        "prefix": "/nl", "locale": "nl_NL",
        "tagline": "Het Tesla-ecosysteem en de AI-race, helder uitgelegd.",
        "home_desc": "TrendingTesla volgt Tesla, FSD, Robotaxi, Optimus, SpaceX, Starship, Starlink, SpaceXSI, Neuralink, The Boring Company en de wereldwijde AI-race.",
        "scope": "Tesla, FSD, Robotaxi, Optimus, SpaceX, Starlink, SpaceXSI, Neuralink en de AI-race.",
        "eyebrow": "Tesla-nieuws & eerlijk advies",
        "hero_h": "Alles over jouw Tesla", "hero_span": "Zonder de hype",
        "hero_p": "Het belangrijkste Tesla-nieuws, één keer per dag helder uitgelegd. Plus eerlijk koopadvies voor jouw model.",
        "btn_news": "Laatste nieuws", "btn_model": "Kies je model",
        "latest": "Laatste nieuws", "more": "Meer nieuws", "top": "Hoofdverhaal",
        "models_h": "Nieuws en advies voor jouw model", "guides_h": "De beste keuzes voor je Tesla",
        "guides_sub": "Uitgezocht per model en bouwjaar, met plus- en minpunten.",
        "related": "Lees ook", "sources": "Bronnen", "imgnote": "Afbeeldingen zijn illustraties, deels gemaakt met AI.", "photocredit": "Foto's", "imgnote_other": "Overige afbeeldingen zijn illustraties, deels gemaakt met AI.", "about": "Over ons", "editorial": "Redactiebeleid",
        "byline": "Door de redactie van TrendingTesla", "privacy": "Privacy",
        "switch": "EN", "switch_full": "English", "i_specs": "Specificaties", "i_watch": "Aandachtspunten", "i_special": "Bijzonderheden", "i_acc": "Accessoires", "i_acc_soon": "Binnenkort: accessoires die op deze uitvoering passen, getest en uitgelegd.", "slogan": "Iedere dag het laatste nieuws &amp; trends", "nav_eco": "Ecosysteem", "nav_tesla": "Tesla", "search": "Zoek op TrendingTesla", "none": "Niets gevonden", "home": "Home", "toc": "Op deze pagina", "prev": "Vorig", "next": "Volgend", "ad": "Advertentie", "videos": "Shorts", "see_all": "Alles bekijken", "read_story": "Lees het verhaal", "nav_models": "Tesla-modellen", "nav_energy": "Energie", "nav_fsd": "FSD / Robotaxi", "nav_space": "SpaceX / Starlink", "nav_xai": "xAI", "nav_more": "Meer", "start_here": "Begin hier", "start_p": "Gidsen die bruikbaar blijven: praktische uitleg voor wie een Tesla heeft of er een wil kopen.", "all_guides": "Alle gidsen", "articles": "Artikelen", "cookie": "Cookie-instellingen", "news_h": "Eén mail per week met de beste uitleg", "news_p": "Eén mail per week met de beste uitleg. Afmelden kan altijd.", "news_btn": "Aanmelden", "news_email": "E-mailadres", "bar_h": "De weekbriefing, in één mail", "bar_ok": "Check je inbox om te bevestigen", "bar_err": "Aanmelden is niet gelukt. Probeer het opnieuw.", "bar_fine": "Afmelden kan altijd.", "signup": "Nieuwsbrief", "signup_h": "Ontvang de TrendingTesla-nieuwsbrief", "signup_lead": "Eén mail per week met de beste uitleg. Dubbele bevestiging, en afmelden kan vanuit elke e-mail.", "signup_fallback": "Open het nieuwsbriefformulier", "signup_desc": "Eén mail per week met de beste uitleg. Dubbele bevestiging, en afmelden kan vanuit elke e-mail.", "aff": "Affiliate-melding: koop je via deze link, dan kan TrendingTesla een commissie ontvangen. Voor jou kost het niets extra.", "aff_btn": "Meer info Amazon", "handy_h": "Handig voor je Tesla", "handy_p": "Een paar accessoires waar rijders naar zoeken. Elke link opent een zoekopdracht bij Amazon.nl, niet één specifiek product.", "handy_note": "Als Amazon-partner verdienen wij aan in aanmerking komende aankopen.", "watch": "Bekijk de video", "watch_short": "Bekijk de Short", "consent_p": "Bezoekcijfers zijn anoniem en zonder cookies. Toestemming is alleen voor advertenties. YouTube laadt pas als je op afspelen drukt.", "consent_yes": "Accepteren", "consent_no": "Weigeren", "consent_more": "Privacybeleid", "collapse": "Inklappen", "like": "Vind ik leuk", "save": "Bewaren", "saved_btn": "Bewaard", "saved": "Bewaarde artikelen", "saved_empty": "Je hebt nog geen artikelen bewaard. Tik op Bewaren onder de titel van een artikel om het hier terug te vinden. Bewaarde artikelen blijven in deze browser op dit apparaat.", "archive": "Alle nieuws", "newer": "Nieuwer", "older": "Ouder", "page": "Pagina", "d_topics": "Onderwerpen", "d_models": "Modellen", "d_more": "Meer", "menu": "Menu", "tip_h": "Een 22 kW-laadpaal laadt je Tesla niet sneller", "tip_p": "Veel Tesla-modellen laden thuis met maximaal 11 kW AC.", "tip_btn": "Lees waarom", "tips": [("HW4", "Tweedehands Model 3 kopen? Check eerst de hardware", "De Highland heeft HW4, oudere Model 3's HW3. Dat bepaalt wat FSD kan.", "Zo check je het", "used-model-3-highland-vs-classic-hw3-hw4-buying-guide"), ("−20%", "Minder bereik in de winter? Dat hoeft niet", "Met voorverwarmen en de juiste instellingen houd je meer kilometers over.", "9 wintertips", "tesla-winter-range-tips-cold-weather")],
        "empty": "Hier staan nog geen artikelen. Er verschijnt één keer per dag een nieuw verhaal.",
        "cat_intro": "Alle artikelen van TrendingTesla over {}.",
        "eco_intro": "Tesla, SpaceX, Starlink, SpaceXSI, Neuralink, The Boring Company en de wereldwijde AI-race, op één kaart.",
        "model_intro": "Nieuws, updates en advies voor de Tesla {}.",
        "model_guides": "Advies voor de {}", "model_news": "Nieuws over de {}",
        "all_versions": "Alle versies", "your_version": "Jouw versie:",
        "notfound": "Pagina niet gevonden", "notfound_text": "Deze pagina bestaat niet (meer).",
        "back": "Terug naar de homepagina", "min": "min lezen", "all": "Al het nieuws",
        "why_h": "Eerlijk nieuws, geen verkooppraatjes",
        "why": [("Eén keer per dag", "We volgen het Tesla-nieuws de klok rond en publiceren één verhaal per dag."),
                ("Uitgelegd, niet overgeschreven", "Eigen artikelen: wat er gebeurde, waarom het ertoe doet en waar je op moet letten."),
                ("Met bronnen", "Elk artikel linkt naar de bronnen die we gebruikten, zodat je ze kunt controleren."),
                ("Altijd gratis", "Koop je via onze links, dan krijgen wij mogelijk een kleine commissie. Jij betaalt niets extra.")],
        "disclaimer": "TrendingTesla is een onafhankelijke site en is niet verbonden aan Tesla, SpaceX, SpaceXSI, Neuralink of The Boring Company. Niets op deze site is financieel advies.",
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
    "boring":   {"en": "Boring Co", "nl": "Boring Co", "menu": True},
    "musk":     {"en": "Elon Musk", "nl": "Elon Musk", "menu": True},
    "earnings": {"en": "Earnings", "nl": "Cijfers",  "menu": True},
    "guides":   {"en": "Guides",  "nl": "Gidsen",   "menu": True},
    "ecosystem": {"en": "Ecosystem", "nl": "Ecosysteem", "menu": False},
}

# Visible intro on each category hub. One or two sentences, no prices, no personal names.
CAT_INTRO = {
    "news": {
        "en": "The daily Tesla story in plain language: what changed, why it matters, and what to watch next.",
        "nl": "Het dagelijkse Tesla-verhaal in gewone taal: wat er veranderde, waarom het ertoe doet en waar je op moet letten.",
    },
    "models": {
        "en": "News and practical advice for every Tesla on the road, from Model S and Model 3 to Cybertruck, Cybercab, Semi and Roadster.",
        "nl": "Nieuws en praktisch advies voor elke Tesla op de weg, van Model S en Model 3 tot Cybertruck, Cybercab, Semi en Roadster.",
    },
    "charging": {
        "en": "Home charging, Superchargers and what it costs to keep a Tesla topped up.",
        "nl": "Thuis laden, Superchargers en wat het kost om een Tesla bij te laden.",
    },
    "software": {
        "en": "Tesla software updates explained: what is in them, and which cars get them.",
        "nl": "Tesla-software-updates uitgelegd: wat erin zit en welke auto's ze krijgen.",
    },
    "fsd": {
        "en": "What Tesla's supervised driver assistance can and cannot do, what it costs, and where it is allowed.",
        "nl": "Wat de begeleide rijhulp van Tesla wel en niet kan, wat het kost en waar het mag.",
    },
    "robotaxi": {
        "en": "Where Tesla's robotaxi service runs, how the cars are supervised, and what the rules say.",
        "nl": "Waar de robotaxidienst van Tesla rijdt, hoe de auto's worden begeleid en wat de regels zeggen.",
    },
    "optimus": {
        "en": "Tesla's humanoid robot: what has been shown, what is still a plan, and how it connects to the car business.",
        "nl": "De humanoïde robot van Tesla: wat er is getoond, wat nog een plan is en hoe het samenhangt met de autotak.",
    },
    "factories": {
        "en": "Gigafactories and production lines: where Teslas are built and what the plants are adding.",
        "nl": "Gigafactories en productielijnen: waar Tesla's worden gebouwd en wat de fabrieken erbij krijgen.",
    },
    "xai": {
        "en": "xAI and Grok, and where that software shows up in Tesla vehicles and energy sites.",
        "nl": "xAI en Grok, en waar die software opduikt in Tesla-auto's en op energielocaties.",
    },
    "energy": {
        "en": "Powerwall, Megapack, solar and the electricity business around Tesla vehicles.",
        "nl": "Powerwall, Megapack, zonne-energie en de stroomtak rond Tesla-auto's.",
    },
    "spacex": {
        "en": "Starship, Falcon and the launch business, explained where it touches Tesla.",
        "nl": "Starship, Falcon en de lanceeractiviteiten, uitgelegd waar ze Tesla raken.",
    },
    "starlink": {
        "en": "Starlink satellites and dishes, and where the network meets Tesla cars and energy sites.",
        "nl": "Starlink-satellieten en schotels, en waar het netwerk Tesla-auto's en energielocaties raakt.",
    },
    "boring": {
        "en": "Tunnels and Loop stations from The Boring Company, and the Tesla vehicles that drive in them.",
        "nl": "Tunnels en Loop-stations van The Boring Company, en de Tesla's die erin rijden.",
    },
    "musk": {
        "en": "Pay awards, board votes and public statements that move Tesla and the companies around it.",
        "nl": "Beloningen, stemmingen en publieke uitspraken die Tesla en de bedrijven eromheen bewegen.",
    },
    "earnings": {
        "en": "Tesla quarterly results in plain language: revenue, margins, cash and what the figures do not say. Not financial advice.",
        "nl": "De kwartaalcijfers van Tesla in gewone taal: omzet, marges, kas en wat de cijfers niet zeggen. Geen beleggingsadvies.",
    },
    "guides": {
        "en": "Evergreen guides for owners and buyers: charging, tyres, warranties, used cars and what to check before you pay.",
        "nl": "Blijvende gidsen voor rijders en kopers: laden, banden, garantie, occasions en wat je controleert voor je betaalt.",
    },
    "ecosystem": {
        "en": "Tesla, SpaceX, Starlink, SpaceXSI, Neuralink, The Boring Company and the global AI race. The map itself lives on the ecosystem page.",
        "nl": "Tesla, SpaceX, Starlink, SpaceXSI, Neuralink, The Boring Company en de wereldwijde AI-race. De kaart zelf staat op de ecosysteempagina.",
    },
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
    "model-3-standard":  {"name": "Model 3 Standard", "menu": "menu-m3s.jpg",   "photo": "m3s-1.jpg", "gallery": ["m3s-1.jpg", "m3s-2.jpg"], "parent": "model-3", "label": "Standard · 2025+"},
    "model-3-performance": {"name": "Model 3 Performance", "menu": "menu-m3p.jpg", "photo": "m3p-1.jpg", "gallery": ["m3p-1.jpg", "m3p-2.jpg"], "parent": "model-3", "label": "Performance"},
    "model-x":           {"name": "Model X", "menu": "menu-mx21.jpg",            "photo": "mx-2.jpg", "gallery": ["mx-1.jpg", "mx-4.jpg", "mx-5.jpg", "mx-2.jpg", "mx-3.jpg"]},
    "model-x-classic":   {"name": "Model X 2015–2020", "menu": "menu-mxc.jpg",  "photo": "mxc-1.jpg", "gallery": ["mxc-1.jpg", "mxc-2.jpg"], "parent": "model-x", "label": "2015–2020"},
    "model-x-2021":      {"name": "Model X 2021+", "menu": "menu-mx21.jpg",      "photo": "mx-1.jpg", "parent": "model-x", "label": "2021+"},
    "model-x-plaid":     {"name": "Model X Plaid",      "photo": "mx-5.jpg", "parent": "model-x", "label": "Plaid", "gallery": ["mxp-1.jpg", "mx-5.jpg"], "menu": "menu-mxp.jpg"},
    "model-y":           {"name": "Model Y", "menu": "menu-myj.jpg",            "photo": "myj-9.jpg", "gallery": ["myj-1.jpg", "myj-9.jpg", "myj-12.jpg", "myj-5.jpg", "myj-2.jpg", "myj-10.jpg", "myj-7.jpg", "myj-3.jpg", "myj-11.jpg", "myj-6.jpg", "myj-8.jpg", "myj-4.jpg"]},
    "model-y-classic":   {"name": "Model Y 2020–2024", "menu": "menu-myc.jpg",  "photo": "myc-1.jpg", "gallery": ["myc-1.jpg", "myc-2.jpg"], "parent": "model-y", "label": "2020–2024"},
    "model-y-juniper":   {"name": "Model Y Juniper", "menu": "menu-myj.jpg",    "photo": "myj-12.jpg", "parent": "model-y", "label": "Juniper · 2025+", "gallery": ["myj-1.jpg", "myj-9.jpg", "myj-12.jpg", "myj-5.jpg", "myj-2.jpg", "myj-10.jpg", "myj-7.jpg", "myj-3.jpg", "myj-11.jpg", "myj-6.jpg", "myj-8.jpg", "myj-4.jpg"]},
    "model-y-standard":  {"name": "Model Y Standard", "menu": "menu-mys.jpg",   "photo": "mys-1.jpg", "gallery": ["mys-1.jpg", "mys-2.jpg"], "parent": "model-y", "label": "Standard · 2025+"},
    "model-y-performance": {"name": "Model Y Performance", "menu": "menu-myp.jpg", "photo": "myp-1.jpg", "gallery": ["myp-1.jpg", "myp-2.jpg"], "parent": "model-y", "label": "Performance"},
    "model-y-l":         {"name": "Model Y L",          "photo": "myl-3.jpg", "parent": "model-y", "label": {"en": "Model Y L · 6 seats", "nl": "Model Y L · 6 zitplaatsen"}, "gallery": ["myl-3.jpg", "myl-4.jpg", "myl-5.jpg", "myl-6.jpg", "myl-7.jpg", "myl-2.jpg", "myl-1.jpg"], "menu": "menu-myl.jpg"},
    "cybertruck":        {"name": "Cybertruck", "menu": "menu-cybertruck.jpg",         "photo": "ct-3.jpg", "gallery": ["ct-1.jpg", "ct-3.jpg", "ct-2.jpg", "ct-4.jpg", "ct-5.jpg"]},
    "cybertruck-awd":    {"name": "Cybertruck AWD", "menu": "menu-cybertruck.jpg",     "photo": "ct-1.jpg", "parent": "cybertruck", "label": "AWD"},
    "cybertruck-cyberbeast": {"name": "Cyberbeast",     "photo": "cb-1.jpg", "gallery": ["cb-1.jpg", "cb-2.jpg", "ct-5.jpg"], "parent": "cybertruck", "label": "Cyberbeast", "menu": "menu-cb.jpg"},
    "cybertruck-foundation": {"name": "Cybertruck Foundation Series", "parent": "cybertruck", "label": "Foundation Series", "photo": "ctf-1.jpg", "gallery": ["ctf-1.jpg"], "menu": "menu-ctf.jpg"},
    "cybercab":          {"name": "Cybercab", "menu": "menu-cybercab.jpg",           "photo": "cybercab.jpg", "gallery": ["cybercab.jpg", "cc-1.jpg", "cc-3.jpg", "cc-2.jpg"]},
    "roadster":          {"name": "Roadster", "photo": "roadster.jpg", "menu": "menu-roadster.jpg", "gallery": ["rd-4.jpg", "rd-5.jpg", "rd-6.jpg", "rd-7.jpg", "rd-8.jpg", "rd-9.jpg", "rd-10.jpg", "rd-11.jpg", "rd-12.jpg", "rd-13.jpg", "rd-14.jpg", "rd-15.jpg", "rd-16.jpg", "rd-17.jpg", "rd-18.jpg", "rd-19.jpg", "rd-20.jpg", "rd-21.jpg", "rd-22.jpg", "rd-23.jpg", "rd-24.jpg", "rd-25.jpg"]},
    "roadster-first-generation": {"name": {"en": "First Tesla Roadster", "nl": "De eerste Tesla Roadster"}, "full_name": True, "parent": "roadster", "photo": "gen/tesla-roadster-origin-story-lotus-elise-first-tesla.jpg", "menu": "gen/tesla-roadster-origin-story-lotus-elise-first-tesla.jpg", "label": {"en": "2008–2012", "nl": "2008–2012"}},
    "roadster-standard": {"name": {"en": "Roadster Standard", "nl": "Roadster Standard"}, "parent": "roadster", "photo": "rd-3.jpg", "menu": "rd-3.jpg", "label": {"en": "Standard", "nl": "Standard"}},
    "roadster-performance": {"name": {"en": "Roadster Performance", "nl": "Roadster Performance"}, "parent": "roadster", "photo": "rd-15.jpg", "menu": "rd-15.jpg", "label": "Performance"},
    "roadster-thrust":   {"name": {"en": "Roadster Thrust", "nl": "Roadster Thrust"}, "parent": "roadster", "photo": "rd-4.jpg", "menu": "rd-4.jpg", "label": "Thrust"},
    "roadster-rocket":   {"name": {"en": "Roadster Rocket", "nl": "Roadster Rocket"}, "parent": "roadster", "photo": "rd-1.jpg", "menu": "rd-1.jpg", "label": "Rocket"},
    "semi":              {"name": "Semi", "photo": "semi-hub.webp", "menu": "semi-hub.webp", "gallery": ["semi.jpg", "semi-6.jpg", "semi-4.jpg", "semi-7.jpg", "semi-2.jpg", "semi-5.jpg", "semi-3.jpg"],
                          "photo_alt": {"en": "Tesla Semi",
                                        "nl": "Tesla Semi"},
                          "credit": {"en": "A Tesla Semi. This picture is not a measured photograph of one specific trim.",
                                     "nl": "Een Tesla Semi. Dit is geen gemeten foto van één specifieke uitvoering."}},
    "semi-standard-range": {"name": {"en": "Semi Standard Range", "nl": "Semi Standard Range"}, "parent": "semi", "photo": "semi-card-standard.webp", "menu": "semi-card-standard.webp", "label": "Standard Range",
                          "photo_alt": {"en": "Tesla Semi",
                                        "nl": "Tesla Semi"},
                          "credit": {"en": "A Tesla Semi. Not a measured photograph of the Standard Range chassis.",
                                     "nl": "Een Tesla Semi. Geen gemeten foto van het Standard Range-chassis."}},
    "semi-long-range":   {"name": {"en": "Semi Long Range", "nl": "Semi Long Range"}, "parent": "semi", "photo": "semi-card-long.webp", "menu": "semi-card-long.webp", "label": "Long Range",
                          "photo_alt": {"en": "Tesla Semi",
                                        "nl": "Tesla Semi"},
                          "credit": {"en": "A Tesla Semi. Not a measured photograph of the longer chassis.",
                                     "nl": "Een Tesla Semi. Geen gemeten foto van het langere chassis."}},
    "semi-europe":       {"name": {"en": "Semi Europe", "nl": "Semi Europa"}, "parent": "semi", "photo": "semi-card-europe.webp", "menu": "semi-card-europe.webp", "label": {"en": "Europe", "nl": "Europa"},
                          "photo_alt": {"en": "Tesla Semi",
                                        "nl": "Tesla Semi"},
                          "credit": {"en": "A Tesla Semi. The Hannover show truck is pictured below.",
                                     "nl": "Een Tesla Semi. De showtruck uit Hannover staat hieronder."},
                          "body_photo": "semi-europe.webp",
                          "body_alt": {"en": "Tesla Semi Europe at IAA Transportation in Hannover on 14 September 2026",
                                       "nl": "Tesla Semi Europa op de IAA Transportation in Hannover op 14 september 2026"},
                          "body_credit": {"author": "Matti Blume", "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                                          "source_url": "https://commons.wikimedia.org/wiki/File:IAA_Transportation_2026,_Hanover_(20260914-P1086985).jpg",
                                          "en": "The European Semi at IAA Transportation in Hannover on 14 September 2026.",
                                          "nl": "De Europese Semi op de IAA Transportation in Hannover op 14 september 2026."}},
    "semi-2022-pilot":   {"name": {"en": "Semi 2022 Pilot", "nl": "Semi-pilot 2022"}, "parent": "semi", "photo": "semi-card-pilot.webp", "menu": "semi-card-pilot.webp", "label": {"en": "2022 Pilot", "nl": "Pilot 2022"},
                          "photo_alt": {"en": "Tesla Semi 2022 Pilot, a blue PepsiCo truck",
                                        "nl": "Tesla Semi-pilot 2022, een blauwe PepsiCo-truck"},
                          "credit": {"author": "Dllu", "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                                     "source_url": "https://commons.wikimedia.org/wiki/File:Tesla_Semi_Pepsi_2023-10-31-13-39-37_DSCF2583_dllu.jpg",
                                     "en": "PepsiCo Tesla Semi, 31 October 2023. The 2022 pilot, not the 2026 truck.",
                                     "nl": "PepsiCo Tesla Semi, 31 oktober 2023. De pilot van 2022, niet de truck van 2026."}},
}
# Fallback photo per category: a file in static/img/topics/, or a list of files to vary between
# (each article always gets the same one, picked from its slug). Missing files are skipped.
TOPIC_PHOTOS = {
    "robotaxi": ["robotaxi-app.jpg", "wireless-hub-4.jpg", "wireless-hub-3.jpg", "cybercab-fleet.jpg", "robotaxi-my-1.jpg", "cybercab-street.jpg", "cybercab-interior.jpg", "robotaxi-my-2.jpg", "models/cc-3.jpg", "models/cybercab.jpg"], "fsd": ["fsd-highway-sunset.jpg", "fsd-night-rain.jpg", "fsd-roundabout-eu.jpg", "fsd-snow.jpg", "fsd-camera-view.jpg", "camera-rain.jpg", "fsd.jpg", "models/myj-3.jpg", "fsd-2.jpg", "models/m3c-1.jpg", "fsd-3.jpg", "models/myj-1.jpg", "fsd-4.jpg"], "software": ["app-ipad.jpg", "app-faceid.jpg", "halloween-mode.jpg", "software-update.jpg", "interior-2.jpg", "grok-2.jpg", "interior-1.jpg", "fsd.jpg", "grok-1.jpg", "fsd-2.jpg", "fsd-3.jpg", "fsd-4.jpg"], "optimus": ["moon-base-optimus-1.jpg", "moon-base-optimus-2.jpg", "starship-optimus-door.jpg", "mars-keynote-optimus.jpg", "mars-keynote-optimus-door.jpg", "optimus-car-door.jpg", "optimus-unboxing.jpg", "optimus-restaurant.jpg", "optimus-checkout.jpg", "optimus-bedroom.jpg", "optimus-hand.jpg", "optimus-touch.jpg", "optimus-stage.jpg", "optimus-army.jpg", "optimus-line.jpg", "optimus.jpg", "optimus-store.jpg", "optimus-factory.jpg", "optimus-kitchen.jpg", "optimus-office.jpg", "optimus-garden.jpg"],
    "energy": ["vpp-suburb.jpg", "powerwall-dutch-house.jpg", "powerwall-texas.jpg", "powerwall-japan.jpg", "powerwall-newengland.jpg", "cybertruck-powerwall.jpg", "powerwall-garage.jpg", "megafactory.jpg", "energy-home-dusk.jpg", "megapack-1.jpg", "energy-3.jpg", "energy.jpg", "energy-5.jpg", "megapack-2.jpg", "energy-2.jpg", "energy-6.jpg", "megapack-3.jpg", "energy-4.jpg"], "charging": ["wireless-hub-1.jpg", "wireless-hub-2.jpg", "megacharger.jpg", "supercharger.jpg", "supercharger-5.jpg", "supercharger-2.jpg", "supercharger-7.jpg", "charge-port-2.jpg", "supercharger-3.jpg", "supercharger-4.jpg", "winter-1.jpg", "supercharger-6.jpg"], "ecosystem": ["spacex-1.jpg", "starlink-car-1.jpg", "spacex-2.jpg", "starlink-1.jpg", "spacex-4.jpg", "starlink-car-3.jpg", "spacex-3.jpg", "starlink-2.jpg", "spacex-5.jpg", "starlink-car-2.jpg", "tunnel-2.jpg", "tunnel-3.jpg", "tunnel-4.jpg"], "spacex": ["starship-fleet-mars.jpg", "mars-keynote-fleet.jpg", "mars-keynote-rover.jpg", "mars-keynote-planet.jpg", "falcon-heavy.jpg", "falcon-boosters.jpg", "crew-dragon-pad.jpg", "starship-moon.jpg", "satellite-ai.jpg", "chip-fab.jpg", "steel-tubes.jpg", "spacex-8.jpg", "spacex-1.jpg", "spacex-6.jpg", "spacex-2.jpg", "spacex-4.jpg", "spacex-7.jpg", "spacex-3.jpg", "spacex-5.jpg"], "starlink": ["starlink-camper.jpg", "starlink-boat.jpg", "starlink-farm.jpg", "starlink-phone-mountain.jpg", "starlink-launch-stack.jpg", "cell-tower.jpg", "inflight-wifi.jpg", "starlink-car-1.jpg", "starlink-1.jpg", "starlink-car-3.jpg", "starlink-2.jpg", "starlink-car-2.jpg"], "xai": ["xai-dc-night.jpg", "xai-gpu-rack.jpg", "grok-car-voice.jpg", "grok-phone-cafe.jpg", "xai-turbines.jpg", "ai-agent-desk.jpg", "ai-agent-screen.jpg", "xai-dc-1.jpg", "grok-3.jpg", "xai-dc-2.jpg", "grok-2.jpg", "grok-1.jpg", "interior-1.jpg"], "boring": ["loop-vegas-station.jpg", "tbm-inside.jpg", "loop-entrance-city.jpg", "tunnel-segments.jpg", "loop-aerial-map.jpg", "tunnel-freight.jpg", "dubai-loop.jpg", "robovan-loop.jpg", "tunnel-6.jpg", "tunnel-2.jpg", "tunnel-5.jpg", "tunnel-3.jpg", "tunnel-4.jpg", "tunnel-1.jpg"], "earnings": ["earnings-1.jpg", "gigafactory.jpg", "earnings-5.jpg", "earnings-2.jpg", "earnings-6.jpg", "earnings-4.jpg", "earnings-7.jpg", "earnings-3.jpg", "earnings-8.jpg", "models/myj-4.jpg", "gigafactory-3.jpg", "gigafactory-5.jpg", "gigafactory-2.jpg", "models/model-3.jpg", "gigafactory-4.jpg", "models/myj-6.jpg", "gigafactory-6.jpg"], "factories": ["gigafactory-texas.jpg", "giga-newyork.jpg", "megafactory.jpg", "gigafactory-berlin.jpg", "gigafactory-shanghai.jpg", "gigafactory-nevada.jpg", "gigafactory-fremont.jpg", "gigafactory-2.jpg", "gigafactory-5.jpg", "gigafactory-3.jpg", "gigafactory-6.jpg", "gigafactory-4.jpg", "gigafactory.jpg", "optimus-factory.jpg", "semi-2.jpg"], "musk": ["mars-keynote-planet.jpg", "mars-keynote-optimus-door.jpg", "musk-1.jpg", "musk-2.jpg", "musk-3.jpg", "earnings-1.jpg", "spacex-2.jpg", "gigafactory-4.jpg", "models/rd-2.jpg"], "guides": ["delivery-handover.jpg", "sentry-mode.jpg", "guide-roadtrip.jpg", "guide-service.jpg", "guide-wintertyres.jpg", "guide-battery.jpg", "guide-papers.jpg", "guide-tread.jpg"], "news": ["gigafactory.jpg", "models/myj-2.jpg", "gigafactory-4.jpg", "gigafactory-2.jpg", "models/m3c-10.jpg", "gigafactory-6.jpg", "models/myj-5.jpg", "gigafactory-3.jpg", "gigafactory-5.jpg"],
}
MODEL_STRIP = ["model-s", "model-3", "model-3-highland", "model-x", "model-y", "model-y-juniper", "cybertruck"]

PAGES = {
    "about": {
        "en": ("About TrendingTesla", "What TrendingTesla is and how we write.",
               "<p>TrendingTesla follows the whole system around its name: Tesla vehicles, FSD, "
               "Robotaxi and Cybercab, Optimus, energy and chips; SpaceX, Starship and Starlink; "
               "SpaceXSI, Grok, X and Cursor; Neuralink and The Boring Company; and the global race "
               "in AI, AGI and superintelligence. Honest buying advice for Tesla owners stays part of the site.</p>"
               "<p>Once a day we pick the story that matters most and explain it in "
               "plain language: what happened, why it matters and what to watch next. We write "
               "our own articles and always link to the sources we used, so you can check them.</p>"
               "<p>Most images on this site are illustrations made for TrendingTesla. Where we use real photos, they are freely licensed (public domain or Creative Commons) and credited under the article. "
               "They show the subject of an article, not the exact event, place or vehicle.</p>"
               "<p>Articles are researched and written with the help of AI and published "
               "under editorial supervision. How we edit and correct articles is described in our "
               '<a href="/editorial/">editorial policy</a>. Spotted a mistake? We correct it as soon as we '
               "know about it.</p>"
               "<p>Some links on this site may be affiliate links: if you buy through them we may "
               "earn a small commission, at no extra cost to you. This never affects our opinion.</p>"
               "<p>TrendingTesla is an independent site. We are not affiliated with, "
               "sponsored by or endorsed by Tesla, Inc. Nothing on this site is financial advice.</p>"),
        "nl": ("Over TrendingTesla", "Wat TrendingTesla is en hoe we schrijven.",
               "<p>TrendingTesla volgt het hele stelsel rond de naam: Tesla-auto's, FSD, "
               "Robotaxi en Cybercab, Optimus, energie en chips; SpaceX, Starship en Starlink; "
               "SpaceXSI, Grok, X en Cursor; Neuralink en The Boring Company; en de wereldwijde race "
               "in AI, AGI en superintelligentie. Eerlijk koopadvies voor Tesla-rijders blijft onderdeel van de site.</p>"
               "<p>Eén keer per dag kiezen we het belangrijkste verhaal en leggen we het "
               "helder uit: wat er gebeurde, waarom het ertoe doet en waar je op moet letten. We "
               "schrijven onze eigen artikelen en linken altijd naar de bronnen die we gebruikten, "
               "zodat je ze kunt controleren.</p>"
               "<p>De meeste afbeeldingen op deze site zijn illustraties die voor TrendingTesla zijn gemaakt. Echte foto's gebruiken we alleen met een vrije licentie (publiek domein of Creative Commons), met bronvermelding onder het artikel. "
               "Ze tonen het onderwerp van een artikel, niet de precieze gebeurtenis, plek of auto.</p>"
               "<p>Artikelen worden met hulp van AI onderzocht en geschreven en onder "
               "redactioneel toezicht gepubliceerd. Hoe we redigeren en corrigeren staat in ons "
               '<a href="/nl/editorial/">redactiebeleid</a>. Een fout gezien? We verbeteren hem zodra '
               "we ervan weten.</p>"
               "<p>Sommige links op deze site kunnen affiliate-links zijn: koop je via zo'n link, "
               "dan krijgen wij mogelijk een kleine commissie. Jij betaalt niets extra en het "
               "verandert nooit ons oordeel.</p>"
               "<p>TrendingTesla is een onafhankelijke site. We zijn niet verbonden aan, "
               "gesponsord door of goedgekeurd door Tesla, Inc. Niets op deze site is "
               "financieel advies.</p>"),
    },
    "editorial": {
        "en": ("Editorial policy", "How TrendingTesla researches, reviews and corrects its articles.",
               "<p>TrendingTesla publishes independent articles about Tesla, SpaceX, Starlink, SpaceXSI, "
               "Neuralink, The Boring Company and the global AI race, in English and Dutch. This page says how those articles are made and who "
               "stands behind them.</p>"
               "<h2>Research and drafting</h2>"
               "<p>Articles are researched and drafted with AI assistance. Before publication the draft "
               "is checked against the sources the article cites. We do not invent quotes, numbers or events.</p>"
               "<h2>Sources</h2>"
               "<p>Every article cites the sources it used. They are listed at the bottom of the article, "
               "each with a link, so you can read the underlying reporting yourself.</p>"
               "<h2>Who is responsible</h2>"
               "<p>The TrendingTesla editorial team is responsible for what appears on the site. Articles are "
               "published from a fact sheet in which every core fact has two sources. There is no separate "
               "approval step after the draft is written. Mistakes are corrected as soon as they are known.</p>"
               "<h2>Corrections</h2>"
               "<p>If an article is wrong, incomplete or unclear, write to us through the "
               '<a href="/contact/">contact form</a>. We correct mistakes as soon as we know about them. '
               "When the text of an article changes, we set its updated date. That is the date search engines "
               "read as the modification date. The original publication date stays as it was.</p>"
               "<h2>Independence</h2>"
               "<p>TrendingTesla is not affiliated with, sponsored by or endorsed by Tesla, Inc., SpaceX, "
               "SpaceXSI, Neuralink or The Boring Company. Nothing on this site is financial, legal or investment advice.</p>"),
        "nl": ("Redactiebeleid", "Hoe TrendingTesla artikelen onderzoekt, nakijkt en verbetert.",
               "<p>TrendingTesla publiceert onafhankelijke artikelen over Tesla, SpaceX, Starlink, SpaceXSI, "
               "Neuralink, The Boring Company en de wereldwijde AI-race, in het Nederlands en het Engels. Op deze pagina staat hoe die artikelen worden "
               "gemaakt en wie er verantwoordelijk voor is.</p>"
               "<h2>Onderzoek en tekst</h2>"
               "<p>Artikelen worden met hulp van AI onderzocht en opgesteld. Voor publicatie wordt de tekst "
               "gecontroleerd aan de hand van de bronnen die in het artikel staan. We verzinnen geen citaten, "
               "cijfers of gebeurtenissen.</p>"
               "<h2>Bronnen</h2>"
               "<p>Elk artikel noemt de bronnen die we gebruikten. Ze staan onderaan het artikel, elk met een "
               "link, zodat je de onderliggende berichtgeving zelf kunt nalezen.</p>"
               "<h2>Wie is verantwoordelijk</h2>"
               "<p>De redactie van TrendingTesla is verantwoordelijk voor wat er op de site staat. Artikelen "
               "worden gepubliceerd vanuit een feitenlijst waarin elk kernfeit twee bronnen heeft. Na het "
               "schrijven is er geen aparte goedkeuringsstap. Fouten verbeteren we zodra we ervan weten.</p>"
               "<h2>Correcties</h2>"
               "<p>Klopt een artikel niet, is het onvolledig of onduidelijk, schrijf ons via het "
               '<a href="/nl/contact/">contactformulier</a>. We verbeteren fouten zodra we ervan weten. '
               "Als de tekst van een artikel verandert, zetten we de bijwerkdatum. Dat is de datum die "
               "zoekmachines als wijzigingsdatum lezen. De oorspronkelijke publicatiedatum blijft staan.</p>"
               "<h2>Onafhankelijkheid</h2>"
               "<p>TrendingTesla is niet verbonden aan, gesponsord door of goedgekeurd door Tesla, Inc., "
               "SpaceX, SpaceXSI, Neuralink of The Boring Company. Niets op deze site is financieel, juridisch of "
               "beleggingsadvies.</p>"),
    },
    "privacy": {
        "en": ("Privacy policy", "How trendingtesla.com handles your data and what your rights are.",
               '<p>This policy explains what personal data trendingtesla.com processes, why, and what your rights are. We keep it to the minimum: you can read the whole site without an account. Advertising through Google AdSense, and the cookies it may set, is described below.</p><h2>Who is responsible?</h2><p>The controller for this site is trendingtesla.com. You can reach us through the <a href="/contact/">contact form</a>.</p><h2>Contact form</h2><p>If you use the contact form, your name, email address and message are forwarded to our mailbox by email (via Cloudflare Email Routing, and our email provider). We use them only to answer you; the legal basis is our legitimate interest in answering questions, or steps you ask us to take. The form is handled by this site\'s Cloudflare worker, which checks the message, applies the spam limit below and emails it on. The message is not stored on the website. We delete your message once it has been handled, and in any case within 12 months.</p><p>To stop spam and abuse, the form keeps a scrambled (hashed) version of your IP address for at most two hours to count how many messages are sent. The original IP address is not stored.</p><h2>Hosting and statistics</h2><p>The site is served through Cloudflare, which processes technical data such as IP addresses to deliver and protect the site. Cloudflare may process data outside the EU; it uses the EU Standard Contractual Clauses and is certified under the EU-US Data Privacy Framework. Aggregated page views use Cloudflare Web Analytics. It is cookieless, stores no personal data, does not track you across sites and only gives us totals. The script runs for every visitor as soon as the page loads. No consent is needed. Fonts are served from our own domain, not from third parties.</p><h2>YouTube</h2><p>We publish short videos on our YouTube channel @TrendingTesla. To upload our own videos we use YouTube API Services; this does not involve any data from you. Videos on YouTube are subject to the <a href="https://www.youtube.com/t/terms" rel="nofollow noopener" target="_blank">YouTube Terms of Service</a>, and YouTube processes data under the <a href="https://policies.google.com/privacy" rel="nofollow noopener" target="_blank">Google Privacy Policy</a>.</p><p>On an article that has a video, and on the <a href="/shorts/">Shorts</a> page, you can play that video here. Nothing is loaded from YouTube when the page opens: you see the article photo or a thumbnail. Only after you click, or press Enter, do we load a player from youtube-nocookie.com, YouTube\'s privacy-enhanced domain. Until that click your browser does not contact YouTube. After it, YouTube can receive technical data such as your IP address and, once playback starts, may set cookies and process data as described in Google\'s privacy policy. We do not load a YouTube player in the background.</p><h2>Your browser</h2><p>Saved articles, and the list of articles you liked, are stored only in your own browser (local storage), not on our servers. You can delete them by clearing your browser data.</p><h2>Likes</h2><p>The like button talks to a small program on our host (a Cloudflare worker). It sends only the article id and whether you added or removed a like. The worker stores one total per article and nothing else: no account, no cookie and no IP address. It cannot tell who liked an article.</p><h2>Your rights</h2><p>You have the right to access, correct or delete your personal data, to object to its use, and to ask for it to be restricted or transferred. Send your request through the contact form; we answer within one month. You can also file a complaint with the Dutch Data Protection Authority (Autoriteit Persoonsgegevens) or the authority in your own country.</p><h2>Cookies and consent</h2><p>Visit counts do not depend on this banner. They are cookieless and anonymous, cover aggregated page views, run for every visitor and need no consent. The banner is only for ads. Your choice is stored in this browser (local storage) so we can remember it. That storage is not a tracking cookie. Saved articles, and the articles you mark as liked, use the same kind of browser storage and stay on this device. You can change the choice at any time with Cookie settings in the footer. Refusing leaves every article readable. YouTube loads only after you press play. Ads still require consent, as described in the next section.</p><h2>Advertising</h2><p>Every page includes the Google AdSense script so Google can show ads. The script loads with the page. It can set cookies, including advertising cookies, and receive technical data such as your IP address, browser and approximate location, as described in the <a href="https://policies.google.com/privacy" rel="nofollow noopener" target="_blank">Google Privacy Policy</a> and in <a href="https://policies.google.com/technologies/ads" rel="nofollow noopener" target="_blank">how Google uses information from sites or apps that use its services</a>. Google may use that data to deliver and measure ads and, where the law allows, to personalise them. We do not place ad units in the page ourselves, so no empty ad box is reserved and the layout does not shift for one. If automatic ads are switched on in the AdSense account, Google chooses where an ad appears.</p><p>In the European Economic Area, the United Kingdom and Switzerland, personalised ads need consent collected by a Google-certified consent tool. This site does not show its own advertising-consent dialog. In those regions, that consent is collected by Google\'s Privacy &amp; messaging European regulations message, which Google provides inside AdSense. When that message is shown, you can accept, refuse or manage personalised ads before Google uses them. That choice is stored by Google, not by the banner on this site. You can also review ad personalisation in <a href="https://adssettings.google.com/" rel="nofollow noopener" target="_blank">Google\'s ad settings</a>. Accepting or refusing our banner does not change those visit counts. Ads still require consent where the law requires it, collected by Google as described above.</p><h2>Newsletter</h2><p>If you sign up for the <a href="/newsletter/">newsletter</a>, your email address is processed by MailerLite (MailerLite UAB, EU) only to send the newsletter. Signup uses double opt-in. You can unsubscribe at any time via the link in every email. We do not share your email address with others. This site does not store the address itself.</p><h2>Affiliate links</h2><p>Some articles may show a product box. If you buy through that link we may earn a commission, at no extra cost to you. The link is marked as sponsored. The box does not show a price.</p><h2>Changes</h2><p>When the way this site handles data changes, this page is updated first.</p><p><em>Last updated: 16 November 2026.</em></p>'),
        "nl": ("Privacybeleid", "Hoe trendingtesla.com met je gegevens omgaat en welke rechten je hebt.",
               '<p>Hier lees je welke persoonsgegevens trendingtesla.com verwerkt, waarom, en welke rechten je hebt. We houden het zo klein mogelijk: je kunt de hele site lezen zonder account. Advertenties via Google AdSense, en de cookies die daarbij kunnen worden geplaatst, staan hieronder.</p><h2>Wie is verantwoordelijk?</h2><p>Verantwoordelijk voor deze site is trendingtesla.com. Je bereikt ons via het <a href="/nl/contact/">contactformulier</a>.</p><h2>Contactformulier</h2><p>Gebruik je het contactformulier, dan worden je naam, e-mailadres en bericht per e-mail doorgestuurd naar onze mailbox (via Cloudflare Email Routing en onze e-mailprovider). We gebruiken ze alleen om je te antwoorden; de grondslag is ons gerechtvaardigd belang om vragen te beantwoorden, of stappen die je ons zelf vraagt te zetten. Het formulier wordt afgehandeld door de Cloudflare-worker van deze site: die controleert het bericht, past de spamlimiet hieronder toe en mailt het door. Het bericht wordt niet op de website bewaard. We verwijderen je bericht zodra het is afgehandeld, en in elk geval binnen 12 maanden.</p><p>Om spam en misbruik te voorkomen, bewaart het formulier hoogstens twee uur een onherkenbaar gemaakte (gehashte) versie van je IP-adres om te tellen hoeveel berichten er worden verstuurd. Het echte IP-adres wordt niet opgeslagen.</p><h2>Hosting en statistieken</h2><p>De site wordt geleverd via Cloudflare, dat technische gegevens zoals IP-adressen verwerkt om de site te leveren en te beveiligen. Cloudflare kan gegevens buiten de EU verwerken; het gebruikt daarvoor de EU-modelcontractbepalingen en is gecertificeerd onder het EU-VS Data Privacy Framework. Totalen van paginaweergaven lopen via Cloudflare Web Analytics. Dat is zonder cookies, slaat geen persoonsgegevens op, volgt je niet over andere sites en geeft ons alleen totalen. Het script draait voor elke bezoeker zodra de pagina laadt. Toestemming is niet nodig. Lettertypen komen van ons eigen domein, niet van derden.</p><h2>YouTube</h2><p>We publiceren korte video\'s op ons YouTube-kanaal @TrendingTesla. Om onze eigen video\'s te uploaden gebruiken we YouTube API Services; daarbij worden geen gegevens van jou gebruikt. Op video\'s op YouTube zijn de <a href="https://www.youtube.com/t/terms" rel="nofollow noopener" target="_blank">Servicevoorwaarden van YouTube</a> van toepassing, en YouTube verwerkt gegevens volgens het <a href="https://policies.google.com/privacy" rel="nofollow noopener" target="_blank">Privacybeleid van Google</a>.</p><p>Bij een artikel met een video, en op de <a href="/nl/shorts/">Shorts</a>-pagina, kun je die video hier afspelen. Er wordt niets van YouTube geladen als de pagina opent: je ziet de artikelfoto of een miniatuur. Pas als je klikt, of op Enter drukt, laden we een speler van youtube-nocookie.com, het privacyvriendelijkere domein van YouTube. Tot die klik neemt je browser geen contact op met YouTube. Daarna kan YouTube technische gegevens ontvangen, zoals je IP-adres, en zodra het afspelen start cookies plaatsen en gegevens verwerken zoals beschreven in het privacybeleid van Google. We laden geen YouTube-speler op de achtergrond.</p><h2>Je browser</h2><p>Bewaarde artikelen, en de lijst van artikelen die je leuk vond, staan alleen in je eigen browser (local storage), niet op onze servers. Je verwijdert ze door je browsergegevens te wissen.</p><h2>Vind-ik-leuks</h2><p>De vind-ik-leukknop praat met een klein programma op onze host (een Cloudflare-worker). Die krijgt alleen het artikel-id en of je een like toevoegt of weghaalt. De worker bewaart één totaal per artikel en verder niets: geen account, geen cookie en geen IP-adres. Hij kan niet zien wie een artikel leuk vond.</p><h2>Je rechten</h2><p>Je hebt het recht om je persoonsgegevens in te zien, te laten corrigeren of verwijderen, bezwaar te maken tegen het gebruik ervan, en te vragen het gebruik te beperken of de gegevens over te dragen. Stuur je verzoek via het contactformulier; we antwoorden binnen een maand. Je kunt ook een klacht indienen bij de Autoriteit Persoonsgegevens.</p><h2>Cookies en toestemming</h2><p>Bezoekcijfers hangen niet af van deze banner. Ze zijn anoniem en zonder cookies, gaan over totalen van paginaweergaven, gelden voor elke bezoeker en hebben geen toestemming nodig. De banner is alleen voor advertenties. Je keuze wordt in deze browser bewaard (local storage), zodat we die kunnen onthouden. Dat is geen trackingcookie. Bewaarde artikelen, en de artikelen die je leuk vindt, gebruiken dezelfde opslag in de browser en blijven op dit apparaat. Je wijzigt de keuze wanneer je wilt via Cookie-instellingen in de voettekst. Weigeren laat elk artikel leesbaar. YouTube laadt pas als je op afspelen drukt. Voor advertenties is nog wel toestemming nodig, zoals in het volgende onderdeel staat.</p><h2>Advertenties</h2><p>Op elke pagina staat het script van Google AdSense, zodat Google advertenties kan tonen. Het script laadt mee met de pagina. Het kan cookies plaatsen, ook advertentiecookies, en technische gegevens ontvangen, zoals je IP-adres, browser en globale locatie, zoals beschreven in het <a href="https://policies.google.com/privacy" rel="nofollow noopener" target="_blank">privacybeleid van Google</a> en in <a href="https://policies.google.com/technologies/ads" rel="nofollow noopener" target="_blank">hoe Google gegevens gebruikt van sites of apps die zijn diensten gebruiken</a>. Google kan die gegevens gebruiken om advertenties te leveren en te meten en, waar de wet dat toestaat, om ze te personaliseren. We plaatsen zelf geen advertentieblokken in de pagina, dus er wordt geen lege advertentieruimte gereserveerd en de indeling verspringt daar niet door. Staan automatische advertenties aan in het AdSense-account, dan bepaalt Google waar een advertentie komt.</p><p>In de Europese Economische Ruimte, het Verenigd Koninkrijk en Zwitserland is voor gepersonaliseerde advertenties toestemming nodig via een door Google gecertificeerde toestemmingstool. Deze site toont zelf geen toestemmingsvenster voor advertenties. In die regio\'s verzamelt Google die toestemming met het eigen Europese-regelgevingbericht onder Privacy en berichten, dat in AdSense zit. Als dat bericht verschijnt, kun je gepersonaliseerde advertenties accepteren, weigeren of beheren voordat Google ze gebruikt. Die keuze bewaart Google, niet de banner op deze site. Je kunt advertentiepersonalisatie ook nakijken in <a href="https://adssettings.google.com/" rel="nofollow noopener" target="_blank">de advertentie-instellingen van Google</a>. Accepteren of weigeren op onze banner verandert die bezoekcijfers niet. Voor advertenties blijft toestemming nodig waar de wet dat vraagt, en die keuze verzamelt Google zoals hierboven beschreven.</p><h2>Nieuwsbrief</h2><p>Meld je je aan voor de <a href="/nl/nieuwsbrief/">nieuwsbrief</a>, dan verwerkt MailerLite (MailerLite UAB, EU) je e-mailadres alleen om de nieuwsbrief te versturen. Aanmelden gaat met dubbele bevestiging. Je kunt je op elk moment afmelden via de link in elke e-mail. We delen je e-mailadres niet met anderen. Deze site bewaart het adres zelf niet.</p><h2>Affiliate-links</h2><p>Sommige artikelen kunnen een productblok tonen. Koop je via die link, dan kunnen wij een commissie ontvangen, zonder extra kosten voor jou. De link is gemarkeerd als gesponsord. In het blok staat geen prijs.</p><h2>Wijzigingen</h2><p>Verandert de manier waarop deze site met gegevens omgaat, dan werken we deze pagina eerst bij.</p><p><em>Laatst bijgewerkt: 16 november 2026.</em></p>'),
    },
    "contact": {
        "en": ("Contact", "Get in touch with TrendingTesla: tips, corrections and questions.",
               "<p>Spotted a mistake, have a tip or a question? Send us a message.</p>"
               '<form class="cform" data-ok="Thanks! Your message has been sent. We will reply as soon as we can." data-err="Sending failed. Please try again later."><label>Name<input name="name" maxlength="100" required autocomplete="name"></label><label>Email<input name="email" type="email" maxlength="200" required autocomplete="email"></label><label class="hp" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off"></label><label>Message<textarea name="message" rows="7" maxlength="5000" required></textarea></label><button type="submit">Send message</button><p class="cstatus" role="status"></p></form>'),
        "nl": ("Contact", "Neem contact op met TrendingTesla: tips, correcties en vragen.",
               "<p>Een fout gezien, een tip of een vraag? Stuur ons een bericht.</p>"
               '<form class="cform" data-ok="Bedankt! Je bericht is verstuurd. We reageren zo snel mogelijk." data-err="Versturen is mislukt. Probeer het later nog eens."><label>Naam<input name="name" maxlength="100" required autocomplete="name"></label><label>E-mail<input name="email" type="email" maxlength="200" required autocomplete="email"></label><label class="hp" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off"></label><label>Bericht<textarea name="message" rows="7" maxlength="5000" required></textarea></label><button type="submit">Verstuur bericht</button><p class="cstatus" role="status"></p></form>'),
    },
    "terms": {
        "en": ("Terms of use", "The terms for using trendingtesla.com and the TrendingTesla YouTube channel.",
               '<p>These terms apply to the use of trendingtesla.com and our YouTube channel @TrendingTesla. By using the site or watching our videos you accept them.</p><h2>What we offer</h2><p>TrendingTesla publishes independent news and explanations about Tesla and related companies, in English and Dutch, as articles and short videos. The site is free to use and has no accounts.</p><h2>Accuracy</h2><p>We check our articles against the sources we cite and correct mistakes as soon as we know about them. Even so, information can be incomplete or outdated. Nothing on this site or channel is financial, legal or investment advice. Images are illustrations or credited, freely licensed photos.</p><h2>Independence and trademarks</h2><p>TrendingTesla is not affiliated with, sponsored by or endorsed by Tesla, Inc., SpaceX, SpaceXSI, Neuralink or The Boring Company. Product and company names are trademarks of their owners and are used only to identify the subject of our reporting.</p><h2>Copyright</h2><p>Our texts, videos and illustrations are our own work. You may link to and quote short parts with a link to the source; please do not copy whole articles or videos. Quotes and facts from other sources belong to their owners and are credited.</p><h2>YouTube</h2><p>Our videos are published on YouTube. Watching them is subject to the <a href="https://www.youtube.com/t/terms" rel="nofollow noopener" target="_blank">YouTube Terms of Service</a> and the <a href="https://policies.google.com/privacy" rel="nofollow noopener" target="_blank">Google Privacy Policy</a>. We use YouTube API Services only to upload our own videos to our own channel.</p><h2>Links to other sites</h2><p>We link to the sources we used and sometimes to shops (affiliate links, which may earn us a small commission at no extra cost to you). We are not responsible for the content of other sites.</p><h2>Liability</h2><p>We provide the site and videos as they are. To the extent the law allows, we are not liable for damage resulting from the use of information on this site or channel.</p><h2>Privacy and contact</h2><p>How we handle personal data is described in our <a href="/privacy/">privacy policy</a>. Questions about these terms can be sent through the <a href="/contact/">contact form</a>. Dutch law applies.</p><p><em>Last updated: 28 October 2026.</em></p>'),
        "nl": ("Gebruiksvoorwaarden", "De voorwaarden voor het gebruik van trendingtesla.com en het YouTube-kanaal van TrendingTesla.",
               '<p>Deze voorwaarden gelden voor het gebruik van trendingtesla.com en ons YouTube-kanaal @TrendingTesla. Door de site te gebruiken of onze video\'s te bekijken, ga je ermee akkoord.</p><h2>Wat we bieden</h2><p>TrendingTesla publiceert onafhankelijk nieuws en uitleg over Tesla en verwante bedrijven, in het Nederlands en Engels, als artikelen en korte video\'s. De site is gratis en heeft geen accounts.</p><h2>Juistheid</h2><p>We controleren onze artikelen aan de hand van de bronnen die we noemen en verbeteren fouten zodra we ze kennen. Toch kan informatie onvolledig of verouderd zijn. Niets op deze site of dit kanaal is financieel, juridisch of beleggingsadvies. Afbeeldingen zijn illustraties of vrij gelicentieerde foto\'s met bronvermelding.</p><h2>Onafhankelijkheid en merken</h2><p>TrendingTesla is niet verbonden aan, gesponsord door of goedgekeurd door Tesla, Inc., SpaceX, SpaceXSI, Neuralink of The Boring Company. Product- en bedrijfsnamen zijn merken van hun eigenaren en worden alleen gebruikt om het onderwerp van onze berichtgeving aan te duiden.</p><h2>Auteursrecht</h2><p>Onze teksten, video\'s en illustraties zijn eigen werk. Je mag ernaar linken en korte stukken citeren met een link naar de bron; neem geen hele artikelen of video\'s over. Citaten en feiten uit andere bronnen zijn van hun eigenaren en worden vermeld.</p><h2>YouTube</h2><p>Onze video\'s staan op YouTube. Op het bekijken ervan zijn de <a href="https://www.youtube.com/t/terms" rel="nofollow noopener" target="_blank">Servicevoorwaarden van YouTube</a> en het <a href="https://policies.google.com/privacy" rel="nofollow noopener" target="_blank">Privacybeleid van Google</a> van toepassing. We gebruiken YouTube API Services alleen om onze eigen video\'s naar ons eigen kanaal te uploaden.</p><h2>Links naar andere sites</h2><p>We linken naar de bronnen die we gebruikten en soms naar winkels (affiliate-links, waarmee we een kleine commissie kunnen verdienen zonder extra kosten voor jou). We zijn niet verantwoordelijk voor de inhoud van andere sites.</p><h2>Aansprakelijkheid</h2><p>We bieden de site en video\'s aan zoals ze zijn. Voor zover de wet dat toestaat, zijn we niet aansprakelijk voor schade door het gebruik van informatie op deze site of dit kanaal.</p><h2>Privacy en contact</h2><p>Hoe we met persoonsgegevens omgaan, staat in ons <a href="/nl/privacy/">privacybeleid</a>. Vragen over deze voorwaarden kun je sturen via het <a href="/nl/contact/">contactformulier</a>. Op deze voorwaarden is Nederlands recht van toepassing.</p><p><em>Laatst bijgewerkt: 28 oktober 2026.</em></p>'),
    },
}

CSS = """
@font-face{font-family:Manrope;font-weight:400;font-display:optional;src:url(/fonts/manrope-latin-400-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:600;font-display:optional;src:url(/fonts/manrope-latin-600-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:700;font-display:optional;src:url(/fonts/manrope-latin-700-normal.woff2) format("woff2")}
@font-face{font-family:Manrope;font-weight:800;font-display:optional;src:url(/fonts/manrope-latin-800-normal.woff2) format("woff2")}
/* Arial-metric fallback. size-adjust is the Manrope advance width over Arial, so a late font does not move the lead story. */
@font-face{font-family:"Manrope Fallback";font-weight:400;src:local("Arial"),local("Arimo"),local("Liberation Sans");size-adjust:111.65%;ascent-override:95.48%;descent-override:26.87%;line-gap-override:0%}
@font-face{font-family:"Manrope Fallback";font-weight:600;src:local("Arial"),local("Arimo"),local("Liberation Sans");size-adjust:115.76%;ascent-override:92.08%;descent-override:25.91%;line-gap-override:0%}
@font-face{font-family:"Manrope Fallback";font-weight:700;src:local("Arial"),local("Arimo"),local("Liberation Sans");size-adjust:117.80%;ascent-override:90.49%;descent-override:25.47%;line-gap-override:0%}
@font-face{font-family:"Manrope Fallback";font-weight:800;src:local("Arial"),local("Arimo"),local("Liberation Sans");size-adjust:119.86%;ascent-override:88.94%;descent-override:25.03%;line-gap-override:0%}
:root{--bg:#04060a;--surface:#212121;--surface2:#272727;--border:#272727;--border2:#3f3f3f;--fg:#e8eef5;--head:#fff;--muted:#b9c4d2;--dim:#8f9db0;--red:#e22822;--red2:#b81e19;--blue:#00d4ff;--edge:#3a4a60;--blue2:#5fe3ff;--max:1160px;--card-gap-x:12px;--card-gap-y:22px;color-scheme:dark}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:150px;background:#04060a}
html,body{overflow-x:clip;max-width:100%}
body{-webkit-text-size-adjust:100%;text-size-adjust:100%;background:linear-gradient(180deg,rgba(15,15,15,0) 0,rgba(15,15,15,0) 35%,#0f0f0f 100%) top left/100% 900px no-repeat,linear-gradient(160deg,#2b2b2b 0%,#1d1d1d 35%,#141414 70%,#0f0f0f 100%) top left/100% 900px no-repeat,#0f0f0f;min-height:100vh;color:var(--fg);font:17px/1.42 Manrope,"Manrope Fallback",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main,footer{position:relative;z-index:1}
a{color:var(--head)}
img{display:block;max-width:100%;height:auto}picture{display:contents}
h1,h2,h3{color:#ebebeb;font-weight:800}
.wrap{max-width:var(--max);margin:0 auto;padding:0 12px}
.narrow{max-width:740px;margin:0 auto}
.read{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:13px;align-items:start;margin-top:0}
.grid2{display:grid;grid-template-columns:1fr;gap:13px;margin-top:20px}
.grid2>.card{display:grid;grid-template-columns:254px 1fr;gap:11px;align-items:start}.grid2>.card .body{padding:0;line-height:1}.grid2>.card .body .tag,.grid2>.card .body .meta{line-height:1;vertical-align:top}.grid2>.card h3{font-size:1.12rem;line-height:1.3;margin:8px 0 6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.grid2>.card p{-webkit-line-clamp:1;line-height:1.42}.grid2>.card .im{height:142px;width:254px}.grid2>.card .im img{height:100%;aspect-ratio:auto}
.grid2>.card{align-content:start}
.below{margin-top:17px}.below>.tip{margin-top:0}.grid2.gall.wide{grid-template-columns:repeat(auto-fill,minmax(max(250px,calc((100% - 72px) / 7 + 1px)),1fr));gap:var(--card-gap-y) var(--card-gap-x);margin-top:14px}.wide .empty{grid-column:1/-1}.grid2.gall{grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--card-gap-y) var(--card-gap-x)}.gall>.card{grid-template-columns:1fr;gap:0}.gall>.card .im{width:auto;height:auto}.gall>.card .im img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}.gall>.card .body{padding:0;line-height:1.3}.gall>.card h2,.gall>.card h3{font-size:.92rem;font-weight:700;line-height:1.3;margin:0 0 5px;color:#ebebeb;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.gall>.card p{font-size:.8rem;line-height:1.35;-webkit-line-clamp:1;margin-bottom:5px}.gall>.card .meta{font-size:.74rem}
.span2{grid-column:1/-1}.span2 .tip{margin:0}
.read article{padding-top:0}
.rside .rh{font-size:1.15rem;margin:0 0 22px;padding-bottom:12px;border-bottom:1px solid var(--border)}
.sr{position:absolute;left:-9999px}
/* header */
.top{position:sticky;top:0;z-index:40;background:transparent;transition:background-color .2s}.top.solid{background:#161616}.bar .search{height:38px}.bar .search input,.bar .search>button{box-sizing:border-box;height:38px;padding-top:0;padding-bottom:0}
.ticker{box-sizing:border-box;width:100%;max-width:100%;min-width:0;margin:0;padding:8px 0;border-top:3px solid var(--red);display:block;overflow:hidden;contain:inline-size;background:transparent;color:var(--fg);font-size:11px;font-weight:600;line-height:14px}
.tk-track{display:flex;width:max-content;animation:tk-run 112s linear infinite}
.tk-set{display:flex;align-items:center;flex:none}
.tk{white-space:nowrap;color:inherit;text-decoration:none}
.ticker a.tk{color:inherit}
.tk::before{content:"";display:inline-block;width:3px;height:3px;margin:0 12px;border-radius:50%;background:currentColor;opacity:.38;vertical-align:middle}
.tk b{color:var(--head);font-weight:700;margin-right:.45em}
.tk .up{color:#3ddc97;margin-left:.35em}
.tk .dn{color:#ff5d57;margin-left:.35em}
.tk .when{margin-left:6px;color:var(--dim);font-weight:500}
.ticker:hover .tk-track,.ticker:focus-within .tk-track{animation-play-state:paused}
.tk[hidden]{display:none}
@keyframes tk-run{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.ticker-main{display:none}
@media (max-width:767.98px){
.ticker-main{display:block;border-bottom:3px solid var(--red)}
.sheet:has(.ticker-main) .pv-side>.ticker{display:none}
}
@media (max-width:900px){
.hfeed .pv-hl b{font-size:13px;line-height:1.3;hyphens:none;-webkit-hyphens:none;overflow-wrap:normal;word-break:normal;-webkit-text-size-adjust:none;text-size-adjust:none}
.hfeed .pv-row time{font-size:12px;-webkit-text-size-adjust:none;text-size-adjust:none}
.hfeed .pv-min{width:48px;min-width:48px;padding:2px 1px}
.hfeed .pv-min b{font-size:12px}
.hfeed .pv-min small{font-size:8px}
.hfeed .pv-row{grid-template-columns:42px minmax(0,1fr) 48px;column-gap:6px}
}
@media (prefers-reduced-motion:reduce){.ticker{overflow-x:auto;overflow-y:hidden}.tk-track{animation:none}.tk-set[aria-hidden="true"]{display:none}}
/* From tablet up, the lichtkrant is the first thing in the sidebar. It stays in normal
   flow so the block under it (Related, Latest, and the rest) is not covered.
   Phones keep the copy that already sits further down the page. */
.ticker-top{display:none}
@media (min-width:768px){
.ticker-top{display:block}
.pv-side>.ticker:not(.ticker-top){display:none}
.sheet>.pv-side,.sheet>.sheet-rail{align-self:stretch}
.sheet-rail>.pv-side:not(.arel){flex:1 1 auto}
}
.bar{display:flex;align-items:center;gap:14px;height:66px}
.brand{display:flex;align-items:baseline;gap:14px;min-width:0}
.logo{font-weight:800;font-size:1.4rem;letter-spacing:-.02em;color:#ebebeb;text-decoration:none;white-space:nowrap}
.logo span{color:var(--red);font-size:calc(1em + 1px);position:relative;top:3px}
.slogan{font-size:.86rem;font-weight:600;color:var(--muted);white-space:nowrap}
.burger{flex:none;width:40px;height:40px;margin-left:-8px;border-radius:10px;border:0;background:transparent;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;cursor:pointer}
.burger span{width:18px;height:2px;border-radius:2px;background:#ebebeb}
.burger:hover{background:var(--surface2)}
.search{position:relative;flex:0 1 auto;width:calc((100% - 13px) * 0.63 - 230px);margin-left:28px;margin-right:auto;display:flex}
.search input{flex:1;min-width:0;background:#121212;border:1px solid #303030;border-right:0;border-radius:10px 0 0 10px;color:var(--head);font:inherit;font-size:.92rem;padding:9px 18px;outline:none}
.search input::placeholder{color:var(--dim)}
.search input:focus,.search input:focus-visible,.search>button:focus,.search>button:focus-visible{outline:none;outline-offset:0;box-shadow:none;border-color:#303030}
.search>button,.sbtn{border:1px solid #303030;background:#222;color:#ebebeb;cursor:pointer;display:grid;place-items:center}
@media (max-width:904.98px){.bar .search input{padding-top:6px;padding-bottom:6px;font-size:.88rem}}.tdd{position:relative;flex:none;display:none}html.hasdd .tdd{display:block}html.hasdd .bar .search{margin-right:0;flex-shrink:0}html.hasdd .bar .savedlink{margin-left:auto}html.hasdd.ddend .bar .tdd{order:9}html.hasdd .bar .brand{flex-shrink:0}html.hasdd.ddend .bar .savedlink{margin-left:12px}.tdb{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;height:41px;background:#121212;border:1px solid #303030;border-radius:10px;color:#ebebeb;font:inherit;font-size:.92rem;font-weight:700;padding:0 0 0 14px;overflow:hidden;cursor:pointer}.tdc{align-self:stretch;flex:none;display:grid;place-items:center;width:var(--bw,58px);background:#222;border-left:1px solid #303030}.tdb:hover{border-color:#4a4a4a}.tdb svg{transition:transform .2s}.tdb[aria-expanded=true] svg{transform:rotate(180deg)}.tdl{position:absolute;left:auto;right:0;min-width:100%;width:max-content;top:calc(100% + 6px);z-index:45;display:grid;grid-template-columns:1fr 1fr;gap:4px;padding:6px;background:#161616;border:1px solid #303030;border-radius:10px;box-shadow:0 12px 32px rgba(0,0,0,.55)}.tdl[hidden]{display:none}.tdl a{padding:9px clamp(6px,1.1vw,14px) 8px;border-radius:10px;color:#ebebeb;font-size:.86rem;font-weight:700;text-decoration:none;white-space:nowrap}.tdl a:hover{background:#272727}.tdl a.on{background:#ebebeb;color:#111}@media (max-width:1100.98px){.tdl{gap:2px;padding:5px}.tdl a{font-size:.82rem}}.search>button{border-radius:0 10px 10px 0;width:max(36px,calc(58px * var(--k,1)))}.search input{padding-left:max(9px,calc(18px * var(--k,1)));padding-right:max(6px,calc(18px * var(--k,1)))}
.sbtn{display:none;width:40px;height:40px;border-radius:10px;margin-left:auto}
.res{position:absolute;top:calc(100% + 8px);left:0;right:0;background:#212121;border:1px solid var(--border2);border-radius:10px;padding:6px;box-shadow:0 24px 48px rgba(0,0,0,.55);max-height:70vh;overflow:auto;z-index:40}
.res a{display:flex;gap:12px;align-items:center;padding:8px;border-radius:10px;text-decoration:none}
.res a:hover{background:var(--surface2)}
.res img{width:76px;aspect-ratio:1200/630;object-fit:cover;border-radius:10px;flex:none}
.res b{display:block;font-size:.88rem;line-height:1.3;color:var(--head)}
.res small{color:var(--dim);font-size:.74rem}
.res p{padding:10px;color:var(--muted);font-size:.88rem}
.lang{flex:none;font-size:.78rem;font-weight:800;letter-spacing:.05em;color:#ebebeb;text-decoration:none;border:1px solid var(--border2);border-radius:10px;padding:4px 11px;margin-left:6px}
.bar .lang{display:inline-flex;align-items:center;box-sizing:border-box}.lang:hover{color:#ebebeb;border-color:#ebebeb}
.scrim{position:fixed;inset:0;z-index:25;background:rgba(0,0,0,.55);opacity:0;pointer-events:none;transition:opacity .25s}
.dopen .scrim{opacity:1;pointer-events:auto}.drawer,.scrim{top:66px}nav.drawer .dh,nav.drawer .dclose{display:none}nav.drawer{padding-top:10px}
.drawer{position:fixed;top:0;bottom:0;left:0;z-index:30;width:290px;max-width:86vw;overflow-y:auto;background:#0f0f0f;border-right:1px solid var(--border);padding:13px 12px 32px;transform:translateX(-102%);transition:transform .25s ease}
.dopen .drawer{transform:none}.dnoanim .drawer,.dnoanim .scrim{transition:none!important}
.drawer{overscroll-behavior:contain}html.dopen{overflow-y:scroll}html.dopen body{position:fixed;left:0;right:0;width:100%;overflow:hidden}
.drawer .dh{display:flex;align-items:center;gap:12px;padding:0 4px 13px 12px;margin:0 -12px 10px;border-bottom:1px solid var(--border)}
@media (max-width:699.98px){.bar{gap:4px}.bar .burger{margin-left:-11px}.bar .brand{transform:none;margin-left:3px}.bar .logo{font-size:1.15rem}}@media (min-width:601px) and (max-width:699.98px){.drawer,.scrim{top:66px}}@media (min-width:700px){header.hb .bar .burger{display:flex}}
@media (max-width:1000.98px){.rside .cats9 a{padding-left:3px;padding-right:3px}}@media (max-width:904.98px) and (min-width:700px){.rside .mini{gap:2px}.rside .mini>div:not(.th){padding-top:0}.rside .mini h3{margin-top:-2px}.rside .mini .mdesc{margin-bottom:0}.rside .mini .meta{display:block;margin-top:2px;line-height:1.3}.rside .side{row-gap:24px}.read{grid-template-columns:minmax(0,2.68fr) minmax(0,1fr)}.rside .cats9{display:none}.rside .mini{grid-template-columns:1fr;gap:6px}.rside .mini img{aspect-ratio:1200/630}}@media (max-width:699.98px){.read{grid-template-columns:minmax(0,1fr);gap:36px}.read:not(.topic) .rside .side{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:var(--card-gap-y) var(--card-gap-x)}.read:not(.topic) .rside .mini{grid-template-columns:1fr;gap:6px;margin:-6px}.read:not(.topic) .rside .mini .th{width:auto}.read:not(.topic) .rside .mini img{aspect-ratio:1200/630}.read:not(.topic) .rside .mini h3{font-size:1rem;margin-top:2px}.read:not(.topic) .rside .mini .mdesc{font-size:.9rem}.rside .cats9,.rside .mnav{display:none}.read.topic .rside{display:none}}
.arch{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:13px;align-items:start}
.archh{margin:6px 0 0}.arch .rside{position:sticky;top:82px}
.pager{display:flex;justify-content:space-between;align-items:center;margin:34px 0 0;font-size:.9rem;color:var(--dim)}
.pager a,.morelink{color:var(--head);text-decoration:none;font-weight:700;background:#272727;border-radius:10px;padding:9px 14px 7px}
.pager a:hover,.morelink:hover{background:#3f3f3f}
.morelink{display:block;text-align:center;margin-top:12px;font-size:.88rem}.rubh{scroll-margin-top:84px}html{scroll-behavior:smooth}
.srow{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 14px}.srow .smeta{margin:0;white-space:nowrap}
.acts{display:flex;gap:8px;flex:none}
.act{display:inline-flex;align-items:center;gap:6px;border:0;border-radius:10px;background:#272727;color:#ebebeb;font:inherit;font-size:.82rem;font-weight:700;padding:7px 13px 6px;cursor:pointer;transition:background .15s}
.act:hover{background:#3f3f3f}.act svg{flex:none}
.act.like[aria-pressed=true] svg{fill:#e22822;stroke:#e22822}
.act.save[aria-pressed=true] svg{fill:#ebebeb;stroke:#ebebeb}
.savedlink{position:relative;flex:none;display:grid;place-items:center;width:36px;height:36px;border-radius:10px;color:#ebebeb;margin-left:6px}
.savedlink:hover{background:#272727}
@media (min-width:601px){.brand{transform:translateX(4px)}.savedlink{transform:translateX(16px)}}
@media (max-width:600.98px){.brand{transform:translateX(-8px)}.savedlink{transform:translateX(8px)}.bar .savedlink i{line-height:13px}.sbtn{transform:translateX(16px)}}
.savedlink i{position:absolute;top:3px;right:2px;min-width:14px;height:14px;border-radius:10px;background:var(--red);color:#fff;font:800 .58rem/14px Manrope,"Manrope Fallback",sans-serif;font-style:normal;text-align:center;padding:0 3px}
.dtopics{display:grid;grid-template-columns:1fr 1fr;gap:5px;padding:0 4px}
.dtopics a{text-align:center;font-size:.84rem;font-weight:700;color:var(--fg);text-decoration:none;background:#272727;border:1px solid #272727;border-radius:10px;padding:6px 6px 5px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dtopics a:hover{background:#3f3f3f;border-color:#3f3f3f;color:var(--head)}
.dtopics a.on,.dtopics a.on:hover{background:#ebebeb;border-color:#ebebeb;color:#111}
.dsep{border:0;border-top:1px solid var(--border2);margin:12px 4px}
.dclose{margin-bottom:10px}
.dmodels{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 4px}
.dm{display:flex;flex-direction:column;border:1px solid var(--edge);border-radius:10px;overflow:hidden;text-decoration:none;color:var(--head);background:#0b0b0b;transition:border-color .15s,background .15s}
.dm:hover{border-color:#6b7d95;background:#1a1a1a}
.dm .ph{aspect-ratio:3/2;background:#000;display:flex;align-items:center;justify-content:center}
.dm .ph img{width:100%;height:100%;object-fit:contain}
.dm span{padding:7px 6px 8px;font-size:.78rem;line-height:1.25;font-weight:800;text-align:center}
.drawer h4{font-size:.7rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);margin:20px 10px 6px}
.drawer .di{display:flex;align-items:center;gap:12px;padding:9px 10px;border-radius:10px;color:#fff;text-decoration:none;font-weight:700;font-size:.92rem}
.drawer button.di,.drawer summary.di{width:100%;border:0;background:transparent;font:inherit;font-weight:700;font-size:.92rem;text-align:left;cursor:pointer;list-style:none}
.drawer summary.di::-webkit-details-marker{display:none}
.dmeer{margin-top:6px;border-top:1px solid #2a2a2a;padding-top:6px}
.dmeer-sub{display:flex;flex-direction:column;gap:1px;padding:2px 0 8px 10px}
.dmeer-sub a{display:block;padding:7px 10px;border-radius:8px;color:var(--muted);text-decoration:none;font-weight:700;font-size:.88rem}
.dmeer-sub a:hover{background:#272727;color:#fff}
.dmeer-sub a.on{background:#ebebeb;color:#111}
.dtesla{display:flex;flex-wrap:wrap;align-items:center}
.dtesla>a.di{flex:1}
.dtesla-btn{flex:none;width:36px;height:36px;border:0;border-radius:10px;background:transparent;color:var(--fg);cursor:pointer}
.dtesla-sub{flex-basis:100%;display:flex;flex-direction:column;gap:1px;padding:2px 0 8px 10px}
.dtesla-sub[hidden]{display:none}
.dtesla-sub a{display:block;padding:7px 10px;border-radius:8px;color:var(--muted);text-decoration:none;font-weight:700;font-size:.88rem}
.dtesla-sub a:hover{background:#272727;color:#fff}
.drawer .di:hover{background:var(--surface2);color:var(--head)}
.drawer .di.on{background:var(--surface2);color:var(--head);font-weight:800}
.drawer .di img,.drawer .di i{width:56px;aspect-ratio:1200/630;object-fit:cover;border-radius:10px;border:1px solid var(--edge);flex:none;background:var(--surface)}
.cats9{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:14px}
.cats9 a{text-align:center;font-size:.8rem;font-weight:700;color:var(--fg);text-decoration:none;background:#272727;border:1px solid #272727;border-radius:10px;padding:9px 6px 7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:border-color .2s,color .2s}
.cats9 a:hover{background:#3f3f3f;border-color:#3f3f3f;color:var(--head)}
.cats9 a b,.dtopics a b{font-weight:900}
.cats9 a.on,.cats9 a.on:hover{background:#ebebeb;border-color:#ebebeb;color:#111}
.mnav{display:flex;flex-direction:column;gap:14px;margin:16px 0 14px}.mgrp{display:flex;flex-direction:column;gap:6px}.mh{font-size:.74rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--blue);text-decoration:none;padding:0 12px;margin-top:4px}.mh:hover,.mh.on{text-decoration:underline;text-underline-offset:3px}.drawer .mnav{margin:8px 4px 0}
.mcell{display:grid;grid-template-columns:1fr 1fr;gap:7px;align-items:start}
.mopts{display:flex;flex-direction:column;gap:6px}
.mopts a{font-size:.8rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid #3f3f3f;border-radius:10px;padding:5px 6px 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center;transition:background .15s}
.mopts a:hover{background:#3f3f3f;color:var(--head)}.mgrp .mopts{gap:0}.mopts a.vt:nth-child(odd){background:rgba(255,255,255,.025)}.mopts a.vt:nth-child(even){background:transparent}.mopts a.vt:hover{background:rgba(255,255,255,.07)}.mopts a.vt.on{background:#333;border-color:var(--border2)}.mopts a.vt b{border-radius:10px}
.mopts a.on,.mopts a.vt.on{background:#333;border-color:#5a5a5a;color:#fff;font-weight:500}.mopts a.vt{display:flex;align-items:center;gap:14px;padding:5px 12px;text-align:left;font-size:.9rem;font-weight:400;color:var(--fg);border-radius:0;border:0;border-bottom:1px solid var(--border2)}.mopts a.vt b{flex:none;width:74px;height:50px;border-radius:10px;overflow:hidden;background:#000}@media(min-width:906px){.rside .mopts a.vt b{width:clamp(74px,30%,210px);height:auto;aspect-ratio:74/50}}.rubh{color:var(--blue);font-size:clamp(1.35rem,2.4vw,1.9rem);font-weight:800;letter-spacing:.01em;line-height:1.15;margin:26px 0 16px}.mopts a.vt b img{width:100%;height:100%;object-fit:cover;display:block}.mopts a span{overflow:hidden;text-overflow:ellipsis}
.dm.on,.dm.in{border-color:var(--head)}
.specs{width:100%;table-layout:fixed;border-collapse:collapse;margin:6px 0 10px;font-size:.92rem}
.specs th,.specs td{overflow-wrap:anywhere;padding:9px 12px;border-bottom:1px solid var(--border2);text-align:left;vertical-align:top}
.specs th{width:38%;color:var(--muted);font-weight:700}
.specs td{color:var(--head)}
.specs tr:nth-child(odd){background:rgba(255,255,255,.025)}
.mfacts .specs th,.mfacts .specs td{overflow-wrap:break-word}
.mfacts .specs th:first-child{width:24%}
.mfacts .specs td:last-child{width:18%;color:var(--muted);font-size:.82rem}
@media (max-width:699px){
  .mfacts .specs th:first-child{width:34%}
  .mfacts .specs td:last-child{width:24%;font-size:.75rem}
}
.mfacts ul{margin:8px 0 16px;padding-left:1.2rem}
.mfacts li{margin:5px 0;color:var(--head)}
.soon{color:var(--muted);background:var(--surface);border:1px dashed var(--border2);border-radius:10px;padding:14px 16px}
.tip{display:flex;align-items:center;gap:26px;margin-top:17px;padding:22px 26px;border-radius:10px;border:1px solid var(--border2);background:linear-gradient(120deg,rgba(0,212,255,.09),rgba(56,96,255,.05) 55%,rgba(255,255,255,.01))}
.tip .big{font-size:2.6rem;font-weight:800;letter-spacing:-.03em;line-height:1;color:var(--blue);white-space:nowrap}
.tip h2{font-size:1.12rem;line-height:1.25;margin-bottom:4px}
.tip p{color:var(--muted);font-size:.9rem}.tip>div:not(.big){flex:1 1 180px;min-width:0}.tip h2,.tip p{overflow-wrap:anywhere}
.tip .btn{margin-left:auto;flex:none}
.tip{text-decoration:none;color:var(--fg);transition:background .15s,border-color .15s}.tip:hover{background:linear-gradient(120deg,rgba(0,212,255,.16),rgba(56,96,255,.09) 55%,rgba(255,255,255,.04));border-color:#4a5a70}.tip:hover .btn{background:var(--red2)}
.home{margin-top:0}
article .st{font-size:clamp(1.05rem,2vw,1.3rem);line-height:1.22;letter-spacing:-.015em;margin:0 0 6px}
.st a{color:inherit;text-decoration:none}
.smeta{margin:0 0 14px;font-size:.88rem}.smeta a.tag{color:var(--blue)}.smeta a.tag:hover{color:var(--blue2)}
.byline{margin:2px 0 12px;font-size:.82rem;line-height:1.3;color:var(--dim)}.byline a{color:inherit;text-decoration:none}.byline a:hover{text-decoration:underline}
.nextread{margin:8px 0 12px;padding:18px 3vw 0;border-top:1px solid var(--border2)}.nextread h2{font-size:1.2rem;margin:0 0 12px}.nextread .grid2{margin-top:0;gap:14px}@media (max-width:600.98px){.nextread{padding-left:0;padding-right:0}}
.sideh{font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:var(--blue);margin:11px 0 -2px;padding-top:9px;border-top:1px solid var(--border2)}
.hi,.th,.im{position:relative}.hi{margin:0 0 8px}.hi .hero-img{margin:0}
.livebadge{position:absolute;top:8px;left:8px;z-index:3;background:#e10600;color:#fff;font-size:.7rem;font-weight:800;letter-spacing:.08em;line-height:1;padding:4px 6px;border-radius:4px}
.pv-min.live{background:#e10600}
.pv-min.live b,.pv-min.live small{color:#fff}
.livefeed{list-style:none;margin:8px 0 22px;padding:0}
.livefeed li{padding:12px 0;border-top:1px solid #2a2a2a}
.livefeed time{display:block;color:var(--dim);font-size:.78rem;font-weight:800;margin-bottom:4px}
.livefeed p{margin:0 0 6px}
.dur{display:inline-flex;align-items:center;gap:4px;position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.8);color:#fff;font-size:.74rem;font-weight:700;line-height:1;padding:4px 6px;border-radius:10px;cursor:help}.agotip{position:fixed;z-index:60;pointer-events:none;background:rgba(0,0,0,.88);color:#fff;font-size:.74rem;font-weight:700;line-height:1;padding:5px 7px;border-radius:10px;white-space:nowrap}time.ago{cursor:help}.im,.th,.hi{container-type:inline-size}.kk{position:absolute;left:2.6cqw;bottom:2.6cqw;z-index:2;pointer-events:none;font-family:Inter,Manrope,"Manrope Fallback",system-ui,sans-serif;font-weight:900;letter-spacing:-.01em;text-transform:uppercase;line-height:1}.kk b{display:table;font-weight:900;white-space:nowrap}.kk b+b{margin-top:.1em}.kk i{font-style:normal;display:inline-block}.kk .yo{color:#ffd400;text-shadow:-.16cqw -.16cqw 0 #666666,.16cqw -.16cqw 0 #666666,-.16cqw .16cqw 0 #666666,.16cqw .16cqw 0 #666666,0 .2cqw 0 #666666,0 -.2cqw 0 #666666,.2cqw 0 0 #666666,-.2cqw 0 0 #666666,0 .5cqw 1.2cqw rgba(0,0,0,.45)}.kk .bk i{background:#d61a1a;color:#fff;padding:.13em .24em .12em;box-shadow:0 .4cqw 1.2cqw rgba(0,0,0,.35)}.kk.p-bw .bk i,.kk.p-by .bk i{background:#1d5cff}.kk.p-gy .bk i{background:#0a7737}.kk.p-yk .bk i{background:#ffd400;color:#111}.kk.p-gy .yo{color:#ffd400;text-shadow:0.16cqw 0.16cqw 0 #666666,-0.16cqw 0.16cqw 0 #666666,0.16cqw -0.16cqw 0 #666666,-0.16cqw -0.16cqw 0 #666666,0cqw 0.2cqw 0 #666666,0cqw -0.2cqw 0 #666666,0.2cqw 0cqw 0 #666666,-0.2cqw 0cqw 0 #666666,0 .5cqw 1.4cqw rgba(0,0,0,.5)}.kk.p-wb .bk i{background:#fff;color:#1d5cff}.kk.p-bw .yo{color:#fff;text-shadow:0.16cqw 0.16cqw 0 #0b2f8f,-0.16cqw 0.16cqw 0 #0b2f8f,0.16cqw -0.16cqw 0 #0b2f8f,-0.16cqw -0.16cqw 0 #0b2f8f,0 .2cqw 0 #0b2f8f,0 -.2cqw 0 #0b2f8f,.2cqw 0 0 #0b2f8f,-.2cqw 0 0 #0b2f8f,0 .5cqw 1.4cqw rgba(0,0,0,.6)}.kk.p-wb .yo{color:#3d7bff;text-shadow:0.16cqw 0.16cqw 0 #fff,-0.16cqw 0.16cqw 0 #fff,0.16cqw -0.16cqw 0 #fff,-0.16cqw -0.16cqw 0 #fff,0 .2cqw 0 #fff,0 -.2cqw 0 #fff,.2cqw 0 0 #fff,-.2cqw 0 0 #fff,0 .5cqw 1.4cqw rgba(0,0,0,.5)}.kk.p-by .yo{color:#ffd400;text-shadow:0.16cqw 0.16cqw 0 #666666,-0.16cqw 0.16cqw 0 #666666,0.16cqw -0.16cqw 0 #666666,-0.16cqw -0.16cqw 0 #666666,0 .2cqw 0 #666666,0 -.2cqw 0 #666666,.2cqw 0 0 #666666,-.2cqw 0 0 #666666,0 .5cqw 1.4cqw rgba(0,0,0,.5)}.kk .nb{font-size:1.32em}.kk .bk .nb{font-size:1.22em}.kk .l1{font-size:6.4cqw}.kk .l2{font-size:8cqw}.th .dur{right:6px;bottom:6px;font-size:.68rem;padding:3px 5px}.th .dur svg{width:12px;height:12px}
/* buttons, labels */
.btn{display:inline-flex;align-items:center;justify-content:center;background:var(--red);color:#fff;font-weight:800;font-size:.9rem;padding:11px 20px;border-radius:10px;text-decoration:none;transition:background .2s}
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
.hero{position:relative;overflow:hidden;border-radius:10px;background:radial-gradient(ellipse at 85% 40%,rgba(0,212,255,.14),transparent 60%),linear-gradient(135deg,#0b1320,#04060a);min-height:340px;margin-top:24px;display:flex;align-items:center}
.hero img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center right}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(4,6,10,.96) 0%,rgba(4,6,10,.7) 45%,rgba(4,6,10,.12) 100%)}
.hero .in{position:relative;z-index:2;max-width:520px;padding:36px 32px}
.eyebrow{display:inline-block;font-size:.7rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--blue);border:1px solid rgba(0,212,255,.35);background:rgba(0,212,255,.1);padding:4px 11px;border-radius:10px;margin-bottom:14px}
.hero h1{font-size:clamp(1.8rem,4vw,2.7rem);line-height:1.08;letter-spacing:-.025em;margin-bottom:12px}
.hero h1 span{color:var(--red)}
.hero p{color:#c9ced3;font-size:1rem;margin-bottom:20px}
#news .h2{margin-top:18px}
.hero .btns{display:flex;gap:10px;flex-wrap:wrap}
/* top stories */
.tops{display:grid;grid-template-columns:1.6fr 1fr;gap:44px}
.feature{text-decoration:none;color:var(--fg);display:block}
.feature .im,.card .im{overflow:hidden;border-radius:10px;border:1px solid var(--edge);background:var(--surface);transition:border-color .2s}

.feature img,.card img{width:100%;aspect-ratio:1200/630;object-fit:cover;transition:transform .4s}

.feature h3{font-size:clamp(1.4rem,2.8vw,2rem);line-height:1.15;letter-spacing:-.02em;margin:14px 0 8px}
.feature p{color:var(--muted);margin-bottom:8px}
.side{display:flex;flex-direction:column;gap:10px}
.mini{display:grid;grid-template-columns:calc((100% - 26px) * 2 / 3 + 7px) 1fr;gap:8px;text-decoration:none;color:var(--fg);align-items:start;box-sizing:border-box}.mini>div{overflow:hidden}
.th{width:100%}.mini img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:10px;border:1px solid var(--edge)}
.mini>div{padding:0 4px 2px 0}.mini>.th{padding-top:0}
.mini h3{font-size:.98rem;line-height:1.3;margin:6px 0 4px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.mini .tag{display:block;line-height:1;margin-top:0}

/* grid */
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--card-gap-y) var(--card-gap-x)}
.card{text-decoration:none;color:var(--fg);display:flex;flex-direction:column}
.card.lead{grid-column:span 2}
.leadside{display:flex;flex-direction:column;justify-content:space-between;gap:28px}
.leadside .card p{display:none}
.leadside .card .body{padding-top:0}
.leadside .card h3{font-size:1rem;margin-bottom:0}
.card.lead h3{font-size:clamp(1.35rem,2.4vw,1.85rem);line-height:1.2;letter-spacing:-.02em}
.card.lead p{font-size:1rem;-webkit-line-clamp:2}
.card .body{padding:0}
.card h3{font-size:1.08rem;line-height:1.3;margin:0 0 6px}.card h3{font-weight:700;color:#ebebeb}.grid2>.card h3{font-size:1rem}.mini h3{font-weight:700;font-size:.9rem;color:#ebebeb}.mini h3{margin-top:0}.meta>time.ago::before{content:'';display:inline-block;width:.62em;height:.72em;margin-right:.42em;vertical-align:-.04em;background:currentColor;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 12'%3E%3Cpath d='M1.2 1.2v9.6L9 6z' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 12'%3E%3Cpath d='M1.2 1.2v9.6L9 6z' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E") center/contain no-repeat}.smeta time.ago::before{content:none}.mini .mdesc{margin-bottom:0}.mini .meta{display:block;margin-top:3px;line-height:1.3}@media (min-width:905px){.rside .mini>div:not(.th){padding-top:0;contain:size;overflow:visible}.rside .mini h3{margin-top:0;line-height:1.22}.rside .mini .mdesc{line-height:1.25}.rside .mini .meta{margin-top:2px}}.mdesc{color:var(--muted);font-size:.8rem;line-height:1.35;margin:0 0 4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}@media (max-width:904.98px){.rside .mini h3{-webkit-line-clamp:2}.rside .mini .mdesc{-webkit-line-clamp:1}}.shintro{color:var(--muted);margin:4px 0 18px;font-size:.95rem}.shintro a{color:inherit}.shgrid{margin-top:14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:var(--card-gap-y) var(--card-gap-x)}.shc{display:flex;flex-direction:column;gap:0;min-width:0}
.shc .sht{margin-top:0}.shv{position:relative;display:block;width:100%;aspect-ratio:9/16;padding:0;border:0;border-radius:10px;overflow:hidden;background:#000;cursor:pointer}.shv img{width:100%;height:100%;object-fit:cover;display:block}.dur .dv{display:inline-flex;align-items:center;gap:3px;font-style:normal;margin-left:5px;padding-left:6px;border-left:1px solid rgba(255,255,255,.35)}.dur.dvo .dv{margin-left:0;padding-left:0;border-left:0}.vpl{position:absolute;left:50%;top:50%;width:15cqw;height:15cqw;min-width:38px;min-height:38px;max-width:84px;max-height:84px;transform:translate(-50%,-50%);border-radius:50%;background:rgba(0,0,0,.55);box-shadow:0 0 0 2px rgba(255,255,255,.9);pointer-events:none;z-index:2}.vpl::after{content:"";position:absolute;left:54%;top:50%;transform:translate(-50%,-50%);border-left:.62em solid #fff;border-top:.4em solid transparent;border-bottom:.4em solid transparent;font-size:clamp(20px,6.5cqw,40px)}.hi[data-vid]{cursor:pointer}.hi[data-vid]:hover .vpl{background:rgba(220,30,30,.85)}.hi.on{aspect-ratio:16/9;background:#000;border-radius:10px;overflow:hidden}@media (max-width:600.98px){.read .hi.on{border-radius:0}}.hi.on iframe{position:absolute;inset:0;width:100%;height:100%;border:0}iframe:fullscreen,iframe:-webkit-full-screen{width:100vw!important;height:100vh!important;inset:0!important}.avid{margin:18px 0 22px}.avb{position:relative;display:block;width:100%;aspect-ratio:16/9;padding:0;border:0;border-radius:12px;overflow:hidden;background:#000;cursor:pointer}.avb img{width:100%;height:100%;object-fit:cover;display:block}.avb iframe{position:absolute;inset:0;width:100%;height:100%;border:0}.avb .shp{width:68px;height:68px;margin:-34px 0 0 -34px}.avb .shp::after{left:26px;top:20px;border-left-width:22px;border-top-width:14px;border-bottom-width:14px}.avid figcaption{color:var(--muted);font-size:.8rem;margin-top:6px}.shm{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center}.shbox{height:min(92vh,1100px);aspect-ratio:9/16;max-width:100vw;border-radius:12px;overflow:hidden;background:#000}.shbox iframe{width:100%;height:100%;border:0;display:block}.shx{position:absolute;top:14px;right:14px;width:44px;height:44px;border-radius:50%;border:0;background:rgba(40,40,40,.85);cursor:pointer}.shx::before,.shx::after{content:"";position:absolute;left:12px;top:21px;width:20px;height:2px;background:#fff;border-radius:2px;transform:rotate(45deg)}.shx::after{transform:rotate(-45deg)}.shx:hover{background:#444}@media (max-width:600.98px){.shm{background:#000;align-items:flex-end}.shbox{width:100vw;height:calc(100vh - 56px);height:calc(100dvh - 56px);aspect-ratio:auto;border-radius:0}.shx{top:6px;right:8px}}.shp{position:absolute;left:50%;top:50%;width:54px;height:54px;margin:-27px 0 0 -27px;border-radius:50%;background:rgba(0,0,0,.55);box-shadow:0 0 0 2px rgba(255,255,255,.85)}.shp::after{content:"";position:absolute;left:21px;top:16px;border-left:17px solid #fff;border-top:11px solid transparent;border-bottom:11px solid transparent}.sht{font-weight:700;font-size:.92rem;line-height:1.3;color:#ebebeb;text-decoration:none;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}a.sht:hover{text-decoration:underline}.shc .meta{font-size:.74rem}@media (max-width:600.98px){.shgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--card-gap-y) var(--card-gap-x)}}.mini .meta{font-size:.74rem}
.card p{color:var(--muted);font-size:.9rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.empty{color:var(--muted);background:var(--surface);border:1px dashed var(--border2);border-radius:10px;padding:28px;text-align:center}
/* models */
.models{display:grid;grid-template-columns:repeat(7,1fr);gap:var(--card-gap-y) var(--card-gap-x)}
.model{display:flex;flex-direction:column;background:transparent;border:0;text-decoration:none;color:var(--head)}
.model .ph{aspect-ratio:3/2;background:#000;display:flex;align-items:center;justify-content:center;border-radius:10px;overflow:hidden}
.model img{width:100%;height:100%;object-fit:contain}
.model .ph b{font-size:1.5rem;color:#2a3544;letter-spacing:-.02em}
.model span{padding:10px 8px;font-size:.82rem;line-height:1.3;font-weight:800;text-align:center}
/* why */
.why{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.why div{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px}
.why i{display:inline-flex;width:32px;height:32px;border-radius:10px;background:rgba(0,212,255,.12);align-items:center;justify-content:center;color:var(--blue);font-weight:800;font-style:normal;margin-bottom:10px}
.why b{display:block;color:var(--head);font-size:.98rem;margin-bottom:4px}
.why p{font-size:.86rem;color:var(--muted)}.why div{min-width:0}.why b,.why p{overflow-wrap:anywhere;hyphens:auto}@media (max-width:380.98px){.why{grid-template-columns:minmax(0,1fr)!important}}
/* page heads */
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.ptop{height:36px}
.phead{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:36px 0 22px;border-bottom:1px solid var(--border);margin-bottom:28px}
.versions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:30px}
.versions span{font-size:.8rem;font-weight:700;color:var(--dim);margin-right:4px}
.versions a{font-size:.84rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid var(--border2);border-radius:10px;padding:6px 13px;transition:border-color .2s,color .2s}
.versions a:hover{color:var(--head);border-color:var(--blue)}
.versions a.on{color:#03131a;background:var(--blue);border-color:var(--blue)}
.phead h1{font-size:clamp(2rem,5vw,3rem);letter-spacing:-.03em;line-height:1.05}
.phead p{color:var(--muted);margin-top:6px}
.phead img{width:min(420px,45%);flex:none;border-radius:10px;border:1px solid var(--edge)}
/* article */
article{padding:13px 0 8px}
@media (min-width:901px){
.sheet-main>article.narrow{padding-top:0}
.sheet-main>article.narrow>h1:first-child{margin-top:0}
.sheet-main article.money>h1:first-child{margin-top:0}
.sheet-main .archh{margin-top:0}
.sheet-main>header.hubhead{padding-top:0}
}
article h1{font-size:clamp(1.8rem,4.6vw,2.6rem);line-height:1.12;letter-spacing:-.025em;margin:10px 0 14px}
article .lead{font-size:1.12rem;line-height:1.38;color:var(--muted);margin:0 0 22px}
article .hero-img{border-radius:10px;margin:0 0 26px;aspect-ratio:1200/630;width:100%;object-fit:cover;border:1px solid var(--edge)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:-8px 0 24px}
.chips a{font-size:.78rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid var(--border2);border-radius:10px;padding:3px 10px}
.chips a:hover{color:var(--head);border-color:var(--head)}
.prose h2{font-size:1.25rem;line-height:1.3;letter-spacing:-.015em;margin:26px 0 10px}
article .prose{font-size:17px}article .prose,article .lead{max-width:860px}article .prose p,article .prose ul,article .prose ol{margin-right:14px}article .prose h2{clear:right}.beside{display:flow-root;margin-bottom:22px}.beside>:last-child{margin-bottom:0}.beside+*{clear:left}article .prose p,article .prose ul,article .prose ol{margin-left:14px}article .prose ul{list-style:none;padding-left:0}article .prose ul>li{position:relative;padding-left:15px}article .prose ul>li::before{content:"";position:absolute;left:0;top:.68em;width:6px;height:6px;border-radius:50%;background:var(--blue)}article .prose ol{padding-left:18px}article .prose h2{border-left:3px solid var(--blue);padding-left:11px;scroll-margin-top:84px}.toc{float:left;width:max-content;max-width:44%;margin:4px 22px 12px 14px;padding:12px 16px;border:1px solid var(--border2);border-radius:10px;background:rgba(255,255,255,.03)}.toc b{display:block;font-size:.7rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--blue);margin-bottom:8px}.toc ol{margin:0;padding-left:20px;font-size:.88rem;line-height:1.5}.toc li{margin:3px 0}.toc li::marker,article .prose .toc li::marker{color:var(--dim)}.toc a,.prose .toc a{color:var(--fg);text-decoration:none}article .prose .toc ol{margin:0;padding-left:20px}.toc a:hover{color:var(--blue)}.pblock{display:flex;gap:20px;align-items:flex-start;margin-bottom:22px}.ptxt{flex:1;min-width:0}.ptxt>:last-child{margin-bottom:0}.pimg{flex:none;width:33%;margin:5px 0 0}.pimg img{width:100%;height:100%;aspect-ratio:3/4;object-fit:cover;object-position:center;border-radius:10px;border:1px solid var(--edge);display:block}html{scroll-behavior:smooth}article .prose{line-height:1.5}.prose p,.prose ul,.prose ol{margin-bottom:22px}
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
.sources ul{margin-top:10px;padding:12px 16px 12px 32px;background:var(--surface);border-radius:10px}
.sources li{margin-bottom:4px}article .prose h2,article .prose li,article h1,article .lead{text-align:left}@media (min-width:601px){article .prose>p{text-align:justify;-webkit-hyphens:auto;hyphens:auto;hyphenate-limit-chars:7 3 3}}article .prose,article .lead{max-width:none;box-sizing:border-box;padding-left:3vw;padding-right:3vw}article .lead{padding-left:calc(3vw + 14px);padding-right:calc(3vw + 14px)}@media (max-width:600.98px){article .prose,article .lead{padding-left:0;padding-right:0}article .lead{padding-left:4px;padding-right:4px}article .prose p,article .prose ul,article .prose ol,article .prose h2{margin-left:4px;margin-right:4px}article .prose .gtable,article .prose .gbox{display:block;width:calc(100% - 8px);max-width:calc(100% - 8px);margin-left:4px;margin-right:4px;box-sizing:border-box}}article .sources{padding-bottom:20px;border-bottom:1px solid var(--border2)}@media(min-width:601px){.tip{padding-top:37px;padding-bottom:37px}}
.sources a{color:var(--muted)}
/* footer */
footer{border-top:1px solid var(--border);margin-top:14px;padding:15px 0 40px;font-size:.85rem;color:var(--dim)}
footer .fbrand{margin:0;min-width:0}
footer .fgrid{display:grid;grid-template-columns:minmax(168px,220px) repeat(5,minmax(max-content,1fr));column-gap:clamp(8px,1.35vw,22px);row-gap:16px;align-items:start}
footer .fcols,footer .fstack{display:contents}
footer .fcol.c1{grid-column:2}footer .fcol.c2{grid-column:3}footer .fcol.c3{grid-column:4}footer .fcol.c4{grid-column:5}footer .fcol.c5{grid-column:6}footer .fcol{grid-row:1}
footer .fbrand p,footer .nform{max-width:none}
footer details.fcol{min-width:0}
footer summary.flabel{cursor:pointer}
footer summary.flabel::-webkit-details-marker{display:none}
@media (min-width:700px){footer summary.flabel{pointer-events:none}}
footer a{color:var(--muted);text-decoration:none}
footer a:hover{color:#00d4ff}
footer .flabel{font-size:.7rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--blue);margin:6px 0 12px}
footer .flist{display:grid;gap:7px 18px}footer .flist.two{grid-template-columns:1fr 1fr}
footer .fbrand p{margin-top:12px;max-width:none;line-height:1.5}
footer .fcopy{margin-top:32px;padding-top:18px;border-top:1px solid var(--border)}
@media (max-width:1000.98px){.grid{grid-template-columns:repeat(2,1fr);gap:var(--card-gap-y) var(--card-gap-x)}.leadside{grid-column:span 2;flex-direction:row}.leadside .card{flex:1}.tops{grid-template-columns:1fr}.arch{grid-template-columns:minmax(0,1fr);gap:36px}.why{grid-template-columns:repeat(2,1fr)}.models{grid-template-columns:repeat(4,1fr);gap:var(--card-gap-y) var(--card-gap-x)}}
@media (max-width:860.98px){.search{display:none}.sbtn{display:grid}.sopen .search{display:flex;position:absolute;left:0;right:0;top:0;bottom:0;height:auto!important;width:auto!important;margin-left:0!important;max-width:none;z-index:41;padding:9px 12px;background:#161616;align-items:center}.sopen .search input,.sopen .search>button{height:38px}.sopen .search input{background:#121212}html.hass .bar .search{display:flex;position:relative;left:auto;right:auto;top:auto}html.hass .bar .sbtn{display:none}html.hass .bar .savedlink{margin-left:auto}html.hass .bar .search{margin-right:0;flex-shrink:0}html.hass .bar .brand{flex-shrink:0}html.hass .bar .savedlink{transform:none}.tip{flex-wrap:wrap;gap:14px 20px}.tip .btn{margin-left:0}}
@media (max-width:860px){footer .fgrid{display:block}footer .fbrand{width:100%;margin-bottom:12px}footer .fstack{display:contents}footer .fcols{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));column-gap:clamp(8px,1.4vw,16px);width:100%}footer .fcol.c1{grid-column:1}footer .fcol.c2{grid-column:2}footer .fcol.c3{grid-column:3}footer .fcol.c4{grid-column:4}footer .fcol.c5{grid-column:5}footer .fcol{grid-row:1}}
@media (max-width:700px){footer .fcols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);column-gap:16px;align-items:start;width:100%}footer .fstack{display:flex;flex-direction:column;gap:16px;min-width:0}footer .fcol.c1,footer .fcol.c2,footer .fcol.c3,footer .fcol.c4,footer .fcol.c5{grid-column:auto;grid-row:auto}footer .flabel{margin-top:0;margin-bottom:8px}}
@media (max-width:600.98px){.wrap{padding:0 12px}
.bar{gap:4px;height:56px}.drawer,.scrim{top:56px}.burger{margin-left:-14px}.logo{font-size:1.15rem}.brand{margin-left:2px}
.sbtn{margin-left:auto;width:36px;height:36px;border:0;background:transparent}.savedlink{margin-left:-2px;width:34px;height:34px}.lang{margin-left:0;margin-right:-10px;font-size:.7rem;padding:3px 9px}
.read .hi{margin:0 -12px 6px}.read .hi .hero-img{border-radius:0;border:0}.hi .dur{right:12px}
article .st{font-size:1rem;line-height:1.25}.srow{flex-wrap:nowrap;gap:8px}.srow .acts{display:flex;gap:6px}.srow .smeta{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}.toc{float:none;width:auto;max-width:none;margin:0 0 0 14px}footer a{overflow-wrap:anywhere}footer summary.flabel{pointer-events:auto}.act{padding:7px 10px 6px}article .lead{font-size:1.02rem}.smeta{font-size:.82rem}
article .prose{font-size:16px}article .prose h2{font-size:1.08rem}.grid2{grid-template-columns:1fr;gap:59px}.grid2.gall{grid-template-columns:1fr;gap:var(--card-gap-y) var(--card-gap-x)}.gall>.card h2,.gall>.card h3{font-size:1rem}.gall>.card p{font-size:.9rem}.side{gap:29px}.grid2>.card{grid-template-columns:1fr;gap:0}.grid2>.card .im{height:auto;width:auto}.grid2>.card .im img{aspect-ratio:1200/630}.grid2>.card .body{padding:0}.card.lead{grid-column:auto}.leadside{grid-column:auto;flex-direction:column;gap:40px}.leadside .card p{display:-webkit-box}.mini{grid-template-columns:1fr;gap:6px;height:auto}.mini>div{height:auto}.th{width:100%;height:auto}.mini img{width:100%;height:auto;aspect-ratio:1200/630}#news .h2{margin-top:16px}.grid{grid-template-columns:1fr;gap:var(--card-gap-y) var(--card-gap-x)}.why{grid-template-columns:1fr 1fr;gap:10px}.why div{padding:14px}.why p{font-size:.8rem}
 .models{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;margin:0 -24px;padding:0 24px 4px}.models::-webkit-scrollbar{display:none}.models{gap:var(--card-gap-x)}.model{flex:0 0 46%;scroll-snap-align:start}
 body{font-size:16.5px}.h2{margin-top:20px}.hero{min-height:0}.hero .in{padding:26px 20px}.hero .btn{flex:1;white-space:nowrap;padding:11px 12px}
 .phead{flex-direction:column-reverse;align-items:flex-start}.phead img{width:100%}}

/* wider than the page (e.g. zoomed far out): framed page, black outside */
@media (min-width:1946px){html{background:#000}body{max-width:1944px;margin:0 auto;border-left:1px solid #2e2e2e;border-right:1px solid #2e2e2e;box-shadow:0 0 0 1px #000,0 0 60px rgba(255,255,255,.04)}}

.gall>.xtra{display:none}.gall>.xtra.on{display:grid}

/* header controls: same border colour as the photos */
.bar .search input,.bar .search>button,.bar .tdd .tdb,.bar .tdd .tdl,.bar .lang,.sbtn{border-color:#3a4a60}
.act,.morelink,.pager a{box-shadow:inset 0 0 0 1px #3a4a60}

/* shadow edge at the very top: 60px, dark fading down, behind the logo and controls */
header.top::before{content:"";position:absolute;left:0;right:0;top:0;height:60px;background:linear-gradient(#0f0f0f,rgba(15,15,15,0));pointer-events:none;z-index:-1}

.imgnote{color:var(--muted);font-size:.8rem;margin:10px 0 0;opacity:.8}
article .sources:has(+ .imgnote){padding-bottom:0;border-bottom:0}
article .imgnote{padding-bottom:20px;border-bottom:1px solid var(--border2)}

.cform{display:grid;gap:14px;margin-top:22px;max-width:620px}.cform label{display:grid;gap:6px;font-size:.9rem;color:var(--muted)}
.cform input,.cform textarea{background:#121212;border:1px solid #3a4a60;border-radius:10px;color:var(--head);font:inherit;font-size:1rem;padding:10px 14px}
.cform input:focus,.cform textarea:focus{outline:none;border-color:#1c62b9}
.cform button{justify-self:start;background:#e8231c;color:#fff;border:0;border-radius:10px;font:inherit;font-weight:700;padding:11px 22px;cursor:pointer}
.cform button:disabled{opacity:.6;cursor:default}.cform .hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}.cstatus{min-height:1.4em;margin:0}

/* static pages (about, privacy, contact): title and text start on the same line */
article.narrow > h1{margin-left:14px}article.narrow .cform{margin-left:14px}

/* mobile search: results attach to the bar, fill the screen, cards with the photo on top */
.sopen .search .res{top:100%;left:0;right:0;margin:0;border-radius:0 0 10px 10px;border-top:0;max-height:calc(100vh - 56px);max-height:calc(100dvh - 56px);padding:10px 12px}
.sopen .search .res a{display:block;padding:8px 0 12px;border-bottom:1px solid var(--border2);border-radius:0}
.sopen .search .res a:last-child{border-bottom:0}
.sopen .search .res img{width:100%;border-radius:10px;margin-bottom:8px;border:1px solid #3a4a60}
.sopen .search .res b{font-size:1rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.sopen .search .res small{display:block;margin-top:3px}

/* search results follow the width of the search field: narrow field -> cards with the photo on top */
.search{container:srch/inline-size}
.res small{display:block;line-height:1.4;margin-top:3px}
.bar .search .res{min-width:300px}
@container srch (max-width:400px){
.res{padding:8px 10px}
.res a{display:block;padding:8px 0 12px;border-bottom:1px solid var(--border2);border-radius:0}
.res a:last-child{border-bottom:0}
.res a:hover{background:none}.res a:hover b{color:#fff;text-decoration:underline}
.res img{width:100%;border-radius:10px;margin-bottom:8px;border:1px solid #3a4a60}
.res b{font-size:.95rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
}

.res a{align-items:flex-start}.res img{object-fit:cover;max-width:40%}
.res b{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.6em}
.res a,.sopen .search .res a{display:flex!important;gap:12px;align-items:center}.res img,.sopen .search .res img{margin:0;flex:none;max-width:none;aspect-ratio:auto}.res a>span:not(.zimg){flex:1;min-width:0}
.res small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.drawer .dmodels{display:none}.drawer .dmodels.show{display:block}
.dpri{display:flex;flex-direction:column;gap:2px;padding:0 4px 4px}
.pnav{display:none}
@media (min-width:700px){.pnav{display:flex;align-items:center;gap:2px;height:44px;margin:0 0 8px;overflow-x:auto;scrollbar-width:none}.pnav::-webkit-scrollbar{display:none}}
.pn{display:flex;align-items:center;height:36px;padding:0 10px;border-radius:5px;color:var(--fg);text-decoration:none;font-size:.84rem;font-weight:700;white-space:nowrap}
.pn:hover{background:#272727;color:#fff}
.pn.on,.pdrop.on>.pn,header.hb .mdrop>button.pn.on{background:#ebebeb;color:#111;border-radius:5px}
.pdrop{position:relative;display:flex;align-items:center;z-index:0}
.pmenu{display:none;position:absolute;top:calc(100% - 1px);left:0;min-width:210px;z-index:50;background:#2a2a2a;border:1px solid rgba(255,255,255,0.28);border-radius:0 5px 5px 5px;padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.45)}
.pdrop::after{content:"";position:absolute;top:calc(100% - 6px);left:0;width:240px;height:14px;z-index:49}
.pdrop:hover,.pdrop:focus-within,.pdrop.is-open{z-index:2}
.pdrop:hover .pmenu,.pdrop:focus-within .pmenu,.pdrop.is-open .pmenu{display:grid}
.pdrop.tone-tesla{--accent:#e31937;--accent-ink:#ff8a9b}
.pdrop.tone-energy{--accent:#4cd964;--accent-ink:#b8ffc6}
.pdrop.tone-spacex{--accent:#ff7a00;--accent-ink:#ffc48a}
.pdrop.tone-link{--accent:#00d1ff;--accent-ink:#a6f4ff}
.pdrop.tone-spacexsi{--accent:#ffc400;--accent-ink:#ffe28a}
.pdrop.tone-neural{--accent:#ff2d95;--accent-ink:#ffb3d6}
.pdrop.tone-boring{--accent:#2f6bff;--accent-ink:#b3c8ff}
.pdrop:hover>a.pn,.pdrop:focus-within>a.pn,.pdrop.is-open>a.pn{position:relative;z-index:51;background:#2a2a2a;color:#fff;border:1px solid rgba(255,255,255,0.28);border-bottom:0;border-radius:5px 5px 0 0;box-shadow:0 1px 0 #2a2a2a}
.pmenu a.child{padding-left:26px;font-weight:650;color:#b7c0cc}
.dlayer{margin:0 0 8px}
.drawer a.tone-tesla,.drawer a.tone-energy,.drawer a.tone-spacex,.drawer a.tone-link,.drawer a.tone-spacexsi,.drawer a.tone-neural,.drawer a.tone-boring{color:#fff}
.dsub{display:flex;flex-direction:column;gap:1px;padding:2px 0 4px 12px}
.dsub a{display:block;padding:6px 10px;border-radius:8px;color:var(--muted);text-decoration:none;font-weight:700;font-size:.86rem}
.dsub a.child{padding-left:22px;font-weight:650;font-size:.82rem}
.dsub a:hover{background:#272727;color:#fff}
.dsub a.on{background:#ebebeb;color:#111}
.drawer a.dmap{margin-top:8px;border-top:1px solid #2a2a2a;padding-top:12px}
.pdrop:last-child .pmenu{left:auto;right:0;border-radius:5px 0 5px 5px}
.pdrop:last-child::after{left:auto;right:0}
.pmenu a{padding:8px 12px;border-radius:8px;color:#ebebeb;text-decoration:none;font-size:.86rem;font-weight:700;white-space:nowrap}
.pmenu a:hover{background:#3a3a3a}
.pmenu a.on,.pmenu a.on:hover{background:#ebebeb;color:#111}
.crumbs{margin:-2px 0 4px;font-size:.82rem;color:var(--dim)}
.crumbs ol{display:flex;flex-wrap:wrap;align-items:center;gap:6px 0;list-style:none;padding:0;margin:0}
.crumbs li{display:flex;align-items:center;min-width:0}
.crumbs li:not(:last-child)::after{content:" / ";color:var(--dim);margin:0;white-space:pre}
.crumbs a{color:var(--muted);text-decoration:none}
.crumbs a:hover{color:var(--head)}
.crumbs li:last-child{min-width:0;flex:1 1 auto;overflow:hidden}
.crumbs [aria-current]{color:var(--fg);display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hubhead{padding:18px 0 6px}
.hubhead h1{font-size:clamp(1.8rem,4vw,2.7rem);letter-spacing:-.03em;line-height:1.08;margin:0 0 10px}
.hubhead .lead{font-size:1.08rem;line-height:1.55;color:var(--muted);max-width:none;margin:0 0 16px 1px}
.mgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 8px;margin:0 0 28px}
@media (min-width:560px){.mgrid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (min-width:760px){.mgrid{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media (min-width:901px){.mgrid{grid-template-columns:repeat(5,minmax(0,1fr))}}
.mcard{display:flex;flex-direction:column;align-items:flex-start;gap:6px;min-width:0;text-decoration:none;color:inherit}
.mcard .mim{display:block;width:100%;border-radius:10px;overflow:hidden;border:0;background:#000;aspect-ratio:16/9}
.mcard .mim img{width:100%;height:100%;object-fit:cover}
.mcard .mname{display:block;max-width:100%;font-weight:800;font-size:.84rem;line-height:1.2;overflow-wrap:break-word}
@media (min-width:901px){.mcard .mname{font-size:.76rem}}
.mcard .mcap{display:block;max-width:100%;font-size:.72rem;line-height:1.3;font-weight:600;color:var(--muted);overflow-wrap:break-word}
.mhero{margin:0 0 16px;background:transparent}
.mhero picture,.mhero>img{display:block;border-radius:12px;overflow:hidden;border:1px solid var(--edge);background:#000}
.mhero img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.mhero.natural img{aspect-ratio:auto;object-fit:contain;background:#0c0e12}
.mhero figcaption{margin-top:8px}
.mintro{font-size:1.08rem;line-height:1.55;color:var(--muted);margin:0 0 18px;max-width:none}
.mfacts{margin:0 0 4px}
.mfacts h2{font-size:1.15rem;margin:0 0 8px}
.starthere{margin:6px 0 26px;padding:16px 16px 18px;border:1px solid rgba(0,212,255,.35);border-radius:12px;background:rgba(0,212,255,.06)}
.starthere>h2{margin:0 0 4px;font-size:1.25rem}
.starthere>.sub{margin:0 0 12px}
.aread{max-width:760px;margin:0 auto}
.aread.with-side{max-width:760px}
@media (min-width:960px){.aread.with-side{max-width:1100px;display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:28px;align-items:start}}
.ad-side-wrap{display:none}
@media (min-width:960px){.ad-side-wrap{display:block;position:sticky;top:120px}}
article.money{padding-top:6px}.sheet-main>article.money{padding-top:0}
article.money h1.atitle{font-size:clamp(1.85rem,4.5vw,2.7rem);line-height:1.14;letter-spacing:-.025em;margin:8px 0 10px;max-width:18em}
article.money .lead{font-size:1.16rem;line-height:1.55;max-width:40em}
article.money .prose{font-size:1.075rem;line-height:1.75;max-width:68ch}
article.money .prose p{margin-bottom:1.15em}
article.money .toc{float:none;width:auto;max-width:68ch;margin:4px 0 20px}
article.money .prose h2{scroll-margin-top:130px}
.leadstory{display:flex;flex-direction:column;gap:0;margin:10px 0 8px;padding:0}
.leadstory .lead{padding:0;max-width:65ch}
.leadstory .leadim{display:block;border-radius:12px;overflow:hidden;border:1px solid var(--edge);background:#000;cursor:default}
.leadstory img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.leadstory .ltitle{font-size:clamp(1.35rem,2vw,1.7rem);line-height:1.2;letter-spacing:-.02em;margin:0 0 12px 1px;font-weight:800}
.leadstory .btn{margin-bottom:22px}
.leadstory .ltitle a,.card.lead .body a,.pv-lead a{color:inherit;text-decoration:none}
.leadstory .ltitle a:hover,.card.lead .body a:hover,.pv-lead a:hover{text-decoration:underline;text-underline-offset:3px}
.leadstory .lead{font-size:1.08rem;line-height:1.55;color:var(--muted);max-width:none;margin:0 0 18px}
.hsec{margin:34px 0 8px}
.topics3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--card-gap-y) var(--card-gap-x)}
.topics3>.card{display:flex;flex-direction:column;min-width:0}
.topics3 .im{border-radius:10px;overflow:hidden;border:1px solid var(--edge)}
.topics3 .im img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.topics3 h3{font-size:1.02rem;line-height:1.3;margin:8px 0 4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.topics3 p{font-size:.88rem;-webkit-line-clamp:2}
.vstrip{display:flex;gap:var(--card-gap-x);overflow-x:auto;scroll-snap-type:x mandatory;padding:8px 8px 14px;margin:-8px -8px 0;scrollbar-width:thin}
.vcard{flex:0 0 240px;scroll-snap-align:start;text-decoration:none;color:inherit;min-width:0}
.vcard .vim{position:relative;display:block;aspect-ratio:16/9;border-radius:10px;overflow:hidden;border:1px solid var(--edge);background:#000;container-type:inline-size}
.vcard img{width:100%;height:100%;object-fit:cover}
.vcard strong{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:.9rem;line-height:1.3;margin-top:0;font-weight:700;color:#ebebeb}
@media (max-width:800.98px){
.topics3{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:var(--card-gap-x);padding-bottom:8px}
.topics3>.card{flex:0 0 82%;scroll-snap-align:start}
.vcard{flex-basis:78vw}
}
article.money .avid{max-width:68ch}
.avid.short{max-width:280px}
.avid.short .avb{aspect-ratio:9/16}
.adslot{margin:20px 0;max-width:68ch;display:flex;flex-direction:column;align-items:stretch;background:rgba(255,255,255,.03);border:1px dashed var(--border2);border-radius:8px;overflow:hidden}
.adlab{font-size:.65rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);padding:8px 12px 0}
.adslot ins{display:block;width:100%}
.pbox{margin:18px 0;max-width:none}
.pbox-in{display:grid;grid-template-columns:200px minmax(0,1fr);gap:14px 18px;align-items:start;padding:16px;border:1px solid #2a3646;border-radius:14px;background:#141414}
.pbox.noimg .pbox-in{grid-template-columns:1fr}
.pshot{display:block;background:#f3f3f3;border-radius:8px;line-height:0;overflow:hidden}
.gbox .pgal,.pbox .pgal{width:200px;max-width:100%}
.gbox .pgal-stage,.pbox .pgal-stage{position:relative;width:200px;height:200px}
.gbox .pgal-stage .pshot,.pbox .pgal-stage .pshot{position:absolute;inset:0;box-sizing:border-box;display:flex;align-items:center;justify-content:center;background:#fff;border-radius:10px;overflow:hidden;padding:12%;line-height:0}
.gbox .pgal-stage .pshot img,.pbox .pgal-stage .pshot img{width:100%;height:100%;aspect-ratio:auto;object-fit:contain;object-position:center;background:transparent;border-radius:0;display:block}
.pgal-nav{position:absolute;top:50%;transform:translateY(-50%);z-index:1;width:26px;height:26px;padding:0;border:0;border-radius:50%;background:rgba(16,16,16,.42);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center}
.pgal-nav:hover{background:rgba(16,16,16,.68)}
.pgal-prev{left:6px}.pgal-next{right:6px}
.pgal-thumbs{display:flex;gap:6px;margin-top:8px}
.pgal-thumb{width:34px;height:34px;padding:3px;box-sizing:border-box;border:1px solid #d5d5d5;border-radius:6px;background:#fff;cursor:pointer;line-height:0}
.pgal-thumb.is-on{border-color:#1a1a1a;box-shadow:0 0 0 1px #1a1a1a}
.gbox .pgal-thumb img,.pbox .pgal-thumb img{width:100%;height:100%;aspect-ratio:1/1;object-fit:contain;background:#fff;border-radius:3px;display:block}
.pgal:focus-visible,.pgal-nav:focus-visible,.pgal-thumb:focus-visible{outline:2px solid var(--blue2);outline-offset:2px}
.pbox h3{font-size:.98rem;line-height:1.25;letter-spacing:-.01em;font-weight:800;margin:0 0 6px;color:#fff}
.pbox ul{margin:0;padding-left:1.05em}
.pbox li{margin:0 0 2px;color:#c5ced8;font-size:.8rem;line-height:1.35}
.pbox .why{margin:8px 0 0;color:#c5ced8;font-size:.8rem;line-height:1.4}
.pbox .btn,.gbox .btn{margin-top:12px}
.affnote{margin:8px 0 0;font-size:.75rem;line-height:1.45;color:var(--dim)}
.affnote a{color:var(--blue2)}
.pv-side .rec li span{display:block;margin-top:3px;font-weight:400;font-size:.78rem;line-height:1.35;color:var(--muted)}
.pv-side .rec li.hasimg{display:grid;grid-template-columns:48px minmax(0,1fr);gap:8px;align-items:center}
.pv-side .rec li.noimg{grid-template-columns:minmax(0,1fr)}
.pv-side .rec .pth{width:48px;height:48px;border-radius:6px;overflow:hidden}
.pv-side .rec .pth img{width:100%;height:100%;object-fit:contain;background:#f3f3f3;display:block}
.pv-side .rec .afftop{margin:8px 0 0;font-weight:400;font-size:.75rem}
.nform{margin:26px 0;padding:16px 16px 14px;border:1px solid var(--border2);border-radius:12px;background:rgba(255,255,255,.03);max-width:68ch}
.nform h2{font-size:1.15rem;margin:0 0 6px}
.nform p{color:var(--muted);font-size:.9rem;line-height:1.45;margin:0 0 12px}
.nrow{display:flex;gap:8px}
.nrow input{flex:1;min-width:0;background:#121212;border:1px solid #3a4a60;border-radius:10px;color:var(--head);font:inherit;font-size:1rem;padding:10px 12px}
.nrow button{background:var(--red);color:#fff;border:0;border-radius:10px;font:inherit;font-weight:800;padding:10px 16px;cursor:pointer;white-space:nowrap}
.nrow button:hover{background:var(--red2)}
footer .nform{margin:14px 0 0;padding:0;border:0;background:transparent;max-width:none}
footer .nform h2{font-size:.7rem;letter-spacing:.09em;text-transform:uppercase;color:var(--blue)}
footer .nrow{flex-direction:column}
.mlbox{margin:22px 0;padding:14px 16px 12px;border:1px solid #3a4a60;border-left:3px solid var(--blue);border-radius:12px;background:#161616}
.mlbox h2{font-size:1.02rem;line-height:1.25;margin:0 0 10px;color:var(--head)}
.mlbox .mlfallback{margin:8px 0 0;font-size:.82rem;line-height:1.4}
.mlbox .mlfallback a{color:var(--blue2)}
.nlbar{margin:0}
.nlbar-form{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid #3a4a60;border-left:3px solid var(--blue);border-radius:12px;background:#161616}
.nlbar-h{margin:0;flex:1 1 220px;min-width:0;font-size:.95rem;font-weight:800;line-height:1.25;color:var(--head)}
.nlbar-form input[type=email]{flex:1 1 180px;min-width:0;height:42px;background:#121212;border:1px solid #3a4a60;border-radius:10px;color:var(--head);font:inherit;font-size:1rem;padding:0 12px}
.nlbar-form button{flex:none;height:42px;background:var(--red);color:#fff;border:0;border-radius:10px;font:inherit;font-weight:800;padding:0 16px;cursor:pointer;white-space:nowrap}
.nlbar-form button:hover{background:var(--red2)}
.nlbar-form button:disabled{opacity:.65;cursor:default}
.nlbar-form input:focus-visible,.nlbar-form button:focus-visible{outline:2px solid var(--blue2);outline-offset:2px}
.nlbar-msg{display:none;flex:1 0 100%;margin:0;font-size:.88rem;line-height:1.35;color:var(--blue2)}
.nlbar-form.is-err .nlbar-msg{display:block}
.nlbar-form.is-ok .nlbar-h,.nlbar-form.is-ok input,.nlbar-form.is-ok button{display:none}
.nlbar-form.is-ok .nlbar-msg{display:block;flex:1 1 auto;font-weight:700}
.nlbar .nlnote{margin:8px 0 0;font-size:.75rem;line-height:1.4;color:var(--dim);font-weight:400}
.nlbar .nlnote a{color:var(--blue2)}
.nlbar .nlfallback{margin:8px 0 0;font-size:.82rem;line-height:1.4}
.nlbar .nlfallback a{color:var(--blue2)}
@media (min-width:601px){.nlbar-form{flex-wrap:nowrap;max-height:70px}.nlbar-form.is-err{flex-wrap:wrap;max-height:none}}
@media (max-width:600.98px){.nlbar-form{flex-wrap:wrap;row-gap:8px}.nlbar-h{flex:1 0 100%}.nlbar-form input[type=email]{flex:1 1 140px}}
nav.seq{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:26px 0 8px}
nav.seq a{display:flex;flex-direction:column;gap:4px;text-decoration:none;border:1px solid var(--border2);border-radius:12px;padding:12px 14px;min-height:88px;color:inherit;font-weight:400;white-space:normal}
nav.seq a.next{text-align:right;align-items:flex-end}
nav.seq a small{color:var(--dim);font-weight:800;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase}
nav.seq a strong{color:var(--head);font-size:.95rem;line-height:1.35;font-weight:800}
nav.seq a:hover{border-color:#6b7d95}
button.flink{background:none;border:0;padding:0;color:var(--muted);font:inherit;cursor:pointer;text-align:left}
button.flink:hover{color:var(--head)}
.consent{position:fixed;z-index:80;left:12px;right:12px;bottom:12px;display:flex;gap:16px;align-items:center;justify-content:space-between;max-width:920px;margin:0 auto;background:#161616;color:var(--fg);border:1px solid #3a4a60;border-radius:14px;padding:14px 16px;box-shadow:0 16px 40px rgba(0,0,0,.55)}
.consent[hidden]{display:none}
.consent p{margin:0;font-size:.92rem;line-height:1.45}
.consent a{color:var(--blue2)}
.consent-btns{display:flex;gap:8px;flex:none}
.consent button{font:inherit;font-weight:800;font-size:.9rem;border-radius:10px;padding:11px 16px;cursor:pointer;min-width:112px}
.consent [data-consent="necessary"]{background:transparent;color:#fff;border:1px solid #8f9db0}
.consent [data-consent="all"]{background:var(--red);color:#fff;border:1px solid var(--red)}
.consent [data-consent="necessary"]:hover{border-color:#fff}
.consent [data-consent="all"]:hover{background:var(--red2)}
@media (max-width:600.98px){
article.money h1.atitle{font-size:1.7rem;line-height:1.18}
.pbox-in{grid-template-columns:1fr}
.consent{flex-direction:column;align-items:stretch;left:8px;right:8px}
.consent-btns{display:grid;grid-template-columns:1fr 1fr}
.consent button{min-width:0}
nav.seq{grid-template-columns:1fr}
nav.seq a.next{text-align:left;align-items:flex-start}
}
/* Header: logo and nav share a baseline; search sits centered underneath. */
header.hb .brand,header.hb .savedlink{transform:none}
header.hb .bar{gap:8px}
header.hb .id{display:flex;align-items:center;gap:28px;min-width:0;flex:1 1 auto}
header.hb .pnav{display:none;flex:1 1 auto;min-width:0;height:auto;margin:0;overflow-x:auto;scrollbar-width:none;transform:translateY(-1px)}
header.hb .pn{height:auto;padding:6px 10px;font-family:Manrope,"Manrope Fallback",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:16px;font-weight:700;line-height:1;letter-spacing:0}
header.hb .savedlink{margin-left:auto}
header.hb .mdrop{position:relative;flex:none;display:flex;align-items:baseline}
header.hb .mdrop>button.pn{border:0;background:transparent;cursor:pointer;appearance:none;font-family:Manrope,"Manrope Fallback",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:16px;font-weight:700;line-height:1;letter-spacing:0;color:var(--fg);gap:6px}
header.hb .mdrop>button.pn .chev{display:block;flex:none}
header.hb .mdrop>button.pn[aria-expanded=true]{background:#272727;color:#fff}
header.hb .mdrop .pmenu{display:none;left:auto;right:0;top:calc(100% + 4px)}
header.hb .mdrop.is-open .pmenu{display:grid}
header.hb{padding-bottom:0}
/* Search row is collapsed until the header magnifier opens it. The row lives in the
   sticky header, so opening it only grows that bar; the page below does not jump. */
.hb-find{display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:0fr;padding:0;transition:grid-template-rows .22s ease}
.hb-find>.wrap{min-width:0;width:100%;min-height:0;overflow:hidden}
html.find-open .hb-find{grid-template-rows:1fr}
html.find-open.find-ready .hb-find>.wrap{overflow:visible}
.hb-find .hb-search{display:flex;position:relative;width:min(640px,calc(100% - 8px));max-width:640px;margin:8px auto 18px;height:42px;background:transparent;padding:0;border-radius:10px;opacity:0;transform:translateY(-8px);transition:opacity .18s ease,transform .22s ease}
html.find-open .hb-find .hb-search{opacity:1;transform:none}
.hb-find .hb-search input,.hb-find .hb-search>button{height:42px}
.hb-find .hb-search input:focus,.hb-find .hb-search input:focus-visible,.hb-find .hb-search>button:focus,.hb-find .hb-search>button:focus-visible{outline:none;outline-offset:0;box-shadow:none;border-color:#303030}
.hb-find .hb-search:hover,.hb-find .hb-search:focus-within{outline:1px solid #4a4a4a;outline-offset:0}
header.hb .sbtn{display:grid;width:36px;height:36px;margin-left:auto;border:0;background:transparent;color:#ebebeb}
header.hb .sbtn:focus-visible{outline:2px solid var(--blue2);outline-offset:2px}
html.find-open header.hb .sbtn{background:#272727;border-radius:8px}
@media (prefers-reduced-motion:reduce){.hb-find,.hb-find .hb-search{transition:none}}
header.hb .savedlink{margin-left:6px}
header.hb ~ .drawer,header.hb ~ .scrim{top:66px}
@media (min-width:900px){header.hb .pnav{display:flex;flex-wrap:nowrap;overflow:visible;align-items:baseline}header.hb .id{align-items:baseline;gap:16px}header.hb .bar{position:relative;z-index:3;align-items:center}header.hb .logo{line-height:1}header.hb .logo span{top:2px}header.hb .bar .burger{display:flex}}
@media (min-width:901px){.hb-find .hb-search{width:min(640px,calc(100% - 292px - 26px));max-width:none;margin:8px calc(292px + 26px) 18px auto}}
@media (max-width:860.98px){header.hb .hb-find .hb-search{display:flex;position:relative;left:auto;right:auto;top:auto;width:min(640px,calc(100% - 8px));height:42px;margin:8px auto 18px;padding:0;background:transparent;z-index:1}}
@media (min-width:900px) and (max-width:1099.98px){header.hb .id{gap:10px}header.hb .pn,header.hb .mdrop>button.pn{font-size:14.5px;padding:5px 7px}}
.hb-find .hb-search{z-index:1}
header.hb .mdrop .pmenu{z-index:6}
header.hb .pnav>.is-parked{display:none}
@media (max-width:899.98px){header.hb .bar .burger{display:flex}header.hb .pnav{display:none}header.hb ~ .drawer,header.hb ~ .scrim{display:block;top:66px}}
@media (max-width:600.98px){header.hb ~ .drawer,header.hb ~ .scrim{top:56px}}
/* Phones only: burger 5px further left; logo 20px left so it clears the search icon.
   Translate, so the burger shift does not also drag the logo. */
@media (max-width:600.98px){header.hb .bar .burger{transform:translateX(-5px)}header.hb .brand{transform:translateX(-20px)}}
/* Layout previews. Scoped so the live pages are unchanged. */
.pv-note{font-size:.82rem;line-height:1.45;color:var(--muted);background:#161616;border:1px solid var(--border2);border-radius:10px;padding:10px 12px;margin:8px 0 12px}
.pv-note a{color:var(--blue2)}
.pv-note b{color:var(--red)}
.pv-tabs{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;border-bottom:1px solid var(--border);margin:0 0 12px}
.pv-tabs a{flex:none;padding:9px 12px 7px;text-decoration:none;font-weight:800;font-size:.84rem;color:var(--muted);border-bottom:2px solid transparent}
.pv-tabs a.on,.pv-tabs a:hover{color:#fff;border-bottom-color:var(--red)}
.pv-grid{display:grid;grid-template-columns:minmax(0,1fr) 292px;gap:26px;align-items:start}
.pv-lead{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);column-gap:14px;row-gap:0;align-items:center;margin:0 0 6px;text-decoration:none;color:inherit}.pv-lead>.lmeta{grid-column:1 / -1}
.pv-lead .im{position:relative;border-radius:10px;overflow:hidden;border:1px solid var(--edge);background:#000;cursor:default}
.pv-lead img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.pv-kicker{font-size:.72rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--blue)}
.pv-lead h1,.pv-lead h2{font-size:clamp(1.25rem,2.2vw,1.7rem);line-height:1.18;margin:4px 0 8px}
.pv-lead p{color:var(--muted);font-size:.92rem;line-height:1.45;margin:0}
.pv-day{font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin:8px 0 2px;padding-top:6px;border-top:1px solid var(--border)}
.pv-row{display:grid;grid-template-columns:52px minmax(0,1fr) 64px;gap:8px;align-items:center;padding:3px 0;border-bottom:1px solid #242424;text-decoration:none;color:inherit}
.pv-row.hasth{grid-template-columns:52px 64px minmax(0,1fr) 64px}
.pv-row time{font-variant-numeric:tabular-nums;font-size:.8rem;font-weight:800;color:var(--dim)}
.pv-th{position:relative;container-type:inline-size;border-radius:6px;overflow:hidden;border:1px solid var(--edge);background:#000}
.pv-th img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.pv-hl{min-width:0}
.pv-hl b{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;white-space:normal;font-size:.95rem;line-height:1.3;font-weight:400;color:var(--blue)}
.pv-min{justify-self:end;box-sizing:border-box;width:64px;min-width:64px;text-align:center;border:1px solid var(--border2);border-radius:8px;padding:3px 2px;line-height:1}
.pv-min b{display:block;color:var(--red);font-size:.85rem;font-weight:800;line-height:1;white-space:nowrap}
.pv-min small{display:block;margin-top:2px;color:var(--dim);font-size:.58rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;line-height:1;white-space:nowrap}
.pv-row:hover .pv-hl b,.pv-row:focus-visible .pv-hl b{color:#fff;text-decoration:underline;text-underline-offset:2px}
.pv-side h2{font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#fff;border-top:3px solid var(--red);padding-top:8px;margin:0 0 8px}
.pv-side section{margin:0 0 18px}
.pv-side a{text-decoration:none;color:inherit}
.pv-side ol li{display:grid;grid-template-columns:1.3rem minmax(0,1fr);gap:6px;padding:7px 0;border-bottom:1px solid #242424;font-size:.88rem;line-height:1.3;font-weight:700}
.pv-side ol{list-style:none;counter-reset:pv;margin:0;padding:0}
.pv-side ol li{counter-increment:pv}
.pv-side ol li::before{content:counter(pv);color:var(--red);font-weight:800}
.pv-side ul{list-style:none;margin:0;padding:0}
.pv-side ul li{padding:7px 0;border-bottom:1px solid #242424;font-size:.88rem;line-height:1.3;font-weight:700}
.pv-side ul.latest li{display:grid;grid-template-columns:1.3rem minmax(0,1fr);gap:6px;align-items:start}
.pv-side ul.latest li::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--red);justify-self:start;align-self:start;margin-top:calc(0.65em - 2.5px);margin-left:1px}
.pv-side ul.hubs li{display:grid;grid-template-columns:6px minmax(0,1fr);column-gap:8px;align-items:start}
.pv-side ul.hubs li::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--red);align-self:start;margin-top:calc(0.65em - 3px)}
.pv-side a:hover,.pv-side a:focus-visible{color:var(--blue)}
.gcatgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px 8px;background:#141414;border:1px solid #2a3646;border-radius:14px;padding:12px}
.gcat{display:flex;flex-direction:column;min-width:0;color:#fff}
.gtile{display:flex;align-items:center;justify-content:center;background:#fff;border-radius:10px;aspect-ratio:1;padding:12%;box-sizing:border-box;overflow:hidden}
.gtile img{width:100%;height:100%;object-fit:contain;display:block}
.gname{display:block;margin-top:6px;font-size:.7rem;font-weight:700;line-height:1.25;text-align:center;color:#fff}
.gcat:hover .gname,.gcat:focus-visible .gname{color:var(--blue)}
.gcat.is-on .gtile{outline:2px solid var(--red);outline-offset:2px}
.pv-side .ticker a:hover,.pv-side .ticker a:focus-visible{color:inherit}
.pv-side .nlside-form{display:flex;flex-direction:column;align-items:stretch;gap:8px;max-height:none;padding:0;border:0;border-radius:0;background:transparent}
.pv-side .nlside-lead{margin:0;font-size:.88rem;line-height:1.35;font-weight:600;color:var(--muted)}
.pv-side .nlside-form input[type=email]{flex:none;width:100%;height:42px}
.pv-side .nlside-form button{flex:none;width:100%;height:42px}
.pv-side .nlnote{margin:2px 0 0;font-size:.72rem;line-height:1.35;font-weight:400;color:var(--dim)}
.pv-side .nlnote a{color:var(--blue2);text-decoration:underline;text-underline-offset:2px}
.pv-side .nlnote a:hover,.pv-side .nlnote a:focus-visible{color:var(--blue)}
.nlside-form.is-ok .nlside-lead,.nlside-form.is-ok .nlnote{display:none}
.nlside .mlfallback{margin:8px 0 0;font-size:.82rem;line-height:1.4}
.nlside .mlfallback a{color:var(--blue2);text-decoration:underline;text-underline-offset:2px}
.pv-side .nform{max-width:none;margin:0 0 18px;padding:0;border:0;background:transparent}
.pv-side .pv-guide{display:grid;grid-template-columns:72px minmax(0,1fr);gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid #242424}
.pv-side .pv-guide img{width:72px;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:6px}
.pv-off{color:var(--dim);font-size:.8rem;line-height:1.4;margin:0}
.pv-block{margin:0 0 18px}
.pv-block h2{font-size:1.05rem;margin:0 0 8px}
.pv-art{display:grid;grid-template-columns:minmax(0,68ch) 280px;gap:28px;align-items:start}
.pv-art.pv-c{grid-template-columns:190px minmax(0,66ch) 260px}
.pv-art h1{font-size:clamp(1.55rem,2.6vw,2.1rem);line-height:1.16;margin:6px 0 8px}
.pv-art .lead{font-size:1.08rem;line-height:1.5;color:var(--muted)}
.pv-art .prose{font-size:1.05rem;line-height:1.7;max-width:66ch}
.pv-art .toc{float:none;width:auto;max-width:none;margin:0 0 16px}
.pv-c .toc{position:sticky;top:118px}
.pv-art .avid{max-width:none}
/* One centered frame for every page: reading column plus a right sidebar.
   Crumbs sit in a full-width row so the red rule on the sidebar shares a top
   edge with the image in the main column, on every page. */
.sheet{display:grid;grid-template-columns:minmax(0,1fr) 292px;column-gap:26px;row-gap:0;align-items:start}
.sheet-main{min-width:0}
.sheet>.crumbs{grid-column:1 / -1;margin:-2px 0 4px}
.sheet .leadstory{margin-top:0;align-items:start}
.pv-side{margin-top:0;min-width:0}
.sheet.front .leadstory,.sheet.front .layerrow,.sheet.front .homenews{margin-top:0}
.homenews{display:grid;grid-template-columns:1fr;gap:var(--card-gap-y) var(--card-gap-x);margin:0 0 var(--card-gap-y)}
.homenews .lim{position:relative;container-type:inline-size}
/* One hover zoom for every card photo: 1.04 over .3s, clipped by the rounded frame. */
.zimg{overflow:hidden}
.zimg img{transition:transform .3s}
.lcard:hover .zimg img,.card:hover .zimg img,.vcard:hover .zimg img,.mini:hover .zimg img,.mcard:hover .zimg img,.feature:hover .zimg img,.shc:hover .zimg img,.shv.zimg:hover img,.pv-row:hover .zimg img,.res a:hover .zimg img{transform:scale(1.04)}
.mini>.th.zimg{border-radius:10px;overflow:hidden;border:1px solid var(--edge)}
.mini>.th.zimg img{border:0;border-radius:0}
.res .zimg{flex:none;overflow:hidden;border-radius:10px;border:1px solid #3a4a60;line-height:0;width:112px;aspect-ratio:16/9}
.res .zimg img,.sopen .search .res .zimg img{width:100%;height:100%;aspect-ratio:16/9;border:0;border-radius:0;display:block;object-fit:cover;max-width:none;margin:0}
.card .im.zimg{aspect-ratio:16/9}
.card .im.zimg img{width:100%;height:100%;object-fit:cover;aspect-ratio:16/9}
@media (min-width:600px){.homenews{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:901px){.homenews{grid-template-columns:repeat(3,minmax(0,1fr))}}
.sheet>.nlbar{margin-top:26px}
@media (max-width:900px){
.sheet{row-gap:26px}
.sheet>.crumbs{margin-bottom:calc(-26px + 4px)}
.sheet>.nlbar{margin-top:0}
}
.layerrow{display:grid;grid-template-columns:1fr 1fr;gap:var(--card-gap-y) var(--card-gap-x);margin:0 0 var(--card-gap-y);align-items:stretch}
.lcard{display:flex;flex-direction:column;min-width:0;height:100%;text-decoration:none;color:inherit;background:transparent;border:0}
.layerrow .lcard:last-child{grid-column:1 / -1}
.lcard .lim{display:block;aspect-ratio:16/9;background:#101010;overflow:hidden;border-radius:8px}
.lcard .lim img{width:100%;height:100%;object-fit:cover}
/* A Short on a news card stays the same 16:9 tile as its neighbours. The vertical
   poster sits centered on a blurred copy of itself, with the Short badge and play icon on top. */
/* A Short in any news card stays a 16:9 tile. A vertical poster is centered on a blurred copy of itself. */
.zimg.fitin{position:relative;background:#070b16}
.zimg.fitin::before{content:"";position:absolute;inset:-8%;background:var(--poster) center/cover no-repeat;filter:blur(18px) brightness(.45);transform:scale(1.12)}
.mini .th.fitin{aspect-ratio:16/9}
.lcard .lim.fitin img,.card .im.fitin img,.res .zimg.fitin img,.vcard .vim.fitin img,.mini .th.fitin img{position:relative;z-index:1;width:auto;max-width:100%;height:100%;aspect-ratio:auto;margin:0 auto;object-fit:contain;object-position:center}
.zimg.fitin .dur,.zimg.fitin .vpl{z-index:2}
.res .zimg{position:relative}
.res .vpl{width:22px;height:22px;min-width:22px;min-height:22px}
.res .dur{right:4px;bottom:4px;font-size:.6rem;padding:2px 4px}
.lcard .lbody{display:flex;flex-direction:column;gap:4px;padding:0 0 10px;min-width:0;flex:1}
.lmeta{display:flex;flex-wrap:nowrap;gap:4px 6px;align-items:baseline;margin:6px 0 4px;padding:0;font-size:.68rem;font-weight:700;line-height:1.3;color:var(--dim);white-space:nowrap}.leadstory>.lmeta,.pv-lead>.lmeta,article.money>.lmeta{margin-bottom:9px}
/* Article pages: rubric sits under the hero and its caption, then the title.
   6px above the line and 9px before the title, as on thumbnail cards. */
article.money>.hi,article.money>.avid{margin-bottom:0}
article.money .hero-img{margin-bottom:0}
article.money>.lmeta,article.money>.lrow{margin-top:6px}
.lrow{display:flex;flex-wrap:nowrap;align-items:center;gap:6px;min-width:0;margin:6px 0 4px}
.lrow>.lmeta,.lrow>a.lgo{flex:1 1 auto;min-width:0;overflow:hidden}
.lrow>.lmeta,.lrow>a.lgo>.lmeta{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:0}
.lrow>.acts{display:flex;flex-flow:row nowrap;flex:0 0 auto;gap:4px;margin-left:auto}
.lrow .act{flex:none;white-space:nowrap;box-sizing:border-box;height:28px;padding:0 7px;gap:3px;font-size:12px;line-height:1;border-radius:8px}
.lrow .act svg{width:15px;height:15px}
a.lgo{display:block;min-width:0;color:inherit;text-decoration:none}
article.money>.lrow{margin-bottom:9px}
.lname{font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--blue)}
article.money .lmeta a.lname{color:var(--blue);text-decoration:none}
article.money .lmeta a.lname:hover{text-decoration:underline}
.lmeta .llayer{font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:inherit;text-decoration:none}
.lmeta .lsub{font-weight:800;color:var(--blue);text-decoration:none}
.lmeta a.llayer:hover,.lmeta a.lsub:hover{text-decoration:underline}
.lcard.empty .lmeta,.lcard.empty .lbody{padding-left:10px;padding-right:10px}
.lcard .lname,.vcard .lname,.shc .lname,.card .lname,.mini .lname,.leadstory .lname,.lcard .lsub,.vcard .lsub,.shc .lsub,.card .lsub,.mini .lsub,.leadstory .lsub{color:var(--blue)}
.lcard strong{font-size:.92rem;line-height:1.28;font-weight:800;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.leadstory .ltitle{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.lcard.empty{border:1px solid rgba(255,45,149,.55);border-radius:8px;overflow:hidden;background:linear-gradient(165deg,#ff2d95 0%,#c41878 38%,#3a0824 100%)}
.lcard.empty .lbody{justify-content:flex-end;padding:16px 14px 14px}
.lcard.empty .lname,.lcard.empty strong{color:#fff}
@media (min-width:700px){
.layerrow{grid-template-columns:repeat(12,minmax(0,1fr))}
.layerrow .lcard{grid-column:span 4}
.layerrow .lcard:nth-child(n+4){grid-column:span 3}
}
.sheet-main article.narrow,.sheet-main>.narrow{max-width:none;margin:0}
.sheet-main article.narrow>h1,.sheet-main article.narrow .cform,.sheet-main article.narrow .lead,.sheet-main article.narrow .prose{margin-left:0;margin-right:0}
.sheet-main .prose{max-width:none}
.sheet-main article.money h1{font-size:clamp(1.55rem,2.6vw,2.1rem);line-height:1.16;margin:3px 0 4px}
.sheet-main article.money>.smeta{margin-bottom:7px}
.sheet-main article.money>.byline{margin-bottom:6px}
.sheet-main article.money>.lead{margin-bottom:11px}
.sheet-main article.money>.avid{margin-top:0;margin-bottom:0}.sheet-main article.money>.hi{margin-bottom:0}.sheet-main article.money>.lmeta,.sheet-main article.money>.lrow{margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}
.sheet-main article.money .lead{font-size:1.08rem;line-height:1.5;color:var(--muted);max-width:none}
.sheet-main article.money .prose{font-size:1.05rem;line-height:1.7;max-width:none}
.sheet-main article .prose h2{margin-right:14px}
.sheet-main article.money .toc{float:none;width:auto;max-width:none;margin:0 calc(3vw + 14px) 16px}
.sheet-main article.money .avid{max-width:none}
.sheet-main article.money .avid.short,.pv-art .avid.short{width:auto;max-width:none;margin-left:0;margin-right:0}
.sheet-main article.money .avid.short .avb,.pv-art .avid.short .avb{display:block;width:50%;max-width:100%;margin-left:auto;margin-right:auto}
.sheet-main article.money .sources,.sheet-main article.money .imgnote,.sheet-main article.money nav.seq,.sheet-main article.money .pbox,.sheet-main article.money .nform,.sheet-main article.money .avid figcaption{margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}
.sheet-main article.money .pbox,.sheet-main article.money .nform,.sheet-main article.money .adslot{max-width:none}
@media (max-width:640px){.sheet-main article.money .avid.short .avb,.pv-art .avid.short .avb{width:calc(100% - 2 * (3vw + 14px));margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}}
.sheet-main article.money .avid.long .avb,.pv-art .avid.long .avb,.sheet-main article.money>.hi,.pv-art article.money>.hi{display:block;width:calc(100% - 2 * (3vw + 14px));margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}
@media (max-width:600.98px){.sheet-main article.money .avid.long .avb,.pv-art .avid.long .avb,.sheet-main article.money>.hi,.pv-art article.money>.hi,.sheet-main article.money .avid.short .avb,.pv-art .avid.short .avb{width:calc(100% - 8px);margin-left:4px;margin-right:4px}}
.sheet-main article.narrow>h1,.sheet-main article.narrow>.byline,.sheet-main article.money>h1,.sheet-main article.money>.meta,.sheet-main article.money>.byline{margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}
.sheet-main article.brief>h1,.sheet-main article.brief>.byline,.sheet-main article.brief>.meta,.sheet-main article.brief>.tplnote,.sheet-main article.brief>.lead{margin-left:0;margin-right:0}
.sheet-main article.brief>.lead{padding-left:0;padding-right:0}
@media (max-width:600.98px){.sheet-main article.narrow>h1,.sheet-main article.narrow>.byline,.sheet-main article.money>h1,.sheet-main article.money>.meta,.sheet-main article.money>.byline,.sheet-main article.money>.lmeta,.sheet-main article.money>.lrow,.sheet-main article.money .toc,.sheet-main article.money .sources,.sheet-main article.money .imgnote,.sheet-main article.money nav.seq,.sheet-main article.money .pbox,.sheet-main article.money .nform,.sheet-main article.money .avid figcaption{margin-left:4px;margin-right:4px}.sheet-main article.brief>h1,.sheet-main article.brief>.byline,.sheet-main article.brief>.meta,.sheet-main article.brief>.tplnote,.sheet-main article.brief>.lead{margin-left:0;margin-right:0}}
.sheet-main article.money .mlbox,.sheet-main article.narrow .mlbox{margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}
@media (max-width:600.98px){.sheet-main article.money .mlbox,.sheet-main article.narrow .mlbox{margin-left:4px;margin-right:4px}}
@media (max-width:767.98px){
.pv-grid,.pv-art,.pv-art.pv-c,.sheet{grid-template-columns:1fr}
.pv-lead{grid-template-columns:1fr}
.pv-c .toc{position:static}
.pv-row.hasth{grid-template-columns:46px 52px minmax(0,1fr) 64px}
}
/* Related and the rest of the sidebar share one rail. The article must not
   span two rows of that rail: auto rows then grow with the story and open a gap
   between Related and Start here. The bar stays a full-width row underneath. */
.sheet:has(.arel){grid-template-areas:"main rail" "bar bar";align-items:start}
.sheet:has(>.crumbs):has(.arel){grid-template-areas:"crumbs crumbs" "main rail" "bar bar"}
.sheet:has(.arel)>.crumbs{grid-area:crumbs}
.sheet:has(.arel)>.sheet-main{grid-area:main}
.sheet:has(.arel)>.sheet-rail{grid-area:rail;display:flex;flex-direction:column;justify-content:flex-start;align-items:stretch;align-self:start;min-width:0;gap:0}
.sheet:has(.arel)>.nlbar{grid-area:bar}
.sheet>.nlbar{grid-column:1 / -1}
@media (max-width:767.98px){
.sheet:has(.arel){grid-template-columns:1fr;grid-template-areas:"main" "side" "bar" "rest"}
.sheet:has(>.crumbs):has(.arel){grid-template-areas:"crumbs" "main" "side" "bar" "rest"}
.sheet:has(.arel)>.sheet-rail{display:contents}
.sheet:has(.arel) .arel{grid-area:side}
.sheet:has(.arel) .pv-side:not(.arel){grid-area:rest}
.nlside{display:none}
}
@media (min-width:768px){
.sheet>.pv-side,.sheet:has(.arel)>.sheet-rail{align-self:stretch}
}
.eco-bit{min-width:0}
.eco-sources{margin:0 0 12px;padding-left:1.1rem}
.eco-sources li{margin:0 0 6px}
.eco-sources a{color:#9ad7ff}
.ss-wrap{overflow-x:auto}
.prose figure.hubfig{margin:6px 14px 18px}
.prose figure.hubfig img{width:100%;max-width:100%;height:auto;border-radius:10px;border:1px solid var(--edge);display:block}
@media (max-width:600.98px){.prose figure.hubfig{margin-left:4px;margin-right:4px}}
.byline{margin:0 0 12px;color:var(--dim);font-size:.86rem}
.upd{margin:-6px 0 12px;color:var(--dim);font-size:.82rem}
.upd time{color:inherit}
.sheet-main article.money>.upd,.sheet-main article.money>.hublink{margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}
@media (max-width:600.98px){.sheet-main article.money>.upd,.sheet-main article.money>.hublink{margin-left:4px;margin-right:4px}}
.hubh{font-size:1.15rem;margin:8px 0 4px}
.hubcount{margin:0 0 12px;color:var(--dim);font-size:.84rem}
.etime{list-style:none;margin:8px 0 22px;padding:0}
.etime li{padding:12px 0;border-top:1px solid #2a2a2a}
.etime time{display:block;color:var(--dim);font-size:.78rem;font-weight:800;margin-bottom:4px}
.etime p{margin:0 0 6px}
.etime .esrc{font-size:.8rem}
.hublink{margin:0 0 12px;font-size:.84rem}
.hublink a{color:var(--blue2);font-weight:800;text-decoration:none}
.hublink a:hover{text-decoration:underline}
.hubnote{margin:8px 0 18px;padding:16px 16px 14px;border:1px dashed #3a4a60;border-radius:14px;background:#141820;color:var(--muted);line-height:1.45}
.eco-map{margin:6px 0 22px}
.eco-flow{display:flex;flex-direction:column;align-items:stretch;gap:0}
.eco-join{width:22px;height:16px;margin:1px auto;color:#8f9db0;flex:none}
.eco-card,.eco-co,.eco-stream,.eco-call{border:1px solid;border-radius:14px;padding:12px 14px 11px;min-width:0}
.eco-cardlink{display:block;text-decoration:none;color:inherit}
.eco-card{display:block}
.eco-card:hover,.eco-co:hover{filter:brightness(1.08)}
.eco-k{display:block;font-size:.68rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;margin-bottom:3px}
.eco-card strong,.eco-co strong,.eco-stream strong,.eco-call strong,.eco-stat b{color:#fff}
.eco-card p,.eco-co p,.eco-stream p,.eco-call p,.eco-stat small{margin:4px 0 0;font-size:.84rem;line-height:1.4;color:#d5deea}
.eco-links{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.eco-links a,.eco-src{display:inline-block;font-size:.75rem;font-weight:800;text-decoration:none;border-radius:999px;padding:3px 8px;border:1px solid currentColor}
.eco-src{margin:8px 8px 0 0;color:#9ad7ff}
.layerhead{border:1px solid;border-radius:16px;padding:14px 16px 12px;margin:0 0 12px}
.layerhead h1{color:#fff;margin:2px 0 0}
.layerhead .eco-k{margin:0 0 4px}
.eco-card.tesla,.layerhead.tesla{background:#3a0812;border-color:#e31937;color:#ff8a9b}
.eco-card.energy,.layerhead.energy{background:#063216;border-color:#4cd964;color:#b8ffc6}
.eco-card.spacex,.layerhead.spacex{background:#3a1400;border-color:#ff7a00;color:#ffc48a}
.eco-card.link,.layerhead.link{background:#043040;border-color:#00d1ff;color:#a6f4ff}
.eco-card.spacexsi,.layerhead.spacexsi{background:#3a2c04;border-color:#ffc400;color:#ffe28a}
.eco-card.neural,.layerhead.neural,.eco-co.neural{background:#3a0824;border-color:#ff2d95;color:#ffb3d6}
.eco-card.boring,.layerhead.boring,.eco-co.boring{background:#0c1840;border-color:#2f6bff;color:#b3c8ff}
.hubhead+.eco-h{margin-top:2px}
.layerintro p{margin:0 0 10px;line-height:1.5;color:var(--muted)}
.visually-hidden{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.eco-stats{display:grid;grid-template-columns:1fr;gap:8px;margin:0 0 16px}
.eco-stat{display:block;text-decoration:none;color:inherit;background:#12161e;border:1px solid #3a4a60;border-radius:14px;padding:10px 12px}
.eco-stat b{display:block;font-size:1.25rem;letter-spacing:-.02em}
.eco-stat span{display:block;font-size:.78rem;font-weight:800;color:#9ad7ff;margin-top:2px}
.eco-split{display:grid;grid-template-columns:1fr;gap:8px;margin:14px 0}
.eco-stream.data{background:#101820;border-color:#5aa7ff;color:#c5e2ff}
.eco-stream.money{background:#1c1608;border-color:#f0c14a;color:#ffe7a8}
.eco-cos{display:grid;grid-template-columns:1fr;gap:8px;margin:8px 0 14px}
.eco-co{background:#141820;border-color:#3a4a60;color:#d5deea}
.eco-call.plan{background:#1a1408;border-color:#e0b15a;color:#ffe3ad;margin:0 0 10px}
.eco-call.promise{background:#2a120c;border-color:#ff7a45;color:#ffd0bc;margin:0 0 10px}
.eco-h{font-size:1.15rem;margin:18px 0 8px}
.eco-explain{margin:6px 0 22px;max-width:68ch}
.eco-explain h2{font-size:1.2rem;margin:0 0 10px}
.eco-explain p{margin:0 0 12px;line-height:1.65;color:#d5deea}
.eco-explain a{color:var(--blue2)}
.ss-board{display:grid;grid-template-columns:1fr;gap:10px;margin:0 0 16px}
.ss-card{border-radius:14px;padding:14px 14px 12px;border:1px solid #3a4a60;background:#12161e}
.ss-card.latest{background:linear-gradient(160deg,#2a120c,#12161e 55%);border-color:#ff7a45}
.ss-card.next{background:linear-gradient(160deg,#062833,#12161e 60%);border-color:#00d4ff}
.ss-card .k{font-size:.68rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#ffb199}
.ss-card.next .k{color:#8eecff}
.ss-card h2{font-size:1.35rem;margin:2px 0 6px}
.ss-card p{margin:0;color:#d5deea;font-size:.92rem;line-height:1.4}
.ss-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.ss-pills span{font-size:.75rem;font-weight:800;border-radius:999px;padding:3px 8px;border:1px solid #3a4a60}
.ss-yes{color:#b8ffe2;border-color:#3dffb0!important}
.ss-no{color:#ffc2bc;border-color:#ff5a4f!important}
.ss-table{width:100%;border-collapse:collapse;font-size:.84rem}
.ss-table th{text-align:left;font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;color:#8f9db0;padding:6px 6px;border-bottom:1px solid #3a4a60}
.ss-table td{padding:8px 6px;border-bottom:1px solid #242a33;vertical-align:top}
.ss-table tr.is-latest td{background:#2a160f}
.ss-table a{color:#9ad7ff}
@media (min-width:700px){
.eco-stats{grid-template-columns:repeat(3,minmax(0,1fr))}
.eco-split,.eco-cos{grid-template-columns:1fr 1fr}
.ss-board{grid-template-columns:1.3fr .7fr}
}
@media (max-width:699.98px){
.ss-table thead{display:none}
.ss-table,.ss-table tbody,.ss-table tr,.ss-table td{display:block;width:100%}
.ss-table tr{margin:0 0 10px;border:1px solid #3a4a60;border-radius:12px;padding:8px 10px;background:#12161e}
.ss-table tr.is-latest{border-color:#ff7a45}
.ss-table td{display:block;border:0;padding:4px 0}
.ss-table td::before{content:attr(data-label);display:block;color:#8f9db0;font-weight:800;font-size:.68rem;letter-spacing:.04em;text-transform:uppercase}
}
@media (min-width:1100px){
.eco-flow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.eco-join{display:none}
}
.eco-orbit{position:relative;overflow:hidden;margin:0 0 22px;isolation:isolate;min-height:280px}
.eco-sun{position:absolute;z-index:0;border-radius:50%;pointer-events:none;background:radial-gradient(circle at 50% 50%, #f7feff 0 .8%, #8af3ff 3.2%, #00b4e0 9%, #07506e 22%, #08131c 40%, transparent 54%);box-shadow:inset 0 0 70px rgba(120,230,255,.28);border:1px solid rgba(170,240,255,.4)}
.eco-sun::after{content:"";position:absolute;inset:12%;border-radius:50%;border:1px solid rgba(160,235,255,.25)}
.eco-core{position:absolute;z-index:3;margin:0;text-align:center;font-weight:800;font-size:1.05rem;line-height:1.15;letter-spacing:-.03em;color:#fff;text-shadow:0 0 8px #d8fbff, 0 0 18px #00c2ea;pointer-events:none;transform:translate(-50%,-50%);white-space:nowrap}
.eco-rays{position:absolute;left:0;top:0;z-index:1;pointer-events:none;overflow:visible}
.eco-arc{position:relative;z-index:2;display:flex;flex-direction:column;gap:12px;margin:0}
.eco-node{position:relative;width:auto;margin:0;padding:6px 8px 5px;border-radius:8px}
.eco-orbit.is-set{height:auto}
.eco-orbit.is-set .eco-arc{position:absolute;inset:0;margin:0}
.eco-orbit.is-set .eco-node{position:absolute}
.eco-k{color:var(--blue)}
.eco-node .eco-k{display:block;font-size:.92rem;font-weight:800;line-height:1.15;margin:0;letter-spacing:.04em}
.eco-node ul{margin:4px 0 0;padding:0 0 0 1.05em}
.eco-node li{font-size:.68rem;line-height:1.22}
a.eco-node{display:block;text-decoration:none;color:inherit}
.lcard:not(.empty),.vcard,.shc,.card:not(.lead),.mini,.pv-row,.mcard,.model{position:relative;isolation:isolate;z-index:0}
.lcard:not(.empty)::before,.vcard::before,.shc::before,.card:not(.lead)::before,.mini::before,.pv-row::before,.mcard::before,.model::before{content:"";position:absolute;z-index:-1;inset:-6px;border-radius:10px;background:rgba(255,255,255,.09);opacity:0;transition:opacity .15s;pointer-events:none}
.lcard:not(.empty):hover::before,.vcard:hover::before,.shc:hover::before,.card:not(.lead):hover::before,.mini:hover::before,.pv-row:hover::before,.mcard:hover::before,.model:hover::before{opacity:1}
.lcard:not(.empty):hover,.vcard:hover,.shc:hover,.card:not(.lead):hover,.mini:hover,.pv-row:hover,.mcard:hover,.model:hover{z-index:1}
a.eco-node:hover{filter:brightness(1.08)}
.card:focus-visible,.lcard:focus-visible,.vcard:focus-visible,.shv:focus-visible,.mcard:focus-visible,a.eco-node:focus-visible,.eco-card:focus-visible,.eco-co:focus-visible,.model:focus-visible,.mini:focus-visible,.leadstory .ltitle a:focus-visible,.leadstory .btn:focus-visible{outline:1px solid rgba(255,255,255,.5);outline-offset:3px}
@media (max-width:560px){
.eco-node .eco-k{font-size:.78rem}
.eco-node li{font-size:.62rem;line-height:1.2}
.eco-core{font-size:.84rem}
}
@media (min-width:1100px){header.hb .id{gap:24px}}
@media (min-width:1320px){header.hb .id{gap:80px}}
@media (min-width:1200px){
header.hb .pnav{gap:4px}
header.hb .pn,header.hb .mdrop>button.pn{font-size:14px;padding:12px 11px}
}
@media (min-width:1000px) and (max-width:1199.98px){
header.hb .pn,header.hb .mdrop>button.pn{font-size:13px;padding:5px 5px}
}
@media (min-width:900px) and (max-width:999.98px){
header.hb .id{gap:6px}
header.hb .pn,header.hb .mdrop>button.pn{font-size:12.5px;padding:5px 3px}
}
/* Inline search from 769px up: visible on every width except the two smallest
   size classes (tablet portrait 768 and phone). 769px sits just above 768,
   which this header work treats as the last compact width. */
header.hb .hb-inline{display:none}
@media (min-width:769px){
header.hb .pnav{display:none}
header.hb .sbtn{display:none}
header.hb .hb-find{display:none}
header.hb .id{align-items:center;gap:16px}
header.hb .hb-inline{display:flex;flex:1 1 auto;min-width:0;align-items:center}
header.hb .hb-inline .hb-search,header.hb .hb-inline .search{display:flex;position:relative;flex:1 1 auto;width:100%;max-width:640px;height:42px;margin:0 0 0 25px;padding:0;opacity:1;transform:none;background:transparent;z-index:1}
header.hb .hb-inline .hb-search input,header.hb .hb-inline .hb-search>button{height:42px}
header.hb .hb-inline .hb-search input:focus,header.hb .hb-inline .hb-search input:focus-visible,header.hb .hb-inline .hb-search>button:focus,header.hb .hb-inline .hb-search>button:focus-visible{outline:none;outline-offset:0;box-shadow:none;border-color:#303030}
header.hb .hb-inline .hb-search:hover,header.hb .hb-inline .hb-search:focus-within{outline:1px solid #4a4a4a;outline-offset:0}
}

/* Header lock: hamburger and logo keep the same size and vertical position at
   every width. Horizontal position is a fixed offset from the content wrap
   (the wrap is centered when the viewport is wider than 1160px). */
header.hb .bar{height:66px;gap:8px;align-items:center}
@media (min-width:901px){main.wrap{margin-top:10px}}
/* Icon stack is 16px (2px bars, 5px gaps), matching the measured cap height of
   the logo's T (solid ink from 25px to 41px in the 66px bar). */
header.hb .bar .burger{display:flex;flex-direction:column;align-items:center;justify-content:center;width:40px;height:40px;margin-left:-8px;padding:0;transform:none;gap:5px}
header.hb .bar .burger span{width:18px;height:2px;flex:none;border-radius:2px;background:#ebebeb}
header.hb .brand{transform:none;margin-left:0}
header.hb .bar .logo{font-size:22.4px;line-height:1;letter-spacing:-.02em;transform:none}
header.hb .logo span{font-size:calc(1em + 1px);top:2px}
@media (max-width:767.98px){.logo span{top:2px}header.hb .logo span{top:1px}}
header.hb ~ .drawer,header.hb ~ .scrim{top:66px}

/* Phones only: shrink logo and hamburger together so the tool row (magnifier,
   saved badge, language) fits on one line down to 320px. 480px is the last
   typical phone width; 481px+ keeps the locked 22.4px logo and 40px button. */
@media (max-width:480px){
header.hb .bar{flex-wrap:nowrap;--hb-logo:clamp(15.5px,4.85vw,22.4px)}
header.hb .bar .logo{font-size:var(--hb-logo)}
header.hb .bar .burger{width:calc(40 * var(--hb-logo) / 22.4);height:calc(40 * var(--hb-logo) / 22.4);gap:calc((16 * var(--hb-logo) / 22.4 - 6px) / 2);transform:none}
header.hb .bar .burger span{width:calc(18 * var(--hb-logo) / 22.4);height:2px}
header.hb .sbtn,header.hb .savedlink{transform:none;flex:none}
header.hb .bar .lang{flex:none;white-space:nowrap;transform:none}
header.hb .id,header.hb .brand{min-width:0}
}
/* Compact header (<=768px, where the magnifier is visible): park leftover
   space between the logo and the tool group, not between the icons.
   .id stays content-sized so it cannot swallow the gap; margin-left:auto
   on .sbtn pulls magnifier, saved, and language to the right as one cluster
   with equal bar-gap spacing (old per-icon auto/negative margins cancelled). */
@media (max-width:768.98px){
header.hb .bar{justify-content:flex-start;flex-wrap:nowrap}
header.hb .id{flex:0 0 auto;min-width:0}
header.hb .sbtn{display:grid;margin-left:auto;margin-right:0;transform:none;flex:none}
header.hb .sbtn svg{transform:translateX(15px)} /* visible glyph only; button and neighbours stay put */
header.hb .savedlink,html.hasdd header.hb .bar .savedlink,html.hasdd.ddend header.hb .bar .savedlink,html.hass header.hb .bar .savedlink{margin-left:0;margin-right:0;transform:none;flex:none}
header.hb .bar .lang{margin-left:0;margin-right:0;flex:none;white-space:nowrap;transform:none}
}
/* Card and list titles wrap in full. No ellipsis on titles. */
.card h3,.grid2>.card h3,.gall>.card h2,.gall>.card h3,.mini h3,.rside .mini h3,.topics3 h3,.vcard strong,.lcard strong,.leadstory .ltitle,.sht,a.sht,.res b,.sopen .search .res b,.pv-hl b{display:block;-webkit-line-clamp:unset;-webkit-box-orient:unset;overflow:visible;text-overflow:unset;white-space:normal;min-height:0}
.adhold{display:block;width:100%}
.ad-sidebar{margin:0 0 16px;max-width:none}
@media (max-width:900px){.ad-sidebar{display:none}}
.tplnote{margin:0 0 14px;padding:10px 12px;border:1px dashed #ffc400;border-radius:8px;color:#ffe28a;font-weight:700;font-size:.92rem;line-height:1.4}
.ltag{display:inline-block;font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--blue);border-radius:8px;padding:2px 8px;text-decoration:none;color:var(--blue)}
.brief-layers{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 16px}
.brief-list{list-style:none;margin:0 0 18px;padding:0}
.brief-list a{display:block;padding:12px 14px;border:1px solid #3a4a60;border-radius:8px;text-decoration:none;color:inherit;margin:0 0 8px;transition:background .15s}
.brief-list a:hover{background:#1a1a1a}
.brief-list strong{display:block;color:#fff}
.brief-list span{color:var(--dim);font-size:.82rem}
.brief-layer{margin:0 0 18px}
.brief-layer h2{margin:0 0 8px}
.brief-layer ol{margin:0;padding:0 0 0 1.2em}
.brief-layer li{margin:0 0 12px}
.brief-layer h3{margin:0 0 4px;font-size:1.05rem}
.brief-why{margin:6px 0 0;color:#d5deea}
.brief-why b{color:#fff}
.brief-cta{margin:0 0 16px}
.prom-filters{display:flex;flex-wrap:wrap;gap:10px 16px;margin:0 0 12px}
.prom-filters label{display:flex;flex-direction:column;gap:4px;font-size:.75rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:var(--dim)}
.prom-filters select{background:#121212;color:var(--head);border:1px solid #3a4a60;border-radius:8px;font:inherit;font-size:.95rem;font-weight:700;padding:8px 10px;text-transform:none;letter-spacing:0}
.prom-wrap{overflow-x:auto;border:1px solid #3a4a60;border-radius:8px}
.prom{width:100%;border-collapse:collapse;font-size:.92rem}
.prom th,.prom td{padding:10px 12px;border-bottom:1px solid #242a33;text-align:left;vertical-align:top}
.prom th{font-size:.72rem;letter-spacing:.04em;text-transform:uppercase;color:var(--dim)}
.prom a{color:#9ad7ff}
.prom-empty{margin:12px 0 0;color:var(--muted)}
.gbox{margin:18px 0;padding:16px;border:1px solid #2a3646;border-radius:14px;background:#141414;display:grid;grid-template-columns:200px minmax(0,1fr);gap:14px 18px;align-items:start}
@media (min-width:601px){article .prose .gbox{margin-left:14px;margin-right:14px}}
.gbox.noimg{grid-template-columns:1fr}
.gbox h2{margin:0 0 6px;font-size:1.25rem;line-height:1.3;letter-spacing:-.015em;font-weight:800;color:#fff}
.gbox h3{margin:8px 0 3px;font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);font-weight:800}
.gbox ul{margin:0;padding-left:1.05em}
.gbox li{margin:0 0 2px;font-size:.8rem;line-height:1.35;color:#c5ced8}
.gbox .btn,.pbox .btn{display:inline-flex;align-items:center;justify-content:center;background:var(--red);color:#fff;text-decoration:none;font-weight:800;font-size:.82rem;border-radius:8px;padding:10px 14px;line-height:1.3;text-align:center}
article .prose .gbox h2,html body article .prose .gbox h2{border:0;padding:0;margin:0 0 6px;font-size:1.25rem;line-height:1.3;letter-spacing:-.015em}
article .prose .gbox p,article .prose .gbox ul,article .prose .gbox li{margin-left:0;margin-right:0}
article .prose .gbox p{margin-top:8px;margin-bottom:0;font-size:.8rem;line-height:1.4;color:#c5ced8}
article .prose .gbox li{font-size:.8rem;line-height:1.35}
.gbox .fits{margin:8px 0 0;color:#c5ced8;font-size:.8rem;line-height:1.4}
.gbox .fits b{font-weight:700;color:#fff}
.pcost{margin:10px 0 0;color:#8b97a6;font-size:.72rem;line-height:1.35}
.popt{margin:6px 0 0;color:#9aa6b4;font-size:.72rem;line-height:1.35}
.pcost b{color:#fff;font-size:.95rem;font-weight:800;letter-spacing:-.01em}
.pcost .alt,.pcost .usd{margin-left:6px;color:#c5ced8;font-weight:700;font-size:.78rem}
.stars{display:flex;align-items:center;gap:8px;margin:8px 0 0;color:#c5ced8;font-size:.78rem;line-height:1}
.starrow{position:relative;display:inline-block;width:78px;height:14px;flex:none}
.starrow .empty,.starrow .full{display:flex;gap:2px;height:14px}
.starrow svg{width:14px;height:14px;display:block;flex:none}
.starrow .empty svg{fill:#3a4454}
.starrow .full{position:absolute;left:0;top:0;overflow:hidden;width:calc(var(--score) / 5 * 100%)}
.starrow .full svg{fill:#f5c451}
article .prose .gbox p.stars{margin-top:8px;font-size:.78rem;color:#c5ced8}
.pcost .asof{display:inline;margin-left:6px;font-size:.68rem;font-weight:600;letter-spacing:.01em;white-space:nowrap}
article .prose .gbox p.pcost,article .prose .gbox p.popt{margin-top:8px;margin-bottom:0;font-size:.72rem;color:#9aa6b4}
.store-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;align-items:center}
.gbox .store-btns .btn,.pbox .store-btns .btn{margin-top:0}
.gbox .btn.ghost,.pbox .btn.ghost{background:transparent;color:var(--head);border:1px solid #8f9db0;font-weight:700}
.gbox .btn.ghost:hover,.pbox .btn.ghost:hover{background:transparent;border-color:#fff}
article.narrow>.hi,article.narrow>.avid{margin:0 0 12px}
article.narrow>.hi img,article.narrow>.avid .avb{width:100%;max-width:100%}
@media (max-width:600.98px){.store-btns{flex-direction:column;align-items:stretch}.store-btns .btn{width:100%}}
.gtable{width:100%;border-collapse:collapse;margin:8px 0 16px;font-size:.92rem}
.gtable th,.gtable td{padding:8px 10px;border:1px solid #3a4a60;text-align:left}
.gtable caption{text-align:left;font-weight:800;margin:0 0 6px}
.afftop{margin:0 0 14px;font-size:.84rem;line-height:1.45;color:var(--dim)}
.afftop a{color:#9ad7ff}
.affend{margin:28px 0 6px;font-size:.75rem;line-height:1.45;color:var(--dim)}
.affend a{color:#9ad7ff}
.nlstick{position:fixed;z-index:70;left:12px;right:12px;display:flex;gap:8px;align-items:center;max-width:min(920px,100vw);margin:0 auto;box-sizing:border-box;background:#161616;border:1px solid #3a4a60;border-radius:8px;padding:8px;box-shadow:0 12px 32px rgba(0,0,0,.5)}
.nlstick[hidden]{display:none}
.nlstick.is-quiet{visibility:hidden;pointer-events:none}
.nlstick .nlbar-form{flex:1;min-width:0;border:0;padding:0;background:transparent;box-shadow:none}
.nlstick-actions{display:contents}
.nlstick-x,.nlbar-form button.nlstick-x{flex:none;height:42px;padding:0 12px;background:transparent;color:#fff;border:1px solid #3a4a60;border-radius:8px;font:inherit;font-weight:800;cursor:pointer}
.nlbar-form button.nlstick-x:hover{background:#272727}
@media (max-width:700px){
.nlstick{left:0;right:0;width:100%;max-width:100vw;flex-direction:column;align-items:stretch;gap:8px;border-radius:12px 12px 0 0;padding:10px max(12px,env(safe-area-inset-right)) calc(10px + env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left))}
.nlstick .nlbar-form{flex-direction:column;align-items:stretch;width:100%;min-width:0;gap:8px}
.nlstick .nlbar-h{flex:none;width:100%}
.nlstick input[type=email]{flex:none;width:100%;min-width:0;box-sizing:border-box}
.nlstick-actions{display:flex;gap:8px;width:100%;min-width:0}
.nlstick-actions>button{flex:1 1 0;min-width:0;width:auto;white-space:normal}
.nlbar,.nlside{max-width:100%;min-width:0;box-sizing:border-box}
.nlbar .nlbar-form,.nlside-form{flex-wrap:wrap;max-width:100%;min-width:0;box-sizing:border-box}
.nlbar .nlbar-h{flex:1 0 100%}
.nlbar input[type=email],.nlside-form input[type=email]{flex:1 1 100%;width:100%;min-width:0;box-sizing:border-box}
.nlbar .nlbar-form>button,.nlside-form>button{max-width:100%;white-space:normal}
}
.nlpitch p{margin:0 0 12px}
@media (max-width:600.98px){.gbox,.pbox-in{grid-template-columns:1fr;gap:12px}.gbox .pgal,.pbox .pgal,.gbox .pgal-stage,.pbox .pgal-stage{width:100%}.gbox .pgal-stage,.pbox .pgal-stage{height:auto;aspect-ratio:1/1}}
@media (max-width:900px){html,body{-webkit-text-size-adjust:100%;text-size-adjust:100%}body{font-size:15px;line-height:1.55}html body h1,html body article h1,html body .sheet-main article.money h1,html body .sheet-main article.narrow>h1,html body .hubhead h1,html body h1.st{font-size:24px;line-height:1.15;-webkit-text-size-adjust:100%;text-size-adjust:100%}html body article .prose h2,html body .sheet-main article .prose h2,html body .prose h2,html body .leadstory .ltitle,html body .hubh{font-size:19px;line-height:1.3;-webkit-text-size-adjust:100%;text-size-adjust:100%}html body article .prose,html body .sheet-main article.money .prose,html body .sheet-main article.narrow .prose{font-size:15px;line-height:1.55;-webkit-text-size-adjust:100%;text-size-adjust:100%}html body article .lead,html body .sheet-main article.money .lead,html body .sheet-main article.narrow .lead,html body .hubhead .lead,html body .leadstory .lead{font-size:16px;line-height:1.5;-webkit-text-size-adjust:100%;text-size-adjust:100%}html body .byline,html body .meta,html body .smeta,html body .upd{font-size:12px;line-height:1.35;-webkit-text-size-adjust:100%;text-size-adjust:100%}html body .lmeta,html body .lname,html body .tag,html body .lmeta .llayer,html body .lmeta .lsub{font-size:11px;line-height:1.3;-webkit-text-size-adjust:100%;text-size-adjust:100%}}
@media (max-width:900px){html body .hfeed .pv-hl b{font-size:13px;line-height:1.3;hyphens:none;-webkit-hyphens:none;overflow-wrap:normal;word-break:normal;-webkit-text-size-adjust:none;text-size-adjust:none}html body .hfeed .pv-row time{font-size:12px;-webkit-text-size-adjust:none;text-size-adjust:none}html body .hfeed .pv-min{width:48px;min-width:48px}html body .hfeed .pv-min b{font-size:12px}}
@media (max-width:900px){html body .sheet-main article .prose .gbox h2{font-size:19px;line-height:1.3;letter-spacing:-.015em}html body .sheet-main article .prose .gbox p,html body .sheet-main article .prose .gbox li{font-size:.8rem;line-height:1.4}}
"""

# Classes left over from retired layouts. They are not emitted by the pages build() writes.
# Ads, the newsletter form, product boxes and the Shorts player stay: those render when configured.
_DEAD_CSS = frozenset("""
arch aread below beside big btns cats9 chips dm eyebrow feature grid h2 hero home
hsec leadside mcell mdesc mini model models morelink nextread pblock ph phead pimg ptop ptxt
pv-art pv-block pv-c pv-grid pv-guide pv-kicker pv-lead pv-note pv-off pv-tabs read rh rside
side sideh slogan soon span2 sr starthere sub tdb tdc tdd tdl th tip topic topics3 tops why
""".split())
_PAGE_CSS = None


def _slim_css(css):
    """Drop selectors that only exist for layouts the build no longer emits."""
    def class_names(sel):
        return re.findall(r"\.([a-zA-Z_][\w-]*)", sel)

    def keep_selector(sel):
        return not any(name in _DEAD_CSS for name in class_names(sel))

    def filter_block(block):
        out = []
        i, n = 0, len(block)
        while i < n:
            if block[i].isspace():
                i += 1
                continue
            if block.startswith("/*", i):
                j = block.find("*/", i + 2)
                j = n if j < 0 else j + 2
                out.append(block[i:j])
                i = j
                continue
            j = block.find("{", i)
            if j < 0:
                break
            head = block[i:j].strip()
            depth = 0
            k = j
            while k < n:
                if block[k] == "{":
                    depth += 1
                elif block[k] == "}":
                    depth -= 1
                    if depth == 0:
                        k += 1
                        break
                k += 1
            body = block[j:k]
            if head.startswith(("@media", "@container", "@supports")):
                inner = filter_block(body[1:-1])
                if inner.strip():
                    out.append(head + "{" + inner + "}")
            elif head.startswith("@"):
                out.append(head + body)
            else:
                kept = [s.strip() for s in head.split(",") if s.strip() and keep_selector(s)]
                if kept:
                    out.append(",".join(kept) + body)
            i = k
        return "".join(out)

    return filter_block(css)


def page_css():
    global _PAGE_CSS
    if _PAGE_CSS is None:
        _PAGE_CSS = _slim_css(CSS)
    return _PAGE_CSS


def esc(s):
    return html.escape(s, quote=True)


def fmt_date(d, lang):
    dt = datetime.strptime(d, "%Y-%m-%d")
    m = LANGS[lang]["months"][dt.month - 1]
    return f"{m} {dt.day}, {dt.year}" if lang == "en" else f"{dt.day} {m} {dt.year}"


def rel_short(dt, lang):
    """Relative card date: 45m, 5h, 5d, 5wk, 5mo, 5y, plus ago / geleden.
    Dutch keeps the same unit letters as English."""
    seconds = (datetime.now(TZ) - dt).total_seconds()
    if seconds < 0:
        return fmt_date(dt.strftime("%Y-%m-%d"), lang)
    hours = seconds / 3600
    days = hours / 24
    if hours < 1:
        label = f"{max(1, int(seconds // 60))}m"
    elif hours < 24:
        label = f"{max(1, int(hours))}h"
    elif days < 7:
        label = f"{max(1, int(days))}d"
    elif days < 42:  # up to 5wk (6 weeks would be 1mo)
        label = f"{max(1, int(days / 7))}wk"
    elif days < 365.25:
        label = f"{max(1, int(days / 30.44))}mo"
    else:
        label = f"{max(1, int(days / 365.25))}y"
    return label + (" geleden" if lang == "nl" else " ago")


def when(a, lang):
    """Short relative date. ttAgo refreshes the same text in the browser."""
    stamp = published(a)
    return f'<time class="ago" datetime="{stamp.isoformat()}">{esc(rel_short(stamp, lang))}</time>'


def published(a):
    """Timezone-aware publication datetime (defaults to 08:00 local)."""
    return datetime.strptime(f"{a['date']} {a.get('time', '08:00')}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


def modified(a):
    """Publication time, or the real edit time when `updated` is set and different."""
    pub = published(a)
    raw = str(a.get("updated") or "").strip()
    if not raw:
        return pub, False
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=TZ)
            return dt, dt.date() != pub.date()
        return pub, False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt, abs((dt - pub).total_seconds()) >= 60


def updated_html(a, lang):
    """Visible Updated / Bijgewerkt line. Empty when the article was not edited later."""
    dt, differs = modified(a)
    if not differs:
        return ""
    label = "Updated" if lang == "en" else "Bijgewerkt"
    text = f"{label} {fmt_date(dt.strftime('%Y-%m-%d'), lang)}"
    if "T" in str(a.get("updated") or ""):
        text += ", " + dt.strftime("%H:%M")
    return f'<p class="upd"><time datetime="{dt.isoformat()}">{esc(text)}</time></p>'


def article_stamp(a):
    """YYYY-MM-DD of a real edit, else the publication date. Never the day the site was built."""
    return str(a.get("updated") or a["date"])[:10]


def latest_stamp(items):
    if not items:
        return None
    return max(article_stamp(a) for a in items)


def url(lang, path=""):
    return f"{LANGS[lang]['prefix']}/{path}"


def other(lang):
    return "nl" if lang == "en" else "en"


def signup_path(lang):
    """Newsletter page slug. English and Dutch use different paths."""
    return "newsletter/" if lang == "en" else "nieuwsbrief/"


def promises_path(lang):
    return "promises/" if lang == "en" else "beloftes/"


def guides_path(lang):
    return "guides/" if lang == "en" else "gidsen/"


def advertise_path(lang):
    return "advertise/" if lang == "en" else "adverteren/"


def disclosure_path(lang):
    return "affiliate-disclosure/"


def ecosystem_path(lang):
    """Ecosystem map. English and Dutch use different slugs, like the newsletter."""
    return "ecosystem/" if lang == "en" else "ecosysteem/"


def model_photo(key, for_article=False):
    m = MODELS[key]
    p = m.get("article_photo", m.get("photo")) if for_article else m.get("photo")
    if p:
        rel = Path(p) if "/" in p else Path("models") / p
        if (STATIC / "img" / rel).is_file():
            return "/img/" + rel.as_posix()
    return model_photo(m["parent"], for_article) if m.get("parent") else None


def model_title(key, lang):
    name = MODELS[key]["name"]
    if isinstance(name, dict):
        return name.get(lang) or name["en"]
    return name


def model_heading(key, lang):
    """Page and card heading. Most models are prefixed with Tesla. A full_name is already complete."""
    name = model_title(key, lang)
    if MODELS[key].get("full_name"):
        return name
    return "Tesla " + name


def photo_alt(key, lang):
    alt = MODELS[key].get("photo_alt")
    if isinstance(alt, dict):
        return alt.get(lang) or alt.get("en") or model_heading(key, lang)
    return model_heading(key, lang)


def photo_caption_from(credit, lang):
    if not credit:
        return ""
    note = credit.get(lang) or credit.get("en") or ""
    author = credit.get("author") or ""
    license_name = credit.get("license") or ""
    bits = [esc(note)] if note else []
    who = []
    if author and credit.get("source_url"):
        who.append(f'<a href="{esc(credit["source_url"])}" rel="noopener noreferrer">{esc(author)}</a>')
    elif author:
        who.append(esc(author))
    if license_name and credit.get("license_url"):
        who.append(f'<a href="{esc(credit["license_url"])}" rel="noopener noreferrer">{esc(license_name)}</a>')
    elif license_name:
        who.append(esc(license_name))
    if who:
        label = "Foto" if lang == "nl" else "Photo"
        bits.append(f"{label}: {', '.join(who)}.")
    return " ".join(bits)


def photo_caption(key, lang):
    """Attribution and an honest note when the photograph is not that exact version."""
    return photo_caption_from(MODELS[key].get("credit"), lang)


def social_img(a, lang):
    return f"/img/{a['slug']}-{lang}.jpg"


# Coarse scene per photo, so neighbouring articles never show the same kind of background.
SCENES = [
    (r"^models/m3c-([1-4])\.jpg$", "highway"), (r"^models/m3c-([5-8])\.jpg$", "city"), (r"^models/m3c-(9|10|11)\.jpg$", "sunset"),
    (r"^models/myj-[126]\.jpg$", "city"), (r"^models/myj-[345]\.jpg$", "sunset"),
    (r"^models/ct-[14]\.jpg$", "city"), (r"^models/ct-2\.jpg$", "sunset"), (r"^models/ct-[35]\.jpg$", "desert"), (r"^models/ctf-1\.jpg$", "sunset"), (r"^models/cb-2", "desert"), (r"^models/myp-2", "coast"), (r"^models/mys-2", "countryside"), (r"^models/m3s-2", "canal"), (r"^models/mxc-2", "trees"), (r"^models/mxp-1", "mountain"), (r"^models/myl-2", "rain"),
    (r"^models/cc-\d\.jpg$", "city"), (r"^models/rd-14\.jpg$", "rd-sky"), (r"^models/rd-15\.jpg$", "rd-road-front"), (r"^models/rd-16\.jpg$", "rd-parked"), (r"^models/rd-17\.jpg$", "rd-side"), (r"^models/rd-18\.jpg$", "rd-rear-wing"), (r"^models/rd-19\.jpg$", "rd-seats"), (r"^models/rd-20\.jpg$", "rd-track-screen"), (r"^models/rd-21\.jpg$", "rd-thruster-display"), (r"^models/rd-22\.jpg$", "rd-tank"), (r"^models/rd-23\.jpg$", "rd-nozzles"), (r"^models/rd-24\.jpg$", "rd-battery"), (r"^models/myl-3", "highway"), (r"^models/myl-4", "coast"), (r"^models/myl-5", "countryside"), (r"^models/myl-6", "parking"), (r"^models/myl-7", "cabin"), (r"^models/rd-4\.jpg$", "rd-countryside"), (r"^models/rd-5\.jpg$", "rd-night"), (r"^models/rd-6\.jpg$", "rd-highway"), (r"^models/rd-7\.jpg$", "rd-stage"), (r"^models/rd-8\.jpg$", "rd-loop"), (r"^models/rd-9\.jpg$", "rd-mountain"), (r"^models/rd-10\.jpg$", "rd-studio-air"), (r"^models/rd-11\.jpg$", "rd-parking"), (r"^models/rd-12\.jpg$", "rd-cabin"), (r"^models/rd-13\.jpg$", "rd-cabin-sunset"), (r"^models/rd-1\.jpg$", "sky"), (r"^models/rd-[23]\.jpg$", "sunset"),
    (r"^models/mx-[12]", "sunset"), (r"^models/mx-3", "trees"), (r"^models/mx-4", "countryside"), (r"^models/mx-5", "night"), (r"^models/msc-1", "village"), (r"^models/msc-2", "hills"), (r"^models/msc-3", "beach"), (r"^models/msc-4", "sunset"), (r"^models/ms-1", "village"), (r"^models/ms-2", "trees"), (r"^models/ms-3", "night"), (r"^models/ms-4", "sunset"), (r"^models/m3h-1", "night"), (r"^models/m3h-2", "street"), (r"^models/m3h-3", "autumn"), (r"^models/m3h-[45]", "coast"), (r"^models/m3p", "track"), (r"^models/myc-1", "polder"), (r"^models/myj-10", "street"), (r"^models/myj-11", "mountain"), (r"^models/myj-12", "rain"), (r"^models/myl", "street"), (r"^models/myj-7", "forest"), (r"^models/myj-8", "spring"), (r"^models/myj-9", "polder"), (r"^models/cc-3", "sunset"), (r"^models/semi-6", "semi-lot"), (r"^models/semi-7", "semi-cab"), (r"^models/semi", "sunset"), (r"^models/", "studio"),
    (r"^topics/guide-roadtrip", "mountain"), (r"^topics/guide-(service|papers)", "street"), (r"^topics/guide-(wintertyres|tread)", "garage"), (r"^topics/(guide-battery|software-update)", "cabin"), (r"^topics/energy-home-dusk", "house"), (r"^topics/spacex-8", "factory"), (r"^topics/gigafactory-(berlin|shanghai|nevada|fremont)", "aerial"), (r"^topics/musk-1", "stage"), (r"^topics/musk-2", "podium"), (r"^topics/musk-3", "desk"), (r"^topics/xai-dc", "datacenter"), (r"^topics/gigafactory-[56]", "aerial"), (r"^topics/gigafactory-4", "sunset"), (r"^topics/earnings-[5-8]", "dashboard"), (r"^topics/earnings-1", "screen-dark"), (r"^topics/earnings", "stage"), (r"^topics/(gigafactory)", "factory"), (r"^topics/(fsd|grok)", "interior"), (r"^topics/spacex-6", "ocean"), (r"^topics/spacex-7", "launchpad"), (r"^topics/(spacex|starlink-\d)", "space"),
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


STUDIO = {"cybertruck.jpg", "model-3-classic.jpg", "model-3.jpg", "model-s.jpg", "model-x.jpg", "model-y-classic.jpg", "model-y.jpg"}  # black studio shots: menu only


def candidates(a):
    """All suitable photos for an article, preferred first, rotated per article."""
    out = []
    if a.get("image") and (STATIC / "img" / a["image"]).exists():
        out.append(f"/img/{a['image']}")
    pics = [x if "/" in x else f"topics/{x}" for x in a.get("images", [])]
    pics = [f"/img/{x}" for x in pics if (STATIC / "img" / x).exists()]
    if pics:
        out += pics  # explicit photos keep their order: best first
        out.append(f"/img/v/{a['slug']}.jpg")
        seen = set()
        return [x for x in out if not (x in seen or seen.add(x))]
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
    return [x for x in out if not (x in seen or seen.add(x)) and not (x.startswith("/img/models/") and x.rsplit("/", 1)[-1] in STUDIO)]


def assign_photos(arts):
    """Oldest first: each article avoids the photo and the scene of the 3 articles before it, so on
    the site (newest first, 3 per row) no photo or background repeats next to or directly above another."""
    hist, cat_hist, cat_use = [], {}, {}
    for a in sorted(arts, key=published):
        cands = candidates(a)
        photos = [c for c in cands if not c.startswith("/img/v/")]
        # least used within this category first, so a topic page repeats a photo only when it runs out
        used = cat_use.setdefault(a["category"], {})
        photos.sort(key=lambda c: used.get(c, 0))
        # neighbours on the homepage (all articles) and on the category / model pages
        groups = [a["category"]] + a.get("also", []) + [MODELS[k].get("parent") or k for k in a.get("models", [])]
        local = [h for g in groups for h in cat_hist.get(g, [])[-3:]]
        recent_files = [h[0] for h in hist[-4:]] + [h[0] for h in local]
        recent_scenes = [h[1] for h in hist[-3:]] + [h[1] for h in local]
        own = f"/img/{a['image']}" if a.get("image") and (STATIC / "img" / a["image"]).exists() else None
        # image_lock keeps the photo the article names. Neighbour-avoidance must not
        # swap in a Tesla or SpaceX picture for a different company's story.
        if a.get("image_lock") and own:
            pick = own
        else:
            pick = own if own and own not in recent_files else None
        if not pick and a.get("images"):
            # explicit images: keep their order (best first), only skip one that a neighbour just used
            exp = [c for c in photos if c.split("/img/", 1)[-1].replace("topics/", "") in a["images"]
                   or c.split("/img/", 1)[-1] in a["images"]]
            if exp:
                pick = next((c for c in exp if c not in recent_files), None)
            if not pick:
                # every listed photo was just used by a neighbour: borrow a fitting one from the model
                # gallery / category instead of showing the same picture twice in a row
                alt = [c for c in candidates({**a, "images": []}) if not c.startswith("/img/v/") and c not in recent_files
                       and not (re.search(r"/rd-\d", c) and a.get("date", "") < "2026-10-15")]
                alt.sort(key=lambda c: used.get(c, 0))
                pick = next((c for c in alt if scene_of(c) not in recent_scenes), None) or (alt[0] if alt else None) \
                    or (exp[0] if exp else None)
        for n in sorted({used.get(c, 0) for c in photos}):
            if pick:
                break
            tier = [c for c in photos if used.get(c, 0) == n]
            pick = next((c for c in tier if c not in recent_files and scene_of(c) not in recent_scenes), None) \
                or next((c for c in tier if c not in recent_files), None)
        pick = pick or (photos[0] if photos else cands[-1])
        CHOSEN[a["slug"]] = pick
        used[pick] = used.get(pick, 0) + 1
        hist.append((pick, scene_of(pick)))
        for g in groups:
            cat_hist.setdefault(g, []).append((pick, scene_of(pick)))


GALLERY_ORDER = {}  # slug -> position among articles sharing the same first model (set in build)
PHOTO_ORDER = {}  # slug -> position among articles of its category, oldest first (set in build)


PALETTES = ["yr", "by", "gy"]  # yellow letters always: red, blue or green block (and "yk": yellow block, black letters, single-line labels)
PALETTE = {}  # slug -> palette
_TONE = {}


def tone(path):
    """Colour mix of the bottom-left area of a photo, where the label sits."""
    if path in _TONE:
        return _TONE[path]
    f = STATIC / path.lstrip("/")
    if path.startswith("/img/v/") or not f.exists():
        f = STATIC / "img" / path.split("/img/", 1)[-1]
    res = None
    try:
        from PIL import Image
        import colorsys
        im = Image.open(f).convert("RGB")
        w, h = im.size
        raw = im.crop((0, int(h * .5), int(w * .6), h)).resize((48, 24)).tobytes()
        px = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
        warm = blue = green = 0
        light = 0.0
        for r, g, b in px:
            hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            light += ll
            if ss < .22 or ll < .12 or ll > .9:
                continue
            d = hh * 360
            if d < 55 or d > 330:
                warm += 1
            elif 180 <= d <= 260:
                blue += 1
            elif 65 <= d < 170:
                green += 1
        n = len(px)
        res = {"warm": warm / n, "blue": blue / n, "green": green / n, "light": light / n}
    except Exception:
        pass
    _TONE[path] = res
    return res


GREEN_CATS = {"energy", "charging", "factories"}
GOOD_NEWS = (r"\bRECORD|\bBEVESTIGD|\bCONFIRMED|GOEDGEKEURD|\bAPPROVED|\d-\d VOOR|\bGROEI|\bGROWTH|UITVERKOCHT|SOLD OUT|"
             r"\bEERDER\b|\bSOONER|\bEARLIER|\bOPEN|\bSNELLER|\bFASTER|"
             r"\bGOEDKOPER|\bCHEAPER|\bMELKKOE|\bCASH COW|\bWINST|\bPROFIT|\bGROOTSTE|\bBIGGEST|\bLARGEST")


def assign_palettes(arts):
    """Label colours: the big letters are always yellow; the block is red (bad news), green (good news) or
    red/blue to suit the photo. A single-block label is red or yellow with black letters. Articles next to
    each other (on the homepage and within a category) get a different block colour."""
    last, hist, single = {}, [], []
    BAD = (r"\b(EINDE|END|ENDS|STOP|STOPS|STOPT|GESTOPT|GESCHRAPT|SCRAPPED|CANCELL?ED|RECALL|TERUGROEP|CRASH|ONGELUK|"
           r"VERBOD|BAN|BANNED|WEG|LEAVES|QUITS|DAALT|DALING|FALLS|DROPS|MIST|MISSES|BOETE|FINE|RECHTSZAAK|LAWSUIT|"
           r"ONDERZOEK|PROBE|SLUIT|CLOSES|VERLIES|LOSS|ZAKT|REMMEN|STIL)\b")
    for a in sorted(arts, key=published):
        lb = a.get("label") or {}
        words = " ".join(str(lb.get(g, {}).get(k, "")) for g in ("en", "nl") for k in ("sub", "text")).upper()
        t = tone(CHOSEN.get(a["slug"], "")) or {"warm": 0, "blue": 0, "green": 0, "light": .45}
        near = hist[-2:] + last.get(a["category"], [])[-2:]
        if lb.get("pal") in PALETTES + ["yk"]:
            pick = lb["pal"]
        elif lb.get("style") == "r":
            # one block only: red, or yellow with black letters; alternate so they do not look alike
            pick = "yk" if (single[-1:] == ["yr"] and t["warm"] < .35 and t["light"] < .7) else "yr"
            single.append(pick)
        else:
            score = {"yr": 0.0, "by": 0.0, "gy": -0.4}
            bad = re.search(BAD, words) or re.search(r"[-−]\d", words)
            if bad:
                score["yr"] += 3; score["gy"] -= 9   # bad news: red, never green
            elif re.search(GOOD_NEWS, words) and "?" not in words:
                score["gy"] += 1.5                   # good news: green
            if t["green"] > .22:
                score["gy"] -= 9                     # green block disappears on green photos
            score["by"] += t["warm"] * 1.5           # blue block on warm / gold / sunset photos
            score["yr"] += t["blue"] * 1.5 + t["green"] * 1.2
            cats = [last.get(g, [])[-1:] for g in [a["category"]] + a.get("also", [])]
            for p in score:                          # variety: neighbours get another colour
                score[p] -= 2.0 * (hist[-1:] == [p]) + 0.8 * (hist[-2:-1] == [p]) + 1.6 * sum(c == [p] for c in cats)
            pick = max(score, key=lambda p: score[p])
        PALETTE[a["slug"]] = pick
        blk = "yr" if pick == "yk" else pick
        hist.append(blk)
        for g in [a["category"]] + a.get("also", []):
            last.setdefault(g, []).append(blk)


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


# Responsive derivatives written under public/img/opt/. The original file stays the img src.
OPT_WIDTHS = (480, 800, 1200)
_OPT = {}
SIZES_LEAD = "(max-width: 900px) 100vw, 900px"
SIZES_CARD = "(max-width: 700px) 100vw, 280px"
SIZES_GRID = "(max-width: 600px) 100vw, (max-width: 1000px) 33vw, 280px"
SIZES_VIDEO = "(max-width: 800px) 78vw, 240px"
SIZES_HERO = "(max-width: 760px) 100vw, 720px"
# Model grid: one column on a phone, two from 700px, three from 1100px beside the sidebar.
SIZES_MODEL = "(max-width: 699px) calc(100vw - 24px), (max-width: 899px) calc(50vw - 20px), (max-width: 1099px) calc(100vw - 40px), 260px"
_DIM = {}


def _opt_variants(src):
    """Build AVIF and WebP widths for one site image. Cached for this build."""
    if src in _OPT:
        return _OPT[src]
    path = OUT / str(src).lstrip("/")
    if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        _OPT[src] = None
        return None
    try:
        from PIL import Image as PILImage
        im = PILImage.open(path)
        im.load()
        if im.mode == "RGBA":
            bg = PILImage.new("RGB", im.size, (8, 8, 8))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")
    except Exception:
        _OPT[src] = None
        return None
    ow, oh = im.size
    key = hashlib.sha1(src.encode()).hexdigest()[:12]
    folder = OUT / "img" / "opt" / key
    folder.mkdir(parents=True, exist_ok=True)
    widths = []
    for want in OPT_WIDTHS:
        w = ow if want >= ow else want
        if w in widths:
            continue
        h = max(1, round(oh * w / ow))
        frame = im if (w, h) == (ow, oh) else im.resize((w, h), PILImage.Resampling.LANCZOS)
        frame.save(folder / f"{w}.webp", "WEBP", quality=62, method=4)
        frame.save(folder / f"{w}.avif", "AVIF", quality=40, speed=8)
        widths.append(w)
        if w == ow:
            break
    _OPT[src] = (key, widths)
    return _OPT[src]


def img_size(src, default=(1200, 630)):
    """Pixel size of a site image, for width/height on the tag."""
    if not isinstance(src, str) or not src.startswith("/"):
        return default
    if src in _DIM:
        return _DIM[src]
    path = OUT / src.lstrip("/")
    if not path.is_file():
        path = STATIC / src.lstrip("/")
    try:
        from PIL import Image
        with Image.open(path) as im:
            _DIM[src] = im.size
    except Exception:
        _DIM[src] = default
    return _DIM[src]


def resp_img(src, alt, sizes, *, high=False, lazy=True, width=1200, height=630, cls=""):
    """AVIF and WebP srcset, with the original file as the fallback src."""
    cls_attr = f' class="{cls}"' if cls else ""
    flags = ['decoding="async"']
    if high:
        flags.insert(0, 'fetchpriority="high"')
    elif lazy:
        flags.insert(0, 'loading="lazy"')
    img = (f'<img{cls_attr} src="{esc(src)}" alt="{esc(alt)}" width="{width}" height="{height}" '
           f'{" ".join(flags)}>')
    info = _opt_variants(src) if isinstance(src, str) and src.startswith("/") else None
    if not info:
        return img
    key, widths = info
    def srcset(ext):
        return ", ".join(f"/img/opt/{key}/{w}.{ext} {w}w" for w in widths)
    sized = esc(sizes)
    return (f'<picture><source type="image/avif" sizes="{sized}" srcset="{srcset("avif")}">'
            f'<source type="image/webp" sizes="{sized}" srcset="{srcset("webp")}">{img}</picture>')


def read_time(a, lang):
    return max(1, round(len(html.unescape(a[lang]["body"]).split()) / 220))


def page(lang, path, title, description, body, og_type="website", extra_head="", image=None, active=None, robots=None, canonical=True, bar=None, alt_path=None):
    L = LANGS[lang]
    alt = other(lang)
    # alt_path is the other language's slug when it differs (newsletter/ vs nieuwsbrief/).
    switch = alt_path if alt_path is not None else path
    en_path = path if lang == "en" else switch
    nl_path = switch if lang == "en" else path
    full_title = f"{title} | {NAME}" if title != NAME else f"{NAME} — {L['tagline']}"
    canon_url = SITE + url(lang, path)
    robots_meta = robots or "max-image-preview:large, max-snippet:-1, max-video-preview:-1"
    if "max-image-preview" not in robots_meta:
        robots_meta = robots_meta.rstrip().rstrip(",") + ", max-image-preview:large"
    if canonical:
        canon_links = (
            f'<link rel="canonical" href="{canon_url}">\n'
            f'<link rel="alternate" hreflang="en" href="{SITE + url("en", en_path)}">\n'
            f'<link rel="alternate" hreflang="nl" href="{SITE + url("nl", nl_path)}">\n'
            f'<link rel="alternate" hreflang="x-default" href="{SITE + url("en", en_path)}">'
        )
        og_url_meta = f'<meta property="og:url" content="{canon_url}">'
    else:
        # A page with no URL of its own (the 404 template) must not claim the homepage.
        canon_links = ""
        og_url_meta = ""
    img = SITE + (image or f"/img/default-{lang}.jpg")
    menu = "".join(
        f'<a href="{url(lang, "category/" + k + "/")}"{" class=\"on\"" if k == active else ""}>{c[lang]}</a>'
        for k, c in CATEGORIES.items() if c["menu"])
    def flinks(rows):
        return "".join(f'<a href="{url(lang, path)}">{esc(name)}</a>' for name, path in rows)

    layers_html = "".join(
        f'<a class="tone-{layer["tone"]}" href="{url(lang, layer["href"])}">{esc(layer["label"][lang])}</a>'
        for layer in NAV_LAYERS)
    explore = flinks([
        (L["nav_eco"], ecosystem_path(lang)),
        ("All news" if lang == "en" else "Al het nieuws", "category/news/"),
        (L["videos"], "shorts/"),
        ("Videos" if lang == "en" else "Video's", "videos/"),
        ("Weekly briefing" if lang == "en" else "Weekbriefing", "briefing/"),
        ("Promises" if lang == "en" else "Beloftes", promises_path(lang)),
        (CATEGORIES["musk"][lang], "category/musk/"),
        (CATEGORIES["earnings"][lang], "category/earnings/"),
        (CATEGORIES["factories"][lang], "category/factories/"),
        (CATEGORIES["software"][lang], "category/software/"),
    ])
    shop = flinks([
        ("Buying guides" if lang == "en" else "Koopgidsen", guides_path(lang)),
        (CATEGORIES["guides"][lang], "category/guides/"),
    ])
    about_col = flinks([
        (L["about"], "about/"),
        (L["editorial"], "editorial/"),
        (L["signup"], signup_path(lang)),
        ("Contact", "contact/"),
        ("Advertise" if lang == "en" else "Adverteren", advertise_path(lang)),
    ])
    legal = flinks([
        (L["privacy"], "privacy/"),
        ("Terms" if lang == "en" else "Voorwaarden", "terms/"),
        ("Affiliate disclosure" if lang == "en" else "Affiliate-melding", disclosure_path(lang)),
    ])
    foot_heads = {
        "en": ("The 7 layers", "Explore", "Shop & guides", "TrendingTesla", "Legal"),
        "nl": ("De 7 lagen", "Ontdekken", "Shop & gidsen", "TrendingTesla", "Juridisch"),
    }[lang]
    foot_cols = (
        (foot_heads[0], layers_html),
        (foot_heads[1], explore),
        (foot_heads[2], shop),
        (foot_heads[3], about_col),
        (foot_heads[4], legal),
    )
    fbits = [
        f'<details class="fcol c{i}" open><summary class="flabel">{esc(title)}</summary>'
        f'<div class="flist">{html}</div></details>'
        for i, (title, html) in enumerate(foot_cols, 1)]
    # Left stack is the odd sections, right stack the even ones, so a short
    # column does not wait for the taller neighbour.
    fsections = (f'<div class="fstack">{fbits[0]}{fbits[2]}{fbits[4]}</div>'
                 f'<div class="fstack">{fbits[1]}{fbits[3]}</div>')
    cats = " · ".join(f'<a href="{url(lang, "category/" + k + "/")}">{c[lang]}</a>' for k, c in CATEGORIES.items() if c["menu"])
    mods = " · ".join(f'<a href="{url(lang, "model/" + k + "/")}">{m["name"]}</a>' for k, m in MODELS.items() if not m.get("parent") or k in MODEL_STRIP)
    search = (f'<form class="search hb-search" role="search" method="post" action="{url(lang)}" '
              f'data-idx="/search-{lang}.json" data-none="{L["none"]}"><input type="search" name="q" '
              f'placeholder="{L["search"]}" aria-label="{L["search"]}" autocomplete="off">'
              f'<button type="submit" aria-label="{L["search"]}">{SEARCH_SVG}</button><div class="res" hidden></div></form>')
    tools = (f'<a class="savedlink" href="{url(lang, "saved/")}" title="{L["saved"]}" aria-label="{L["saved"]}">{BOOK_SVG}<i hidden></i></a>'
             f'<a class="lang" href="{url(alt, switch)}" hreflang="{alt}" lang="{alt}" title="{L["switch_full"]}">{L["switch"]}</a>')
    news_href = url(lang, signup_path(lang))
    burger = f'<button class="burger" type="button" aria-label="{L["menu"]}" aria-expanded="false" aria-controls="drawer"><span></span><span></span><span></span></button>'
    brand = f'<div class="brand"><a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a></div>'
    find_label = "Search" if lang == "en" else "Zoeken"
    header = (f'<header class="top hb"><div class="wrap"><div class="bar">{burger}'
              f'<div class="id">{brand}{primary_nav(lang, active)}<div class="hb-inline"></div></div>'
              f'<button class="sbtn" type="button" aria-label="{find_label}" aria-expanded="false" aria-controls="site-search">{SEARCH_SVG}</button>'
              f'{tools}</div></div>'
              f'<div class="hb-find" id="site-search" inert><div class="wrap">{search}</div></div></header>'
              '<script>(function(){if(!matchMedia("(min-width:769px)").matches)return;var f=document.querySelector("form.hb-search"),s=document.querySelector("header.hb .hb-inline");if(!f||!s)return;s.appendChild(f);var p=document.getElementById("site-search");if(p)p.inert=true;})();</script>')
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{adsense_tag()}<meta name="robots" content="{robots_meta}">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
{canon_links}
<link rel="alternate" type="application/rss+xml" title="{NAME}" href="{url(lang, 'feed.xml')}">
<link rel="preload" href="/fonts/manrope-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/manrope-latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/manrope-latin-800-normal.woff2" as="font" type="font/woff2" crossorigin>
<meta property="og:site_name" content="{NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="{og_type}">
{og_url_meta}
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{L['locale']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{img}">
<meta name="theme-color" content="#03050a">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-48.png" sizes="48x48" type="image/png">
<link rel="icon" href="/favicon-192.png" sizes="192x192" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>{page_css()}</style>
{extra_head}
</head>
<body>
{header}
<div class="scrim"></div>
<nav id="drawer" class="drawer" aria-label="{L['menu']}">{drawer(lang, active, path.strip("/").split("/")[1] if path.strip("/").startswith("model/") else None)}</nav>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
<div class="fgrid"><div class="fbrand"><a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a><p>{L['tagline']} {L['disclaimer']}</p>{newsletter(lang, "foot")}</div><div class="fcols">{fsections}</div></div>
<p class="fcopy">&copy; {datetime.now().year} {NAME} · <a href="https://www.youtube.com/@TrendingTesla" rel="noopener" target="_blank">YouTube</a> · <button type="button" class="flink" data-consent-open>{L['cookie']}</button> · <a href="{url(lang, 'feed.xml')}">RSS</a> · <a href="{url(alt, switch)}">{L['switch_full']}</a></p>
</div></footer>
{consent_bar(lang)}
<script>{JS}{PRODUCT_JS}</script>
</body>
</html>
"""


SEARCH_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/></svg>'
CHEV_SVG = '<svg class="chev" width="11" height="11" viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M2.1 4.2 6 8.1 9.9 4.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
HEART_SVG = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.4 4.5 7 4.5c2 0 3.6 1.1 5 2.9 1.4-1.8 3-2.9 5-2.9 3.6 0 5.6 3.5 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z"/></svg>'
BOOK_SVG = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"><path d="M6 3.5h12v17l-6-4.2-6 4.2z"/></svg>'


def story_actions(slug, lang):
    """Heart (like) and bookmark (save). The same localStorage list the navbar badge reads."""
    L = LANGS[lang]
    return (
        f'<div class="acts">'
        f'<button class="act like" type="button" data-like="{esc(slug)}" aria-pressed="false" title="{esc(L["like"])}">{HEART_SVG}<span>0</span></button>'
        f'<button class="act save" type="button" data-save="{esc(slug)}" aria-pressed="false" title="{esc(L["save"])}" aria-label="{esc(L["save"])}">{BOOK_SVG}</button>'
        f'</div>')


def with_actions(meta, slug, lang, href=""):
    """Caption and the two icons on one line. A long caption ellipsizes before the icons."""
    if not meta:
        return ""
    text = f'<a class="lgo" href="{href}">{meta}</a>' if href else meta
    if not slug:
        return f'<div class="lrow">{text}</div>' if href else meta
    return f'<div class="lrow">{text}{story_actions(slug, lang)}</div>'
DRAWER_MODELS = MODEL_STRIP + ["cybercab", "semi", "roadster"]


def drawer(lang, active=None, model=None):
    L = LANGS[lang]
    cur = nav_current(active)
    out = (f'<div class="dh"><button class="burger" type="button" aria-label="{L["menu"]}"><span></span><span></span><span></span></button>'
           f'<a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a></div>'
           f'<button class="di dclose" type="button">‹ {L["collapse"]}</button>'
           f'<div class="dpri">{drawer_links(lang, active)}</div>')
    show = cur == "models" or model in MODELS
    out += f'<div class="dmodels{" show" if show else ""}">' + modelnav(lang, model if model in MODELS else None) + '</div>'
    return out


# --- no question right before a heading (the heading is the question) ---
Q_LEAD = re.compile(r"(so here is the (big |real )?question|here is the (big |real )?question|the (big |real )?question is|"
                  r"dus de (grote )?vraag is|de (grote )?vraag is dus|dat roept de vraag op|en dan de (grote )?vraag)[.:!]?$", re.I)
Q_SENT = re.compile(r"[^.!?]+[.!?]+[\"'”’)]*\s*$")

def strip_q(t):
    t0 = t.rstrip()
    if not t0.endswith("?"):
        return t
    m = Q_SENT.search(t0)
    rest = t0[:m.start()].rstrip() if m else ""
    while rest:
        m2 = Q_SENT.search(rest)
        last = rest[m2.start():].strip() if m2 else rest
        if Q_LEAD.search(last.strip()) or last.endswith("?"):
            rest = rest[:m2.start()].rstrip() if m2 else ""
        else:
            break
    return rest if rest else t



def drop_q_before_h2(body):
    return re.sub(r"<p>((?:(?!</?p>).)*?\?)\s*</p>(\s*<h2)",
                  lambda m: f"<p>{strip_q(m.group(1))}</p>{m.group(2)}", body, flags=re.S)


def enrich(a, lang, with_toc=False):
    """Anchors on subheadings. Longer articles (4 or more headings) get a table of contents."""
    body = drop_q_before_h2(a[lang]["body"])
    heads = []

    def anchor(m):
        heads.append(re.sub(r"<[^>]+>", "", m.group(1)))
        return f'<h2 id="s{len(heads)}">{m.group(1)}</h2>'
    body = re.sub(r"<h2>(.*?)</h2>", anchor, body)
    toc = ""
    if with_toc and len(heads) >= 4:
        label = LANGS[lang]["toc"]
        items = "".join(f'<li><a href="#s{i}">{esc(text)}</a></li>' for i, text in enumerate(heads, 1))
        toc = f'<nav class="toc" aria-label="{esc(label)}"><b>{esc(label)}</b><ol>{items}</ol></nav>'
    return toc, body


def story(a, lang, tag="h1"):
    """Full article block: photo, title, intro, meta, model chips, body and sources."""
    L = LANGS[lang]
    t = a[lang]
    src = ""
    if a.get("sources"):
        items = "".join(f'<li><a href="{esc(s["url"])}" rel="nofollow noopener" target="_blank">{esc(s["title"])}</a></li>'
                        for s in a["sources"])
        src = f'<details class="sources"><summary>{L["sources"]} ({len(a["sources"])})</summary><ul>{items}</ul></details>'
    if a.get("credits"):  # real, freely licensed photos: the licence requires the credit
        cr = "; ".join(f'<a href="{esc(c["page"])}" rel="nofollow noopener" target="_blank">{esc(c["credit"])}</a>'
                       for c in a["credits"] if c.get("page"))
        src += f'<p class="imgnote">{L["photocredit"]}: {cr}. {L["imgnote_other"]}{footage_note(a["slug"], lang)}</p>'
    else:
        src += f'<p class="imgnote">{L["imgnote"]}{footage_note(a["slug"], lang)}</p>'
    chips = ""
    if a.get("models"):
        chips = '<div class="chips">' + "".join(
            f'<a href="{url(lang, "model/" + k + "/")}">{esc(model_heading(k, lang))}</a>' for k in a["models"]) + "</div>"
    title = esc(t["title"]) if tag == "h1" else f'<a href="{url(lang, a["slug"] + "/")}">{esc(t["title"])}</a>'
    byline = (f'<p class="byline"><a href="{url(lang, "editorial/")}">{L["byline"]}</a></p>' if tag == "h1" else "")
    toc, body = enrich(a, lang)
    section, section_href = topic_meta(a, lang)
    return (f'<article>'
            f'<div class="hi"{vhero(a, lang)}>{resp_img(site_img(a), t["title"], SIZES_HERO, lazy=False, cls="hero-img")}{dur(a, lang)}{ovl(a, lang)}</div>{vscript(a, lang)}'
            f'<{tag} class="st">{title}</{tag}>{byline}'
            f'<div class="srow"><p class="meta smeta"><a class="tag" href="{url(lang, section_href)}">{esc(section)}</a> · {when(a, lang)}</p>'
            f'<div class="acts"><button class="act like" type="button" data-like="{a["slug"]}" aria-pressed="false" title="{L["like"]}">{HEART_SVG}<span>0</span></button>'
            f'<button class="act save" type="button" data-save="{a["slug"]}" aria-pressed="false" title="{L["save"]}" aria-label="{L["save"]}">{BOOK_SVG}</button></div></div>'
            f'<p class="lead">{esc(t["description"])}</p>{toc}'
            f'<div class="prose">{body}</div>{src}</article>')


ALL_ARTS = []
ARCH_PAGES = [1]
VIDEOS = {}  # (slug, lang) -> long YouTube video from content/videos.json


MODEL_ROOTS = ["model-s", "model-3", "model-x", "model-y", "cybertruck", "cybercab", "semi", "roadster"]


def modelnav(lang, current=None):
    """Models with their versions: a model header with a bar (photo + type/year) per version."""
    cur_root = (MODELS[current].get("parent") or current) if current else None
    rows = ""
    for r in MODEL_ROOTS:
        kids = [(k, v) for k, v in MODELS.items() if v.get("parent") == r]
        items = []
        for k, v in kids:
            lbl = v["label"][lang] if isinstance(v["label"], dict) else v["label"]
            items.append((k, lbl.split(" · ")[0], v.get("menu")))
        if not items:
            items = [(r, MODELS[r]["name"], MODELS[r].get("menu"))]
        bars = ""
        for k, lbl, img in items:
            rel = (Path(img) if "/" in img else Path("models") / img) if img else None
            src = "/img/" + rel.as_posix() if rel and (STATIC / "img" / rel).is_file() else ""
            w, h = img_size(src, (148, 100)) if src else (148, 100)
            th = resp_img(src, lbl, "74px", width=w, height=h) if src else ""
            bars += f'<a href="{url(lang, "model/" + k + "/")}" class="vt{" on" if k == current else ""}"><b>{th}</b><span>{esc(lbl)}</span></a>'
        st = " on" if current == r else (" in" if cur_root == r else "")
        rows += (f'<div class="mgrp"><a class="mh{st}" href="{url(lang, "model/" + r + "/")}">{MODELS[r]["name"]}</a>'
                 f'<div class="mopts">{bars}</div></div>')
    return f'<nav class="mnav" aria-label="Models">{rows}</nav>'


def modelinfo(key, lang, heading=True):
    L = LANGS[lang]
    inf = INFO.get(key)
    if not inf:
        return ""
    t = inf[lang]
    ph = model_photo(key)
    img = f'<div class="hi">{resp_img(ph, "Tesla " + MODELS[key]["name"], SIZES_HERO, lazy=False, cls="hero-img")}</div>' if ph else ""
    rows = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in t["specs"])
    li = lambda xs: "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in xs) + "</ul>"
    src = "".join(f'<li><a href="{esc(u)}"{"" if u.startswith("/") else " rel=nofollow target=_blank"}>{esc(ti)}</a></li>'
                  for ti, u in inf["sources"])
    title = f'<h1 class="st">Tesla {MODELS[key]["name"]}</h1><p class="lead">{esc(t["intro"])}</p>' if heading else ""
    return (f'<article class="minfo">{img}{title}'
            f'<div class="prose"><h2>{L["i_specs"]}</h2><table class="specs">{rows}</table>'
            f'<h2>{L["i_watch"]}</h2>{li(t["watch"])}<h2>{L["i_special"]}</h2>{li(t["special"])}'
            f'<h2>{L["i_acc"]}</h2>{model_accessory_links(key, lang)}</div>'
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
    own = [x for x in items if x is not lead]  # never repeat the lead in the grid below it
    if active == "news":
        return feed(lead, story(lead, lang, "h2"), own, lang, active, L["latest"], extra_side=extra)
    rest = [x for x in ALL_ARTS if x is not lead]
    own = sorted(own, key=published, reverse=True)
    return feed(lead, modelinfo(model, lang) if info else story(lead, lang, "h2"), rest, lang,
                "models" if model else active, L["latest"], extra_side=extra, left_exact=own,
                lead_px=1500 if info else None, left_pad=pad_grid(lead, own))


def pad_grid(lead, own):
    """Related articles from neighbouring topics that complete the last grid row (4, 3 and 2 columns)."""
    return []  # only articles of the topic itself are shown (owner's choice, 2026-10-24)
    if not own:
        return []
    need = (-len(own)) % 12
    if not need:
        return []
    base = (lead or own[0])["category"]
    cats = ([base] if not lead else []) + NEAR_CATS.get(base, []) + ["news"]
    taken = {id(x) for x in own} | ({id(lead)} if lead else set())
    pool = [x for c in cats for x in sorted((y for y in ALL_ARTS if y["category"] == c), key=published, reverse=True)]
    pool += sorted(ALL_ARTS, key=published, reverse=True)
    out = []
    for x in pool:
        if id(x) not in taken:
            out.append(x); taken.add(id(x))
        if len(out) == need:
            break
    return out


def btn_label(c, lang):
    return f'<b>{c["btn"]}</b>' if c.get("btn") else c[lang]


def menu_key(active):
    """Every page highlights one topic button; pages outside the menu fall back to News."""
    return active if active in CATEGORIES and CATEGORIES[active]["menu"] else "news"


def topicdd(lang, active=None):
    """Topic dropdown in the top bar (replaces the button grid in the right column)."""
    key = menu_key(active)
    items = "".join(f'<a href="{url(lang, "category/" + k + "/")}"{" class=\"on\"" if k == key else ""}>{c[lang]}</a>'
                    for k, c in CATEGORIES.items() if c["menu"])
    lbl = {"en": "Topics", "nl": "Rubrieken"}[lang]
    return (f'<div class="tdd"><button class="tdb" type="button" aria-haspopup="true" aria-expanded="false" aria-label="{lbl}">'
            f'<span>{CATEGORIES[key][lang]}</span><span class="tdc"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></span></button>'
            f'<nav class="tdl" aria-label="{lbl}" hidden>{items}</nav></div>')


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
MAX_HOME_GRID = 60  # articles in the grid under the tip bar on the home page
MAX_HOME_FEED = 30  # preview lists only; the live homepage list includes every story
MAX_HOME_CARDS = 24  # chronological card grid at the top of the homepage
XTRA = 0  # hidden spare cards after a paged grid; the browser shows enough of them to complete the last row
PER_PAGE = 60   # articles per archive page (60 fills every row at 1-6 columns)


def feed(lead, lead_html, rest, lang, active=None, side_title="", left_first=(), more=(), extra_side="", lead_px=None, left_pool=None, min_left=0, left_exact=None, no_left=False, left_pad=(), article=False):
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
    if left_exact is not None and (active != "news" or article):
        # topic, model and article pages: the 6 most relevant articles open the right column,
        # followed without a heading by the general news
        # topic, model and article pages: the right column holds only articles of this topic
        right_items = [x for x in left_items if x is not lead]
    home_more = False
    if no_left:
        # Home: the open story is `lead`. The rail takes the next articles and the grid
        # continues after the rail, so each article appears once.
        pool = [x for x in rest if x is not lead]
        right_items = pool[:MAX_RIGHT]
        rail_ids = {id(x) for x in right_items}
        grid_pool = [x for x in pool if id(x) not in rail_ids]
        left_items = grid_pool[:MAX_HOME_GRID + XTRA]
        home_more = len(grid_pool) > MAX_HOME_GRID
    more_link = ""
    topic = (left_exact is not None and (active != "news" or article)) or no_left
    if len(left_items) > MAX_LEFT and not topic:
        left_items = left_items[:MAX_LEFT]
        more_link = f'<a class="morelink" href="{url(lang, "archive/")}">{LANGS[lang]["archive"]} →</a>'
    right_items = right_items[:MAX_RIGHT]
    tl = tips(lang)
    g, ti = "", 1
    for i, a in enumerate(list(left_items) + (list(left_pad) if topic else [])):
        if False and i and i % (12 if topic else 6) == 0:  # in-grid tip bars removed (2026-10-24)
            g += f'<div class="span2">{tl[ti % len(tl)]}</div>'
            ti += 1
        c = gcard(a, lang) if topic else card(a, lang)
        g += c.replace('<div class="card"', '<div class="card xtra"', 1) if no_left and i >= MAX_HOME_GRID else c
    side = "".join(mini(a, lang) for a in right_items[:n_own] if more) if more else "".join(mini(a, lang) for a in right_items)
    if more and len(right_items) > n_own:
        side += f'<h2 class="sideh">{CATEGORIES["news"][lang]}</h2>' + "".join(mini(a, lang) for a in right_items[n_own:])
    grid = (f'<div class="grid2 gall wide">{g}</div>' if topic else f'<div class=grid2>{g}</div>') if g else ""
    rubh = f'<h2 class="rubh" id="meer">{esc(CATEGORIES[active][lang])} info</h2>' if g and topic and active in CATEGORIES else ""
    if no_left and home_more:
        L = LANGS[lang]
        more_link = (f'<nav class="pager"><span></span><span>{L["page"]} 1 / {1 + max(1, -(-(len(rest) + 1 - PER_PAGE) // PER_PAGE))}</span>'
                     f'<a href="{url(lang, "archive/2/")}">{L["older"]} ›</a></nav>')
    side_more = (f'<a class="morelink moredn" href="#meer">{LANGS[lang]["d_more"]} <span aria-hidden="true">↓</span></a>' if rubh
                 else f'<a class="morelink" href="{url(lang, "archive/")}">{LANGS[lang]["archive"]} →</a>')
    return (f'<section class="read home{" topic" if topic else ""}"><div class="lcol">{lead_html}</div>'
            f'<aside class="rside">{extra_side}'
            + ("" if active == "models" and not article else f'<h2 class="sr">{side_title}</h2><div class="side">{side}</div>'
               + side_more)
            + '</aside></section>'
            f'<section class="below">{tl[0]}{rubh}{grid}{more_link}</section>')


JS = r"""(function(){function f(){var t=document.querySelector('header.top');if(t)t.classList.toggle('solid',scrollY>0||document.documentElement.classList.contains('dopen'))}addEventListener('scroll',f,{passive:true});document.addEventListener('DOMContentLoaded',f);f()})();(function(){var Q='main h1,main h2,main h3,main p,main li,main tr,main .card,main .gcard,main .mini,main .im,main .hi',K='tt-lswap';try{if('scrollRestoration' in history)history.scrollRestoration='manual'}catch(e){}document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a.lang');if(!a)return;var R=innerHeight*.33,els=document.querySelectorAll(Q),i=-1,off=0;for(var k=0;k<els.length;k++){var r=els[k].getBoundingClientRect();if(r.height>0&&r.top<=R&&r.bottom>R){i=k;off=(R-r.top)/r.height}}var H=document.documentElement.scrollHeight-innerHeight;try{sessionStorage.setItem(K,JSON.stringify({i:i,o:off,r:H>0?scrollY/H:0,y:scrollY,n:els.length,p:location.pathname,t:Date.now()}))}catch(x){}},true);function go(){var d;try{d=JSON.parse(sessionStorage.getItem(K)||'null')}catch(x){}if(!d||Date.now()-d.t>15000||d.p==location.pathname)return;var els=document.querySelectorAll(Q);if(d.i>=0&&els.length==d.n&&els[d.i]){var r=els[d.i].getBoundingClientRect();scrollTo(0,r.top+scrollY+d.o*r.height-innerHeight*.33)}else if(d.y<10){scrollTo(0,0)}else{scrollTo(0,d.r*(document.documentElement.scrollHeight-innerHeight))}}document.addEventListener('DOMContentLoaded',go);addEventListener('load',function(){go();setTimeout(function(){go();try{sessionStorage.removeItem(K)}catch(x){}},350)})})();function ttKK(){var M={a:[6.6,10.5],c:[8,6.2],n:[10,5.8],r:[7.4,7.4]};document.querySelectorAll('.kk').forEach(function(k){var p=k.parentElement,W=p.clientWidth;if(!W)return;var d=p.querySelector('.dur'),A=(d?d.offsetLeft:W)-k.offsetLeft-.026*W,t=(k.className.match(/t-(\w)/)||[])[1]||'a',m=M[t]||M.a,f=[];[].forEach.call(k.children,function(b,i){var s=(k.children.length==1?m[1]:m[i])*W/100;b.style.fontSize=s+'px';for(var j=0;j<3;j++){var w=b.getBoundingClientRect().width;if(w>A){s*=A/w*.995;b.style.fontSize=s+'px'}}f.push(s)});if(f.length==2){if(t=='a'){var w0=k.children[0].getBoundingClientRect().width,w1=k.children[1].getBoundingClientRect().width;if(w1>w0*1.04){var g=Math.max(f[1]*w0/w1,f[0]*1.18);if(g<f[1]){f[1]=g;k.children[1].style.fontSize=g+'px'}}if(f[0]>f[1]*.85)k.children[0].style.fontSize=f[1]*.85+'px'}if(t=='c'&&f[1]>f[0]*.9)k.children[1].style.fontSize=f[0]*.9+'px';if(t=='n'&&f[1]>f[0]*.62)k.children[1].style.fontSize=f[0]*.62+'px'}})}addEventListener('load',ttKK);document.addEventListener('submit',function(e){var f=e.target;if(!f.classList||!f.classList.contains('cform'))return;e.preventDefault();var b=f.querySelector('button'),st=f.querySelector('.cstatus'),d={};new FormData(f).forEach(function(v,k){d[k]=v});d.lang=document.documentElement.lang;d.page=location.pathname;b.disabled=true;st.textContent='…';fetch('/api/contact',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(d)}).then(function(r){return r.json().then(function(j){if(!r.ok||!j.ok)throw 0;st.textContent=f.dataset.ok;f.reset()})}).catch(function(){st.textContent=f.dataset.err;b.disabled=false})});function ttRow(){document.querySelectorAll('.gall').forEach(function(g){var x=g.querySelectorAll(':scope>.xtra');if(!x.length)return;x.forEach(function(e){e.classList.remove('on')});var c=getComputedStyle(g).gridTemplateColumns.split(' ').length,n=g.children.length-x.length,need=(c-n%c)%c;for(var i=0;i<need&&i<x.length;i++)x[i].classList.add('on')})}ttRow();addEventListener('resize',ttRow);document.addEventListener('DOMContentLoaded',ttRow);addEventListener('resize',ttKK);if(document.fonts)document.fonts.ready.then(ttKK);document.addEventListener('DOMContentLoaded',ttKK);function mq(n){return matchMedia('(min-width:'+n+'px)').matches}function ttAgo(){document.querySelectorAll('time.ago').forEach(function(t){var ms=Date.now()-Date.parse(t.dateTime);if(!(ms>=0))return;if(!t.dataset.d)t.dataset.d=t.textContent;var h=ms/36e5,d=h/24,n,u;if(h<1){n=Math.max(1,Math.floor(ms/6e4));u='m'}else if(h<24){n=Math.max(1,Math.floor(h));u='h'}else if(d<7){n=Math.max(1,Math.floor(d));u='d'}else if(d<42){n=Math.max(1,Math.floor(d/7));u='wk'}else if(d<365.25){n=Math.max(1,Math.floor(d/30.44));u='mo'}else{n=Math.max(1,Math.floor(d/365.25));u='y'}t.textContent=n+u+(document.documentElement.lang==='nl'?' geleden':' ago')})}ttAgo();setInterval(ttAgo,60000);function ttSearch(){if(mq(769)){var s=document.querySelector('.bar .search'),h=document.documentElement;if(s){s.style.width='';s.style.marginLeft='';s.style.removeProperty('--k')}h.classList.remove('hass');return;}var s=document.querySelector('.bar .search'),h=document.documentElement;if(!s)return;document.querySelector('.bar .lang').style.height='';h.classList.remove('hasdd');document.querySelector('.bar .savedlink').style.marginLeft='';var bar=s.parentNode,br=bar.querySelector('.brand')||bar.querySelector('.logo'),sv=bar.querySelector('.savedlink');var m=!mq(601)?12:28,L=br.getBoundingClientRect().right+m,R=sv.getBoundingClientRect().left-14,l=document.querySelector('.read .lcol');if(l&&mq(700))R=Math.min(R,l.getBoundingClientRect().right);else if(!l&&mq(905)){var b=bar.getBoundingClientRect();R=Math.min(R,b.left+(b.width-13)*1.7/2.7)}s.style.marginLeft=m+'px';h.classList.add('hass');s.style.width='200px';var w=R-s.getBoundingClientRect().left;if(w>=200){s.style.width=w+'px';s.style.setProperty('--k',Math.min(1,w/520).toFixed(3))}else{h.classList.remove('hass');s.style.width=''}}function ttDD(){var d=document.querySelector('.bar .tdd'),s=document.querySelector('.bar .search'),h=document.documentElement;if(!d)return;h.classList.remove('hasdd','ddend');if(!mq(700)||!h.classList.contains('hass'))return;var bn=d.parentNode,bar=bn.getBoundingClientRect(),L,R,rs=document.querySelector('.read .rside'),ph=rs&&[].slice.call(rs.querySelectorAll('.mini .th img')).filter(function(x){return x.offsetParent})[0];if(ph){var q=ph.getBoundingClientRect();L=q.left;R=q.right}else{var W=bar.width,rw=mq(905)?(W-13)/2.7:(W-13)/3.68;L=bar.right-rw;R=mq(905)?L+(rw-26)*2/3+7:bar.right}var end=!mq(905),sv=document.querySelector('.bar .savedlink'),lg=document.querySelector('.bar .lang');if(!end){var a=sv.getBoundingClientRect(),c=lg.getBoundingClientRect();R=Math.min(R,bar.right-(c.right-a.left)-28)}R=Math.min(R,bar.right);if(R-L<140)return;h.classList.add('hasdd');if(end)h.classList.add('ddend');d.dataset.l=L;d.style.width=(R-L)+'px';function al(){d.style.marginLeft='0px';for(var i=0;i<2;i++)d.style.marginLeft=(parseFloat(d.style.marginLeft)+L-d.getBoundingClientRect().left)+'px'}if(end){for(var k=0;k<2;k++){var gap=L-14-lg.getBoundingClientRect().right;s.style.width=Math.max(160,s.getBoundingClientRect().width+gap)+'px';d.style.marginLeft='14px'}}al();var ov=bn.scrollWidth-bn.clientWidth;if(ov>0){d.style.width=(R-L-ov)+'px';al()}d.querySelector('.tdb').style.height=s.getBoundingClientRect().height+'px'}function ttCenter(){var h=document.documentElement,s=document.querySelector('.bar .search');if(!s||!h.classList.contains('hass'))return;var d=document.querySelector('.bar .tdd'),dd=h.classList.contains('hasdd'),end=h.classList.contains('ddend'),sv=document.querySelector('.bar .savedlink'),br=document.querySelector('.bar .brand');for(var i=0;i<3;i++){if(!dd&&i==0)s.style.width='120px';var bl=br.getBoundingClientRect().right,lg=document.querySelector('.bar .lang').getBoundingClientRect(),lc=document.querySelector('.read .lcol'),wide=dd&&!end,rn=end?(+d.dataset.l)-14-(lg.right-sv.getBoundingClientRect().left):wide?(lc?lc.getBoundingClientRect().right:(+d.dataset.l)-13):sv.getBoundingClientRect().left,G=Math.max(10,Math.min(24,(rn-bl-160)/2)),off=Math.min(10,G-6),w=Math.max(160,wide?rn-bl-G-off:rn-bl-2*G);s.style.width=w+'px';s.style.setProperty('--k',Math.min(1,w/520).toFixed(3));s.style.marginLeft=(parseFloat(getComputedStyle(s).marginLeft)+bl+G+off-s.getBoundingClientRect().left)+'px';if(end)sv.style.marginLeft=(parseFloat(getComputedStyle(sv).marginLeft)+s.getBoundingClientRect().right+G-off-sv.getBoundingClientRect().left)+'px';if(dd)d.style.marginLeft=(parseFloat(getComputedStyle(d).marginLeft)+(+d.dataset.l)-d.getBoundingClientRect().left)+'px'}var lgb=document.querySelector('.bar .lang');lgb.style.height=s.getBoundingClientRect().height+'px';if(d){var sb=s.querySelector('button');d.style.setProperty('--bw',sb.getBoundingClientRect().width+'px');d.querySelector('.tdb').style.height=s.getBoundingClientRect().height+'px'}}addEventListener('resize',function(){ttSearch();ttDD();ttCenter()});document.addEventListener('DOMContentLoaded',function(){var d=document.querySelector('.bar .tdd');if(!d)return;var b=d.querySelector('.tdb'),l=d.querySelector('.tdl');function set(o){l.hidden=!o;b.setAttribute('aria-expanded',o)}b.addEventListener('click',function(e){e.stopPropagation();set(l.hidden)});document.addEventListener('click',function(e){if(!d.contains(e.target))set(false)});document.addEventListener('keydown',function(e){if(e.key=='Escape')set(false)})});document.addEventListener('DOMContentLoaded',function(){ttSearch();ttDD();ttCenter();if(window.ResizeObserver){var rq=0,lw=0;new ResizeObserver(function(e){var w=e[0].contentRect.width;if(Math.abs(w-lw)<0.5)return;lw=w;cancelAnimationFrame(rq);rq=requestAnimationFrame(function(){ttSearch();ttDD();ttCenter()})}).observe(document.querySelector('.bar'))}if(document.fonts)document.fonts.ready.then(function(){ttSearch();ttDD();ttCenter()})});addEventListener('load',function(){ttSearch();ttDD();ttCenter()});addEventListener('resize',ttAgo);(function(){var tip=document.createElement('div');tip.className='agotip';document.addEventListener('mouseover',function(ev){var t=ev.target.closest&&ev.target.closest('time.ago');if(!t||!t.dataset.d){tip.remove();return}tip.textContent=t.dataset.d;document.body.appendChild(tip);var r=t.getBoundingClientRect();tip.style.left=Math.max(4,Math.min(innerWidth-tip.offsetWidth-4,r.left+r.width/2-tip.offsetWidth/2))+'px';tip.style.top=(r.bottom+6)+'px'});addEventListener('scroll',function(){tip.remove()},{passive:true})})();(function(){function fit(){var t=document.querySelector('.prose .toc'),b=document.querySelector('.beside');if(t&&b&&getComputedStyle(t).float!='none'){var n;while(b.offsetHeight<t.offsetHeight-8&&(n=b.nextElementSibling)&&!n.classList.contains('pblock')&&!(n.tagName=='H2'&&n.nextElementSibling&&n.nextElementSibling.classList.contains('pblock'))){b.appendChild(n);if(n.tagName=='H2'&&(n=b.nextElementSibling)&&!n.classList.contains('pblock'))b.appendChild(n)}}document.querySelectorAll('.pblock').forEach(function(k){var x=k.querySelector('.ptxt'),f=k.querySelector('.pimg'),W=k.offsetWidth,mx=W*(!mq(601)?.36:.45),w;for(var i=0;i<6;i++){w=Math.min(mx,x.offsetHeight*.75);f.style.width=w+'px'}f.style.height=Math.max(x.offsetHeight-5,w*4/3)+'px';f.querySelector('img').style.aspectRatio='auto'})}addEventListener('load',fit);addEventListener('resize',fit);var d=document.documentElement,o=document.querySelector('.scrim');
function t(x){var was=d.classList.contains('dopen'),B=document.body;var H=document.querySelector('header.top');if(x&&!was){var y=scrollY;B.dataset.y=y;B.style.top=-y+'px';if(H)H.style.transform='translateY('+y+'px)'}if(!x&&H)H.style.transform='';d.classList.toggle('dopen',x);if(!x&&was){var y2=+B.dataset.y||0;B.style.top='';scrollTo({top:y2,behavior:'instant'})}document.querySelectorAll('.burger').forEach(function(b){b.setAttribute('aria-expanded',x)})}
document.querySelectorAll('.burger').forEach(function(b){b.onclick=function(){t(!d.classList.contains('dopen'))}});
o.onclick=function(){t(false)};(function(){var dr=document.querySelector('.drawer'),x0=null,y0=0;if(!dr)return;
dr.addEventListener('touchstart',function(e){x0=e.touches[0].clientX;y0=e.touches[0].clientY},{passive:true});
dr.addEventListener('touchend',function(e){if(x0===null)return;var dx=e.changedTouches[0].clientX-x0,dy=e.changedTouches[0].clientY-y0;x0=null;
if(dx<-60&&Math.abs(dx)>Math.abs(dy)*1.5)t(false)},{passive:true})})();document.querySelectorAll('.dclose').forEach(function(b){b.onclick=function(){t(false)}});
document.querySelectorAll('.drawer a[href$="/category/models/"]').forEach(function(a){a.addEventListener('click',function(){var m=document.querySelector('.drawer .dmodels');if(m)m.classList.add('show');a.classList.add('on');try{sessionStorage.setItem('tt_dm','1')}catch(_){}})});
(function(){var k=null;try{k=sessionStorage.getItem('tt_dm');sessionStorage.removeItem('tt_dm')}catch(_){}
if(k&&window.matchMedia('(max-width:860px)').matches){d.classList.add('dnoanim');t(true);
requestAnimationFrame(function(){requestAnimationFrame(function(){d.classList.remove('dnoanim')})})}})();
function isWideFind(){return matchMedia('(min-width:769px)').matches}function placeSearch(){var form=document.querySelector('form.hb-search'),slot=document.querySelector('header.hb .hb-inline'),panel=document.querySelector('#site-search>.wrap');if(!form||!slot||!panel)return;if(isWideFind()){if(form.parentNode!==slot)slot.appendChild(form);var p=document.getElementById('site-search');if(p)p.inert=true;d.classList.remove('find-open','find-ready');var btn=document.querySelector('header.hb .sbtn');if(btn)btn.setAttribute('aria-expanded','false')}else if(form.parentNode!==panel){panel.appendChild(form);var p2=document.getElementById('site-search');if(p2&&!d.classList.contains('find-open'))p2.inert=true}}placeSearch();addEventListener('resize',placeSearch);function setFind(open,opts){opts=opts||{};if(isWideFind()){if(open&&opts.focus!==false){var input=document.querySelector('form.hb-search input');if(input)input.focus({preventScroll:true})}return;}var panel=document.getElementById('site-search'),btn=document.querySelector('header.hb .sbtn');if(!panel||!btn)return;d.classList.toggle('find-open',open);btn.setAttribute('aria-expanded',open?'true':'false');if(open){panel.inert=false;if(opts.focus!==false){var input=panel.querySelector('input');if(input)input.focus({preventScroll:true})}var show=function(ev){if(ev&&ev.target!==panel)return;d.classList.add('find-ready')};panel.addEventListener('transitionend',show,{once:true});setTimeout(function(){d.classList.add('find-ready')},280)}else{d.classList.remove('find-ready');if(r)r.hidden=true;panel.inert=true;if(opts.restore)btn.focus({preventScroll:true})}}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){t(false);d.classList.remove('sopen');if(r)r.hidden=true;if(d.classList.contains('find-open'))setFind(false,{restore:true})}});
var f=document.querySelector('.search'),i=f.querySelector('input'),r=f.querySelector('.res'),idx=null;
function e(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function rubric(a){var when=' · <time class="ago" datetime="'+a.ts+'">'+e(a.dt)+'</time>';return a.s?'<span class="lmeta"><span class="lpath"><span class="llayer">'+e(a.k||'')+'</span> / <span class="lsub">'+e(a.s)+'</span></span>'+when+'</span>':'<span class="lmeta"><span class="lname">'+e(a.k||'')+'</span>'+when+'</span>'}
function still(a,tag,cls,w,h){var img='<img src="'+e(a.i||'')+'" alt="'+e(a.t)+'" width="'+w+'" height="'+h+'" decoding="async">';var mark=(a.sp||a.sb)?'<span class="dur dvo">Short</span><span class="vpl" aria-hidden="true"></span>':'';return '<'+tag+' class="'+cls+(a.sp?' fitin':'')+'"'+(a.sp?' style="--poster:url('+e(a.i)+')"':'')+'>'+img+mark+'</'+tag+'>'}
function load(){return idx?Promise.resolve(idx):fetch(f.dataset.idx).then(function(x){return x.json()}).then(function(j){idx=j;return j})}
i.addEventListener('focus',load);
i.addEventListener('input',function(){var q=i.value.trim().toLowerCase();if(q.length<2){r.hidden=true;return}
load().then(function(){var w=q.split(/\s+/),h=idx.filter(function(a){var s=(a.t+' '+a.d+' '+a.c).toLowerCase();return w.every(function(x){return s.indexOf(x)>-1})}).slice(0,8);
r.innerHTML=h.length?h.map(function(a){return '<a href="'+a.u+'">'+still(a,'span','zimg',112,63)+'<span>'+rubric(a)+'<b>'+e(a.t)+'</b></span></a>'}).join(''):'<p>'+e(f.dataset.none)+'</p>';r.hidden=false});});
f.addEventListener('submit',function(x){x.preventDefault();var a=r.querySelector('a');if(a)location.href=a.href});
document.addEventListener('click',function(x){if(!f.contains(x.target)&&!x.target.closest('.sbtn')){r.hidden=true;d.classList.remove('sopen');if(d.classList.contains('find-open'))setFind(false)}});
document.querySelector('.sbtn').addEventListener('click',function(ev){ev.stopPropagation();var open=!d.classList.contains('find-open');setFind(open,{restore:!open})});
try{var qs=new URLSearchParams(location.search).get('q');if(qs&&qs.trim()){i.value=qs;setFind(true,{focus:true});i.dispatchEvent(new Event('input'))}}catch(err){}
function fill(){[].slice.call(document.querySelectorAll('.grid2>.card')).forEach(function(c){var h=c.querySelector('h3'),p=c.querySelector('p');if(!h||!p)return;p.style.webkitLineClamp='';var n=Math.round(h.getBoundingClientRect().height/parseFloat(getComputedStyle(h).lineHeight));if(getComputedStyle(c).gridTemplateColumns.split(' ').length>1)p.style.webkitLineClamp=1})}
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
function paintSave(){document.querySelectorAll('[data-save]').forEach(function(b){var on=LS.get('tt_saved').indexOf(b.dataset.save)>-1;b.setAttribute('aria-pressed',on);b.title=SAVE[on?1:0];b.setAttribute('aria-label',SAVE[on?1:0])})}
paintSave();
document.addEventListener('click',function(ev){var b=ev.target.closest&&ev.target.closest('[data-save]');if(!b)return;ev.preventDefault();var s=b.dataset.save,l=LS.get('tt_saved'),i=l.indexOf(s);if(i>-1)l.splice(i,1);else l.unshift(s);LS.set('tt_saved',l);paintSave();badge()});
function paintLike(){var lb=[].slice.call(document.querySelectorAll('[data-like]'));if(!lb.length)return;var liked=LS.get('tt_liked');lb.forEach(function(b){b.setAttribute('aria-pressed',liked.indexOf(b.dataset.like)>-1)});fetch('/api/likes?s='+lb.map(function(b){return b.dataset.like}).join(',')).then(function(r){return r.json()}).then(function(j){lb.forEach(function(b){var n=j[b.dataset.like]||0;var sp=b.querySelector('span');if(sp)sp.textContent=n})}).catch(function(){})}
paintLike();
document.addEventListener('click',function(ev){var b=ev.target.closest&&ev.target.closest('[data-like]');if(!b)return;ev.preventDefault();var s=b.dataset.like,liked=LS.get('tt_liked'),i=liked.indexOf(s),d=i>-1?-1:1;if(d>0)liked.push(s);else liked.splice(i,1);LS.set('tt_liked',liked);b.setAttribute('aria-pressed',d>0);var sp=b.querySelector('span');sp.textContent=Math.max(0,(+sp.textContent||0)+d);fetch('/api/likes',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({slug:s,d:d})}).then(function(r){return r.json()}).then(function(j){if(j.n!=null)sp.textContent=j.n}).catch(function(){})});
var sl=document.querySelector('.savedlist');if(sl){var keep=LS.get('tt_saved');if(!keep.length){sl.innerHTML='<p class="empty">'+e(sl.dataset.empty)+'</p>'}else{load().then(function(){var m={};idx.forEach(function(a){var k=a.u.replace(/\/$/,'').split('/').pop();m[k]=a});
sl.innerHTML=keep.filter(function(k){return m[k]}).map(function(k){var a=m[k];return '<div class="card"><a class="lgo" href="'+a.u+'">'+still(a,'div','im zimg',1200,630)+'</a><div class="body"><div class="lrow"><a class="lgo" href="'+a.u+'">'+rubric(a)+'</a></div><a class="lgo" href="'+a.u+'"><h3>'+e(a.t)+'</h3></a></div></div>'}).join('');paintSave();paintLike();ttAgo()})}}window.addEventListener('resize',bal);bal();
})();"""
JS += r"""
document.querySelectorAll(".avb[data-vid]").forEach(function(b){b.addEventListener("click",function(){if(b.classList.contains("on"))return;b.classList.add("on");var f=document.createElement("iframe");f.src="https://www.youtube-nocookie.com/embed/"+b.dataset.vid+"?autoplay=1"+(matchMedia("(pointer:coarse)").matches?"":"&playsinline=1")+"&rel=0";f.title=b.getAttribute("aria-label")||"YouTube";f.setAttribute("allow","autoplay; encrypted-media; picture-in-picture; fullscreen");f.allowFullscreen=true;b.appendChild(f)})});
(function(){var box=document.getElementById("consent");if(!box)return;var KEY="tt-consent";function get(){try{return localStorage.getItem(KEY)}catch(e){return null}}function loadAnalytics(){if(!box.dataset.beacon||document.querySelector('script[src*="cloudflareinsights"]'))return;var s=document.createElement("script");s.defer=true;s.async=true;s.src="https://static.cloudflareinsights.com/beacon.min.js";s.setAttribute("fetchpriority","low");s.setAttribute("data-cf-beacon",JSON.stringify({token:box.dataset.beacon}));document.body.appendChild(s)}function apply(v,store){if(store){try{localStorage.setItem(KEY,v)}catch(e){}}box.hidden=true}loadAnalytics();var cur=get();if(cur==="all"||cur==="necessary")apply(cur,false);else box.hidden=false;box.addEventListener("click",function(e){var t=e.target.closest&&e.target.closest("[data-consent]");if(!t)return;apply(t.getAttribute("data-consent"),true)});document.addEventListener("click",function(e){var t=e.target.closest&&e.target.closest("[data-consent-open]");if(!t)return;e.preventDefault();box.hidden=false})})();
"""


JS += r"""
(function(){function shut(except){document.querySelectorAll("header.hb .pdrop.is-open").forEach(function(drop){if(drop===except)return;drop.classList.remove("is-open");var a=drop.querySelector("a.pn");if(a)a.setAttribute("aria-expanded","false")})}document.querySelectorAll("header.hb .pdrop").forEach(function(drop){var link=drop.querySelector("a.pn");if(!link)return;link.addEventListener("click",function(e){if(!matchMedia("(pointer:coarse)").matches)return;if(!drop.classList.contains("is-open")){e.preventDefault();shut(drop);drop.classList.add("is-open");link.setAttribute("aria-expanded","true")}})});document.addEventListener("click",function(e){if(!e.target.closest||!e.target.closest("header.hb .pdrop"))shut(null)});document.addEventListener("keydown",function(e){if(e.key==="Escape")shut(null)})})();
"""

TOPIC_LABEL = {
    "cars": {"en": "Cars", "nl": "Auto's", "href": "cars/"},
    "semi": {"en": "Semi", "nl": "Semi", "href": "semi/"},
    "robotaxi": {"en": "Robotaxi", "nl": "Robotaxi", "href": "robotaxi/"},
    "fsd": {"en": "FSD", "nl": "FSD", "href": "fsd/"},
    "optimus": {"en": "Optimus", "nl": "Optimus", "href": "optimus/"},
    "megapack": {"en": "Megapack", "nl": "Megapack", "href": "megapacks/"},
    "charging": {"en": "Charging", "nl": "Laden", "href": "charging-network/"},
    "charging-network": {"en": "Charging", "nl": "Laden", "href": "charging-network/"},
    "home-charging": {"en": "Home charging", "nl": "Thuisladen", "href": "home-charging/"},
    "solar": {"en": "Solar", "nl": "Zon", "href": "solar/"},
    "powerwall": {"en": "Powerwall", "nl": "Powerwall", "href": "tesla-energy/"},
    "energy": {"en": "Energy", "nl": "Energie", "href": "tesla-energy/"},
    "starship": {"en": "Starship", "nl": "Starship", "href": "starship-vehicle/"},
    "falcon": {"en": "Falcon", "nl": "Falcon", "href": "falcons/"},
    "spacex": {"en": "SpaceX", "nl": "SpaceX", "href": "spacex/"},
    "starlink": {"en": "Starlink", "nl": "Starlink", "href": "satellite-network/"},
    "ai": {"en": "AI", "nl": "AI", "href": "ai/"},
    "ai-compute": {"en": "Compute", "nl": "Rekenkracht", "href": "ai-compute/"},
    "datacenters": {"en": "Datacenters", "nl": "Datacenters", "href": "datacenters/"},
    "chips": {"en": "Chips", "nl": "Chips", "href": "chips/"},
    "spacexsi": {"en": "SpaceXSI", "nl": "SpaceXSI", "href": "spacexsi/"},
    "neuralink": {"en": "Neuralink", "nl": "Neuralink", "href": "brain-interfaces/"},
    "boring": {"en": "Boring", "nl": "Boring", "href": "car-tunnels/"},
    "agi": {"en": "AGI", "nl": "AGI", "href": "agi/"},
    "ecosystem": {"en": "Ecosystem", "nl": "Ecosysteem", "href": "ecosystem/"},
}


def topic_meta(a, lang):
    """Visible section name and the hub it links to. Never a redirected category URL."""
    info = TOPIC_LABEL.get(a.get("topic") or "")
    if info:
        href = ecosystem_path(lang) if a.get("topic") == "ecosystem" else info["href"]
        return info[lang], href
    cat_key = a["category"]
    cat = CATEGORIES[cat_key]
    name = cat.get("tag", cat[lang])
    if cat_key in REDIRECT_CATS:
        return name, REDIRECT_CATS[cat_key]
    return name, "category/" + cat_key + "/"


def card_title(a, lang):
    """Short title for cards and lists. The article page keeps the full headline."""
    card = a.get("card") or {}
    text = card.get(lang) if isinstance(card, dict) else ""
    return text or a[lang]["title"]


def label(a, lang):
    name, _href = topic_meta(a, lang)
    return f'<span class="tag">{esc(name)}</span>'


def card(a, lang, lead=False):
    t = a[lang]
    cls = "card lead" if lead else "card"
    line = rubric_line(a, lang)
    src, portrait = short_visual(a)
    if not src:
        src = site_img(a)
    im = still_box("div", "im zimg", src, t["title"], SIZES_CARD, portrait=portrait, mark=card_mark(a, lang))
    title = f'<h3>{esc(card_title(a, lang))}</h3>'
    # The rubric sits under the photo, then the title. The lead photo is not a link.
    href = url(lang, a["slug"] + "/")
    row = with_actions(line, "", lang, href)
    if lead:
        return (f'<div class="{cls}">{im}'
                f'<div class="body">{row}<a class="lgo" href="{href}">{title}</a></div></div>')
    return (f'<div class="{cls}"><a class="lgo" href="{href}">{im}</a>'
            f'<div class="body">{row}<a class="lgo" href="{href}">{title}</a></div></div>')


def gcard(a, lang, eager=False):
    """Topic list under the lead: photo on top, then title, summary and date."""
    t = a[lang]
    href = url(lang, a["slug"] + "/")
    src, portrait = short_visual(a)
    if not src:
        src = site_img(a)
    photo = still_box("div", "im zimg", src, t["title"], SIZES_GRID, portrait=portrait, high=eager, lazy=not eager, mark=card_mark(a, lang))
    return (f'<div class="card"><a class="lgo" href="{href}">'
            f'{photo}</a>'
            f'<div class="body">{with_actions(rubric_line(a, lang), "", lang, href)}'
            f'<a class="lgo" href="{href}"><h2>{esc(card_title(a, lang))}</h2></a></div></div>')


def split2(t):
    """Split a label text into a shorter top line and a main bottom line."""
    w = t.split()
    if len(w) < 2:
        return "", t
    for i in range(1, len(w)):
        if w[i - 1].endswith((":", "?", "!", ",")) and i < len(w):
            return " ".join(w[:i]), " ".join(w[i:])
    weak = {"PER", "IN", "OF", "DE", "HET", "EEN", "TO", "THE", "A", "AN", "FOR", "AND", "EN", "VAN", "OP", "BIJ", "MET",
            "VOOR", "ON", "AT", "BY", "WITH", "NAAR", "UIT", "OM", "TE", "IS", "ZIJN", "ARE", "NIET", "NOT", "NO", "GEEN"}
    best = min(range(1, len(w)), key=lambda i: max(len(" ".join(w[:i])) * .7, len(" ".join(w[i:])))
               + (8 if w[i - 1].upper() in weak else 0) + (6 if len(" ".join(w[i:])) < 6 else 0))
    return " ".join(w[:best]), " ".join(w[best:])


NUMRE = re.compile(r"^([+\-−]?[€$]?\d[\d.,]*(?:[-–]\d[\d.,]*)?%?(?:\s?(?:MLD|MLN|MLJ|MRD|BN|B|M|K|GW|GWH|MW|MWH|KWH|TWH|X|JAAR|YEARS?|DAGEN|DAYS|MPH|KM/H|KM|MILES|MIJL)\b)?)(.*)$")


def numbig(t):
    """Show a leading number or amount, with its unit, bigger than the rest of the line."""
    m = NUMRE.match(t)
    if not m or not m.group(2).strip():
        return esc(t)
    tok = m.group(1)
    if sum(ch.isdigit() for ch in tok) < 2 and not re.search(r"[€$%+\-–−]|[A-Z]", tok):
        return esc(t)
    return f'<span class="nb">{esc(m.group(1))}</span>{esc(m.group(2))}'


def is_live(a):
    return (a or {}).get("type") == "live" and bool((a or {}).get("live"))


def live_updates(a):
    rows = [row for row in ((a or {}).get("updates") or []) if isinstance(row, dict)]
    rows.sort(key=lambda row: str(row.get("at") or ""), reverse=True)
    return rows


def live_mark(a):
    if not is_live(a):
        return ""
    return '<span class="livebadge">LIVE</span>'


def live_feed(a, lang):
    rows = []
    for update in live_updates(a):
        text = str(update.get(lang) or "").strip()
        if not text:
            continue
        raw = str(update.get("at") or "")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
            label = fmt_date(dt.strftime("%Y-%m-%d"), lang) + ", " + dt.strftime("%H:%M")
        except ValueError:
            label = raw
        rows.append(
            f'<li><time datetime="{esc(raw)}">{esc(label)}</time><p>{esc(text)}</p>'
            f'{_src_links(update.get("sources") or [])}</li>')
    if not rows:
        return ""
    return f'<ol class="livefeed">{"".join(rows)}</ol>'


def ovl(a, lang):
    """Two-line label on the photo, bottom-left. Types: a (red block + yellow), c (yellow + red block),
    n (big number + red block), r (one red block)."""
    lb = a.get("label")
    if not lb or not lb.get(lang, {}).get("text"):
        return ""
    st, t = lb.get("style", "a"), lb[lang]
    st = {"k": "a", "y": "a", "tag": "a", "w": "c", "s": "c"}.get(st, st)
    txt, sub = t["text"], t.get("sub", "")
    if st == "n":
        lines = [("yo", esc(txt)), ("bk", esc(sub))]
    elif st == "r":
        lines = [("bk", numbig(txt))]
    else:
        if not sub:
            sub, txt = split2(txt)
        lines = [("bk", numbig(sub)), ("yo", numbig(txt))] if st == "a" else [("yo", numbig(sub)), ("bk", numbig(txt))]
    inner = "".join(f'<b class="l{i + 1} {c}"><i>{x}</i></b>' for i, (c, x) in enumerate(lines) if x)
    pal = PALETTE.get(a.get("slug"), "yr")
    return f'<div class="kk t-{st} p-{pal or "yr"}" aria-hidden="true">{inner}</div>'

def dur(a, lang):
    if VIDEOS.get((a["slug"], lang)):  # an article with a video shows only the video length
        return f'<span class="dur dvo">{vdur(a, lang)}</span><span class="vpl" aria-hidden="true"></span>'
    secs = max(10, round(len(html.unescape(re.sub(r"<[^>]+>", " ", a[lang]["body"])).split()) / 220 * 60))
    lbl = {"en": "Reading time", "nl": "Leestijd"}[lang]
    return (f'<span class="dur" title="{lbl}" aria-label="{lbl}: {-(-secs // 60)} min">'
            f'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<path d="M2 4h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7z"/></svg>'
            f'{-(-secs // 60)} min{vdur(a, lang)}</span>'
            + ('<span class="vpl" aria-hidden="true"></span>' if VIDEOS.get((a["slug"], lang)) else ''))


def vdur(a, lang):
    """Extra '▶ 4:15' in the duration badge when the article has a long video."""
    v = VIDEOS.get((a["slug"], lang))
    if not v:
        return ""
    sec = int(v.get("seconds") or 0)
    t = f"{sec // 60}:{sec % 60:02d}" if sec else "video"  # exact length like YouTube, e.g. 4:15
    lbl = {"en": "Video", "nl": "Video"}[lang]
    return (f'<i class="dv" title="{lbl}" aria-label="{lbl}: {t}">'
            f'<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path d="M7 4.5v15l12.5-7.5z" fill="currentColor"/></svg>{t}</i>')


def vhero(a, lang):
    """Attributes that turn the article photo into a click-to-play YouTube player."""
    v = VIDEOS.get((a["slug"], lang))
    if not v:
        return ""
    play = "Play the video" if lang == "en" else "Speel de video af"
    return f' data-vid="{esc(v["id"])}" role="button" tabindex="0" aria-label="{play}"'


def vscript(a, lang):
    if not VIDEOS.get((a["slug"], lang)):
        return ""
    return ("<script>(function(){[].forEach.call(document.querySelectorAll('.hi[data-vid]:not([data-on])'),function(h){h.setAttribute('data-on','');function go(){if(h.classList.contains('on'))return;"
            "h.classList.add('on');h.innerHTML='<iframe src=\"https://www.youtube-nocookie.com/embed/'+h.dataset.vid+'?autoplay=1'+(matchMedia('(pointer:coarse)').matches?'':'&playsinline=1')+'&rel=0\" title=\"YouTube\" "
            "allow=\"autoplay; encrypted-media; picture-in-picture; fullscreen\" allowfullscreen></iframe>'}"
            "h.addEventListener('click',go);h.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}})})})()</script>")


def mini(a, lang):
    t = a[lang]
    src, portrait = short_visual(a)
    if not src:
        src = site_img(a)
    return (f'<a class="mini" href="{url(lang, a["slug"] + "/")}">'
            f'{still_box("div", "th zimg", src, t["title"], SIZES_CARD, portrait=portrait, mark=card_mark(a, lang))}'
            f'<div>{rubric_line(a, lang)}<h3>{esc(card_title(a, lang))}</h3></div></a>')


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
        inner = f'<img src="{ph}" alt="Tesla {m["name"]}" width="480" height="320" loading="lazy" decoding="async">' if ph else f'<b>{m["name"].replace("Model ", "")}</b>'
        tiles += f'<a class="model" href="{url(lang, "model/" + k + "/")}"><div class="ph">{inner}</div><span>{m["name"]}</span></a>'
    return f'<div class="models">{tiles}</div>'


def why(lang):
    return '<div class="why">' + "".join(
        f"<div><i>{i}</i><b>{h}</b><p>{p}</p></div>" for i, (h, p) in enumerate(LANGS[lang]["why"], 1)) + "</div>"


def load_filing():
    path = ROOT / "content" / "filing.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


FILING = load_filing()


def load_articles():
    arts = []
    for f in sorted(CONTENT.glob("*.json")):
        a = json.loads(f.read_text(encoding="utf-8"))
        for key in ("slug", "date", "category", "en", "nl"):
            if key not in a:
                raise SystemExit(f"{f.name}: missing '{key}'")
        if a["category"] not in CATEGORIES:
            raise SystemExit(f"{f.name}: unknown category '{a['category']}'")
        if a.get("type") == "live":
            updates = a.get("updates")
            if not isinstance(updates, list) or not updates:
                raise SystemExit(f"{f.name}: a live article needs an updates list")
            for update in updates:
                if not isinstance(update, dict) or not str(update.get("at") or "").strip():
                    raise SystemExit(f"{f.name}: each update needs at")
                if not str(update.get("en") or "").strip() or not str(update.get("nl") or "").strip():
                    raise SystemExit(f"{f.name}: each update needs en and nl")
                sources = update.get("sources") or []
                if not isinstance(sources, list) or len(sources) < 2:
                    raise SystemExit(f"{f.name}: each update needs two sources")
        extra = []
        for key in a.get("also_topics") or []:
            if key not in TOPIC_LABEL:
                raise SystemExit(f"{f.name}: unknown also_topics '{key}'")
            if key not in extra:
                extra.append(key)
        filed = FILING.get(a["slug"])
        if filed:
            a["layer"] = filed["layer"]
            a["topic"] = filed["topic"]
            if filed.get("card"):
                a["card"] = filed["card"]
        # Extra topics add the article to those hubs. The primary topic stays the breadcrumb.
        a["also_topics"] = [t for t in extra if t != a.get("topic")]
        for m in a.get("models", []):
            if m not in MODELS:
                raise SystemExit(f"{f.name}: unknown model '{m}' (use a key from MODELS)")
        arts.append(a)
    vf = ROOT / "content" / "videos.json"
    VIDEOS.clear()
    for v in (json.loads(vf.read_text(encoding="utf-8")) if vf.exists() else []):
        if v.get("slug") and (v["slug"], v.get("lang", "en")) not in VIDEOS:
            VIDEOS[(v["slug"], v.get("lang", "en"))] = v
    # `updated` is taken only from the article JSON. Attaching a YouTube video, or rebuilding
    # the site, must not change dateModified or the article's sitemap lastmod.
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


def related(a, arts, n=4):
    """Up to n other articles that share a category or a model (including the model family)."""
    fam = lambda x: {MODELS[k].get("parent") or k for k in x.get("models", [])}
    ms, mf, ta = set(a.get("models", [])), fam(a), _terms(a)
    cats = {a["category"]} | set(a.get("also", []))

    def shares(x):
        xc = {x["category"]} | set(x.get("also", []))
        return bool(cats & xc or ms & set(x.get("models", [])) or mf & fam(x))

    def score(x):
        sc = 4 * len(ms & set(x.get("models", []))) + 2 * len(mf & fam(x))
        sc += 3 * (x["category"] == a["category"] or a["category"] in x.get("also", []) or x["category"] in a.get("also", []))
        sc += min(len(ta & _terms(x)), 5)
        return (sc, published(x))

    pool = [x for x in arts if x is not a and shares(x)]
    return sorted(pool, key=score, reverse=True)[:n]


def related_block(a, arts, lang):
    """'Read next' / 'Lees ook' under an article. Up to four items; hidden when none qualify."""
    items = related(a, arts, 4)
    if not items:
        return ""
    title = LANGS[lang]["related"]
    return (f'<section class="nextread" aria-label="{esc(title)}"><h2>{esc(title)}</h2><div class="grid2">'
            + "".join(card(x, lang) for x in items) + "</div></section>")


MONEY = {}
SHORTS = {}
SHORT_ROWS = []  # every Short, including ones that are not attached to an article yet
PRIMARY_CATS = {"models", "fsd", "robotaxi", "optimus", "spacex", "starlink", "xai", "boring"}
# Category indexes that repeat a layer or sub-hub. The worker and public/_redirects send them on.
REDIRECT_CATS = {
    "charging": "charging-network/",
    "energy": "tesla-energy/",
    "fsd": "fsd/",
    "robotaxi": "robotaxi/",
    "optimus": "optimus/",
    "spacex": "spacex/",
    "starlink": "starlink/",
    "boring": "boring/",
    "xai": "spacexsi/",
}
AD_HEIGHT = {"after_intro": 280, "mid_article": 280, "end": 280, "sidebar": 600}
# Slots stay out of the HTML until this is true, so the layout does not reserve empty space.
# TT_ADS=1 is a local override for a placement screenshot. Do not set it in production.
ADS_ENABLED = False
if os.environ.get("TT_ADS") == "1":
    ADS_ENABLED = True
# content/guides/_*.md and the same pattern elsewhere stay out of the build.
INCLUDE_EXAMPLES = os.environ.get("TT_EXAMPLES") == "1"


def load_money():
    """Ads, Amazon tags and the newsletter endpoint. Empty values render nothing."""
    global MONEY
    MONEY = {}
    path = ROOT / "content" / "monetization.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return
    if isinstance(data, dict):
        MONEY = data


def load_shorts():
    SHORTS.clear()
    SHORT_ROWS.clear()
    path = ROOT / "content" / "shorts.json"
    if not path.exists():
        return
    for sh in json.loads(path.read_text(encoding="utf-8")):
        slug, vid = sh.get("slug"), sh.get("id")
        if not vid:
            continue
        SHORT_ROWS.append(sh)
        if slug and slug not in SHORTS:
            SHORTS[slug] = sh


def _ads():
    block = MONEY.get("adsense")
    return block if isinstance(block, dict) else {}


def publisher_client():
    raw = str(_ads().get("publisher_id") or "").strip()
    if raw.startswith("pub-"):
        raw = "ca-" + raw
    return raw if re.fullmatch(r"ca-pub-\d+", raw) else ""


def adsense_tag():
    """AdSense loader. It starts on the first tap or key, or eight seconds after load.

    That keeps the ~230 KB script off the LCP path. It is not gated on the site cookie
    banner: in the EEA, Google's Privacy & messaging message comes from this same script,
    so a quiet visitor still gets it. Slot pushes made earlier stay queued on
    window.adsbygoogle.
    """
    client = publisher_client()
    if not client:
        return ""
    return (
        "<script>(function(){var id=" + json.dumps(client) + ",done=false;"
        "function load(){if(done)return;done=true;var s=document.createElement('script');"
        "s.async=true;s.crossOrigin='anonymous';"
        "s.src='https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='+encodeURIComponent(id);"
        "document.head.appendChild(s)}"
        "['pointerdown','keydown','touchstart'].forEach(function(ev){addEventListener(ev,load,{capture:true,once:true,passive:true})});"
        "addEventListener('load',function(){setTimeout(function(){"
        "if(window.requestIdleCallback)requestIdleCallback(load,{timeout:2000});else load();"
        "},8000)});"
        "})()</script>\n"
    )


def slot_id(place):
    slots = _ads().get("slots") if isinstance(_ads().get("slots"), dict) else {}
    raw = str(slots.get(place) or "").strip()
    return raw if re.fullmatch(r"\d{6,20}", raw) else ""


def ad_html(place, lang):
    """Reserved ad slot. Nothing at all while ADS_ENABLED is false, so there is no empty gap."""
    if not ADS_ENABLED:
        return ""
    client, slot = publisher_client(), slot_id(place)
    height = AD_HEIGHT.get(place, 280)
    label = LANGS[lang]["ad"]
    if client and slot:
        unit = (f'<ins class="adsbygoogle" style="display:block;min-height:{height}px" '
                f'data-ad-client="{esc(client)}" data-ad-slot="{esc(slot)}" '
                f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
                f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script>')
    else:
        unit = f'<div class="adhold" style="min-height:{height}px"></div>'
    return (f'<aside class="adslot ad-{place}" aria-label="{esc(label)}" style="min-height:{height + 28}px">'
            f'<span class="adlab">{esc(label)}</span>{unit}</aside>')


def insert_mid(body, snippet):
    """In-article slot after the third paragraph."""
    if not snippet:
        return body
    marks = list(re.finditer(r"</p>", body, flags=re.IGNORECASE))
    if len(marks) < 3:
        return body + snippet
    at = marks[2].end()
    return body[:at] + snippet + body[at:]


def _loc(val, lang):
    if isinstance(val, dict):
        return val.get(lang) or val.get("en") or ""
    return "" if val is None else val


def amazon_tag(lang):
    block = MONEY.get("amazon") if isinstance(MONEY.get("amazon"), dict) else {}
    raw = str(block.get(lang) or "").strip()
    return raw if re.fullmatch(r"[A-Za-z0-9\-]{2,40}", raw) else ""


def with_amazon_tag(href, lang):
    tag = amazon_tag(lang)
    if not tag or re.search(r"[?&]tag=", href):
        return href
    host = href.split("/")[2].lower() if href.startswith("https://") and href.count("/") >= 2 else ""
    if "amazon." not in host and not host.startswith("amzn."):
        return href
    sep = "&" if "?" in href else "?"
    return f"{href}{sep}tag={quote(tag, safe='')}"


def _query_set(href, key, value):
    if re.search(rf"[?&]{re.escape(key)}=", href):
        return href
    sep = "&" if "?" in href else "?"
    return f"{href}{sep}{key}={quote(str(value), safe='')}"


def ali_href(raw, lang="nl"):
    """An AliExpress tracking link, opened in the page language. Any other host is dropped."""
    href = str(raw or "").strip()
    if not href.startswith("https://") or href.count("/") < 2:
        return ""
    host = href.split("/")[2].lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in ("s.click.aliexpress.com", "aliexpress.com"):
        return ""
    # lang rides on the short link. The redirect keeps the affiliate parameters.
    return _query_set(href, "lang", "en" if lang == "en" else "nl")


def amazon_nl_href(product, lang="nl"):
    """An amazon.nl product URL with the Associates tag. Anything else is dropped."""
    if not isinstance(product, dict):
        return ""
    href = str(_loc(product.get("url"), "nl")).strip()
    asin = str(product.get("asin") or "").strip().upper()
    if re.fullmatch(r"[A-Z0-9]{10}", asin):
        href = f"https://www.amazon.nl/dp/{asin}"
    if not href.startswith("https://") or href.count("/") < 2:
        return ""
    host = href.split("/")[2].lower()
    if host not in ("www.amazon.nl", "amazon.nl"):
        return ""
    tagged = guide_amazon(href, lang)
    tag = affiliate_tag("nl")
    if not tag or f"tag={tag}" not in tagged:
        return ""
    return tagged


AMAZON_IMAGES = {}
AMAZON_GALLERIES = {}
PRODUCT_PRICES = {"rate": {}, "prices": {}}
_IMG_HIDE = ("var g=this.closest('.pgal');if(g){g.remove();}else{var n=this.closest('a.pshot,span.pshot');if(n)n.remove();}"
             "var c=this.closest('.pbox,.gbox,li');if(c)c.classList.add('noimg');")
_ARROW_PREV = ('<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">'
               '<path d="M8.6 2.4 4.2 7l4.4 4.6" fill="none" stroke="currentColor" stroke-width="1.6" '
               'stroke-linecap="round" stroke-linejoin="round"/></svg>')
_ARROW_NEXT = ('<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">'
               '<path d="M5.4 2.4 9.8 7 5.4 11.6" fill="none" stroke="currentColor" stroke-width="1.6" '
               'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _amazon_urls(value):
    rows = value if isinstance(value, list) else [value]
    out = []
    for item in rows:
        src = str(item or "").strip()
        if src.startswith("https://m.media-amazon.com/images/I/") and src not in out:
            out.append(src)
        if len(out) == 5:
            break
    return out


def load_amazon_images():
    """Hotlinked Amazon CDN URLs. A missing or rejected URL leaves the card as text."""
    global AMAZON_IMAGES, AMAZON_GALLERIES
    AMAZON_IMAGES = {}
    AMAZON_GALLERIES = {}
    path = ROOT / "content" / "amazon-images.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    images = data.get("images") if isinstance(data, dict) else None
    if not isinstance(images, dict):
        return
    for asin, value in images.items():
        key = str(asin or "").strip().upper()
        urls = _amazon_urls(value)
        if not re.fullmatch(r"[A-Z0-9]{10}", key) or not urls:
            continue
        AMAZON_GALLERIES[key] = urls
        AMAZON_IMAGES[key] = urls[0]


ALI_GALLERIES = {}


def load_ali_images():
    """Hotlinked AliExpress gallery photos. A missing list falls back to the promo pictures."""
    global ALI_GALLERIES
    ALI_GALLERIES = {}
    path = ROOT / "content" / "ali-images.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    images = data.get("images") if isinstance(data, dict) else None
    if not isinstance(images, dict):
        return
    for item, value in images.items():
        key = str(item or "").strip()
        if not key.isdigit():
            continue
        rows = value if isinstance(value, list) else [value]
        urls = []
        for raw in rows:
            src = str(raw or "").strip().split("?")[0]
            remote = src.startswith("https://ae-pic-a1.aliexpress-media.com/kf/") and src.endswith((".jpg", ".png"))
            local = src.startswith("/img/guides/") and src.endswith(".webp") and (STATIC / src.lstrip("/")).is_file()
            if (remote or local) and src not in urls:
                urls.append(src)
            if len(urls) == 6:
                break
        if urls:
            ALI_GALLERIES[key] = urls


def load_product_prices():
    """Dated euro prices and the ECB dollar rate. A stale row is ignored."""
    global PRODUCT_PRICES
    PRODUCT_PRICES = {"rate": {}, "prices": {}}
    path = ROOT / "content" / "product-prices.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(data, dict):
        PRODUCT_PRICES = data


def _product_asin(product):
    if isinstance(product, dict):
        asin = str(product.get("asin") or "").strip().upper()
        if re.fullmatch(r"[A-Z0-9]{10}", asin):
            return asin
        href = str(_loc(product.get("url"), "nl") or "")
    else:
        href = str(product or "")
    match = re.search(r"/dp/([A-Z0-9]{10})", href, re.I)
    return match.group(1).upper() if match else ""


def product_photo(product):
    """Amazon's own image, hotlinked. Anything else stays a text card."""
    asin = _product_asin(product)
    src = AMAZON_IMAGES.get(asin, "")
    if src.startswith("https://m.media-amazon.com/images/I/"):
        return src, True
    return "", False


LICENCE_PHOTOS = {}


def load_image_licences():
    """Exact-product photos whose licence file marks them as allowed. No caption is printed."""
    global LICENCE_PHOTOS
    LICENCE_PHOTOS = {}
    path = ROOT / "content" / "image-licences.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    rows = data.get("products") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict) or not row.get("photo"):
            continue
        asin = str(row.get("asin") or "").strip().upper()
        src = str(row.get("file") or "").strip()
        if not re.fullmatch(r"[A-Z0-9]{10}", asin) or not src.startswith("/img/"):
            continue
        if (STATIC / src.lstrip("/")).is_file():
            LICENCE_PHOTOS[asin] = src


def guide_local_image(fields):
    """A self-hosted product photo named on the card. No caption is printed."""
    local = str((fields or {}).get("image") or "").strip()
    if local.startswith("/img/") and (STATIC / local.lstrip("/")).is_file():
        return local
    return ""


def licensed_card_photo(href):
    asin = ""
    match = re.search(r"/dp/([A-Z0-9]{10})", str(href or ""), re.I)
    if match:
        asin = match.group(1).upper()
    return LICENCE_PHOTOS.get(asin, "")


def _parse_stamp(value):
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt


def _thumb_src(src):
    if src.startswith("https://m.media-amazon.com/images/I/"):
        return re.sub(r"\._[^./]+(?=\.jpg$)", "._AC_US100_", src)
    if src.startswith("https://ae-pic-a1.aliexpress-media.com/kf/"):
        return src
    return src


def price_html(key, lang):
    """Dated price. English leads with dollars. A fetched price lasts a day; a manual one lasts a week."""
    row = (PRODUCT_PRICES.get("prices") or {}).get(key) or {}
    if not isinstance(row, dict):
        return ""
    try:
        eur = float(row.get("eur"))
    except (TypeError, ValueError):
        return ""
    if not 1 <= eur <= 5000:
        return ""
    fetched = _parse_stamp(row.get("fetched"))
    manual = str(row.get("source") or "") == "manual"
    try:
        fresh_days = int(row.get("fresh_days") or (7 if manual else 1))
    except (TypeError, ValueError):
        fresh_days = 7 if manual else 1
    if manual:
        fresh_days = max(fresh_days, 7)
    fresh_days = max(1, min(fresh_days, 14))
    if fetched is None or datetime.now(TZ) - fetched > timedelta(days=fresh_days):
        return ""
    day = fetched.astimezone(TZ).strftime("%Y-%m-%d")
    eur_en = f"€{eur:.2f}"
    eur_nl = eur_en.replace(".", ",")
    usd_en = ""
    usd_nl = ""
    rate = PRODUCT_PRICES.get("rate") or {}
    rate_at = _parse_stamp(rate.get("fetched")) if isinstance(rate, dict) else None
    try:
        per = float(rate.get("usd_per_eur")) if isinstance(rate, dict) else 0
    except (TypeError, ValueError):
        per = 0
    if per > 0 and rate_at is not None and datetime.now(TZ) - rate_at <= timedelta(days=5):
        usd_en = f"${eur * per:.2f}"
        usd_nl = usd_en.replace(".", ",")
    if lang == "nl":
        shown = eur_nl
        asof = "(Prijs bij publicatie)"
    elif usd_en:
        shown = usd_en
        asof = "(Price at publication)"
    else:
        return ""
    return (f'<p class="pcost" data-priced="{esc(fetched.isoformat())}" data-days="{fresh_days}">'
            f'<b>{shown}</b><span class="asof">{esc(asof)}</span></p>')


_STAR = ('<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 1.6 12.6 7l5.9.5-4.5 3.8 1.4 5.8L10 14.4 4.6 17.1 6 11.3 1.5 7.5 7.4 7z"/></svg>')


def rating_html(key, lang):
    """Star row from a stored rating. Hidden once the figure is a week old."""
    row = (PRODUCT_PRICES.get("ratings") or {}).get(key) or {}
    if not isinstance(row, dict):
        return ""
    try:
        score = float(row.get("score"))
    except (TypeError, ValueError):
        return ""
    if not 1 <= score <= 5:
        return ""
    fetched = _parse_stamp(row.get("fetched"))
    if fetched is None or datetime.now(TZ) - fetched > timedelta(days=7):
        return ""
    try:
        count = int(row.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    if count < 0:
        count = 0
    score_s = f"{score:.1f}"
    if lang == "nl":
        score_s = score_s.replace(".", ",")
        count_s = f"{count:,}".replace(",", ".") if count else ""
        label = f"{score_s} van 5" + (f", {count_s} beoordelingen" if count_s else "")
    else:
        count_s = f"{count:,}" if count else ""
        label = f"{score_s} out of 5" + (f", {count_s} reviews" if count_s else "")
    text = score_s + (f" ({count_s})" if count_s else "")
    stars = _STAR * 5
    return (
        f'<p class="stars" data-rated="{esc(fetched.isoformat())}" data-days="7">'
        f'<span class="starrow" style="--score:{score:.2f};height:14px;overflow:hidden" role="img" aria-label="{esc(label)}">'
        f'<span class="empty" style="display:flex;height:14px;gap:2px">{stars}</span>'
        f'<span class="full" style="display:flex;height:14px;gap:2px">{stars}</span></span>'
        f'<span class="scorenum">{esc(text)}</span></p>')


def gallery_html(srcs, alt, href, remote, lang):
    srcs = [src for src in srcs if src][:6]
    if not srcs:
        return ""
    hero = (f'<img class="pgal-hero" src="{esc(srcs[0])}" alt="{esc(alt)}" width="200" height="200"'
            f' loading="lazy" decoding="async" onerror="{_IMG_HIDE}">')
    if remote and href:
        shot = (f'<a class="pshot" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{hero}</a>')
    else:
        shot = f'<span class="pshot">{hero}</span>'
    if len(srcs) == 1:
        return f'<div class="pgal"><div class="pgal-stage">{shot}</div></div>'
    prev = "Vorige foto" if lang == "nl" else "Previous photo"
    nxt = "Volgende foto" if lang == "nl" else "Next photo"
    label = "Foto's" if lang == "nl" else "Photos"
    photo = "Foto" if lang == "nl" else "Photo"
    thumbs = []
    for n, src in enumerate(srcs, 1):
        on = " is-on" if n == 1 else ""
        current = ' aria-current="true"' if n == 1 else ""
        thumbs.append(
            f'<button type="button" class="pgal-thumb{on}" data-src="{esc(src)}" aria-label="{esc(f"{photo} {n}")}"{current}>'
            f'<img src="{esc(_thumb_src(src))}" alt="" width="34" height="34" loading="lazy" decoding="async"'
            f' onerror="var b=this.closest(\'.pgal-thumb\');if(b)b.remove()"></button>')
    return (
        f'<div class="pgal" data-pgal tabindex="0" aria-label="{esc(label)}">'
        f'<div class="pgal-stage">{shot}'
        f'<button type="button" class="pgal-nav pgal-prev" aria-label="{esc(prev)}">{_ARROW_PREV}</button>'
        f'<button type="button" class="pgal-nav pgal-next" aria-label="{esc(nxt)}">{_ARROW_NEXT}</button>'
        f'</div><div class="pgal-thumbs">{"".join(thumbs)}</div></div>')


def local_gallery(src):
    if not src:
        return []
    out = [src]
    match = re.fullmatch(r"(/img/guides/ali-\d+)\.webp", src)
    if match:
        second = match.group(1) + "-2.webp"
        if (STATIC / second.lstrip("/")).is_file():
            out.append(second)
    return out


PRODUCT_JS = r"""(function(){document.querySelectorAll("[data-priced],[data-rated]").forEach(function(n){var raw=n.getAttribute("data-priced")||n.getAttribute("data-rated");var t=Date.parse(raw);var days=+n.getAttribute("data-days")||1;if(!t||Date.now()-t>days*86400000)n.remove()});document.querySelectorAll("[data-pgal]").forEach(function(root){var hero=root.querySelector(".pgal-hero"),thumbs=[].slice.call(root.querySelectorAll(".pgal-thumb"));if(!hero||thumbs.length<2)return;var i=0;function show(n){i=(n+thumbs.length)%thumbs.length;var src=thumbs[i].getAttribute("data-src");thumbs.forEach(function(t,k){var on=k===i;t.classList.toggle("is-on",on);if(on)t.setAttribute("aria-current","true");else t.removeAttribute("aria-current")});if(src&&hero.getAttribute("src")!==src){var pre=new Image();pre.onload=function(){hero.src=src};pre.src=src}}thumbs.forEach(function(t,k){t.addEventListener("click",function(){show(k)})});root.querySelectorAll(".pgal-nav").forEach(function(b){b.addEventListener("click",function(e){e.preventDefault();e.stopPropagation();show(i+(b.classList.contains("pgal-next")?1:-1))})});root.addEventListener("keydown",function(e){if(e.key==="ArrowLeft"||e.key==="ArrowRight"){e.preventDefault();show(i+(e.key==="ArrowRight"?1:-1))}});var x0=null,stage=root.querySelector(".pgal-stage")||root;stage.addEventListener("touchstart",function(e){x0=e.changedTouches[0].clientX},{passive:true});stage.addEventListener("touchend",function(e){if(x0==null)return;var dx=e.changedTouches[0].clientX-x0;x0=null;if(Math.abs(dx)>40)show(dx<0?i+1:i-1)},{passive:true})})})();"""


def product_photo_html(src, alt, href, remote):
    if not src:
        return ""
    return gallery_html([src], alt, href, remote, "en")


# A video only when it shows that exact product. Anything else stays a text card.
GUIDE_VIDEO = {
    "portable-chargers-adapters": {
        "id": "-PJMoBQfAzo",
        "alt": {"en": "Juice Booster 2", "nl": "Juice Booster 2"},
    },
    "sentry-usb-drive": {
        "id": "V34pAk2zfNI",
        "alt": {"en": "Samsung BAR Plus", "nl": "Samsung BAR Plus"},
    },
}


def guide_lead_photo(doc):
    """Guides do not use a stand-in photo. The card stays text."""
    return ""


def side_thumb(src, alt, href, sponsored=False):
    """48px thumbnail. Sponsored only when the link itself opens Amazon."""
    if not src or not href:
        return ""
    img = (f'<img src="{esc(src)}" alt="{esc(alt)}" width="48" height="48" loading="lazy" decoding="async"'
           f' onerror="{_IMG_HIDE}">')
    rel = ' rel="sponsored nofollow noopener" target="_blank"' if sponsored else ""
    return f'<a class="pshot pth" href="{esc(href)}"{rel}>{img}</a>'


def product_boxes(a, lang):
    """Optional affiliate box after the body. A price shows only when it was fetched today."""
    products = a.get("products") or []
    if not isinstance(products, list):
        return ""
    blocks = []
    for product in products:
        if not isinstance(product, dict):
            continue
        name = str(_loc(product.get("name"), lang)).strip()
        href = amazon_nl_href(product, lang)
        ali = ali_href(_loc(product.get("ali_url"), lang) or product.get("ali_url"), lang)
        if href and ali:
            amazon_only = dict(product)
            amazon_only.pop("ali_url", None)
            amazon_only.pop("ali_item", None)
            ali_only = dict(product)
            ali_only.pop("asin", None)
            ali_only.pop("url", None)
            blocks.extend(_article_product(amazon_only, lang))
            blocks.extend(_article_product(ali_only, lang))
            continue
        blocks.extend(_article_product(product, lang))
    if not blocks:
        return ""
    return "".join(blocks) + disclosure_line(lang)


def _article_product(product, lang):
    """One store per card. An empty card (no name and no link) is left out."""
    if not isinstance(product, dict):
        return []
    name = str(_loc(product.get("name"), lang)).strip()
    href = amazon_nl_href(product, lang)
    ali = ali_href(_loc(product.get("ali_url"), lang) or product.get("ali_url"), lang)
    if not name or not (href or ali):
        return []
    why = str(_loc(product.get("why"), lang)).strip()
    specs = _loc(product.get("specs"), lang)
    if isinstance(specs, str):
        specs = [specs]
    if not isinstance(specs, list):
        specs = []
    specs = [str(item).strip() for item in specs if str(item).strip()][:6]
    if href:
        button = "Vergelijk op Amazon" if lang == "nl" else "Compare on Amazon"
        asin = _product_asin(product)
        img = gallery_html(AMAZON_GALLERIES.get(asin, []), name, href, True, lang)
        key = asin
        link = (f'<a class="btn" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{esc(button)}</a>')
    else:
        button = "Vergelijk op AliExpress" if lang == "nl" else "Compare on AliExpress"
        item = str(product.get("ali_item") or "").strip()
        img = gallery_html(ALI_GALLERIES.get(item, []), name, ali, True, lang)
        key = f"ali:{item}" if item else ""
        link = (f'<a class="btn" href="{esc(ali)}" rel="sponsored nofollow noopener" target="_blank">{esc(button)}</a>')
    klass = "pbox" if img else "pbox noimg"
    lis = "".join(f"<li>{esc(item)}</li>" for item in specs)
    ul = f"<ul>{lis}</ul>" if lis else ""
    why_html = f'<p class="why">{esc(why)}</p>' if why else ""
    option = str(_loc(product.get("option"), lang)).strip()
    option_html = f'<p class="popt">{esc(option)}</p>' if option else ""
    cost = price_html(key, lang) if key else ""
    stars = rating_html(key, lang) if key else ""
    return [
        f'<aside class="{klass}"><div class="pbox-in">{img}<div><h3>{esc(name)}</h3>{why_html}{ul}'
        f'{option_html}{stars}{cost}'
        f'<div class="store-btns">{link}</div></div></div></aside>']


AFFILIATE = {}
GUIDE_DOCS = []
# Passenger cars an owner can put mats, a screen cover or a console tray in.
# Semi, Cybercab and Roadster are not that shopping moment.
_PASSENGER_PREFIXES = ("model-3", "model-y", "model-s", "model-x", "cybertruck")
HANDY_CSS = (
    ".handy{margin:26px 0 8px;padding:16px 16px 14px;border:1px solid rgba(0,212,255,.35);"
    "border-radius:12px;background:rgba(0,212,255,.06);max-width:68ch}"
    ".handy h2{margin:0 0 6px;font-size:1.15rem;line-height:1.25;letter-spacing:-.01em;"
    "color:var(--blue);font-weight:800;border:0;padding:0;text-transform:none}"
    ".handy .handy-lead{margin:0 0 12px;color:var(--muted);font-size:.92rem;line-height:1.45}"
    ".handy ul{list-style:none;margin:0;padding:0}"
    ".handy li{display:flex;flex-direction:column;gap:2px;margin:0;padding:10px 0;"
    "border-top:1px solid rgba(0,212,255,.18)}"
    ".handy li:first-child{border-top:0;padding-top:2px}"
    ".handy a{color:var(--blue2);font-weight:800;text-decoration:none;font-size:1.02rem;line-height:1.35}"
    ".handy a:hover,.handy a:focus-visible{text-decoration:underline;text-underline-offset:3px}"
    ".handy li span{color:var(--muted);font-size:.9rem;line-height:1.4}"
    ".handy .handy-note{margin:4px 0 0;font-size:.75rem;line-height:1.45;color:var(--dim)}"
    ".sheet-main article.money .handy{margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px);max-width:none}"
    "@media (max-width:600.98px){.sheet-main article.money .handy{margin-left:4px;margin-right:4px}"
    ".handy{padding:14px 12px 12px}}"
)


def load_affiliate():
    """Search-link catalog and the two Associates tags. Empty tags render nothing."""
    global AFFILIATE
    AFFILIATE = {}
    path = ROOT / "content" / "affiliate.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return
    if isinstance(data, dict):
        AFFILIATE = data


def affiliate_tag(lang):
    """Tag actually placed on links. Both languages use the amazon.nl tag.

    The account is registered on amazon.nl, and that tag is not credited on amazon.com,
    so every accessory link goes to amazon.nl. amazon_com_tag is kept for a future .com
    account and is not applied while it is empty. lang is accepted so callers stay the same.
    """
    if lang not in ("en", "nl"):
        return ""
    raw = str(AFFILIATE.get("amazon_nl_tag") or "").strip()
    return raw if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-]{1,39}", raw) else ""


def _passenger_models(models):
    return any(str(m).startswith(_PASSENGER_PREFIXES) for m in models)


def article_affiliate_topics(a):
    """Which catalog groups fit this article. News that merely mentions a car stays out.

    charging: the charging section, plus a model or guide piece that is itself about a cable,
    adapter or wall connector. owner: buying or living with a passenger Tesla (Model 3, Y, S, X
    or Cybertruck), not a sales figure, a Semi, a Cybercab or the Roadster. dashcam: Sentry Mode.
    tyres: the tyre guide, the winter guide and the maintenance schedule.
    """
    slug = str(a.get("slug") or "")
    cat = str(a.get("category") or "")
    models = a.get("models") or []
    topics = set()
    if cat == "charging":
        topics.add("charging")
    elif cat in ("models", "guides") and any(bit in slug for bit in (
            "wall-connector", "chademo", "home-charging", "type-2", "nacs", "charging-cable")):
        topics.add("charging")
    owner_bits = ("buying-used", "delivery-day", "which-to-buy", "16-inch-screen",
                  "standard-europe", "what-happens-to-your-tesla")
    if any(bit in slug for bit in owner_bits) and (
            "delivery-day" in slug or "what-happens-to-your-tesla" in slug or _passenger_models(models)):
        topics.add("owner")
    if cat == "guides" and _passenger_models(models) and any(
            bit in slug for bit in ("-vs-", "buying-used", "checklist", "used-")):
        topics.add("owner")
    if cat == "models" and _passenger_models(models) and any(bit in slug for bit in ("explained", "-screen")):
        topics.add("owner")
    if "sentry" in slug or "dashcam" in slug:
        topics.add("dashcam")
    if any(bit in slug for bit in ("tyre", "tire", "winter-range", "maintenance-schedule")):
        topics.add("tyres")
    return topics


def amazon_search_url(query, lang, tag):
    """Amazon.nl search. lang only selects the query words already chosen by the caller."""
    if lang not in ("en", "nl"):
        return ""
    language = "en_GB" if lang == "en" else "nl_NL"
    return "https://www.amazon.nl/s?" + urlencode({"k": query, "tag": tag, "language": language})


def handy_picks(a, lang):
    """Catalog rows for this article, in catalog order, at most four. No tag required."""
    topics = article_affiliate_topics(a)
    if not topics:
        return []
    catalog = AFFILIATE.get("catalog")
    if not isinstance(catalog, list):
        return []
    picks = []
    for item in catalog:
        if not isinstance(item, dict):
            continue
        item_topics = item.get("topics") or []
        if not isinstance(item_topics, list) or topics.isdisjoint(item_topics):
            continue
        name = str(_loc(item.get("name"), lang)).strip()
        note = str(_loc(item.get("note"), lang)).strip()
        query = str(_loc(item.get("search"), lang)).strip()
        # A search phrase only. A bare ASIN or a product URL is refused.
        if not name or " " not in query or "/" in query or re.search(r"\bB0[A-Z0-9]{8}\b", query):
            continue
        picks.append({"id": str(item.get("id") or ""), "name": name, "note": note, "query": query})
        if len(picks) == 4:
            break
    return picks


def handy_box(a, lang):
    """Accessory box. Nothing at all until this language's Associates tag is set."""
    tag = affiliate_tag(lang)
    if not tag:
        return ""
    picks = handy_picks(a, lang)
    if not picks:
        return ""
    L = LANGS[lang]
    rows = []
    for pick in picks:
        href = amazon_search_url(pick["query"], lang, tag)
        note = f"<span>{esc(pick['note'])}</span>" if pick["note"] else ""
        rows.append(
            f'<li><a href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{esc(pick["name"])}</a>{note}</li>')
    return (
        f'<aside class="handy" aria-label="{esc(L["handy_h"])}"><style>{HANDY_CSS}</style>'
        f'<h2>{esc(L["handy_h"])}</h2><p class="handy-lead">{esc(L["handy_p"])}</p>'
        f'<ul>{"".join(rows)}</ul><p class="handy-note">{esc(L["handy_note"])}</p></aside>')


def affiliate_disclosure(page_key, lang):
    """Amazon section for About and Privacy. Omitted entirely while this language's tag is empty."""
    if page_key not in ("about", "privacy") or not affiliate_tag(lang):
        return ""
    if lang == "nl":
        if page_key == "about":
            return (
                "<h2>Amazon-partner</h2><p>Staat er een Amazon-partnertag, dan tonen sommige artikelen "
                "over laden, Tesla-modellen en accessoires een korte lijst onder het kopje "
                "‘Handig voor je Tesla’. De links openen een zoekopdracht bij Amazon.nl. Als Amazon-partner "
                "verdienen wij aan in aanmerking komende aankopen. Dat verandert nooit wat we schrijven. "
                "Zonder tag blijft de lijst helemaal weg.</p>")
        return (
            "<h2>Amazon-partner</h2><p>Staat er een Amazon-partnertag, dan tonen sommige artikelen een "
            "korte lijst met Tesla-accessoires. De links gaan naar een zoekopdracht op Amazon.nl en zijn "
            "gemarkeerd als gesponsord. Als Amazon-partner verdienen wij aan in aanmerking komende "
            "aankopen. Wie een link volgt, gaat naar Amazon. Amazon kan dan eigen cookies plaatsen en "
            "technische gegevens ontvangen, zoals je IP-adres, volgens de "
            '<a href="https://www.amazon.nl/privacy?language=nl_NL" rel="nofollow noopener" target="_blank">'
            "privacyverklaring van Amazon</a>. We sturen Amazon geen naam door, en we tonen geen prijzen "
            "of beoordelingen. Zonder tag blijft de lijst verborgen.</p>")
    if page_key == "about":
        return (
            "<h2>Amazon Associates</h2><p>When an Amazon Associates tag is set, some articles about "
            "charging, Tesla models and accessories show a short list under the heading "
            "“Handy for your Tesla”. The links open a search on Amazon.nl. As an Amazon Associate we earn "
            "from qualifying purchases. That never changes what we write. The list is left out entirely "
            "while the tag is empty.</p>")
    return (
        "<h2>Amazon Associates</h2><p>When an Amazon Associates tag is set, some articles show a short "
        "list of Tesla accessories. The links go to a search on Amazon.nl and are marked as sponsored. "
        "As an Amazon Associate we earn from qualifying purchases. Following a link takes you to Amazon.nl, "
        "which can set its own cookies and receive technical data such as your IP address under the "
        '<a href="https://www.amazon.nl/privacy?language=en_GB" rel="nofollow noopener" target="_blank">Amazon.nl privacy notice</a>. '
        "We do not send Amazon a name, and we do not show prices or ratings. The list stays hidden "
        "while the tag is empty.</p>")


def with_affiliate_disclosure(page_key, lang, content):
    extra = affiliate_disclosure(page_key, lang)
    if not extra:
        return content
    if page_key == "privacy":
        needle = "<h2>Changes</h2>" if lang == "en" else "<h2>Wijzigingen</h2>"
    else:
        needle = ("<p>TrendingTesla is an independent site." if lang == "en"
                  else "<p>TrendingTesla is een onafhankelijke site.")
    if needle in content:
        return content.replace(needle, extra + needle, 1)
    return content + extra


# One MailerLite form for both languages. The free plan allows a single active form.
# Dutch pages keep Dutch headings; the embed and the noscript link stay on this form.
ML_ACCOUNT = "2799453"
ML_FORM = {"slug": "LKXOI2", "id": "204278464923042953"}
ML_SCRIPT = (
    "<script>(function(w,d,e,u,f,l,n){w[f]=w[f]||function(){(w[f].q=w[f].q||[]).push(arguments);},"
    "l=d.createElement(e),l.async=1,l.src=u,n=d.getElementsByTagName(e)[0],n.parentNode.insertBefore(l,n);})"
    "(window,document,'script','https://assets.mailerlite.com/js/universal.js','ml');"
    "ml('account','" + ML_ACCOUNT + "');</script>"
)


def ml_share():
    return f"https://preview.mailerlite.io/forms/{ML_ACCOUNT}/{ML_FORM['id']}/share"


def ml_endpoint():
    return f"https://assets.mailerlite.com/jsonp/{ML_ACCOUNT}/forms/{ML_FORM['id']}/subscribe"


# One handler for every compact signup (the bar under an article and the rail block).
# The script is emitted once per page, after every form it should bind.
ML_BAR_JS = (
    "<script>(function(){document.querySelectorAll('.nlbar-form').forEach(function(f){"
    "if(f.dataset.bound)return;f.dataset.bound='1';"
    "var msg=f.querySelector('.nlbar-msg'),btn=f.querySelector('button');if(!msg||!btn)return;"
    "f.addEventListener('submit',function(e){e.preventDefault();if(f.dataset.busy)return;"
    "f.dataset.busy='1';btn.disabled=true;msg.hidden=true;f.classList.remove('is-err','is-ok');"
    "var body=new URLSearchParams(new FormData(f));body.set('ajax','1');"
    "fetch(f.action,{method:'POST',headers:{'Accept':'application/json'},body:body})"
    ".then(function(r){return r.json().catch(function(){return null})})"
    ".then(function(j){if(j&&j.success){f.classList.add('is-ok');msg.hidden=false;"
    "msg.textContent=f.getAttribute('data-ok')}else{f.classList.add('is-err');msg.hidden=false;"
    "msg.textContent=f.getAttribute('data-err')}})"
    ".catch(function(){f.classList.add('is-err');msg.hidden=false;"
    "msg.textContent=f.getAttribute('data-err')})"
    ".then(function(){delete f.dataset.busy;if(!f.classList.contains('is-ok'))btn.disabled=false})})})})();"
    "</script>"
)


def ml_form_attrs(lang):
    L = LANGS[lang]
    return (f'method="post" action="{ml_endpoint()}" '
            f'data-ok="{esc(L["bar_ok"])}" data-err="{esc(L["bar_err"])}"')


def ml_hidden():
    return ('<input type="hidden" name="ml-submit" value="1">'
            '<input type="hidden" name="anticsrf" value="true">')


def ml_noscript(lang):
    L = LANGS[lang]
    return (f'<noscript><p class="mlfallback"><a href="{ml_share()}" rel="nofollow noopener" target="_blank">'
            f'{esc(L["signup_fallback"])}</a></p></noscript>')


def ml_signup(lang, heading=True):
    """Full MailerLite embed for /newsletter/ and /nl/nieuwsbrief/."""
    L = LANGS[lang]
    label = "" if heading else f' aria-label="{esc(L["signup"])}"'
    head = f'<h2>{esc(L["signup_h"])}</h2>' if heading else ""
    return (
        f'<aside class="mlbox"{label}>{head}'
        f'<div class="ml-embedded" data-form="{ML_FORM["slug"]}"></div>'
        f'<noscript><p class="mlfallback"><a href="{ml_share()}" rel="nofollow noopener" target="_blank">'
        f'{esc(L["signup_fallback"])}</a></p></noscript>{ML_SCRIPT}</aside>'
    )


def ml_privacy(lang):
    """Double opt-in and the privacy link. Shown on the article bar and the sidebar."""
    if lang == "en":
        text = "We email a confirmation first. Unsubscribe any time."
    else:
        text = "Je krijgt eerst een bevestiging per mail. Afmelden kan altijd."
    return (f'<p class="nlnote">{esc(text)} '
            f'<a href="{url(lang, "privacy/")}">{esc(LANGS[lang]["privacy"])}</a>.</p>')


def ml_bar(lang, suffix=""):
    """One-row signup under an article. Posts to the same form, so double opt-in stays.
    The shared handler is included here because this bar is the last signup on the page."""
    L = LANGS[lang]
    fid = f"nlbar-email-{lang}{suffix}"
    return (
        f'<aside class="nlbar" aria-label="{esc(L["signup"])}">'
        f'<form class="nlbar-form" {ml_form_attrs(lang)}>'
        f'<label class="nlbar-h" for="{fid}">{esc(L["bar_h"])}</label>'
        f'<input id="{fid}" type="email" name="fields[email]" required maxlength="200" '
        f'autocomplete="email" inputmode="email" placeholder="{esc(L["news_email"])}">'
        f'<button type="submit">{esc(L["news_btn"])}</button>'
        f'{ml_hidden()}'
        f'<p class="nlbar-msg" role="status" hidden></p></form>'
        f'{ml_privacy(lang)}{ml_noscript(lang)}{ML_BAR_JS}</aside>'
    )


def rail_signup(lang, script=False):
    """Rail block that posts with the same handler as the article bar.
    CSS hides it while the rail stacks under the story."""
    L = LANGS[lang]
    fid = f"nlside-email-{lang}"
    note = ml_privacy(lang)
    block = (
        f'<section class="nlside">'
        f'<h2>{esc(L["signup"])}</h2>'
        f'<form class="nlbar-form nlside-form" {ml_form_attrs(lang)}>'
        f'<label class="nlside-lead" for="{fid}">{esc(L["bar_h"])}</label>'
        f'<input id="{fid}" type="email" name="fields[email]" required maxlength="200" '
        f'autocomplete="email" inputmode="email" placeholder="{esc(L["news_email"])}">'
        f'<button type="submit">{esc(L["news_btn"])}</button>'
        f'{ml_hidden()}'
        f'<p class="nlbar-msg" role="status" hidden></p>{note}</form>'
        f'{ml_noscript(lang)}</section>'
    )
    return block + (ML_BAR_JS if script else "")


def newsletter(lang, where):
    cfg = MONEY.get("newsletter") if isinstance(MONEY.get("newsletter"), dict) else {}
    action = str(cfg.get("action") or "").strip()
    if not action.startswith("https://"):
        return ""
    method = str(cfg.get("method") or "post").lower()
    if method not in ("get", "post"):
        method = "post"
    field = str(cfg.get("email_field") or "email").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]{0,40}", field):
        field = "email"
    L = LANGS[lang]
    fid = f"nf-{where}-{lang}"
    return (f'<form class="nform" method="{method}" action="{esc(action)}">'
            f'<h2>{esc(L["news_h"])}</h2><p>{esc(L["news_p"])}</p>'
            f'<label class="sr" for="{fid}">{esc(L["news_email"])}</label>'
            f'<div class="nrow"><input id="{fid}" type="email" name="{esc(field)}" required maxlength="200" '
            f'autocomplete="email" placeholder="{esc(L["news_email"])}">'
            f'<button type="submit">{esc(L["news_btn"])}</button></div>'
            f'<input type="hidden" name="lang" value="{lang}"></form>')


def consent_bar(lang):
    L = LANGS[lang]
    show = ('<script>(function(){try{if(!localStorage.getItem("tt-consent"))'
            'document.getElementById("consent").hidden=false}catch(e){'
            'document.getElementById("consent").hidden=false}})();</script>')
    return (f'<div id="consent" class="consent" hidden '
            f'data-beacon="5c536a7c183844ccb97e1ac151b5d018">'
            f'<p>{esc(L["consent_p"])} <a href="{url(lang, "privacy/")}">{esc(L["consent_more"])}</a></p>'
            f'<div class="consent-btns">'
            f'<button type="button" data-consent="necessary">{esc(L["consent_no"])}</button>'
            f'<button type="button" data-consent="all">{esc(L["consent_yes"])}</button>'
            f'</div></div>{show}')


# Top nav is the seven map layers. plain=True is a single link, with no menu.
# child=True indents a page that belongs under the item above it.
NAV_LAYERS = [
    {
        "key": "tesla", "tone": "tesla", "href": "tesla/",
        "label": {"en": "Tesla", "nl": "Tesla"},
        "items": [
            {"key": "cars", "href": "cars/", "en": "Electric car news", "nl": "Elektrisch autonieuws"},
            {"key": "models", "href": "category/models/", "en": "Tesla models", "nl": "Tesla-modellen"},
            {"key": "semi", "href": "semi/", "en": "Semi Truck", "nl": "Semi-truck"},
            {"key": "robotaxi", "href": "robotaxi/", "en": "Robotaxi", "nl": "Robotaxi"},
            {"key": "fsd", "href": "fsd/", "en": "FSD", "nl": "FSD"},
            {"key": "fsd-europe", "href": "fsd-in-europe/", "en": "FSD in Europe step by step", "nl": "FSD in Europa stap voor stap"},
            {"key": "deliveries", "href": "tesla-deliveries/", "en": "Tesla deliveries each quarter", "nl": "Tesla leveringen per kwartaal"},
            {"key": "optimus", "href": "optimus/", "en": "Optimus", "nl": "Optimus"},
        ],
    },
    {
        "key": "tesla-energy", "tone": "energy", "href": "tesla-energy/",
        "label": {"en": "Tesla Energy", "nl": "Tesla Energy"},
        "items": [
            {"key": "megapacks", "href": "megapacks/", "en": "Megapacks", "nl": "Megapacks"},
            {"key": "charging-network", "href": "charging-network/", "en": "Charging Network", "nl": "Laadnetwerk"},
            {"key": "home-charging", "href": "home-charging/", "en": "Home charging stations", "nl": "Thuisladers"},
            {"key": "solar", "href": "solar/", "en": "Solar", "nl": "Zonne-energie"},
        ],
    },
    {
        "key": "spacex", "tone": "spacex", "href": "spacex/",
        "label": {"en": "SpaceX", "nl": "SpaceX"},
        "items": [
            {"key": "starship-vehicle", "href": "starship-vehicle/", "en": "Starship", "nl": "Starship"},
            {"key": "starship", "href": "starship/", "en": "All Starship flights", "nl": "Alle Starship-vluchten"},
            {"key": "falcons", "href": "falcons/", "en": "Falcons", "nl": "Falcons"},
        ],
    },
    {
        "key": "spacexsi", "tone": "spacexsi", "href": "spacexsi/",
        "label": {"en": "SpaceXSI", "nl": "SpaceXSI"},
        "items": [
            {"key": "ai", "href": "ai/", "en": "AI news", "nl": "AI-nieuws"},
            {"key": "ai-compute", "href": "ai-compute/", "en": "Compute", "nl": "Rekenkracht"},
            {"key": "datacenters", "href": "datacenters/", "en": "Datacenters", "nl": "Datacenters"},
            {"key": "chips", "href": "chips/", "en": "Chips", "nl": "Chips"},
        ],
    },
    {
        "key": "starlink", "tone": "link", "href": "starlink/",
        "label": {"en": "Starlink", "nl": "Starlink"},
        "items": [
            {"key": "starlink-nl", "href": "starlink-netherlands/", "en": "Starlink in the Netherlands", "nl": "Starlink in Nederland"},
        ],
    },
    {
        "key": "neuralink", "tone": "neural", "href": "neuralink/",
        "label": {"en": "Neuralink", "nl": "Neuralink"},
        "plain": True,
    },
    {
        "key": "boring", "tone": "boring", "href": "boring/",
        "label": {"en": "Boring Co", "nl": "Boring Co"},
        "plain": True,
    },
]

_LAYER_FOR = {}
for _layer in NAV_LAYERS:
    _LAYER_FOR[_layer["key"]] = _layer["key"]
    for _item in _layer.get("items") or []:
        _LAYER_FOR[_item["key"]] = _layer["key"]


def nav_current(active):
    return _LAYER_FOR.get(active or "", "")


def _nav_rows(lang):
    return [(layer["key"], layer["href"], layer["label"][lang]) for layer in NAV_LAYERS]


def _menu_link(lang, item, active):
    cls = []
    if item.get("child"):
        cls.append("child")
    if active == item["key"]:
        cls.append("on")
    klass = f' class="{" ".join(cls)}"' if cls else ""
    return f'<a{klass} role="menuitem" href="{url(lang, item["href"])}">{esc(item[lang])}</a>'


def primary_nav(lang, active=None):
    cur = nav_current(active)
    parts = []
    for layer in NAV_LAYERS:
        on = " on" if cur == layer["key"] else ""
        label = layer["label"][lang]
        if layer.get("plain"):
            parts.append(f'<a class="pn{on}" href="{url(lang, layer["href"])}">{esc(label)}</a>')
            continue
        menu = "".join(_menu_link(lang, item, active) for item in layer.get("items") or [])
        parts.append(
            f'<div class="pdrop tone-{layer["tone"]}{on}">'
            f'<a class="pn{on}" href="{url(lang, layer["href"])}" aria-haspopup="true" aria-expanded="false">'
            f'{esc(label)}</a>'
            f'<div class="pmenu" role="menu">{menu}</div></div>')
    eco_on = " on" if active == "ecosystem" else ""
    parts.append(
        f'<a class="pn{eco_on}" href="{url(lang, ecosystem_path(lang))}">{esc(LANGS[lang]["nav_eco"])}</a>')
    return f'<nav class="pnav" aria-label="{esc(LANGS[lang]["menu"])}">{"".join(parts)}</nav>'


def drawer_links(lang, active):
    out = []
    for layer in NAV_LAYERS:
        on = " on" if nav_current(active) == layer["key"] else ""
        link = (f'<a class="di tone-{layer["tone"]}{on}" href="{url(lang, layer["href"])}">'
                f'{esc(layer["label"][lang])}</a>')
        if layer.get("plain"):
            out.append(f'<div class="dlayer">{link}</div>')
            continue
        subs = []
        for item in layer.get("items") or []:
            mark = " on" if active == item["key"] else ""
            child = " child" if item.get("child") else ""
            subs.append(
                f'<a class="{child.strip()}{mark}" href="{url(lang, item["href"])}">{esc(item[lang])}</a>')
        out.append(f'<div class="dlayer">{link}<div class="dsub">{"".join(subs)}</div></div>')
    eco_on = " on" if active == "ecosystem" else ""
    out.append(
        f'<a class="di dmap{eco_on}" href="{url(lang, ecosystem_path(lang))}">{esc(LANGS[lang]["nav_eco"])}</a>')
    return "".join(out)


def crumbs(lang, parts, current=True):
    """BreadcrumbList JSON-LD. The visible trail was removed from the page.

    By default the last crumb is the current page. Pass current=False when
    every segment should point at its hub (article pages). A part whose path
    is None is stored as a name only. The first return value is empty so
    callers can keep unpacking (nav, ld) without emitting a visible trail.
    """
    chain = [(LANGS[lang]["home"], "")] + list(parts)
    lis = []
    ld_items = []
    last = len(chain)
    label = "Breadcrumb" if lang == "en" else "Kruimelpad"
    for i, (name, path) in enumerate(chain, 1):
        as_current = current and i == last
        href = None if path is None or as_current else url(lang, path)
        item = {"@type": "ListItem", "position": i, "name": name}
        if href is not None:
            item["item"] = SITE + href
            lis.append(f'<li><a href="{href}">{esc(name)}</a></li>')
        elif as_current:
            lis.append(f'<li><span aria-current="page">{esc(name)}</span></li>')
        else:
            lis.append(f'<li><span>{esc(name)}</span></li>')
        ld_items.append(item)
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": ld_items}
    return "", ld


def ld_script(obj):
    raw = json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{raw}</script>'


def hub_cards(items, lang, eager_first=False):
    if not items:
        return f'<p class="empty">{LANGS[lang]["empty"]}</p>'
    cards = "".join(gcard(a, lang, eager=eager_first and i == 0) for i, a in enumerate(items))
    return f'<div class="grid2 gall wide">{cards}</div>'


def category_hub(key, items, lang):
    c = CATEGORIES[key]
    L = LANGS[lang]
    intro = (CAT_INTRO.get(key) or {}).get(lang) or L["cat_intro"].format(c[lang])
    nav, ld = crumbs(lang, [(c[lang], f"category/{key}/")])
    ordered = sorted(items, key=published, reverse=True)
    feature = home_lead(ordered[0], lang, title_tag="h2") if ordered else ""
    rest = ordered[1:]
    grid = hub_cards(rest, lang) if rest else ""
    body = (f'{nav}<header class="hubhead"><h1>{esc(c[lang])}</h1><p class="lead">{esc(intro)}</p></header>'
            f'{feature}{grid}')
    return body, ld, intro


MODEL_ORDER = ["model-s", "model-3", "model-x", "model-y", "cybercab", "cybertruck", "roadster", "semi"]


def models_overview(lang):
    """One card per version, grouped by family. Family pages stay as hubs."""
    L = LANGS[lang]
    nav, ld = crumbs(lang, [(L["nav_models"], "category/models/")])
    intro = ({
        "en": "Every Tesla version the site covers, grouped by model. Open a card for the facts and the articles.",
        "nl": "Elke Tesla-uitvoering die de site volgt, per model gegroepeerd. Open een kaart voor de feiten en de artikelen.",
    })[lang]
    sections = []
    listed = []
    n = 0
    for root, keys in model_groups():
        cards = []
        for key in keys:
            cards.append(model_card(key, lang, eager=n < 4, high=(n == 0)))
            listed.append(key)
            n += 1
        title = MODELS[root]["name"]
        sections.append(
            f'<section><h2 class="rubh">{esc(title)}</h2><div class="mgrid">{"".join(cards)}</div></section>')
    body = (f'{nav}<header class="hubhead"><h1>{esc(L["nav_models"])}</h1>'
            f'<p class="lead">{esc(intro)}</p></header>{"".join(sections)}')
    return body, ld, intro, listed


def model_groups():
    """Family order, then each version in the order it is defined. A model with no versions is its own card."""
    groups = []
    for root in MODEL_ORDER:
        kids = [k for k, v in MODELS.items() if v.get("parent") == root]
        groups.append((root, kids or [root]))
    return groups


def model_card(key, lang, eager=False, high=False):
    name = model_title(key, lang)
    if "," in name or len(name.split()) > 8:
        raise SystemExit(f"model card title must be at most 8 words and have no comma: {name}")
    ph = model_photo(key) or ""
    img = ""
    if ph:
        w, h = img_size(ph)
        img = resp_img(ph, photo_alt(key, lang), SIZES_MODEL, high=high, lazy=not eager, width=w, height=h)
    note = MODELS[key].get("card_note")
    cap = ""
    if isinstance(note, dict):
        text = note.get(lang) or note.get("en")
        if text:
            cap = f'<span class="mcap">{esc(text)}</span>'
    return (f'<a class="mcard" href="{url(lang, "model/" + key + "/")}">'
            f'<span class="mim zimg">{img}</span><span class="mname">{esc(name)}</span>{cap}</a>')


def fact_sources(key, lang):
    inf = INFO.get(key) or {}
    links = []
    for title, href in inf.get("sources") or []:
        if href.startswith("http"):
            links.append(f'<a href="{esc(href)}" rel="noopener noreferrer">{esc(title)}</a>')
        else:
            path = href.lstrip("/")
            links.append(f'<a href="{url(lang, path)}">{esc(title)}</a>')
    if not links and not inf.get("asof"):
        return ""
    when = ""
    if inf.get("asof"):
        when = ("As of 19 November 2026. " if lang == "en" else "Stand van 19 november 2026. ")
    label = "Sources" if lang == "en" else "Bronnen"
    return f'<p class="imgnote">{when}{esc(label)}: {" · ".join(links)}</p>'


def model_hub(key, items, lang):
    """Model page: photo, sourced facts and the articles. Not a news lead."""
    m = MODELS[key]
    name = model_title(key, lang)
    heading_name = model_heading(key, lang)
    L = LANGS[lang]
    inf = INFO.get(key)
    facts = PAGE_FACTS.get(key)
    if facts:
        intro = facts["intro"][lang]
    else:
        intro = inf[lang]["intro"] if inf and inf.get(lang, {}).get("intro") else L["model_intro"].format(name)
    parts = [(L["nav_models"], "category/models/")]
    parent = m.get("parent")
    if parent:
        parts.append((model_title(parent, lang), f"model/{parent}/"))
    parts.append((name, f"model/{key}/"))
    nav, ld = crumbs(lang, parts)
    ph = model_photo(key)
    cap = photo_caption(key, lang)
    figcap = f'<figcaption class="imgnote">{cap}</figcaption>' if cap else ""
    klass = "mhero"
    hero = (f'<figure class="{klass}">{resp_img(ph, photo_alt(key, lang), "(max-width: 900px) 100vw, 820px", high=True, lazy=False, width=1600, height=900)}{figcap}</figure>'
            if ph else "")
    extra = ""
    body_name = m.get("body_photo")
    if body_name:
        body_src = "/img/models/" + body_name
        body_alt = m.get("body_alt") or {}
        alt = body_alt.get(lang) or body_alt.get("en") or heading_name
        body_cap = photo_caption_from(m.get("body_credit"), lang)
        body_fig = f'<figcaption class="imgnote">{body_cap}</figcaption>' if body_cap else ""
        extra = (f'<figure class="mhero">{resp_img(body_src, alt, "(max-width: 900px) 100vw, 820px", lazy=True, width=1600, height=900)}{body_fig}</figure>')
    if facts:
        specs = render_fact_sections(facts, lang)
        sourced = ""
    else:
        specs = ""
        rows = (inf or {}).get(lang, {}).get("specs") or []
        if rows:
            label = "Key facts" if lang == "en" else "Kernfeiten"
            body_rows = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows)
            specs = f'<section class="mfacts"><h2>{label}</h2><table class="specs">{body_rows}</table></section>'
        sourced = fact_sources(key, lang)
    ordered = sorted(items, key=published, reverse=True)
    heading = ("Articles about " if lang == "en" else "Artikelen over ") + name
    if ordered:
        listing = f'<h2 class="rubh">{esc(heading)}</h2>{hub_cards(ordered, lang)}'
    elif parent:
        back = "Articles about this version are listed with the model." if lang == "en" else "Artikelen over deze uitvoering staan bij het model."
        listing = (f'<p class="hubnote">{esc(back)} <a href="{url(lang, "model/" + parent + "/")}">'
                   f'{esc(model_title(parent, lang))}</a>.</p>')
    else:
        listing = f'<p class="empty">{esc(L["empty"])}</p>'
    versions = ""
    if not parent:
        kids = [k for k, v in MODELS.items() if v.get("parent") == key]
        if kids:
            vlabel = "Versions" if lang == "en" else "Uitvoeringen"
            versions = f'<h2 class="rubh">{esc(vlabel)}</h2><div class="mgrid">{"".join(model_card(k, lang) for k in kids)}</div>'
    acc = ""
    if str(key).startswith(("model-3", "model-y")):
        acc = f'<section class="mfacts"><h2>{esc(L["i_acc"])}</h2>{model_accessory_links(key, lang)}</section>'
    body = (f'{nav}<header class="hubhead"><h1>{esc(heading_name)}</h1></header>'
            f'{hero}<p class="mintro">{esc(intro)}</p>{extra}{versions}{specs}{sourced}{acc}{listing}')
    desc = re.sub(r"\s+", " ", intro).strip()
    if len(desc) > 180:
        desc = desc[:179].rsplit(" ", 1)[0] + "…"
    return body, ld, desc


def render_fact_sections(facts, lang):
    status = {
        "en": {"official": "official", "reported": "reported", "video": "stated on video",
               "derived": "derived", "estimated": "estimated", "unclear": "unclear",
               "conflict": "conflict", "unknown": "not announced"},
        "nl": {"official": "officieel", "reported": "gemeld", "video": "gezegd op video",
               "derived": "berekend", "estimated": "geschat", "unclear": "onduidelijk",
               "conflict": "tegenstrijdig", "unknown": "niet bekendgemaakt"},
    }[lang]
    heads = ("Fact", "Value", "Status") if lang == "en" else ("Punt", "Waarde", "Status")
    parts = []
    for sec in facts["sections"]:
        body = "".join(
            f"<tr><th>{esc(r[lang][0])}</th><td>{esc(r[lang][1])}</td><td>{esc(status[r['status']])}</td></tr>"
            for r in sec["rows"])
        notes = "".join(f'<p class="imgnote">{esc(n)}</p>' for n in sec.get("notes", {}).get(lang, []))
        parts.append(
            f'<section class="mfacts"><h2>{esc(sec["title"][lang])}</h2>'
            f'<table class="specs"><thead><tr><th>{heads[0]}</th><th>{heads[1]}</th><th>{heads[2]}</th></tr></thead>'
            f'<tbody>{body}</tbody></table>{notes}</section>')
    unknown = facts.get("unknown", {}).get(lang) or []
    if unknown:
        items = "".join(f"<li>{esc(x)}</li>" for x in unknown)
        label = "Not announced" if lang == "en" else "Niet bekendgemaakt"
        parts.append(f'<section class="mfacts"><h2>{label}</h2><ul>{items}</ul></section>')
    links = []
    for title, href in facts.get("sources") or []:
        if href.startswith("http"):
            links.append(f'<a href="{esc(href)}" rel="noopener noreferrer">{esc(title)}</a>')
        elif href.startswith("/"):
            links.append(f'<a href="{url(lang, href.lstrip("/"))}">{esc(title)}</a>')
        else:
            links.append(esc(title))
    when = "As of 19 November 2026. " if lang == "en" else "Stand van 19 november 2026. "
    label = "Sources" if lang == "en" else "Bronnen"
    parts.append(f'<p class="imgnote">{when}{label}: {" · ".join(links)}</p>')
    return "".join(parts)


def video_for(a, lang):
    return VIDEOS.get((a["slug"], lang)) or VIDEOS.get((a["slug"], "en"))


def player(vid, kind, label, poster, priority, title=""):
    w, h = (1200, 630) if kind == "long" else (360, 640)
    sizes = SIZES_HERO if kind == "long" else "(max-width: 800px) 70vw, 280px"
    # The first picture on the page is the LCP image: eager and high priority.
    photo = resp_img(poster, title or label, sizes, high=priority, lazy=not priority, width=w, height=h)
    return (f'<figure class="avid {kind}"><button class="avb" type="button" data-vid="{esc(vid)}" aria-label="{esc(label)}">'
            f'{photo}<span class="shp" aria-hidden="true"></span></button></figure>')


def short_poster(short):
    """Local 9:16 still for one Short, when shorts.json names a file that is on the site."""
    poster = str((short or {}).get("poster") or "")
    if poster.startswith("/img/") and (STATIC / poster.lstrip("/")).is_file():
        return poster
    return ""


def short_visual(a):
    """Photo for a news card whose video is a Short, not a long video.

    A local 9:16 poster is centered on a blurred copy. Without one, the card uses the
    YouTube still and stays a normal 16:9 cover. Future Shorts pick this up from shorts.json.
    """
    if not a or video_for(a, "en"):
        return "", False
    sh = SHORTS.get(a.get("slug") or "")
    if not sh:
        return "", False
    local = short_poster(sh)
    if local:
        return local, True
    if sh.get("id"):
        return yt_thumb(sh["id"]), False
    return "", False


def still_box(tag, frame, src, alt, sizes, *, portrait=False, high=False, lazy=True, width=640, height=360, mark=""):
    klass = f"{frame} fitin" if portrait else frame
    style = f' style="--poster:url({esc(src)})"' if portrait else ""
    w, h = (1080, 1920) if portrait else (width, height)
    return (f'<{tag} class="{klass}"{style}>'
            f'{resp_img(src, alt, sizes, high=high, lazy=lazy, width=w, height=h)}{mark}</{tag}>')


def card_mark(a, lang, badge=""):
    """Short badge and play icon when this card is a Short. Otherwise the usual length mark."""
    if not badge and short_visual(a)[0]:
        badge = "Short"
    bits = live_mark(a)
    if badge:
        return bits + f'<span class="dur dvo">{esc(badge)}</span><span class="vpl" aria-hidden="true"></span>'
    return bits + dur(a, lang) + ovl(a, lang)


def article_media(a, lang):
    poster = site_img(a)
    video = video_for(a, lang)
    # A long video stands in for the Short on the article. The Short stays on /shorts/.
    short = None if video else SHORTS.get(a["slug"])
    blocks = []
    if video:
        blocks.append(player(video["id"], "long", LANGS[lang]["watch"], poster, True, a[lang]["title"]))
    if short:
        blocks.append(player(short["id"], "short", LANGS[lang]["watch_short"], short_poster(short) or poster, True, a[lang]["title"]))
    still = f'<div class="hi">{resp_img(poster, a[lang]["title"], SIZES_HERO, high=True, lazy=False, cls="hero-img")}</div>'
    note = a.get("hero_note")
    if isinstance(note, dict):
        text = str(note.get(lang) or note.get("en") or "").strip()
        if text:
            still += f'<p class="imgnote">{esc(text)}</p>'
    if blocks:
        return "".join(blocks)
    return still


def footage_note(slug, lang):
    """Credits for real clips a render actually used. Empty when this article has none yet."""
    path = ROOT / "content" / "footage-used.json"
    if not path.exists():
        return ""
    try:
        row = json.loads(path.read_text(encoding="utf-8")).get(slug) or {}
    except (OSError, json.JSONDecodeError):
        return ""
    items = [c for c in row.get("credits") or [] if c.get("page") and c.get("credit")]
    if not items:
        return ""
    links = "; ".join(
        f'<a href="{esc(c["page"])}" rel="nofollow noopener" target="_blank">{esc(c["credit"])}</a>' for c in items)
    lab = "Footage" if lang == "en" else "Beeld"
    return f" {lab}: {links}."


def article_sources(a, lang):
    L = LANGS[lang]
    src = ""
    if a.get("sources"):
        items = "".join(
            f'<li><a href="{esc(s["url"])}" rel="nofollow noopener" target="_blank">{esc(s["title"])}</a></li>'
            for s in a["sources"])
        src = f'<details class="sources"><summary>{L["sources"]} ({len(a["sources"])})</summary><ul>{items}</ul></details>'
    if a.get("credits"):
        credit = "; ".join(
            f'<a href="{esc(item["page"])}" rel="nofollow noopener" target="_blank">{esc(item["credit"])}</a>'
            for item in a["credits"] if item.get("page"))
        src += f'<p class="imgnote">{L["photocredit"]}: {credit}. {L["imgnote_other"]}{footage_note(a["slug"], lang)}</p>'
    else:
        src += f'<p class="imgnote">{L["imgnote"]}{footage_note(a["slug"], lang)}</p>'
    return src


def prev_next(a, arts, lang):
    ordered = sorted(arts, key=published)
    index = next(i for i, item in enumerate(ordered) if item is a)
    older = ordered[index - 1] if index else None
    newer = ordered[index + 1] if index + 1 < len(ordered) else None
    L = LANGS[lang]

    def cell(item, kind):
        if not item:
            return "<span></span>"
        label = L["prev"] if kind == "prev" else L["next"]
        small = f"← {label}" if kind == "prev" else f"{label} →"
        return (f'<a class="{kind}" href="{url(lang, item["slug"] + "/")}">'
                f"<small>{small}</small><strong>{esc(item[lang]['title'])}</strong></a>")

    return (f'<nav class="seq" aria-label="{esc(L["prev"])} / {esc(L["next"])}">'
            f'{cell(older, "prev")}{cell(newer, "next")}</nav>')


def money_article(a, arts, lang):
    L = LANGS[lang]
    t = a[lang]
    section, section_href = topic_meta(a, lang)
    nav, ld = article_crumbs(a, lang)
    toc, body = enrich(a, lang, with_toc=True)
    body = insert_mid(body, ad_html("mid_article", lang))
    chips = ""
    if a.get("models"):
        chips = '<div class="chips">' + "".join(
            f'<a href="{url(lang, "model/" + k + "/")}">{esc(model_heading(k, lang))}</a>' for k in a["models"]) + "</div>"
    side = ad_html("sidebar", lang)
    article = (
        f'<article class="money">'
        f'<h1 class="atitle">{esc(t["title"])}</h1>'
        f'<p class="byline"><a href="{url(lang, "editorial/")}">{L["byline"]}</a></p>'
        f'<div class="srow"><p class="meta smeta"><a class="tag" href="{url(lang, section_href)}">{esc(section)}</a>'
        f' · {when(a, lang)} · {read_time(a, lang)} {L["min"]}</p>'
        f'<div class="acts"><button class="act like" type="button" data-like="{a["slug"]}" aria-pressed="false" title="{esc(L["like"])}">{HEART_SVG}<span>0</span></button>'
        f'<button class="act save" type="button" data-save="{a["slug"]}" aria-pressed="false" title="{esc(L["save"])}" aria-label="{esc(L["save"])}">{BOOK_SVG}</button></div></div>'
        f'{chips}<p class="lead">{esc(t["description"])}</p>'
        f'{article_media(a, lang)}{toc}'
        f'<div class="prose">{body}</div>{live_feed(a, lang) if a.get("type") == "live" else ""}{product_boxes(a, lang)}{handy_box(a, lang)}{ad_html("end", lang)}'
        f'{article_sources(a, lang)}</article>')
    col = f'{nav}{article}{related_block(a, arts, lang)}{ml_bar(lang)}'
    wrap = "aread with-side" if side else "aread"
    aside = f'<div class="ad-side-wrap">{side}</div>' if side else ""
    return f'<div class="{wrap}"><div class="acol">{col}</div>{aside}</div>', ld


HOME_TOPICS = (
    ("models", "nav_models", "category/models/", ("models",)),
    ("energy", "nav_energy", "tesla-energy/", ("energy",)),
    ("fsd", "nav_fsd", "fsd/", ("fsd", "robotaxi")),
    ("spacex", "nav_space", "spacex/", ("spacex", "starlink")),
    ("xai", "nav_xai", "spacexsi/", ("xai",)),
    ("guides", None, "category/guides/", ("guides",)),
)


def _in_topics(a, keys):
    cats = {a["category"]} | set(a.get("also") or [])
    return bool(cats & set(keys))


def home_lead(a, lang, title_tag="h1"):
    """Featured story: photo, then the rubric line, then the headline."""
    L = LANGS[lang]
    t = a[lang]
    href = url(lang, a["slug"] + "/")
    tag = "h1" if title_tag == "h1" else "h2"
    photo = site_img(a)
    # Spans, not hub links. A link inside the story link is invalid HTML, and the
    # browser then draws this line larger, underlined and in the wrong colours.
    line = rubric_line(a, lang)
    im = (f'<div class="leadim">'
          f'{resp_img(photo, t["title"], SIZES_LEAD, high=True, lazy=False, width=1600, height=900)}</div>'
          if photo else "")
    return (f'<article class="leadstory">{im}{with_actions(line, "", lang, href)}'
            f'<div>'
            f'<{tag} class="ltitle"><a href="{href}">{esc(card_title(a, lang))}</a></{tag}>'
            f'<a class="btn" href="{href}">{esc(L["read_story"])}</a></div></article>')


def layer_tone(a):
    """Colour class for a filed layer. Matches the homepage layer cards."""
    return {
        "tesla": "tesla",
        "tesla-energy": "energy",
        "spacex": "spacex",
        "starlink": "link",
        "spacexsi": "spacexsi",
        "neuralink": "neural",
        "boring": "boring",
    }.get((a or {}).get("layer") or "", "")


def layer_name(a, lang):
    """Layer title used as the cyan rubric on cards and video tiles."""
    key = (a or {}).get("layer") or ""
    for layer in LAYERS:
        if layer["key"] == key:
            return _bi(layer["title"], lang)
    if not a:
        return ""
    name, _href = topic_meta(a, lang)
    return name


def layer_href(a, lang):
    """Hub for this article's layer. Falls back to the topic hub, which is never a redirect."""
    key = (a or {}).get("layer") or ""
    for layer in LAYERS:
        if layer["key"] == key:
            return layer["path"]
    if not a:
        return ""
    _name, href = topic_meta(a, lang)
    return href


def _specific_topic_hub(topic):
    """The subtopic hub for a filing topic, skipping layer landing pages."""
    if not topic:
        return None
    layer_keys = {layer["key"] for layer in LAYERS}
    layer_paths = {layer["path"] for layer in LAYERS}
    matches = [spec for spec in HUBS
               if topic in (spec.get("topics") or [])
               and spec["key"] not in layer_keys
               and spec["path"] not in layer_paths]
    if not matches:
        return None
    for spec in matches:
        if spec["key"] == topic:
            return spec
    for spec in matches:
        if spec.get("topics") == [topic]:
            return spec
    return matches[0]


def _nav_layer_for_topic(topic):
    """Parent NAV_LAYERS entry for a topic key, when filing has no layer."""
    if not topic:
        return None
    for nav in NAV_LAYERS:
        if nav["key"] == topic:
            return nav
        for item in nav.get("items") or []:
            if item["key"] == topic:
                return nav
    spec = _specific_topic_hub(topic)
    if not spec:
        return None
    for nav in NAV_LAYERS:
        if nav["key"] == spec["key"] or nav["href"] == spec["path"]:
            return nav
        for item in nav.get("items") or []:
            if item["key"] == spec["key"] or item["href"] == spec["path"]:
                return nav
    return None


def _hub_parent_layer(spec, items):
    """Parent LAYERS entry for a topic hub, from filing.json, then the nav map."""
    counts = {}
    for a in items or ():
        key = (a or {}).get("layer") or ""
        if key:
            counts[key] = counts.get(key, 0) + 1
    layer_key = max(counts, key=counts.get) if counts else ""
    if not layer_key:
        candidates = list(spec.get("topics") or [])
        if spec.get("key"):
            candidates.append(spec["key"])
        for t in candidates:
            for layer in LAYERS:
                if layer["key"] == t:
                    return layer
            nav = _nav_layer_for_topic(t)
            if nav:
                layer_key = nav["key"]
                break
    if not layer_key:
        return None
    for layer in LAYERS:
        if layer["key"] == layer_key:
            return layer
    return None


def topic_hub_crumb_parts(spec, items, lang):
    """Layer and subtopic for a topic hub trail. crumbs() prepends Home."""
    title = _bi(spec["title"], lang)
    path = spec["path"]
    layer = _hub_parent_layer(spec, items)
    if not layer:
        return [(title, path)]
    layer_label = _bi(layer["title"], lang)
    layer_path = layer["path"]
    if path == layer_path or spec.get("key") == layer["key"]:
        return [(layer_label, layer_path)]
    return [(layer_label, layer_path), (title, path)]


def article_crumb_parts(a, lang):
    """Layer and optional subtopic for an article trail. crumbs() prepends Home."""
    parts = []
    layer_key = (a or {}).get("layer") or ""
    topic = (a or {}).get("topic") or ""
    layer_label = None
    layer_path = None
    if layer_key:
        for layer in LAYERS:
            if layer["key"] == layer_key:
                layer_label = _bi(layer["title"], lang)
                layer_path = layer["path"]
                break
        if layer_label is None and layer_key == "ecosystem":
            layer_label = LANGS[lang].get("nav_eco") or ("Ecosystem" if lang == "en" else "Ecosysteem")
            layer_path = ecosystem_path(lang)
    if layer_label is None and topic:
        nav = _nav_layer_for_topic(topic)
        if nav:
            layer_label = nav["label"][lang]
            layer_path = nav["href"]
            layer_key = layer_key or nav["key"]
    if layer_label is None:
        name, href = topic_meta(a, lang)
        if name:
            parts.append((name, href))
        return parts
    parts.append((layer_label, layer_path))
    if not topic or topic == layer_key:
        return parts
    spec = _specific_topic_hub(topic)
    if spec:
        parts.append((_bi(spec["title"], lang), spec["path"]))
        return parts
    for nav in NAV_LAYERS:
        for item in nav.get("items") or []:
            if item["key"] == topic:
                parts.append((item[lang], item["href"]))
                return parts
    info = TOPIC_LABEL.get(topic)
    if info and info[lang] != layer_label:
        href = ecosystem_path(lang) if topic == "ecosystem" else info["href"]
        parts.append((info[lang], href))
    return parts


def article_crumbs(a, lang):
    """Full path Home / Layer / Subtopic, each segment linked to its hub when one exists."""
    return crumbs(lang, article_crumb_parts(a, lang), current=False)


def _rubric_pair(a, lang):
    """Layer and optional distinct subtopic for the line under an image."""
    if not a:
        return "", "", "", ""
    parts = article_crumb_parts(a, lang)
    if not parts:
        return layer_name(a, lang), layer_href(a, lang), "", ""
    layer_label, layer_path = parts[0]
    if len(parts) >= 2 and (parts[1][0] or "").casefold() != (layer_label or "").casefold():
        return layer_label, layer_path, parts[1][0], parts[1][1]
    return layer_label, layer_path, "", ""


def _rubric_mark(text, cls, href, lang, link):
    if not text:
        return ""
    if link and href:
        return f'<a class="{cls}" href="{url(lang, href)}">{esc(text)}</a>'
    return f'<span class="{cls}">{esc(text)}</span>'


def rubric_line(a, lang, stamp="", link=False):
    """Label under an image: grey LAYER / cyan Subtopic · date, or cyan layer · date."""
    layer, layer_path, sub, sub_path = _rubric_pair(a, lang)
    when_html = stamp or (when(a, lang) if a else "")
    if layer and sub:
        label = (
            f'<span class="lpath">{_rubric_mark(layer, "llayer", layer_path, lang, link)}'
            f' / {_rubric_mark(sub, "lsub", sub_path, lang, link)}</span>'
        )
    elif layer:
        label = _rubric_mark(layer, "lname", layer_path, lang, link)
    else:
        label = ""
    if label and when_html:
        return f'<span class="lmeta">{label} · {when_html}</span>'
    if label:
        return f'<span class="lmeta">{label}</span>'
    if when_html:
        return f'<span class="lmeta">{when_html}</span>'
    return ""


def home_videos(arts, lang, n=8):
    """Compact strip of the newest stories that have a long video or a Short. Links to the article.
    Always newest first; stories already shown as layer cards are not skipped."""
    by = {a["slug"]: a for a in arts}
    rows = []
    seen = set()
    for (slug, vlang), video in VIDEOS.items():
        if vlang not in ("en", lang) or slug not in by or slug in seen:
            continue
        seen.add(slug)
        rows.append((by[slug], video.get("seconds") or 0, False))
    for slug, short in SHORTS.items():
        if slug not in by or slug in seen:
            continue
        seen.add(slug)
        rows.append((by[slug], 0, True))
    rows.sort(key=lambda row: published(row[0]), reverse=True)
    rows = rows[:n]
    cards = []
    for a, seconds, is_short in rows:
        t = a[lang]
        href = url(lang, a["slug"] + "/")
        if is_short:
            badge = "Short"
        elif seconds:
            badge = f"{int(seconds) // 60}:{int(seconds) % 60:02d}"
        else:
            badge = LANGS[lang]["videos"]
        tone = layer_tone(a)
        src, portrait = short_visual(a) if is_short else ("", False)
        if not src:
            src = site_img(a)
        mark = (f'<span class="vpl" aria-hidden="true"></span>'
                f'<span class="dur dvo">{esc(badge)}</span>')
        cards.append(
            f'<div class="vcard {tone}"><a class="lgo" href="{href}">'
            f'{still_box("span", "vim zimg", src, t["title"], SIZES_VIDEO, portrait=portrait, width=480, height=270, mark=mark)}</a>'
            f'{with_actions(rubric_line(a, lang), "", lang, href)}'
            f'<a class="lgo" href="{href}"><strong>{esc(card_title(a, lang))}</strong></a></div>')
    return "".join(cards), [a for a, _, _ in rows]


def home_topics(arts, shown, lang):
    L = LANGS[lang]
    out = []
    for _key, label_key, path, keys in HOME_TOPICS:
        pool = [a for a in arts if _in_topics(a, keys)]
        if not pool:
            continue
        pick = sorted(pool, key=published, reverse=True)[:3]
        title = L[label_key] if label_key else CATEGORIES["guides"][lang]
        cards = f'<div class="topics3">{"".join(gcard(a, lang) for a in pick)}</div>'
        label = {"en": f"All {title} articles", "nl": f"Alle artikelen over {title}"}[lang]
        out.append(f'<section class="hsec"><div class="h2"><h2>{esc(title)}</h2>'
                   f'<a href="{url(lang, path)}" aria-label="{esc(label)}">{esc(L["see_all"])}</a></div>{cards}</section>')
    return "".join(out)


def _side_section(title, inner):
    if not inner:
        return ""
    return f'<section><h2>{esc(title)}</h2>{inner}</section>'


def _side_links(items):
    return "".join(f'<li><a href="{href}">{esc(name)}</a></li>' for name, href in items)


def _side_ol(lang, items):
    return "<ol>" + _side_links([(x[lang]["title"], url(lang, x["slug"] + "/")) for x in items]) + "</ol>"


def _side_ul(lang, items, cls=""):
    klass = f' class="{cls}"' if cls else ""
    return f"<ul{klass}>" + _side_links([(x[lang]["title"], url(lang, x["slug"] + "/")) for x in items]) + "</ul>"


def _recommend_context(kind, current):
    """Which shopping moment this page is. Unrelated news falls back to the guides."""
    if kind == "article" and isinstance(current, dict):
        slug = str(current.get("slug") or "")
        cat = str(current.get("category") or "")
        models = current.get("models") or []
        if cat == "starlink" or "starlink" in slug:
            return "starlink"
        if "sentry" in slug or "dashcam" in slug:
            return "sentry"
        if cat == "charging" or any(bit in slug for bit in ("wall-connector", "charging", "charger")):
            return "charging"
        if any(str(m).startswith(("model-3", "model-y")) for m in models) or any(
                bit in slug for bit in ("winter", "tyre", "tire", "floor-mat", "accessory")):
            return "mats"
        return "default"
    if kind == "model" and isinstance(current, str) and current.startswith(("model-3", "model-y")):
        return "accessories"
    if kind == "hub" and current == "starlink":
        return "starlink"
    if kind == "hub" and current in ("tesla", "cars", "models"):
        return "mats"
    if kind == "hub" and current in ("tesla-energy", "energy"):
        return "charging"
    return "default"


def _article_asins(current):
    found = set()
    if not isinstance(current, dict):
        return found
    for product in current.get("products") or []:
        if isinstance(product, dict):
            asin = str(product.get("asin") or "").strip().upper()
            if asin:
                found.add(asin)
    return found


def recommend_block(lang, kind, current):
    """Compact sidebar. Two or three real products, or links to the buying guides."""
    path = ROOT / "content" / "picks.json"
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return ""
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    contexts = data.get("contexts") if isinstance(data.get("contexts"), dict) else {}
    keys = contexts.get(_recommend_context(kind, current)) or contexts.get("default") or []
    if not isinstance(keys, list):
        return ""
    used = _article_asins(current)
    title = "Recommended" if lang == "en" else "Aanbevolen"
    rows = []
    amazon = False
    for key in keys:
        if len(rows) == 3:
            break
        key = str(key)
        if key.startswith("guide:"):
            slug = key.split(":", 1)[1]
            doc = next((d for d in GUIDE_DOCS if d["slug"] == slug and not d.get("template")), None)
            if doc is None:
                continue
            name = doc["meta"].get(f"title_{lang}") or doc["meta"].get("title_en") or slug
            href = url(lang, guides_path(lang) + slug + "/")
            thumb = side_thumb(guide_lead_photo(doc), name, href)
            klass = "hasimg" if thumb else ""
            rows.append(f'<li class="{klass}">{thumb}<div class="rt"><a href="{esc(href)}">{esc(name)}</a></div></li>')
            continue
        item = items.get(key)
        if not isinstance(item, dict):
            continue
        asin = str(item.get("asin") or "").strip().upper()
        if asin and asin in used:
            continue
        name = str(_loc(item.get("name"), lang)).strip()
        why = str(_loc(item.get("why"), lang)).strip()
        href = amazon_nl_href(item, lang)
        if not name or not href:
            continue
        note = f"<span>{esc(why)}</span>" if why else ""
        src, _remote = product_photo(item)
        thumb = side_thumb(src, name, href, sponsored=True)
        klass = "hasimg" if thumb else ""
        rows.append(
            f'<li class="{klass}">{thumb}<div class="rt"><a href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{esc(name)}</a>{note}</div></li>')
        amazon = True
    if not rows:
        return ""
    note = disclosure_line(lang) if amazon else ""
    return f'<section class="rec"><h2>{esc(title)}</h2><ul>{"".join(rows)}</ul>{note}</section>'


def page_side(arts, lang, kind="home", current=None, skip=None, tail="", signup=True, shop=False):
    """Right column. Sections with nothing to show are left out. Latest News is always newest first."""
    L = LANGS[lang]
    C = pv_copy(lang)
    # skip: articles already visible in the main column (used for related, not for Latest News).
    main_ids = {id(x) for x in (skip or [])}
    if kind == "article" and current is not None:
        main_ids.add(id(current))
    start = []
    if kind != "guides":
        # Guides stay in Start here even when the hub column already lists them.
        guides = sorted(
            (x for x in arts if x["category"] == "guides" and x is not current),
            key=lambda x: words(x, "en"), reverse=True)
        start = guides[:6]
    start_ids = {id(x) for x in start}
    # Latest News lists the newest non-guide stories. The current article is omitted on article pages.
    show_latest = kind in ("home", "static", "videos", "model", "saved", "hub", "guides", "article", "archive")
    if kind == "hub" and current == "news":
        show_latest = False
    latest = []
    if show_latest:
        # Always the newest news, even when those stories already appear in the main column.
        ban = set(start_ids)
        if kind == "article" and current is not None:
            ban.add(id(current))
        for x in sorted(arts, key=published, reverse=True):
            if x["category"] == "guides" or id(x) in ban:
                continue
            latest.append(x)
            if len(latest) == 10:
                break
    related_items = []
    if kind == "article" and current is not None:
        ban = main_ids | start_ids
        related_items = [x for x in related(current, arts, 12) if id(x) not in ban][:5]
    parts = []
    related_html = ""
    # Homepage: Latest is the first block, so its red rule lines up with the lead photo.
    if kind == "article":
        if related_items:
            block = _side_section(C["related"], _side_ol(lang, related_items))
            # Related stays its own piece so the bar can sit under it on a phone.
            # Desktop wraps both sidebar pieces in one rail so they stack.
            if tail:
                related_html = f'<aside class="pv-side arel">{block}</aside>'
            else:
                parts.append(block)
        if latest:
            parts.append(ticker_bar(lang) + _side_section(L["latest"], _side_ul(lang, latest, "latest")))
        if start:
            parts.append(_side_section(C["start"], _side_ol(lang, start)))
    else:
        if latest:
            parts.append(ticker_bar(lang) + _side_section(L["latest"], _side_ul(lang, latest, "latest")))
        if start:
            parts.append(_side_section(C["start"], _side_ol(lang, start)))
    news = newsletter(lang, "side")
    slot = ad_html("sidebar", lang)
    if slot:
        parts.insert(0, slot)
    if signup:
        # The rail form is in the HTML for desktop. At the stack breakpoint
        # CSS hides .nlside, so a phone keeps only the article bar.
        parts.append(rail_signup(lang, script=not tail))
    hubs = evergreen_side(lang)
    if hubs:
        parts.append(hubs)
    if shop:
        cards = guide_category_cards(lang, current if isinstance(current, str) else "")
        if cards:
            parts.insert(0, cards)
    guides = buying_guides_side(lang)
    if guides and not shop:
        parts.append(guides)
    rec = recommend_block(lang, kind, current)
    if rec:
        parts.append(rec)
    if news:
        parts.append(news)
    inner = "".join(parts)
    # Desktop and tablet: this copy leads the sidebar, above Related or whatever is first.
    # The copy inside the column stays for phones, where this one is hidden.
    top = ticker_bar(lang, top=True, script=False)
    if tail and kind == "article" and related_html:
        aside = f'<aside class="pv-side">{inner}</aside>' if inner else ""
        return f'<div class="sheet-rail">{top}{related_html}{aside}</div>{tail}'
    aside = f'<aside class="pv-side">{top}{inner}</aside>' if (top or inner) else ""
    if tail and kind == "article":
        return f"{aside}{tail}"
    return aside


def shell(main, side, extra=""):
    """Same centered content column and sidebar on every page.

    A leading breadcrumb is hoisted to a full-width sheet row so the red
    rule on the sidebar lines up with the first image in the main column.
    """
    klass = f"sheet {extra}".strip()
    crumb = ""
    if main.startswith('<nav class="crumbs"'):
        end = main.find("</nav>")
        if end != -1:
            crumb = main[:end + len("</nav>")]
            main = main[end + len("</nav>"):]
    return f'<div class="{klass}">{crumb}<div class="sheet-main">{main}</div>{side}</div>'


def layer_latest(arts, lang):
    """One card per ecosystem layer: its newest article, or a note when coverage has not started."""
    used = set()
    cards = []
    shown = []
    note = "Coverage starting" if lang == "en" else "Verslaggeving start binnenkort"
    for layer in LAYERS:
        name = _bi(layer["title"], lang)
        tone = layer["tone"]
        pick = next((a for a in _layer_articles(layer, arts) if id(a) not in used), None)
        if pick is None:
            cards.append(
                f'<a class="lcard empty {tone}" href="{url(lang, layer["path"])}">'
                f'<span class="lmeta"><span class="lname">{esc(name)}</span></span>'
                f'<span class="lbody"><strong>{esc(note)}</strong></span></a>')
            continue
        used.add(id(pick))
        shown.append(pick)
        t = pick[lang]
        cards.append(
            f'<div class="lcard {tone}"><a class="lgo" href="{url(lang, pick["slug"] + "/")}">'
            f'<span class="lim zimg">{resp_img(site_img(pick), t["title"], "(max-width: 699px) 46vw, 220px", lazy=False, width=640, height=360)}</span></a>'
            f'{with_actions(rubric_line(pick, lang), "", lang, url(lang, pick["slug"] + "/"))}'
            f'<a class="lgo" href="{url(lang, pick["slug"] + "/")}"><span class="lbody"><strong>{esc(card_title(pick, lang))}</strong></span></a></div>')
    label = "Latest from each layer" if lang == "en" else "Het laatste per laag"
    return f'<section class="layerrow" aria-label="{esc(label)}">{"".join(cards)}</section>', shown


def home_grid_card(a, lang, eager=False, badge=""):
    """Article card: rubric flush under the photo, title below. A video badge sits on the photo."""
    t = a[lang]
    href = url(lang, a["slug"] + "/")
    src, portrait = short_visual(a)
    if not src:
        src = site_img(a)
    photo = still_box("span", "lim zimg", src, t["title"], "(max-width: 599px) 92vw, (max-width: 900px) 46vw, 280px",
                      portrait=portrait, high=eager, lazy=not eager, mark=card_mark(a, lang, badge))
    return (
        f'<div class="lcard"><a class="lgo" href="{href}">'
        f'{photo}</a>'
        f'{with_actions(rubric_line(a, lang), "", lang, href)}'
        f'<a class="lgo" href="{href}"><span class="lbody"><strong>{esc(card_title(a, lang))}</strong></span></a></div>')


def story_badge(a):
    """Duration of the long video, else Short. A story with both shows the long video."""
    video = video_for(a, "en")
    if video:
        sec = int(video.get("seconds") or 0)
        if sec:
            return f"{sec // 60}:{sec % 60:02d}"
        return "Video"
    if SHORTS.get(a["slug"]):
        return "Short"
    return ""


def parse_published(raw):
    """YouTube publish time from videos.json or shorts.json, in the site timezone."""
    dt = datetime.fromisoformat(str(raw))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def stamp_html(stamp, lang):
    return f'<time class="ago" datetime="{stamp.isoformat()}">{esc(rel_short(stamp, lang))}</time>'


def clip_layer_name(title):
    guess = (title or "").lower()
    if "starlink" in guess:
        return "Starlink"
    if "spacex" in guess or "starship" in guess or "falcon" in guess:
        return "SpaceX"
    if "neuralink" in guess:
        return "Neuralink"
    if "boring" in guess:
        return "Boring Co"
    return "Tesla"


def home_items(arts):
    """One item per story. A video that belongs to an article is a badge on that article.
    A video or Short with no article stays its own item, ordered by its YouTube time."""
    by = {a["slug"]: a for a in arts}
    items = [{
        "kind": "article",
        "stamp": published(a),
        "article": a,
        "badge": story_badge(a),
        "title": "",
        "id": "",
        "seconds": 0,
        "path": a["slug"] + "/",
    } for a in arts]
    seen = set()
    for video in VIDEOS.values():
        vid = video.get("id") or ""
        slug = video.get("slug") or ""
        if not vid or vid in seen or slug in by:
            continue
        seen.add(vid)
        items.append({
            "kind": "video",
            "stamp": parse_published(video.get("published") or ""),
            "article": None,
            "badge": "",
            "title": video.get("title") or "",
            "id": vid,
            "seconds": int(video.get("seconds") or 0),
            "path": f"videos/{vid}/",
        })
    for short in SHORT_ROWS:
        vid = short.get("id") or ""
        slug = short.get("slug") or ""
        if not vid or vid in seen or slug in by:
            continue
        seen.add(vid)
        items.append({
            "kind": "short",
            "stamp": parse_published(short.get("published") or ""),
            "article": None,
            "badge": "",
            "title": short.get("title") or "",
            "id": vid,
            "seconds": 0,
            "path": f"shorts/{vid}/",
        })
    items.sort(key=lambda item: item["stamp"], reverse=True)
    return items


def clip_items(arts):
    """Articles, long videos and Shorts, each once. Used by the videos index and watch pages."""
    by = {a["slug"]: a for a in arts}
    items = [{
        "kind": "article",
        "stamp": published(a),
        "article": a,
        "title": "",
        "id": "",
        "seconds": 0,
        "path": a["slug"] + "/",
    } for a in arts]
    seen = set()
    for (_slug, _vlang), video in VIDEOS.items():
        vid = video.get("id") or ""
        if not vid or vid in seen:
            continue
        seen.add(vid)
        items.append({
            "kind": "video",
            "stamp": parse_published(video.get("published") or ""),
            "article": by.get(video.get("slug")),
            "title": video.get("title") or "",
            "id": vid,
            "seconds": int(video.get("seconds") or 0),
            "path": f"videos/{vid}/",
        })
    for short in SHORT_ROWS:
        vid = short.get("id") or ""
        if not vid or vid in seen:
            continue
        seen.add(vid)
        items.append({
            "kind": "short",
            "stamp": parse_published(short.get("published") or ""),
            "article": by.get(short.get("slug") or ""),
            "title": short.get("title") or "",
            "id": vid,
            "seconds": 0,
            "path": f"shorts/{vid}/",
            "poster": short.get("poster") or "",
        })
    items.sort(key=lambda item: item["stamp"], reverse=True)
    return items


def clip_badge(item):
    if item["kind"] == "short":
        return "Short"
    sec = int(item.get("seconds") or 0)
    if sec:
        return f"{sec // 60}:{sec % 60:02d}"
    return "Video"


def whole_minutes(seconds):
    """Video length in whole minutes, at least one."""
    seconds = int(seconds or 0)
    if seconds <= 0:
        return 1
    return max(1, round(seconds / 60))


def list_badge(top, sub):
    """The same boxed badge on every dated-list row: red figure, small label under it."""
    return f'<span class="pv-min"><b>{esc(str(top))}</b><small>{esc(sub)}</small></span>'


def story_list_badge(a, lang):
    """A live story shows LIVE. A story with a video shows that video. A plain article shows its reading time."""
    if is_live(a):
        return '<span class="pv-min live"><b>LIVE</b><small></small></span>'
    video = video_for(a, "en")
    if video:
        return list_badge("Video", f"{whole_minutes(video.get('seconds') or 0)} min")
    if SHORTS.get(a["slug"]):
        return list_badge("Short", "1 min")
    return list_badge(read_time(a, lang), "min")


def clip_meta(item, lang):
    stamp = stamp_html(item["stamp"], lang)
    article = item.get("article")
    if article:
        return rubric_line(article, lang, stamp)
    return f'<span class="lmeta"><span class="lname">{esc(clip_layer_name(item.get("title") or ""))}</span> · {stamp}</span>'


def yt_thumb(vid):
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"


def clip_card(item, lang, eager=False):
    """News card. Articles keep their photo. A video uses its own thumbnail, title and badge."""
    if item["kind"] == "article":
        return home_grid_card(item["article"], lang, eager)
    title = item["title"]
    row = next((sh for sh in SHORT_ROWS if sh.get("id") == item.get("id")), {}) if item["kind"] == "short" else {}
    local = short_poster(row)
    src = local or yt_thumb(item["id"])
    badge = f'<span class="dur dvo">{esc(clip_badge(item))}</span><span class="vpl" aria-hidden="true"></span>'
    href = url(lang, item["path"])
    article = item.get("article")
    photo = still_box("span", "lim zimg", src, title, "(max-width: 599px) 92vw, (max-width: 900px) 46vw, 280px",
                      portrait=bool(local), high=eager, lazy=not eager, mark=badge)
    return (
        f'<div class="lcard"><a class="lgo" href="{href}">'
        f'{photo}</a>'
        f'{with_actions(clip_meta(item, lang), "", lang, href)}'
        f'<a class="lgo" href="{href}"><span class="lbody"><strong>{esc(title)}</strong></span></a></div>')


def home_card(item, lang, eager=False):
    """Article cards link to the article. Only a video with no article links to its watch page."""
    if item["kind"] == "article":
        return home_grid_card(item["article"], lang, eager, item.get("badge") or "")
    return clip_card(item, lang, eager)


def home_feed(items, lang):
    """Dated newest-first list. Every row uses the same badge. One row per story."""
    out, last = [], None
    for item in items:
        day = item["stamp"].astimezone(TZ).date().isoformat()
        if day != last:
            out.append(f'<h2 class="pv-day">{fmt_date(day, lang)}</h2>')
            last = day
        if item["kind"] == "article":
            out.append(pv_row(item["article"], lang))
            continue
        if item["kind"] == "short":
            badge = list_badge("Short", "1 min")
        else:
            badge = list_badge("Video", f"{whole_minutes(item.get('seconds') or 0)} min")
        out.append(
            f'<a class="pv-row" href="{url(lang, item["path"])}">'
            f'<time datetime="{item["stamp"].isoformat()}">{item["stamp"].strftime("%H:%M")}</time>'
            f'<span class="pv-hl"><b>{esc(item["title"])}</b></span>'
            f'{badge}</a>')
    return "".join(out)


TICKER = {}
TICKER_QUOTES = (
    ("tsla", "TSLA", "TSLA", "Tesla, Inc."),
    ("spcx", "SPCX", "SPCX", "Space Exploration Technologies"),
    ("nvda", "NVDA", "NVDA", "NVIDIA"),
    ("googl", "GOOGL", "GOOGL", "Alphabet"),
    ("rklb", "RKLB", "RKLB", "Rocket Lab"),
    ("asts", "ASTS", "ASTS", "AST SpaceMobile"),
    ("ixic", "^IXIC", "Nasdaq", "NASDAQ Composite"),
)
TICKER_JS = r"""(function(){
var bars=[].slice.call(document.querySelectorAll('.ticker'));
if(!bars.length)return;
var nl=document.documentElement.lang==='nl';
var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
function esc(s){return String(s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]})}
function pace(){if(reduce)return;bars.forEach(function(bar){
if(getComputedStyle(bar).display==='none')return;
var track=bar.querySelector('.tk-track');if(!track)return;
var px=track.scrollWidth/2;if(px>40)track.style.animationDuration=Math.max(39,px/33)+'s';
});}
function slots(){var out=[];bars.forEach(function(bar){bar.querySelectorAll('[data-tk="launch"]').forEach(function(el){out.push(el);});});return out;}
function hide(){slots().forEach(function(el){el.hidden=true;});pace();}
fetch('https://ll.thespacedevs.com/2.2.0/launch/upcoming/?lsp__id=121&limit=8&mode=list').then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(d){
var now=Date.now(),best=null;(d.results||[]).forEach(function(x){var net=Date.parse(x.net||''),st=(x.status&&x.status.abbrev)||'';
if(!(net>now)||st==='Success'||st==='Failure')return;if(!best||net<best.net)best={net:net,name:String(x.name||'')}});
if(!best){hide();return}
var bits=best.name.split('|'),name=bits.length>1?bits[bits.length-1].trim():'';
function paint(){var left=best.net-Date.now();if(left<=0){hide();return}
var s=Math.floor(left/1000),days=Math.floor(s/86400);s-=days*86400;var h=Math.floor(s/3600);s-=h*3600;var m=Math.floor(s/60);
var clock=(days?days+'d ':'')+h+'h '+m+'m';
var html='<b>'+(nl?'Volgende lancering':'Next launch')+'</b> '+esc(clock)+(name?' \u00b7 '+esc(name):'');
slots().forEach(function(el){el.hidden=false;el.innerHTML=html});pace();}
paint();setInterval(paint,30000);}).catch(hide);
pace();
window.addEventListener('resize',pace);
})();"""


def ticker_num(n, lang, decimals):
    """Grouped number. Dutch uses a dot for thousands and a comma for the decimal."""
    text = f"{n:,.{decimals}f}" if decimals else f"{n:,.0f}"
    if lang == "nl":
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


def ticker_when(iso, lang):
    dt = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
    short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    nl = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
    month = nl[dt.month - 1] if lang == "nl" else short[dt.month - 1]
    return f"{dt.day} {month} {dt.year}"


def _ticker_file(name):
    return json.loads((ROOT / "content" / "data" / name).read_text(encoding="utf-8"))


def _latest_hub_event(key):
    data = _ticker_file("evergreen.json")
    hub = next((item for item in data.get("hubs") or [] if item.get("key") == key), None)
    events = [event for event in (hub or {}).get("events") or [] if str(event.get("date") or "")[:10]]
    if not events:
        return None
    return max(events, key=lambda event: event["date"])


def ticker_quote_html(key, label, quote, lang, href):
    up = quote["c"] >= 0
    sign = "+" if up else "\u2212"
    kind = "up" if up else "dn"
    money = "" if key == "ixic" else "$"
    price = ticker_num(quote["p"], lang, 2)
    change = ticker_num(abs(quote["c"]), lang, 2)
    pct = ticker_num(abs(quote["pct"]), lang, 1)
    when = f'<span class="when">{esc(ticker_when(quote["d"], lang))}</span>' if quote.get("d") else ""
    inner = (f"<b>{esc(label)}</b> {money}{price} "
             f'<span class="{kind}">{sign}{change} ({sign}{pct}%)</span>{when}')
    if href:
        return f'<a class="tk" href="{url(lang, href)}">{inner}</a>'
    return f'<span class="tk">{inner}</span>'


def ticker_fact(text, when, lang, href, lead=""):
    inner = f"{lead}{esc(text)}<span class=\"when\">{esc(when)}</span>"
    return f'<a class="tk" href="{url(lang, href)}">{inner}</a>'


def ticker_delivery(lang):
    event = _latest_hub_event("deliveries")
    if not event:
        return ""
    match = re.search(
        r"delivered ([\d,]+) vehicles in the (first|second|third|fourth) quarter of (\d{4})",
        event["text"]["en"])
    if not match:
        return ""
    count = int(match.group(1).replace(",", ""))
    quarter = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}[match.group(2)]
    shown = ticker_num(count, lang, 0)
    if lang == "en":
        text = f"Tesla {quarter} {match.group(3)} deliveries {shown}"
    else:
        text = f"Tesla {quarter} {match.group(3)} leveringen {shown}"
    return ticker_fact(text, ticker_when(event["date"], lang), lang, "tesla-deliveries/")


def ticker_fsd(lang):
    event = _latest_hub_event("fsd-europe")
    if not event or "every month" not in event["text"]["en"]:
        return ""
    text = "FSD Europe: RDW checks monthly" if lang == "en" else "FSD Europa: RDW controleert maandelijks"
    return ticker_fact(text, ticker_when(event["date"], lang), lang, "fsd-in-europe/")


def ticker_starlink_nl(lang):
    event = _latest_hub_event("starlink-nl")
    if not event or "across the Netherlands" not in event["text"]["en"]:
        return ""
    text = "Starlink available across the Netherlands" if lang == "en" else "Starlink in heel Nederland beschikbaar"
    return ticker_fact(text, ticker_when(event["date"], lang), lang, "starlink-netherlands/")


def ticker_starship(lang):
    data = _ticker_file("starship.json")
    updated = str(data.get("updated") or "")
    nxt = data.get("next") or {}
    note = str((nxt.get("note") or {}).get("en") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated) or nxt.get("announced") or "not announced" not in note.lower():
        return ""
    numbers = [flight.get("number") for flight in data.get("flights") or [] if isinstance(flight.get("number"), int)]
    if not numbers:
        return ""
    number = max(numbers) + 1
    text = f"Starship flight {number} not announced" if lang == "en" else f"Starship-vlucht {number} nog niet aangekondigd"
    return ticker_fact(text, ticker_when(updated, lang), lang, "starship/")


def ticker_headlines(lang, limit=3):
    rows = sorted(ALL_ARTS, key=published, reverse=True)[:limit]
    out = []
    for article in rows:
        title = str(article[lang].get("title") or "").strip()
        if not title or "tbeugelink" in title.lower():
            continue
        lead = '<b class="dn">LIVE</b> ' if is_live(article) else ""
        out.append(ticker_fact(title, ticker_when(article["date"], lang), lang, article["slug"] + "/", lead))
    return "".join(out)


def ticker_items(lang):
    """One copy of the line. A missing source is left out, not shown as a blank."""
    parts = []
    quotes = TICKER.get("quotes") or {}
    homes = {"tsla": "tesla/", "spcx": "spacex/"}
    for key, _symbol, label, _expect in TICKER_QUOTES:
        quote = quotes.get(key)
        if not quote:
            continue
        parts.append(ticker_quote_html(key, label, quote, lang, homes.get(key, "")))
    parts.append(
        f'<a class="tk" data-tk="launch" hidden href="{url(lang, "spacex/")}"></a>')
    count = TICKER.get("starlink")
    if isinstance(count, int) and count > 1000 and TICKER.get("starlink_d"):
        shown = ticker_num(count, lang, 0)
        text = f"Starlink {shown} in orbit" if lang == "en" else f"Starlink {shown} in een baan"
        parts.append(ticker_fact(text, ticker_when(TICKER["starlink_d"], lang), lang, "starlink/"))
    for piece in (ticker_starship(lang), ticker_delivery(lang), ticker_fsd(lang), ticker_starlink_nl(lang)):
        if piece:
            parts.append(piece)
    parts.append(ticker_headlines(lang))
    return "".join(parts)


def ticker_bar(lang, main=False, script=True, top=False):
    """Scrolling one-line ticker. The second copy makes the loop seamless and stays out of tab order.

    The sidebar copy is the desktop lichtkrant. The main copy is the same line on a phone,
    between the cards and the dated list, and the script drives whichever one is visible.
    top=True is the copy placed first in the sidebar from tablet width up.
    """
    items = ticker_items(lang)
    if not items:
        return ""
    clone = items.replace("<a ", '<a tabindex="-1" ')
    label = "News ticker" if lang == "en" else "Lichtkrant"
    if main:
        klass, ident = "ticker ticker-main", ""
    elif top:
        klass, ident = "ticker ticker-top", ""
    else:
        klass, ident = "ticker", ' id="ticker"'
    html = (
        f'<div class="{klass}"{ident} role="region" aria-label="{label}">'
        f'<div class="tk-track"><div class="tk-set">{items}</div>'
        f'<div class="tk-set" aria-hidden="true">{clone}</div></div></div>')
    if script:
        html += f"<script>{TICKER_JS}</script>"
    return html


def _fetch_quote(symbol, expect):
    import urllib.request
    req = urllib.request.Request(
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + quote(symbol, safe="") + "?interval=1d&range=5d",
        headers={"User-Agent": "TrendingTesla/1.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        chart = json.load(response)["chart"]["result"][0]
    meta = chart.get("meta") or {}
    name = f"{meta.get('longName') or ''} {meta.get('shortName') or ''}"
    if expect.lower() not in name.lower() or meta.get("currency") != "USD":
        return None
    closes = [c for c in chart["indicators"]["quote"][0]["close"] if isinstance(c, (int, float))]
    if len(closes) < 2 or not closes[-2]:
        return None
    price, prev = closes[-1], closes[-2]
    change = price - prev
    stamp = meta.get("regularMarketTime")
    day = ""
    if isinstance(stamp, (int, float)):
        zone = meta.get("exchangeTimezoneName") or "America/New_York"
        try:
            day = datetime.fromtimestamp(stamp, ZoneInfo(zone)).date().isoformat()
        except Exception:
            day = ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return None
    return {"p": round(price, 2), "c": round(change, 2), "pct": round(change / prev * 100, 2), "d": day}


def write_ticker():
    """Build-time quotes and the Starlink count. A failed fetch is omitted."""
    import urllib.request
    data = {"quotes": {}}
    for key, symbol, _label, expect in TICKER_QUOTES:
        try:
            quote_row = _fetch_quote(symbol, expect)
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            quote_row = None
        if quote_row:
            data["quotes"][key] = quote_row
    for _try in range(2):
        try:
            req = urllib.request.Request(
                "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=json",
                headers={"User-Agent": "TrendingTesla/1.0"})
            with urllib.request.urlopen(req, timeout=40) as response:
                chunks, size = [], 0
                while size < 40_000_000:
                    block = response.read(1_000_000)
                    if not block:
                        break
                    chunks.append(block)
                    size += len(block)
            rows = json.loads(b"".join(chunks))
            if isinstance(rows, list) and len(rows) > 1000:
                data["starlink"] = len(rows)
                data["starlink_d"] = datetime.now(TZ).date().isoformat()
            break
        except (OSError, ValueError, TypeError):
            continue
    TICKER.clear()
    TICKER.update(data)
    (OUT / "ticker.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def homepage(arts, lang):
    """Newest stories, one card each. A video on an article is a badge, not a second card."""
    L = LANGS[lang]
    nav, crumb_ld = crumbs(lang, [])
    if not arts:
        return shell(f'{nav}<h1>{esc(NAME)}</h1><p class="empty">{L["empty"]}</p>', page_side(arts, lang, "home")), crumb_ld
    ordered = home_items(arts)
    grid = ordered[:MAX_HOME_CARDS]
    # The dated list repeats the cards above on purpose, then continues through every story.
    feed = ordered
    label = "Latest news" if lang == "en" else "Het laatste nieuws"
    cards = "".join(home_card(item, lang, eager=i < 4) for i, item in enumerate(grid))
    row = f'<section class="homenews" aria-label="{esc(label)}">{cards}</section>'
    # Phone shows this copy between the cards and the dated list. Desktop hides it.
    main = (f'{nav}<h1 class="visually-hidden">{esc(NAME)}</h1>{row}'
            f'{ticker_bar(lang, main=True, script=False)}'
            f'<div class="hfeed">{home_feed(feed, lang)}</div>')
    shown = [item["article"] for item in (*grid, *feed) if item["kind"] == "article" and item.get("article")]
    return shell(main, page_side(arts, lang, "home", skip=shown), "front"), crumb_ld


def iso_duration(seconds):
    seconds = int(seconds or 0)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    out = "PT"
    if hours:
        out += f"{hours}H"
    if minutes:
        out += f"{minutes}M"
    out += f"{secs}S"
    return out


def clip_page(item, arts, lang):
    """One watch page: click-to-load embed, the video's title, a description, and the related article."""
    L = LANGS[lang]
    title = item["title"] or (L["watch_short"] if item["kind"] == "short" else L["watch"])
    article = item.get("article")
    desc = article[lang]["description"] if article else title
    kind = "short" if item["kind"] == "short" else "long"
    label = L["watch_short"] if kind == "short" else L["watch"]
    poster = short_poster({"poster": item.get("poster")}) or yt_thumb(item["id"])
    play = player(item["id"], kind, label, poster, True, title)
    story = ""
    if article:
        story = f'<p><a href="{url(lang, article["slug"] + "/")}">{esc(L["read_story"])}</a></p>'
    slug = article["slug"] if article else item["id"]
    body = (f'<article class="money"><h1>{esc(title)}</h1>{play}'
            f'{with_actions(clip_meta(item, lang), slug, lang)}'
            f'<p class="lead">{esc(desc)}</p>{story}</article>')
    video_ld = {
        "@context": "https://schema.org", "@type": "VideoObject",
        "name": title, "description": desc,
        "thumbnailUrl": [yt_thumb(item["id"])],
        "uploadDate": item["stamp"].isoformat(),
        "embedUrl": f"https://www.youtube-nocookie.com/embed/{item['id']}",
        "url": SITE + url(lang, item["path"]),
        "inLanguage": lang,
        "publisher": {"@type": "Organization", "name": NAME, "url": SITE},
    }
    if item.get("seconds"):
        video_ld["duration"] = iso_duration(item["seconds"])
    section = "Videos" if lang == "en" else "Video's"
    hub = "videos/" if item["kind"] == "video" else "shorts/"
    hub_name = section if item["kind"] == "video" else "Shorts"
    _nav, crumb_ld = crumbs(lang, [(hub_name, hub), (title, None)])
    return body, ld_script(video_ld) + ld_script(crumb_ld), desc


def videos_index(arts, lang):
    """Long videos, newest YouTube publish time first, in the same card style as the homepage."""
    items = [item for item in clip_items(arts) if item["kind"] == "video"]
    title = "Videos" if lang == "en" else "Video's"
    intro = ("Longer videos, newest first." if lang == "en" else "Langere video's, nieuwste eerst.")
    cards = "".join(clip_card(item, lang, eager=i < 3) for i, item in enumerate(items))
    empty = "No videos yet." if lang == "en" else "Nog geen video's."
    grid = f'<section class="homenews" aria-label="{esc(title)}">{cards}</section>' if cards else f'<p class="empty">{esc(empty)}</p>'
    body = f'<section class="wide"><h1 class="st archh">{esc(title)}</h1>{grid}</section>'
    shown = [item["article"] for item in items if item.get("article")]
    return body, title, intro, shown


def pv_copy(lang):
    en = lang == "en"
    return {
        "all": "All" if en else "Alles",
        "note": "Layout preview. Not indexed. The live site is unchanged." if en else "Voorbeeld van de indeling. Niet geïndexeerd. De live site blijft zoals hij is.",
        "open": "Sample article" if en else "Voorbeeldartikel",
        "live": "Live homepage" if en else "Live homepagina",
        "guides": "Guides" if en else "Gidsen",
        "start": "Tesla drivers" if en else "Tesla rijders",
        "gear": "Gear" if en else "Spullen",
        "gear_off": "Product boxes show up here when an article opts in. No prices, and nothing until a tag is set." if en else "Productblokken verschijnen hier als een artikel ervoor kiest. Geen prijzen, en niets tot er een tag is ingevuld.",
        "related": "Related" if en else "Gerelateerd",
        "more": "Compare" if en else "Vergelijk",
    }


PV_TABS = (
    ("models", "nav_models", "category/models/"),
    ("energy", "nav_energy", "tesla-energy/"),
    ("fsd", "nav_fsd", "fsd/"),
    ("spacex", "nav_space", "spacex/"),
    ("xai", "nav_xai", "spacexsi/"),
    ("guides", None, "category/guides/"),
    ("videos", "videos", "shorts/"),
)


def pv_tabs(lang, variant):
    L = LANGS[lang]
    C = pv_copy(lang)
    here = url(lang, f"preview/{variant}/")
    links = f'<a class="on" href="{here}">{C["all"]}</a>'
    for _key, label_key, path in PV_TABS:
        label = L[label_key] if label_key else CATEGORIES["guides"][lang]
        links += f'<a href="{url(lang, path)}">{esc(label)}</a>'
    return f'<nav class="pv-tabs" aria-label="{esc(L["menu"])}">{links}</nav>'


def pv_banner(lang, variant, blurb):
    C = pv_copy(lang)
    bits = [f'<b>{variant.upper()}</b> {esc(blurb)} {esc(C["note"])}']
    bits.append(f'<a href="{url(lang, "preview/")}">{C["more"]}</a>')
    bits.append(f'<a href="{url(lang, f"preview/{variant}/article/")}">{C["open"]}</a>')
    bits.append(f'<a href="{url(lang)}">{C["live"]}</a>')
    return f'<p class="pv-note">{" · ".join(bits)}</p>'


def pv_row(a, lang, thumb=False):
    t = a[lang]
    href = url(lang, a["slug"] + "/")
    im = ""
    if thumb:
        im = (f'<span class="pv-th zimg">{resp_img(site_img(a), t["title"], "(max-width: 700px) 22vw, 64px", width=256, height=144)}'
              f'{ovl(a, lang)}</span>')
    shown = card_title(a, lang)
    return (f'<a class="pv-row{" hasth" if thumb else ""}" href="{href}" title="{esc(t["title"])}">'
            f'<time datetime="{published(a).isoformat()}">{published(a).strftime("%H:%M")}</time>{im}'
            f'<span class="pv-hl"><b>{esc(shown)}</b></span>'
            f'{story_list_badge(a, lang)}</a>')


def pv_feed(items, lang, thumbs=0):
    out, last = [], None
    for i, a in enumerate(items):
        if a["date"] != last:
            out.append(f'<h2 class="pv-day">{fmt_date(a["date"], lang)}</h2>')
            last = a["date"]
        out.append(pv_row(a, lang, thumb=i < thumbs))
    return "".join(out)


def pv_side(arts, lang, a=None):
    C = pv_copy(lang)
    start = sorted((x for x in arts if x["category"] == "guides"), key=lambda x: words(x, "en"), reverse=True)[:6]
    guides = "".join(
        f'<a class="pv-guide" href="{url(lang, x["slug"] + "/")}">'
        f'{resp_img(site_img(x), "", "72px", width=144, height=81)}'
        f'<span>{rubric_line(x, lang)}<span>{esc(x[lang]["title"])}</span></span></a>'
        for x in start[:3])
    numbered = "".join(
        f'<li><a href="{url(lang, x["slug"] + "/")}">{esc(x[lang]["title"])}</a></li>' for x in start)
    rel = ""
    if a is not None:
        items = related(a, arts, 5)
        if items:
            rel = (f'<section><h2>{esc(C["related"])}</h2><ol>'
                   + "".join(f'<li><a href="{url(lang, x["slug"] + "/")}">{esc(x[lang]["title"])}</a></li>' for x in items)
                   + "</ol></section>")
    gear = product_boxes(a, lang) if a is not None else ""
    if not gear:
        gear = f'<p class="pv-off">{esc(C["gear_off"])}</p>'
    slot = ad_html("sidebar", lang)
    return (f'<aside class="pv-side">{rel}'
            f'<section><h2>{esc(C["guides"])}</h2>{guides}</section>'
            f'<section><h2>{esc(C["start"])}</h2><ol>{numbered}</ol></section>'
            f'<section><h2>{esc(C["gear"])}</h2>{gear}</section>{slot}</aside>')


def pv_lead(a, lang, href):
    t = a[lang]
    return (f'<div class="pv-lead">'
            f'<span class="im zimg">{resp_img(site_img(a), t["title"], SIZES_LEAD, high=True, lazy=False)}{ovl(a, lang)}</span>'
            f'{rubric_line(a, lang)}'
            f'<span><a href="{href}"><h1>{esc(t["title"])}</h1></a></span></div>')


def pv_home(variant, arts, lang):
    en = lang == "en"
    blurbs = {
        "a": "Newsfeed first. Clock times, a compact lead, guides in the side column." if en else "Nieuwslijst voorop. Kloktijden, een compacte hoofdfoto, gidsen in de zijbalk.",
        "b": "Hybrid. The lead story and the video strip stay, then a dense news list." if en else "Hybride. Het hoofdartikel en de videostrip blijven, daarna een dichte nieuwslijst.",
        "c": "Sections. Each topic is its own block, with the same side column." if en else "Rubrieken. Elk onderwerp is een eigen blok, met dezelfde zijbalk.",
    }
    lead = arts[0]
    sample = url(lang, f"preview/{variant}/article/")
    main = pv_banner(lang, variant, blurbs[variant]) + pv_tabs(lang, variant)
    if variant == "a":
        main += pv_lead(lead, lang, sample) + pv_feed(sorted(arts, key=published, reverse=True)[:24], lang, thumbs=4)
    elif variant == "b":
        videos, _strip_arts = home_videos(arts, lang, 8)
        strip = f'<div class="vstrip">{videos}</div>' if videos else ""
        main += home_lead(lead, lang) + strip + pv_feed(sorted(arts, key=published, reverse=True)[:MAX_HOME_FEED], lang, thumbs=2)
    else:
        blocks = []
        for _key, label_key, path, keys in HOME_TOPICS:
            pool = [x for x in arts if _in_topics(x, keys)][:5]
            if not pool:
                continue
            title = LANGS[lang][label_key] if label_key else CATEGORIES["guides"][lang]
            head = pool[0]
            rows = pv_feed(pool[1:], lang, thumbs=0)
            blocks.append(
                f'<section class="pv-block"><div class="h2"><h2>{esc(title)}</h2>'
                f'<a href="{url(lang, path)}">{esc(LANGS[lang]["see_all"])}</a></div>'
                f'<div class="pv-lead">'
                f'<span class="im zimg">{resp_img(site_img(head), "", SIZES_CARD)}{ovl(head, lang)}</span>'
                f'{rubric_line(head, lang)}'
                f'<a href="{url(lang, head["slug"] + "/")}"><h2>{esc(head[lang]["title"])}</h2></a></div>{rows}</section>')
        main += f'<h1 class="sr">{esc(NAME)}</h1>' + "".join(blocks)
    return f'<div class="pv pv-{variant}"><div class="pv-grid"><div>{main}</div>{pv_side(arts, lang)}</div></div>'


def pv_article(variant, a, arts, lang, live=False):
    en = lang == "en"
    blurb = {
        "a": "Narrow column, related and guides on the right." if en else "Smalle kolom, gerelateerd en gidsen rechts.",
        "b": "Same sidebar, with the video and the table of contents in the column." if en else "Dezelfde zijbalk, met de video en de inhoudsopgave in de kolom.",
        "c": "Contents on the left, the story in the middle, the sidebar on the right." if en else "Inhoud links, het verhaal in het midden, de zijbalk rechts.",
    }[variant]
    L = LANGS[lang]
    t = a[lang]
    toc, body = enrich(a, lang, with_toc=True)
    body = insert_mid(body, ad_html("mid_article", lang))
    media = article_media(a, lang) if variant != "a" else (
        f'<div class="hi">{resp_img(site_img(a), t["title"], SIZES_HERO, lazy=False, cls="hero-img")}</div>')
    # Variant A keeps a still photo. B and C use the player when a video exists.
    if variant == "a":
        toc_here, rail = toc, ""
    elif variant == "c":
        toc_here, rail = "", toc
    else:
        toc_here, rail = toc, ""
    article = (
        f'<article class="money">{media}'
        f'{with_actions(rubric_line(a, lang, link=True), a["slug"], lang)}'
        f'<h1>{esc(t["title"])}</h1>'
        f'<p class="byline"><a href="{url(lang, "editorial/")}">{L["byline"]}</a>'
        f' · {read_time(a, lang)} {L["min"]}</p>{updated_html(a, lang)}{evergreen_article_links(a, lang)}'
        f'<p class="lead">{esc(t["description"])}</p>'
        f'{toc_here}'
        f'<div class="prose">{body}</div>{live_feed(a, lang) if a.get("type") == "live" else ""}{product_boxes(a, lang)}{handy_box(a, lang)}{ad_html("end", lang)}'
        f'{article_sources(a, lang)}{prev_next(a, arts, lang)}</article>')
    if live:
        return article
    inner = f'<div class="pv-art pv-{variant}">{rail}<div>{article}</div>{pv_side(arts, lang, a)}</div>'
    return (f'<div class="pv">{pv_banner(lang, variant, blurb)}{inner}</div>')


def preview_page(lang, path, title, desc, body, real, bar=None):
    extra = (
        f'<link rel="canonical" href="{SITE + url(lang, real)}">'
        f'<link rel="alternate" hreflang="en" href="{SITE + url("en", path)}">'
        f'<link rel="alternate" hreflang="nl" href="{SITE + url("nl", path)}">'
        f'<link rel="alternate" hreflang="x-default" href="{SITE + url("en", path)}">'
    )
    return page(lang, path, title, desc, body, robots="noindex, follow", canonical=False, extra_head=extra, bar=bar)


def write_previews(arts, lang):
    if not arts:
        return
    en = lang == "en"
    cards = []
    blurbs = {
        "a": ("A · Newsfeed", "A · Nieuwslijst"),
        "b": ("B · Hybrid", "B · Hybride"),
        "c": ("C · Sections", "C · Rubrieken"),
    }
    for key, names in blurbs.items():
        cards.append(
            f'<a class="card" href="{url(lang, f"preview/{key}/")}"><div class="body"><h3>{names[0] if en else names[1]}</h3>'
            f'<p>{esc(pv_copy(lang)["open"])}: <span>{esc(arts[0][lang]["title"])}</span></p></div></a>')
    intro = ("Three layouts to compare. None of these pages is indexed." if en else "Drie indelingen om te vergelijken. Geen van deze pagina's wordt geïndexeerd.")
    write(url(lang, "preview/"), preview_page(
        lang, "preview/", "Layout previews" if en else "Voorbeelden van de indeling", intro,
        f'<h1>{esc("Layout previews" if en else "Voorbeelden van de indeling")}</h1><p class="lead">{esc(intro)}</p><div class="grid2">{"".join(cards)}</div>',
        ""))
    sample = arts[0]
    for key in ("a", "b", "c"):
        title = blurbs[key][0 if en else 1]
        write(url(lang, f"preview/{key}/"), preview_page(
            lang, f"preview/{key}/", title, title, pv_home(key, arts, lang), "",
            bar="inline" if key == "b" else None))
        write(url(lang, f"preview/{key}/article/"), preview_page(
            lang, f"preview/{key}/article/", sample[lang]["title"], sample[lang]["description"],
            pv_article(key, sample, arts, lang), sample["slug"] + "/",
            bar="inline" if key == "b" else None))


HUBS = [
    {
        "key": "cars", "path": "cars/",
        "title": {"en": "Cars", "nl": "Auto's"},
        "topics": ["cars"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Tesla's passenger cars: the models on sale, the factories that build them, and the rules around buying one.",
            "nl": "Tesla's personenauto's: de modellen die te koop zijn, de fabrieken die ze bouwen, en de regels rond de aankoop.",
        },
    },
    {
        "key": "semi", "path": "semi/",
        "title": {"en": "Semi Truck", "nl": "Semi-truck"},
        "topics": ["semi"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "The Tesla Semi: the truck, the factory and the trips that are on the record.",
            "nl": "De Tesla Semi: de truck, de fabriek en de ritten die vastliggen.",
        },
    },
    {
        "key": "megapacks", "path": "megapacks/",
        "title": {"en": "Megapacks", "nl": "Megapacks"},
        "topics": ["megapack"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Tesla Megapacks for the grid, factories and data centres.",
            "nl": "Tesla Megapacks voor het net, fabrieken en datacenters.",
        },
    },
    {
        "key": "charging-network", "path": "charging-network/",
        "title": {"en": "Charging Network", "nl": "Laadnetwerk"},
        "topics": ["charging-network"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Superchargers and the public charging network: sites, plugs and who can use them.",
            "nl": "Superchargers en het openbare laadnetwerk: locaties, stekkers en wie ze mag gebruiken.",
        },
    },
    {
        "key": "home-charging", "path": "home-charging/",
        "title": {"en": "Home charging stations", "nl": "Thuisladers"},
        "topics": ["home-charging"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Charging a Tesla at home: wall connectors, power and what 11 kW is enough for.",
            "nl": "Een Tesla thuis laden: wall connectors, vermogen en waar 11 kW genoeg voor is.",
        },
    },
    {
        "key": "solar", "path": "solar/",
        "title": {"en": "Solar", "nl": "Zonne-energie"},
        "topics": ["solar"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Tesla solar: the roof, the factories and what is still on sale.",
            "nl": "Tesla-zonne-energie: het dak, de fabrieken en wat nog te koop is.",
        },
    },
    {
        "key": "starship-vehicle", "path": "starship-vehicle/",
        "title": {"en": "Starship", "nl": "Starship"},
        "topics": ["starship"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Starship flights, catches and the vehicle itself. The flight table lives on the tracker.",
            "nl": "Starship-vluchten, vangsten en het voertuig zelf. De vluchttabel staat op de tracker.",
        },
    },
    {
        "key": "falcons", "path": "falcons/",
        "title": {"en": "Falcons", "nl": "Falcons"},
        "topics": ["falcon"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Falcon 9 and Falcon Heavy: the rockets SpaceX flies today.",
            "nl": "Falcon 9 en Falcon Heavy: de raketten die SpaceX nu vliegt.",
        },
    },
    {
        "key": "satellite-network", "path": "satellite-network/",
        "title": {"en": "Satellite network", "nl": "Satellietnetwerk"},
        "topics": ["starlink"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "The Starlink satellite network: dishes, orbits and where the service reaches.",
            "nl": "Het Starlink-satellietnetwerk: schotels, banen en waar de dienst komt.",
        },
    },
    {
        "key": "ai", "path": "ai/",
        "title": {"en": "AI news", "nl": "AI-nieuws"},
        "topics": ["ai", "agi"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Grok, Cursor and the models SpaceXSI ships, plus the wider lab race.",
            "nl": "Grok, Cursor en de modellen die SpaceXSI uitbrengt, plus de bredere labrace.",
        },
    },
    {
        "key": "ai-compute", "path": "ai-compute/",
        "title": {"en": "Compute", "nl": "Rekenkracht"},
        "topics": ["ai-compute"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "The compute behind Grok: clusters, power and what SpaceXSI reports.",
            "nl": "De rekenkracht achter Grok: clusters, stroom en wat SpaceXSI meldt.",
        },
    },
    {
        "key": "datacenters", "path": "datacenters/",
        "title": {"en": "Datacenters", "nl": "Datacenters"},
        "topics": ["datacenters"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "SpaceXSI datacenters, including Colossus and what is planned in orbit.",
            "nl": "Datacenters van SpaceXSI, inclusief Colossus en wat er in een baan is gepland.",
        },
    },
    {
        "key": "chips", "path": "chips/",
        "title": {"en": "Chips", "nl": "Chips"},
        "topics": ["chips"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "The chips Tesla and SpaceX want to build, including the Terafab plan.",
            "nl": "De chips die Tesla en SpaceX zelf willen bouwen, inclusief het Terafab-plan.",
        },
    },
    {
        "key": "brain-interfaces", "path": "brain-interfaces/",
        "title": {"en": "Brain-computer interfaces", "nl": "Brein-computerinterfaces"},
        "topics": ["neuralink"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Neuralink's implants and the trials that test them.",
            "nl": "De implantaten van Neuralink en de proeven die ze testen.",
        },
    },
    {
        "key": "car-tunnels", "path": "car-tunnels/",
        "title": {"en": "Car tunnels", "nl": "Autotunnels"},
        "topics": ["boring"],
        "categories": [],
        "keywords": [],
        "intro": {
            "en": "Tunnels cars drive through: Vegas, Nashville and the other Loop projects on the record.",
            "nl": "Tunnels waar auto's doorheen rijden: Vegas, Nashville en de andere Loop-projecten die vastliggen.",
        },
    },
    {
        "key": "tesla", "path": "tesla/",
        "title": {"en": "Tesla", "nl": "Tesla"},
        "topics": ["cars", "semi", "robotaxi", "fsd", "optimus"],
        "categories": ["news", "models", "charging", "software", "factories", "earnings", "energy", "guides", "musk"],
        "keywords": [],
        "intro": {
            "en": "Cars, factories, deliveries and energy. The list below is filled from topic tags already on the site.",
            "nl": "Auto's, fabrieken, leveringen en energie. De lijst hieronder komt uit de onderwerptags die al op de site staan.",
        },
    },
    {
        "key": "fsd", "path": "fsd/",
        "title": {"en": "FSD", "nl": "FSD"},
        "topics": ["fsd"],
        "categories": ["fsd"],
        "keywords": ["fsd", "full self-driving", "full self driving"],
        "intro": {
            "en": "Supervised driver assistance: versions, where it is allowed, and what regulators do.",
            "nl": "Begeleide rijhulp: versies, waar het mag en wat toezichthouders doen.",
        },
    },
    {
        "key": "robotaxi", "path": "robotaxi/",
        "title": {"en": "Robotaxi", "nl": "Robotaxi"},
        "topics": ["robotaxi"],
        "categories": ["robotaxi"],
        "keywords": ["robotaxi", "cybercab"],
        "intro": {
            "en": "Robotaxi and Cybercab: where the service runs, and the sale terms when they are public.",
            "nl": "Robotaxi en Cybercab: waar de dienst rijdt, en de verkoopvoorwaarden als ze openbaar zijn.",
        },
    },
    {
        "key": "optimus", "path": "optimus/",
        "title": {"en": "Optimus", "nl": "Optimus"},
        "topics": ["optimus"],
        "categories": ["optimus"],
        "keywords": ["optimus"],
        "intro": {
            "en": "Tesla's humanoid robot: demos, factory work and plans. A promise stays a promise.",
            "nl": "De humanoïde robot van Tesla: demo's, fabriekswerk en plannen. Een belofte blijft een belofte.",
        },
    },
    {
        "key": "spacex", "path": "spacex/",
        "title": {"en": "SpaceX", "nl": "SpaceX"},
        "topics": ["starship", "falcon", "spacex"],
        "categories": ["spacex"],
        "keywords": ["falcon 9", "falcon heavy"],
        "intro": {
            "en": "Falcon, Starship and SpaceX as a company, including launches and the stock listing.",
            "nl": "Falcon, Starship en SpaceX als bedrijf, inclusief lanceringen en de beursgang.",
        },
    },
    {
        "key": "spacexsi", "path": "spacexsi/",
        "title": {"en": "SpaceXSI / Grok", "nl": "SpaceXSI / Grok"},
        "topics": ["ai", "ai-compute", "datacenters", "chips", "agi", "spacexsi"],
        "categories": ["xai"],
        "keywords": ["xai", "grok", "spacexsi", "spacexai", "colossus"],
        "intro": {
            "en": "SpaceXSI, formerly xAI and then SpaceXAI: Grok, compute, Cursor and X.",
            "nl": "SpaceXSI, eerder xAI en daarna SpaceXAI: Grok, rekenkracht, Cursor en X.",
        },
    },
    {
        "key": "starlink", "path": "starlink/",
        "title": {"en": "Starlink", "nl": "Starlink"},
        "topics": ["starlink"],
        "categories": ["starlink"],
        "keywords": ["starlink", "starshield"],
        "intro": {
            "en": "Starlink for homes and businesses, and Starshield only where a public record exists.",
            "nl": "Starlink voor thuis en bedrijven, en Starshield alleen waar een openbaar stuk bestaat.",
        },
    },
    {
        "key": "neuralink", "path": "neuralink/",
        "title": {"en": "Neuralink", "nl": "Neuralink"},
        "topics": ["neuralink"],
        "categories": [],
        "keywords": ["neuralink", "telepathy", "blindsight"],
        "intro": {
            "en": "Neuralink's brain-computer work: Telepathy, the VOICE speech study and the Blindsight vision study.",
            "nl": "Het hersen-computerwerk van Neuralink: Telepathy, de spraakstudie VOICE en de visieproef Blindsight.",
        },
    },
    {
        "key": "boring", "path": "boring/",
        "title": {"en": "Boring Co", "nl": "Boring Co"},
        "topics": ["boring"],
        "categories": ["boring"],
        "keywords": ["boring company", "vegas loop", "cybertunnel"],
        "intro": {
            "en": "Tunnels and Loop projects. Passenger figures only when the company or a local authority publishes them.",
            "nl": "Tunnels en Loop-projecten. Reizigerscijfers alleen als het bedrijf of een lokale overheid ze publiceert.",
        },
    },
    {
        "key": "agi", "path": "agi/",
        "title": {"en": "AGI race", "nl": "AGI-race"},
        "topics": ["agi"],
        "categories": [],
        "keywords": ["agi", "superintelligence", "superintelligentie", "openai", "anthropic", "deepmind", "deepseek", "ai race"],
        "intro": {
            "en": "The global race in AI, AGI and superintelligence, and where Tesla and SpaceXSI do and do not take part. Not a fixed ranking.",
            "nl": "De wereldwijde race in AI, AGI en superintelligentie, en waar Tesla en SpaceXSI wel en niet meedoen. Geen vaste ranglijst.",
        },
    },
]


def _bi(value, lang):
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or ""
    return value or ""


def _kw_pattern(words):
    if not words:
        return None
    parts = sorted((re.escape(w) for w in words), key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.I)


def article_topics(a):
    """Primary topic, then any extra topics. Breadcrumbs keep the primary one."""
    found = []
    primary = a.get("topic")
    if primary:
        found.append(primary)
    for key in a.get("also_topics") or []:
        if key and key not in found:
            found.append(key)
    return found


def hub_articles(spec, arts):
    """Articles filed under this hub's topics. Keyword matching is not used."""
    topics = set(spec.get("topics") or [])
    if topics:
        out = [a for a in arts if topics & set(article_topics(a))]
        out.sort(key=published, reverse=True)
        return out
    cats = set(spec.get("categories") or [])
    pat = _kw_pattern(spec.get("keywords") or [])
    out = []
    for a in arts:
        own = {a["category"]} | set(a.get("also") or [])
        if own & cats:
            out.append(a)
            continue
        if not pat:
            continue
        blob = " ".join([
            a["slug"].replace("-", " "),
            a["en"]["title"], a["en"]["description"],
            a["nl"]["title"], a["nl"]["description"],
        ])
        if pat.search(blob):
            out.append(a)
    out.sort(key=published, reverse=True)
    return out


def _compact_src(title):
    if "," not in title:
        return title.strip()
    head, tail = [part.strip() for part in title.split(",", 1)]
    months = ("january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december", "januari", "februari",
              "maart", "mei", "juni", "augustus", "oktober")
    return head if any(month in tail.lower() for month in months) else tail


def _src_links(sources, compact=False):
    parts = []
    if compact:
        grouped = []
        index = {}
        for s in sources or []:
            label = _compact_src(s["title"])
            if label in index:
                grouped[index[label]]["n"] += 1
            else:
                index[label] = len(grouped)
                grouped.append({"label": label, "url": s["url"], "n": 1})
        items = grouped
    else:
        items = [{"label": s["title"], "url": s["url"], "n": 1} for s in sources or []]
    for item in items:
        label = item["label"] + (f" ×{item['n']}" if item["n"] > 1 else "")
        parts.append(
            f'<a class="eco-src" href="{esc(item["url"])}" rel="noopener noreferrer" target="_blank">{esc(label)}</a>')
    if not parts:
        return ""
    if compact:
        return f'<div class="eco-chiprow">{"".join(parts)}</div>'
    return "".join(parts)


def load_data(name):
    path = ROOT / "content" / "data" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _count_label(n, lang):
    if lang == "nl":
        return "1 artikel" if n == 1 else f"{n} artikelen"
    return "1 article" if n == 1 else f"{n} articles"


def _coverage_note(lang):
    if lang == "nl":
        return "Hier staat nog niets. Artikelen voor deze rubriek verschijnen zodra ze zijn gepubliceerd."
    return "Nothing here yet. Articles for this section will show up when they are published."


def _article_list(items, lang, title, path, crumb_parts=None):
    """Breadcrumb, a hidden page title, then the lead photo and the other articles."""
    parts = list(crumb_parts) if crumb_parts is not None else [(title, path)]
    nav, ld = crumbs(lang, parts)
    hidden = f'<h1 class="visually-hidden">{esc(title)}</h1>'
    if not items:
        return f'{nav}{hidden}<p class="hubnote">{esc(_coverage_note(lang))}</p>', ld
    feature = home_lead(items[0], lang, title_tag="h2")
    rest = hub_cards(items[1:], lang) if len(items) > 1 else ""
    return f'{nav}{hidden}{feature}{rest}', ld


def topic_hub(spec, items, lang):
    """Article list for a topic. The intro stays in the meta description only."""
    title = _bi(spec["title"], lang)
    intro = _bi(spec["intro"], lang)
    parts = topic_hub_crumb_parts(spec, items, lang)
    body, ld = _article_list(items, lang, title, spec["path"], crumb_parts=parts)
    return body, ld, intro


JOIN_SVG = ('<svg class="eco-join" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<path d="M12 3v12M7 12l5 7 5-7" fill="none" stroke="currentColor" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _eco_piece(block, lang, kind, extra_cls="", style="", links=True):
    title = _bi(block.get("title"), lang)
    fact = _bi(block.get("fact"), lang)
    kicker = _bi(block.get("kicker"), lang)
    href = block.get("href") or ""
    tone = block.get("tone") or ""
    kick = f'<span class="eco-k">{esc(kicker)}</span>' if kicker else ""
    inner = f'{kick}<strong>{esc(title)}</strong><p>{esc(fact)}</p>'
    if href:
        inner = f'<a class="eco-cardlink" href="{url(lang, href)}">{inner}</a>'
    extra = "".join(
        f'<a href="{url(lang, link["href"])}">{esc(_bi(link.get("label") or link.get("title"), lang))}</a>'
        for link in (block.get("links") or []) if links)
    extra = f'<div class="eco-links">{extra}</div>' if extra else ""
    cls = {"layer": "eco-card", "branch": "eco-card", "company": "eco-co",
           "stream": "eco-stream", "callout": "eco-call"}[kind]
    style_attr = f' style="{style}"' if style else ""
    chips = _src_links(block.get("sources"), compact=not links)
    return f'<div class="{cls} {tone}{extra_cls}"{style_attr}>{inner}{extra}{chips}</div>'


def _orbit_box(block, lang):
    """Coloured layer name plus one bullet per part. The whole box is the link."""
    kicker = _bi(block.get("kicker"), lang)
    parts = [part.strip() for part in _bi(block.get("fact"), lang).split(",") if part.strip()]
    tone = block.get("tone") or ""
    items = "".join(f"<li>{esc(part)}</li>" for part in parts)
    return (
        f'<a class="eco-card eco-node {tone}" href="{url(lang, block.get("href") or "")}">'
        f'<span class="eco-k">{esc(kicker)}</span><ul>{items}</ul></a>'
    )


def _orbit_blocks(blocks, lang):
    """Boxes along an arc. Lines are drawn from the measured circle centre."""
    parts = "".join(_orbit_box(block, lang) for block in blocks)
    label = "Elon<br>ecosystem" if lang == "en" else "Elon<br>ecosysteem"
    script = r"""
(function(){
  var root = document.currentScript.previousElementSibling;
  if (!root || !root.hasAttribute("data-eco-orbit")) return;
  var nodes = [].slice.call(root.querySelectorAll(".eco-node"));
  var sun = root.querySelector(".eco-sun");
  var core = root.querySelector(".eco-core");
  var svg = root.querySelector(".eco-rays");
  var ns = "http://www.w3.org/2000/svg";
  var edge = 10, gap = 14, maxBox = 320, minBox = 136;

  function measure(widths) {
    nodes.forEach(function(el, i) {
      el.style.position = "absolute";
      el.style.width = widths[i] + "px";
    });
    return nodes.map(function(el) { return el.offsetHeight; });
  }

  function solve(heights, W, labelW, labelH) {
    var total = gap * (heights.length - 1);
    heights.forEach(function(h) { total += h; });
    var H = total + edge * 2, cy = H / 2;
    var cx = labelW / 2 + 18;
    var y = edge, centers = [], maxDy = 1;
    heights.forEach(function(h) {
      centers.push(y + h / 2);
      y += h + gap;
    });
    centers.forEach(function(c) { maxDy = Math.max(maxDy, Math.abs(c - cy)); });
    var labelFit = Math.hypot(labelW / 2, labelH / 2) + 14;
    var right = W - edge;
    var sunR = Math.min(H / 2 - 8, Math.max(labelFit, Math.min(W * 0.42, 280)));
    var leftFloor = cx + sunR + 10;
    if (leftFloor > right - minBox - 36) {
      sunR = Math.max(labelFit, Math.min(sunR, right - minBox - 46 - cx));
      leftFloor = cx + sunR + 10;
    }
    var leftEnd = Math.max(leftFloor, right - maxBox);
    var leftMid = Math.min(right - minBox, leftEnd + Math.min(110, Math.max(36, W * 0.14)));
    if (leftMid < leftEnd + 18) leftMid = Math.min(right - minBox, leftEnd + 18);
    var placed = centers.map(function(c, i) {
      var t = maxDy ? (c - cy) / maxDy : 0;
      var x = leftEnd + (leftMid - leftEnd) * Math.sqrt(Math.max(0, 1 - t * t));
      var w = Math.max(96, right - x);
      if (w > maxBox) w = maxBox;
      return {x:x, y:c - heights[i] / 2, h:heights[i], w:w, my:c};
    });
    var align = 0;
    placed.forEach(function(p) { align = Math.max(align, p.x + p.w); });
    if (align > right) align = right;
    placed.forEach(function(p) {
      p.w = Math.min(maxBox, Math.max(96, align - p.x));
    });
    return {H:H, cy:cy, cx:cx, radius:sunR, placed:placed};
  }

  function layout() {
    var W = root.clientWidth;
    if (W < 40 || !nodes.length) return;
    root.classList.add("is-set");
    core.style.width = "max-content";
    var labelW = core.offsetWidth, labelH = core.offsetHeight;
    var guess = Math.max(minBox, Math.min(maxBox, (W - labelW) * 0.42));
    var widths = nodes.map(function() { return guess; });
    var pass;
    for (var n = 0; n < 4; n++) {
      pass = solve(measure(widths), W, labelW, labelH);
      var next = pass.placed.map(function(p) { return p.w; });
      var same = next.every(function(w, i) { return Math.abs(w - widths[i]) < 1; });
      widths = next;
      if (same) break;
    }
    root.style.height = pass.H + "px";
    sun.style.width = (pass.radius * 2) + "px";
    sun.style.height = (pass.radius * 2) + "px";
    sun.style.left = (pass.cx - pass.radius) + "px";
    sun.style.top = (pass.cy - pass.radius) + "px";
    core.style.left = pass.cx + "px";
    // The rays meet at the sun's centre. Keep the words above that point.
    core.style.top = (pass.cy - labelH) + "px";
    pass.placed.forEach(function(p, i) {
      nodes[i].style.left = p.x + "px";
      nodes[i].style.top = p.y + "px";
      nodes[i].style.width = p.w + "px";
    });
    var hb = root.getBoundingClientRect();
    var sb = sun.getBoundingClientRect();
    var ocx = sb.left + sb.width / 2 - hb.left;
    var ocy = sb.top + sb.height / 2 - hb.top;
    svg.setAttribute("width", String(W));
    svg.setAttribute("height", String(pass.H));
    svg.setAttribute("viewBox", "0 0 " + W + " " + pass.H);
    svg.setAttribute("preserveAspectRatio", "xMinYMin meet");
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    nodes.forEach(function(el) {
      var r = el.getBoundingClientRect();
      var x = r.left - hb.left;
      var y = (r.top + r.bottom) / 2 - hb.top;
      var line = document.createElementNS(ns, "line");
      line.setAttribute("x1", String(ocx));
      line.setAttribute("y1", String(ocy));
      line.setAttribute("x2", String(x));
      line.setAttribute("y2", String(y));
      line.setAttribute("stroke", "rgba(198,240,255,.9)");
      line.setAttribute("stroke-width", "0.8");
      line.setAttribute("stroke-linecap", "butt");
      svg.appendChild(line);
    });
  }

  var frame = 0;
  function schedule() {
    if (frame) cancelAnimationFrame(frame);
    frame = requestAnimationFrame(layout);
  }
  if (window.ResizeObserver) new ResizeObserver(schedule).observe(root);
  else window.addEventListener("resize", schedule);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(schedule);
  layout();
})();
"""
    return (
        f'<div class="eco-orbit" data-eco-orbit>'
        f'<div class="eco-sun" aria-hidden="true"></div>'
        f'<svg class="eco-rays" aria-hidden="true"></svg>'
        f'<p class="eco-core">{label}</p>'
        f'<div class="eco-arc">{parts}</div>'
        f'</div>'
        f'<script>{script}</script>'
    )


def _stat_card(block, lang, self_path=""):
    """One sourced figure, with its source chips. A link is omitted when it points at this page."""
    value = esc(_bi(block["value"], lang))
    label = esc(_bi(block["label"], lang))
    detail = esc(_bi(block["detail"], lang))
    inner = f'<b>{value}</b><span>{label}</span><small>{detail}</small>'
    href = block.get("href") or ""
    if href and href != self_path:
        inner = f'<a class="eco-stat" href="{url(lang, href)}">{inner}</a>'
    else:
        inner = f'<div class="eco-stat">{inner}</div>'
    return f'<div class="eco-bit">{inner}{_src_links(block.get("sources"))}</div>'


# One landing page per map box. Paths that already exist as hubs are upgraded in place.
LAYERS = [
    {
        "key": "tesla", "path": "tesla/", "tone": "tesla", "nav": "tesla",
        "kicker": {"en": "1 · Tesla", "nl": "1 · Tesla"},
        "title": {"en": "Tesla", "nl": "Tesla"},
        "fact": {
            "en": "Cars, Semi Truck, Robotaxi, FSD, Optimus",
            "nl": "Auto's, Semi-truck, Robotaxi, FSD, Optimus",
        },
        "stats": ["deliveries"],
        "articles": {
            "topics": ["cars", "semi", "robotaxi", "fsd", "optimus"],
        },
        "links": [
            {"en": "FSD", "nl": "FSD", "href": "fsd/"},
            {"en": "Robotaxi", "nl": "Robotaxi", "href": "robotaxi/"},
            {"en": "Optimus", "nl": "Optimus", "href": "optimus/"},
        ],
        "intro": {
            "en": [
                "Tesla is the cars layer of the ecosystem: the passenger cars, the Semi truck, Robotaxi, supervised FSD and the Optimus robot. The cars and the Semi move people and freight. FSD is the supervised assistance in those vehicles, and Robotaxi is the ride service built on it. Optimus is the humanoid robot for factory work.",
                "FSD, Robotaxi and Optimus each have their own page below.",
            ],
            "nl": [
                "Tesla is de autolaag van het ecosysteem: de personenauto's, de Semi-truck, Robotaxi, begeleide FSD en de robot Optimus. De auto's en de Semi vervoeren mensen en vracht. FSD is de begeleide rijhulp in die voertuigen, en Robotaxi is de ritdienst die daarop steunt. Optimus is de humanoïde robot voor werk in de fabriek.",
                "FSD, Robotaxi en Optimus hebben hieronder elk een eigen pagina.",
            ],
        },
    },
    {
        "key": "tesla-energy", "path": "tesla-energy/", "tone": "energy", "nav": "tesla-energy",
        "kicker": {"en": "2 · Tesla Energy", "nl": "2 · Tesla Energy"},
        "title": {"en": "Tesla Energy", "nl": "Tesla Energy"},
        "fact": {
            "en": "Megapacks, Charging Network, Home charging stations, Solar",
            "nl": "Megapacks, laadnetwerk, thuisladers, zonne-energie",
        },
        "stats": [],
        "articles": {
            "topics": ["megapack", "charging-network", "home-charging", "solar", "powerwall", "energy"],
        },
        "links": [
            {"en": "Tesla", "nl": "Tesla", "href": "tesla/"},
        ],
        "intro": {
            "en": [
                "Tesla Energy is the power layer: Megapacks for the grid, the charging network, home charging and solar. Megapacks store electricity for utilities, factories and data centres. The charging network and the home chargers put that power into the cars. Solar is the generation side of the same business.",
                "The layer sits under Tesla and feeds the rest of the ecosystem.",
            ],
            "nl": [
                "Tesla Energy is de stroomlaag: Megapacks voor het net, het laadnetwerk, thuisladers en zonne-energie. Megapacks slaan stroom op voor netbeheerders, fabrieken en datacenters. Het laadnetwerk en de thuisladers brengen die stroom naar de auto's. Zonne-energie is de opwekking in hetzelfde bedrijf.",
                "De laag hoort bij Tesla en voedt de rest van het ecosysteem.",
            ],
        },
    },
    {
        "key": "spacex", "path": "spacex/", "tone": "spacex", "nav": "spacex", "hub": "spacex",
        "kicker": {"en": "3 · SpaceX", "nl": "3 · SpaceX"},
        "title": {"en": "SpaceX", "nl": "SpaceX"},
        "fact": {"en": "Starship, Falcons", "nl": "Starship, Falcons"},
        "stats": ["flight15"],
        "links": [
            {"en": "All Starship flights", "nl": "Alle Starship-vluchten", "href": "starship/"},
        ],
        "intro": {
            "en": [
                "SpaceX is the rocket layer: Starship and the Falcon family. Falcon flies the launches of today. Starship is the larger vehicle, still learning to reach orbit and to be caught. Mars stays the long-term aim rather than a scheduled date.",
                "The flight-by-flight record is the Starship tracker, linked below.",
            ],
            "nl": [
                "SpaceX is de raketlaag: Starship en de Falcon-familie. Falcon vliegt de lanceringen van nu. Starship is het grotere voertuig, dat nog leert een baan te halen en gevangen te worden. Mars blijft het doel op termijn en geen ingeplande datum.",
                "Het vlucht-voor-vluchtverslag is de Starship-tracker, hieronder gelinkt.",
            ],
        },
    },
    {
        "key": "spacexsi", "path": "spacexsi/", "tone": "spacexsi", "nav": "spacexsi",
        "kicker": {"en": "4 · SpaceXSI", "nl": "4 · SpaceXSI"},
        "title": {"en": "SpaceXSI", "nl": "SpaceXSI"},
        "fact": {
            "en": "AI, Compute, Datacenters, Chips",
            "nl": "AI, rekenkracht, datacenters, chips",
        },
        "stats": ["compute"],
        "articles": {
            "topics": ["ai", "ai-compute", "datacenters", "chips", "agi", "spacexsi"],
        },
        "links": [],
        "intro": {
            "en": [
                "SpaceXSI is the AI layer: the models, the compute, the datacenters and the chips. Grok is the model, Cursor is the coding tool, and X is the live network they can read. The clusters and datacenters train those models and keep them running. The chips, including the planned Terafab plant, are how that compute gets built.",
                "This page brings the reporting on all of those parts together.",
            ],
            "nl": [
                "SpaceXSI is de AI-laag: de modellen, de rekenkracht, de datacenters en de chips. Grok is het model, Cursor is het programmeergereedschap, en X is het live netwerk dat ze kunnen lezen. De clusters en datacenters trainen die modellen en laten ze draaien. De chips, inclusief de geplande fabriek Terafab, zijn hoe die rekenkracht wordt gebouwd.",
                "Deze pagina brengt de berichtgeving over al die delen samen.",
            ],
        },
    },
    {
        "key": "starlink", "path": "starlink/", "tone": "link", "nav": "starlink", "hub": "starlink",
        "kicker": {"en": "5 · Starlink", "nl": "5 · Starlink"},
        "title": {"en": "Starlink", "nl": "Starlink"},
        "fact": {"en": "Satellite network", "nl": "Satellietnetwerk"},
        "stats": ["starlink"],
        "links": [
            {"en": "SpaceX", "nl": "SpaceX", "href": "spacex/"},
        ],
        "intro": {
            "en": [
                "Starlink is the satellite network. Dishes on the ground talk to satellites that reach places cables do not. The service is for homes and for businesses. The same network is the connection layer of the ecosystem, between the cars and the rockets on the map.",
                "Starshield is mentioned only when a public record exists.",
            ],
            "nl": [
                "Starlink is het satellietnetwerk. Schotels op de grond praten met satellieten die plaatsen bereiken waar geen kabel ligt. De dienst is er voor thuis en voor bedrijven. Hetzelfde netwerk is de verbindingslaag van het ecosysteem, op de kaart tussen de auto's en de raketten.",
                "Starshield komt alleen aan bod als er een openbaar stuk over bestaat.",
            ],
        },
    },
    {
        "key": "neuralink", "path": "neuralink/", "tone": "neural", "nav": "neuralink", "hub": "neuralink",
        "kicker": {"en": "6 · Neuralink", "nl": "6 · Neuralink"},
        "title": {"en": "Neuralink", "nl": "Neuralink"},
        "fact": {"en": "Brain-computer interfaces", "nl": "Brein-computerinterfaces"},
        "stats": ["neuralink"],
        "links": [],
        "intro": {
            "en": [
                "Neuralink builds brain-computer interfaces. An implant can move a cursor, and studies aim at speech and at sight. It is its own company, beside the main stack rather than inside the cars or the rockets.",
                "Articles will show up here as they are published. Nothing is written in ahead of that.",
            ],
            "nl": [
                "Neuralink bouwt brein-computerinterfaces. Een implantaat kan een cursor bewegen, en studies richten zich op spraak en op zicht. Het is een eigen bedrijf, naast de hoofdstapel en niet in de auto's of de raketten.",
                "Artikelen verschijnen hier zodra ze zijn gepubliceerd. Er wordt niets vooraf ingevuld.",
            ],
        },
    },
    {
        "key": "boring", "path": "boring/", "tone": "boring", "nav": "boring", "hub": "boring",
        "kicker": {"en": "7 · Boring Co", "nl": "7 · Boring Co"},
        "title": {"en": "Boring Co", "nl": "Boring Co"},
        "fact": {"en": "Car tunnels", "nl": "Autotunnels"},
        "stats": [],
        "links": [],
        "intro": {
            "en": [
                "The Boring Company digs car tunnels and runs Loop transit through them, often with Tesla vehicles. It is a separate company, next to the main stack on the map. The public projects include Vegas, Nashville, Dubai and the tunnel at Gigafactory Texas.",
                "Passenger figures appear here only when the company or a local authority publishes them.",
            ],
            "nl": [
                "The Boring Company graaft autotunnels en laat er Loop-vervoer door rijden, vaak met Tesla-voertuigen. Het is een apart bedrijf, naast de hoofdstapel op de kaart. De openbare projecten zijn Vegas, Nashville, Dubai en de tunnel bij Gigafactory Texas.",
                "Reizigerscijfers staan hier alleen als het bedrijf of een lokale overheid ze publiceert.",
            ],
        },
    },
]

def _layer_articles(layer, arts):
    if layer.get("hub"):
        spec = next(h for h in HUBS if h["key"] == layer["hub"])
        return hub_articles(spec, arts)
    return hub_articles(layer.get("articles") or {}, arts)


def layer_page(layer, arts, lang):
    """Hidden title, then the lead photo and the other articles."""
    title = _bi(layer["title"], lang)
    items = _layer_articles(layer, arts)
    body, ld = _article_list(items, lang, title, layer["path"])
    desc = layer["intro"][lang][0]
    return body, ld, desc, items


def _eco_explain(lang):
    """How the seven layers hand work to each other. The Megapack figure is the only number."""
    src = ('<a href="https://electrek.co/2026/05/01/tesla-tsla-web-transactions-musk-companies-spacex-xai-10ka-2025/" '
           'rel="noopener noreferrer" target="_blank">Electrek, 1 May 2026</a>' if lang == "en" else
           '<a href="https://electrek.co/2026/05/01/tesla-tsla-web-transactions-musk-companies-spacex-xai-10ka-2025/" '
           'rel="noopener noreferrer" target="_blank">Electrek, 1 mei 2026</a>')
    if lang == "en":
        title = "How the ecosystem fits together"
        paragraphs = [
            "Elon Musk's companies are separate businesses that share a few loops. Those loops are the seven layers. A car, a rocket, a satellite dish and a chatbot belong to different companies, and the work still runs from one layer into the next.",
            "Tesla is the car and robot layer. The cars, the Semi, the Robotaxi service, supervised FSD and the Optimus robot all live here. The fleet's cameras supply the pictures that train FSD and Robotaxi.",
            "Tesla Energy is the power layer beside the cars. Megapacks, the charging network, home chargers and solar sit here. The same Megapacks that store power for the grid are the batteries that can feed a datacenter. "
            f"In 2025 Tesla booked $430.1 million of business with xAI, mostly Megapacks ({src}).",
            "SpaceX is the launch layer. Falcon flies the regular missions. Starship is the larger vehicle, and each flight stands on its own. SpaceX also puts Starlink's satellites into orbit. Starlink is the connectivity layer: dishes on the ground talk to that constellation, for homes and for businesses, and the subscriptions are the revenue that comes back from the network.",
            "SpaceXSI is the intelligence layer, formerly xAI and then SpaceXAI. It covers the models, including Grok, the compute that trains them, the datacenters that house that compute, and the chips meant to build more of it. That same intelligence is what Tesla is building into supervised FSD and into Optimus.",
            "Neuralink is the brain-computer layer, its own company beside the stack. An implant can move a cursor. Studies aim at speech and at sight. It does not sit inside the car or the rocket.",
            "Boring Co is the tunnel layer, also its own company. It digs car tunnels and runs Loop transit through them, often with Tesla vehicles. The public projects include Vegas, Nashville, Dubai and the tunnel at Gigafactory Texas.",
            "Four things keep handing work to each other: energy, compute, launch and connectivity. Energy feeds compute. Compute feeds the models. A launch puts connectivity in orbit. Connectivity and the models come back down into the cars, the robots and the tunnels.",
        ]
    else:
        title = "Hoe het ecosysteem in elkaar zit"
        paragraphs = [
            "De bedrijven van Elon Musk zijn aparte ondernemingen die een paar lussen delen. Die lussen zijn de zeven lagen. Een auto, een raket, een schotel en een chatbot horen bij verschillende bedrijven, en het werk loopt toch van de ene laag naar de volgende.",
            "Tesla is de laag van de auto en de robot. De auto's, de Semi, de robotaxidienst, begeleide FSD en de robot Optimus horen hier. De camera's van de vloot leveren de beelden waarmee FSD en Robotaxi trainen.",
            "Tesla Energy is de stroomlaag naast de auto's. Megapacks, het laadnetwerk, thuisladers en zonne-energie horen hier. Dezelfde Megapacks die stroom bewaren voor het net zijn de batterijen die een datacenter kunnen voeden. "
            f"In 2025 boekte Tesla $430,1 miljoen aan zaken met xAI, vooral Megapacks ({src}).",
            "SpaceX is de lanceerlaag. Falcon vliegt de gewone missies. Starship is het grotere voertuig, en elke vlucht staat op zichzelf. SpaceX brengt ook de satellieten van Starlink in een baan. Starlink is de verbindingslaag: schotels op de grond praten met die constellatie, voor thuis en voor bedrijven, en de abonnementen zijn de omzet die uit dat netwerk terugkomt.",
            "SpaceXSI is de intelligentielaag, eerder xAI en daarna SpaceXAI. Het gaat om de modellen, waaronder Grok, de rekenkracht die ze traint, de datacenters waar die rekenkracht staat, en de chips die meer van die rekenkracht moeten bouwen. Diezelfde intelligentie is wat Tesla in begeleide FSD en in Optimus bouwt.",
            "Neuralink is de brein-computerlaag, een eigen bedrijf naast de stapel. Een implantaat kan een cursor bewegen. Studies richten zich op spraak en op zicht. Het zit niet in de auto en niet in de raket.",
            "Boring Co is de tunnellaag, ook een eigen bedrijf. Het graaft autotunnels en laat er Loop-vervoer door rijden, vaak met Tesla-voertuigen. De openbare projecten zijn Vegas, Nashville, Dubai en de tunnel bij Gigafactory Texas.",
            "Vier dingen geven werk aan elkaar door: energie, rekenkracht, lancering en verbinding. Energie voedt rekenkracht. Rekenkracht voedt de modellen. Een lancering zet verbinding in een baan. Verbinding en de modellen komen terug in de auto's, de robots en de tunnels.",
        ]
    body = "".join(f"<p>{p if '<a ' in p else esc(p)}</p>" for p in paragraphs)
    return f'<section class="eco-explain"><h2>{esc(title)}</h2>{body}</section>'


def ecosystem_page(lang):
    data = load_data("ecosystem.json")
    L = LANGS[lang]
    title = L["nav_eco"]
    intro = _bi(data["intro"], lang)
    nav, ld = crumbs(lang, [(title, ecosystem_path(lang))])
    orbit = _orbit_blocks([
        {"tone": layer["tone"], "href": layer["path"], "kicker": layer["kicker"],
         "title": layer["title"], "fact": layer["fact"]}
        for layer in LAYERS
    ], lang)
    streams = "".join(_eco_piece(b, lang, "stream") for b in data["streams"])
    companies = "".join(_eco_piece(b, lang, "company") for b in data["companies"])
    calls = "".join(_eco_piece(b, lang, "callout") for b in data["callouts"])
    seen, sources = set(), []
    for group in ("layers", "branches", "streams", "companies", "callouts"):
        for block in data[group]:
            for src in block.get("sources") or []:
                if src["url"] in seen:
                    continue
                seen.add(src["url"])
                sources.append(src)
    src_list = "".join(
        f'<li><a href="{esc(s["url"])}" rel="noopener noreferrer" target="_blank">{esc(s["title"])}</a></li>'
        for s in sources)
    heads = {
        "en": ("The layers", "What moves through it", "The companies", "Plans and promises", "Sources"),
        "nl": ("De lagen", "Wat erdoorheen gaat", "De bedrijven", "Plannen en beloftes", "Bronnen"),
    }[lang]
    body = (
        f'{nav}<h1 class="visually-hidden">{esc(title)}</h1>'
        f'{orbit}'
        f'{_eco_explain(lang)}'
        f'<h2 class="eco-h">{esc(heads[1])}</h2><div class="eco-split">{streams}</div>'
        f'<h2 class="eco-h">{esc(heads[2])}</h2><div class="eco-cos">{companies}</div>'
        f'<h2 class="eco-h">{esc(heads[3])}</h2>{calls}'
        f'<h2 class="eco-h">{esc(heads[4])}</h2><ul class="eco-sources">{src_list}</ul>'
    )
    desc = intro
    return body, ld, desc


def _flight_when(flight, lang):
    start = datetime.strptime(flight["date"], "%Y-%m-%d")
    end_s = flight.get("end_date")
    if not end_s:
        return fmt_date(flight["date"], lang)
    end = datetime.strptime(end_s, "%Y-%m-%d")
    month = LANGS[lang]["months"][start.month - 1]
    if start.year == end.year and start.month == end.month:
        if lang == "en":
            return f"{month} {start.day}–{end.day}, {start.year}"
        return f"{start.day}–{end.day} {month} {start.year}"
    return fmt_date(flight["date"], lang) + " – " + fmt_date(end_s, lang)


def _yes_no(flag, lang):
    word = ("Yes" if flag else "No") if lang == "en" else ("Ja" if flag else "Nee")
    return f'<span class="{"ss-yes" if flag else "ss-no"}">{word}</span>'


_HUB_PHOTOS = None


def hub_photos():
    global _HUB_PHOTOS
    if _HUB_PHOTOS is None:
        path = ROOT / "content" / "data" / "hub_photos.json"
        try:
            _HUB_PHOTOS = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _HUB_PHOTOS = {}
    return _HUB_PHOTOS


def hub_photo(pid):
    item = hub_photos().get(pid or "")
    if not item or not item.get("src"):
        return None
    if not (STATIC / str(item["src"]).lstrip("/")).is_file():
        return None
    return item


def hub_credit_link(item):
    return (f'<a href="{esc(item["page"])}" rel="nofollow noopener" target="_blank">'
            f'{esc(item["credit"])}</a>')


def hub_hero(pid, lang):
    item = hub_photo(pid)
    if not item:
        return "", ""
    alt = (item.get("alt") or {}).get(lang) or (item.get("alt") or {}).get("en") or ""
    img = resp_img(item["src"], alt, SIZES_HERO, high=True, lazy=False, cls="hero-img")
    return f'<div class="hi">{img}</div>', hub_credit_link(item)


def hub_figure(pid, lang):
    item = hub_photo(pid)
    if not item:
        return "", ""
    alt = (item.get("alt") or {}).get(lang) or ""
    cap = (item.get("caption") or {}).get(lang) or ""
    link = hub_credit_link(item)
    img = resp_img(item["src"], alt, SIZES_HERO, lazy=True)
    return (f'<figure class="hubfig">{img}'
            f'<figcaption class="imgnote">{esc(cap)} {link}</figcaption></figure>', link)


def hub_rubric(lang, layer, layer_path, sub="", sub_path=""):
    layer_html = f'<a class="llayer" href="{url(lang, layer_path)}">{esc(layer)}</a>'
    if sub:
        sub_html = f'<a class="lsub" href="{url(lang, sub_path)}">{esc(sub)}</a>'
        label = f'<span class="lpath">{layer_html} / {sub_html}</span>'
    else:
        label = f'<a class="lname" href="{url(lang, layer_path)}">{esc(layer)}</a>'
    return f'<span class="lmeta">{label}</span>'


def hub_article(lang, title, intro, updated, rubric, hero_id, sections):
    """Same frame as a news article: photo, rubric, title, byline, contents, prose."""
    L = LANGS[lang]
    seen = []
    for pid in [hero_id] + [photo_id for _heading, _inner, photo_id in sections]:
        item = hub_photo(pid)
        if not item:
            continue
        if item["src"] in seen:
            raise RuntimeError(f"hub photo used twice: {item['src']}")
        seen.append(item["src"])
    hero, hero_credit = hub_hero(hero_id, lang)
    credits = [hero_credit] if hero_credit else []
    blocks = []
    for i, (heading, inner, photo_id) in enumerate(sections, 1):
        fig, credit = hub_figure(photo_id, lang) if photo_id else ("", "")
        if credit and credit not in credits:
            credits.append(credit)
        blocks.append(f'<h2 id="s{i}">{esc(heading)}</h2>{fig}{inner}')
    toc = ""
    if sections:
        label = L["toc"]
        items = "".join(
            f'<li><a href="#s{i}">{esc(heading)}</a></li>'
            for i, (heading, _inner, _photo) in enumerate(sections, 1))
        toc = (f'<nav class="toc" aria-label="{esc(label)}"><b>{esc(label)}</b>'
               f'<ol>{items}</ol></nav>')
    when = ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(updated or "")):
        prefix = "Updated " if lang == "en" else "Bijgewerkt "
        when = (f' · <time datetime="{esc(updated)}">'
                f'{esc(prefix + fmt_date(updated, lang))}</time>')
    note = ""
    if credits:
        note = f'<p class="imgnote">{L["photocredit"]}: {"; ".join(credits)}.</p>'
    article = (
        f'<article class="money">{hero}{rubric}'
        f'<h1>{esc(title)}</h1>'
        f'<p class="byline"><a href="{url(lang, "editorial/")}">{esc(L["byline"])}</a>{when}</p>'
        f'<p class="lead">{esc(intro)}</p>{toc}'
        f'<div class="prose">{"".join(blocks)}</div>{note}</article>')
    src = (hub_photo(hero_id) or {}).get("src")
    return article, src


def starship_page(lang, arts):
    data = load_data("starship.json")
    L = LANGS[lang]
    # Newest launch date first, then the higher flight number, so a new flight lands on top.
    flights = sorted(data["flights"], key=lambda f: (str(f.get("date") or ""), int(f.get("number") or 0)), reverse=True)
    latest = flights[0]
    titles = {"en": "All Starship flights", "nl": "Alle Starship-vluchten"}
    title = titles[lang]
    intro = ("Every full-stack Starship flight: the date, the outcome, and whether the booster, the ship and a payload made it. "
             "The page is rendered from a data file, so a new flight is a new row."
             if lang == "en" else
             "Elke volledige Starship-vlucht: de datum, de afloop, en of de booster, het schip en een lading het haalden. "
             "De pagina komt uit een databestand, dus een nieuwe vlucht is een nieuwe rij.")
    ship_spec = {"key": "starship", "path": "starship/", "title": titles, "topics": ["starship"]}
    nav, ld = crumbs(lang, topic_hub_crumb_parts(ship_spec, hub_articles(ship_spec, arts), lang))
    updated = ("Updated on " if lang == "en" else "Bijgewerkt op ") + fmt_date(data["updated"], lang)
    labels = {
        "en": ("Latest result", "Next launch", "Not announced", "Flight archive", "Flight", "Date", "Outcome",
               "Booster catch", "Ship catch", "Payload", "On TrendingTesla"),
        "nl": ("Laatste resultaat", "Volgende lancering", "Niet aangekondigd", "Vluchtarchief", "Vlucht", "Datum", "Afloop",
               "Boostervangst", "Scheepsvangst", "Lading", "Op TrendingTesla"),
    }[lang]
    pills = (
        f'<span>{esc(labels[7])} {_yes_no(latest["booster_catch"], lang)}</span>'
        f'<span>{esc(labels[8])} {_yes_no(latest["ship_catch"], lang)}</span>'
        f'<span>{esc(labels[9])}: {esc(_bi(latest["payload"], lang))}</span>'
    )
    nxt = data["next"]
    if nxt.get("announced") and nxt.get("date"):
        next_main = esc(fmt_date(nxt["date"], lang))
    else:
        next_main = esc(labels[2])
    rows = []
    for flight in flights:
        cls = " class=\"is-latest\"" if flight["number"] == latest["number"] else ""
        cells = [
            (labels[4], str(flight["number"])),
            (labels[5], esc(_flight_when(flight, lang))),
            (labels[6], esc(_bi(flight["outcome"], lang)) + _src_links(flight.get("sources"))),
            (labels[7], _yes_no(flight["booster_catch"], lang)),
            (labels[8], _yes_no(flight["ship_catch"], lang)),
            (labels[9], esc(_bi(flight["payload"], lang))),
        ]
        tds = "".join(f'<td data-label="{esc(label)}">{value}</td>' for label, value in cells)
        rows.append(f"<tr{cls}>{tds}</tr>")
    head = "".join(f"<th>{esc(name)}</th>" for name in labels[4:10])
    related = hub_articles({"topics": ["starship"]}, arts)
    flight_photo = {
        1: "starship-1", 2: "starship-2", 3: "starship-3", 4: "starship-4",
        5: "starship-5", 6: "starship-6", 8: "starship-8", 11: "starship-11",
        15: "starship-15",
    }
    flight_word = "Flight" if lang == "en" else "Vlucht"
    map_link = (f'<p class="hubcount"><a href="{url(lang, ecosystem_path(lang))}">'
                + ("See the ecosystem map" if lang == "en" else "Zie de kaart van het ecosysteem")
                + "</a></p>")
    latest_html = (
        f'<div class="ss-board"><article class="ss-card latest"><p class="k">{esc(labels[0])}</p>'
        f'<p class="hubh">{flight_word} {latest["number"]}</p>'
        f'<p>{esc(_flight_when(latest, lang))}. {esc(_bi(latest["outcome"], lang))}</p>'
        f'<div class="ss-pills">{pills}</div>{_src_links(latest.get("sources"))}</article></div>')
    next_html = (
        f'<div class="ss-board"><article class="ss-card next"><p class="k">{esc(labels[1])}</p>'
        f'<p class="hubh">{next_main}</p><p>{esc(_bi(nxt.get("note"), lang))}</p>'
        f'{_src_links(nxt.get("sources"))}</article></div>')
    table = (f'<div class="ss-wrap"><table class="ss-table"><thead><tr>{head}</tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    sections = [
        (labels[0], latest_html, ""),
        (labels[1], next_html, ""),
        (labels[3], table, ""),
    ]
    for flight in flights:
        fact = (
            f'<p>{esc(_flight_when(flight, lang))}. {esc(_bi(flight["outcome"], lang))}</p>'
            f'<div class="ss-pills">'
            f'<span>{esc(labels[7])} {_yes_no(flight["booster_catch"], lang)}</span>'
            f'<span>{esc(labels[8])} {_yes_no(flight["ship_catch"], lang)}</span>'
            f'<span>{esc(labels[9])}: {esc(_bi(flight["payload"], lang))}</span>'
            f'</div>{_src_links(flight.get("sources"))}')
        sections.append((f'{flight_word} {flight["number"]}', fact, flight_photo.get(flight["number"], "")))
    if related:
        rel = (f'<p class="hubcount">{esc(_count_label(len(related), lang))}.</p>'
               + hub_cards(related, lang))
        sections.append((labels[10], rel + map_link, ""))
    else:
        sections.append((labels[10], map_link, ""))
    rubric = hub_rubric(lang, "SpaceX", "spacex/", "Starship", "starship/")
    article, image = hub_article(
        lang, title, intro, data["updated"], rubric, "starship-5-catch", sections)
    return nav + article, ld, intro, image


def load_evergreen():
    path = ROOT / "content" / "data" / "evergreen.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    hubs = data.get("hubs") if isinstance(data, dict) else None
    return hubs if isinstance(hubs, list) else []


def evergreen_articles(hub, arts):
    rule = hub.get("match") if isinstance(hub.get("match"), dict) else {}
    cat = str(rule.get("category") or "")
    bits = [str(bit).lower() for bit in (rule.get("any") or []) if str(bit).strip()]
    topic = str(rule.get("topic") or "")
    out = []
    for a in arts:
        if cat and a.get("category") != cat and cat not in (a.get("also") or []):
            continue
        if topic and topic not in set(article_topics(a)):
            continue
        if bits:
            blob = " ".join([
                a.get("slug") or "",
                (a.get("en") or {}).get("title") or "",
                (a.get("nl") or {}).get("title") or "",
            ]).lower()
            if not any(bit in blob for bit in bits):
                continue
        if cat or topic or bits:
            out.append(a)
    out.sort(key=published, reverse=True)
    return out


def evergreen_for(a):
    return [hub for hub in load_evergreen() if a in evergreen_articles(hub, [a])]


GUIDE_CATS = (
    ("winter-mats-model-3-y", "Floor mats", "Vloermatten"),
    ("model-y-trunk-floor-mats", "Trunk mats", "Kofferbakmatten"),
    ("screen-glass-model-3-y", "Screen protectors", "Schermbeschermers"),
    ("phone-mounts-model-3-y", "Phone mounts", "Telefoonhouders"),
    ("tyre-pumps", "Tyre pumps", "Bandenpompen"),
    ("europe-home-chargers", "Home chargers", "Thuisladers"),
    ("type-2-cables", "Charging cables", "Laadkabels"),
    ("portable-chargers-adapters", "Portable chargers", "Mobiele laders"),
    ("starlink-mini-road-trip", "Starlink", "Starlink"),
    ("sentry-usb-drive", "USB drives", "USB-sticks"),
    ("mud-flaps-model-y", "Mud flaps", "Spatlappen"),
    ("roof-shades-model-y", "Roof shades", "Dakschermen"),
    ("console-trays-model-3-y", "Console trays", "Consolebakjes"),
    ("key-card-holders", "Key cards", "Keycards"),
    ("model-y-3-accessories", "Accessories", "Accessoires"),
)


# A later product, when the first photo is already another tile or is no longer the one to show.
GUIDE_CAT_PICK = {
    "model-y-3-accessories": "B09SWFCTFQ",
    "sentry-usb-drive": "B00P8XQPY4",
}


def _guide_product_photos(doc):
    """Main photo of each product currently on the guide, in page order."""
    photos = []
    for kind, fields in doc.get("pieces") or []:
        if kind != "product" or not isinstance(fields, dict):
            continue
        asin = _product_asin(str(fields.get("url") or ""))
        gallery = AMAZON_GALLERIES.get(asin) or []
        item = str(fields.get("item") or "").strip()
        ali = ALI_GALLERIES.get(item) or []
        local = guide_local_image(fields)
        src = (gallery[0] if gallery else "") or (ali[0] if ali else "") or local
        key = asin or item
        if src and key:
            photos.append((key, src))
    return photos


def _guide_category_photo(doc, used):
    """One unused main photo from a product on this guide."""
    photos = _guide_product_photos(doc)
    prefer = GUIDE_CAT_PICK.get(doc.get("slug") or "")
    if prefer:
        photos = [row for row in photos if row[0] == prefer] + [row for row in photos if row[0] != prefer]
    for _key, src in photos:
        if src in used:
            continue
        used.add(src)
        return src
    return ""


def guide_category_cards(lang, current=""):
    """Two-column category tiles for the buying-guide sidebar."""
    docs = {d["slug"]: d for d in GUIDE_DOCS if not d.get("template")}
    if not docs:
        return ""
    order = [row[0] for row in GUIDE_CATS]
    labels = {row[0]: row for row in GUIDE_CATS}
    for slug in docs:
        if slug not in labels:
            doc = docs[slug]
            title = doc["meta"].get(f"title_{lang}") or doc["meta"].get("title_en") or slug
            labels[slug] = (slug, title, title)
            order.append(slug)
    cards = []
    used_photos = set()
    for slug in order:
        doc = docs.get(slug)
        row = labels.get(slug)
        if not doc or not row:
            continue
        name = row[1] if lang == "en" else row[2]
        href = url(lang, guides_path(lang) + slug + "/")
        photo = _guide_category_photo(doc, used_photos)
        img = (f'<img src="{esc(photo)}" alt="" width="160" height="160" loading="lazy" decoding="async">'
               if photo else "")
        on = " is-on" if slug == current else ""
        here = ' aria-current="page"' if slug == current else ""
        cards.append(
            f'<a class="gcat{on}" href="{esc(href)}"{here}>'
            f'<span class="gtile">{img}</span><span class="gname">{esc(name)}</span></a>')
    if not cards:
        return ""
    title = "Guides" if lang == "en" else "Gidsen"
    return _side_section(title, f'<div class="gcatgrid">{"".join(cards)}</div>')


def buying_guides_side(lang):
    """Every published buying guide, on the sidebar of every page."""
    docs = [d for d in GUIDE_DOCS if not d.get("template")]
    if not docs:
        return ""
    docs.sort(key=lambda d: (d["meta"].get(f"title_{lang}") or d["meta"].get("title_en") or "").lower())
    items = []
    for doc in docs:
        name = doc["meta"].get(f"title_{lang}") or doc["meta"].get("title_en") or doc["slug"]
        items.append((name, url(lang, guides_path(lang) + doc["slug"] + "/")))
    title = "Buying guides" if lang == "en" else "Koopgidsen"
    return _side_section(title, "<ul>" + _side_links(items) + "</ul>")


def model_accessory_links(key, lang):
    """Model 3 and Model Y pages list the buying guides. Other cars keep the coming-soon line."""
    L = LANGS[lang]
    if not str(key).startswith(("model-3", "model-y")):
        return f'<p class="soon">{L["i_acc_soon"]}</p>'
    docs = [d for d in GUIDE_DOCS if not d.get("template")]
    if not docs:
        return f'<p class="soon">{L["i_acc_soon"]}</p>'
    lead = ("Buying guides for a Model 3 or a Model Y. Match the year on the product page."
            if lang == "en" else
            "Koopgidsen voor een Model 3 of een Model Y. Stem het jaar af op de productpagina.")
    items = []
    for doc in docs:
        name = doc["meta"].get(f"title_{lang}") or doc["meta"].get("title_en") or doc["slug"]
        href = url(lang, guides_path(lang) + doc["slug"] + "/")
        items.append(f'<li><a href="{esc(href)}">{esc(name)}</a></li>')
    return f'<p>{esc(lead)}</p><ul>{"".join(items)}</ul>'


def evergreen_side(lang):
    items = [
        (hub["title"][lang], url(lang, hub["path"]))
        for hub in load_evergreen()
        if hub.get("title") and hub.get("path")
    ]
    items.append((
        "All Starship flights" if lang == "en" else "Alle Starship-vluchten",
        url(lang, "starship/"),
    ))
    if not items:
        return ""
    title = "Hubs" if lang == "en" else "Dossiers"
    return _side_section(title, '<ul class="hubs">' + _side_links(items) + "</ul>")


def evergreen_article_links(a, lang):
    hubs = evergreen_for(a)
    if not hubs:
        return ""
    links = "".join(
        f'<a href="{url(lang, hub["path"])}">{esc(hub["title"][lang])}</a>' for hub in hubs)
    return f'<p class="hublink">{links}</p>'


def evergreen_body(hub, arts, lang):
    title = hub["title"][lang]
    intro = (hub.get("intro") or {}).get(lang) or ""
    updated = str(hub.get("updated") or load_data("evergreen.json").get("updated") or "")[:10]
    events = sorted(hub.get("events") or [], key=lambda row: str(row.get("date") or ""), reverse=True)
    related = evergreen_articles(hub, arts)
    rel = f'<p class="hubcount">{esc(_coverage_note(lang))}</p>'
    if related:
        rel = (f'<p class="hubcount">{esc(_count_label(len(related), lang))}.</p>'
               + hub_cards(related, lang))
    nav, ld = crumbs(lang, [(title, None)])
    photos = {
        "fsd-europe": {"2026-04-10": "fsd-modelx", "2026-06-17": "fsd-madmax"},
        "deliveries": {"2026-07-02": "deliver-3", "2026-10-02": "deliver-ct"},
        "starlink-nl": {"2021-05-13": "starlink-dish2", "2021-10-13": "starlink-ship"},
    }.get(hub.get("key"), {})
    heroes = {
        "fsd-europe": "fsd-tahoe",
        "deliveries": "deliver-y",
        "starlink-nl": "starlink-dish",
    }
    rubrics = {
        "fsd-europe": ("Tesla", "tesla/", "FSD", "fsd/"),
        "deliveries": ("Tesla", "tesla/", "", ""),
        "starlink-nl": ("Starlink", "starlink/", "", ""),
    }
    sections = []
    for event in events:
        text = (event.get("text") or {}).get(lang) or ""
        sources = event.get("sources") or []
        if len(sources) < 2 or not text:
            continue
        date = str(event.get("date") or "")
        label = fmt_date(date, lang) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else date
        inner = f'<p>{esc(text)}</p>{_src_links(sources)}'
        sections.append((label, inner, photos.get(date, "")))
    head = "On TrendingTesla" if lang == "en" else "Op TrendingTesla"
    sections.append((head, rel, ""))
    layer, layer_path, sub, sub_path = rubrics.get(hub.get("key"), ("Tesla", "tesla/", "", ""))
    rubric = hub_rubric(lang, layer, layer_path, sub, sub_path)
    article, image = hub_article(
        lang, title, intro, updated, rubric, heroes.get(hub.get("key"), ""), sections)
    return nav + article, ld, intro, updated, image


BRIEF_LAYERS = (
    ("tesla", "tesla/", "tesla", "Tesla"),
    ("energy", "tesla-energy/", "energy", "Tesla Energy"),
    ("spacex", "spacex/", "spacex", "SpaceX"),
    ("spacexsi", "spacexsi/", "spacexsi", "SpaceXSI"),
    ("starlink", "starlink/", "link", "Starlink"),
    ("neuralink", "neuralink/", "neural", "Neuralink"),
    ("boring", "boring/", "boring", "Boring"),
)
PROMISE_STATUS = ("delivered", "late", "pending", "abandoned")
_KV_KEYS = (
    "title_en", "title_nl", "en", "nl", "why_en", "why_nl",
    "name_en", "name_nl", "pros_en", "pros_nl", "cons_en", "cons_nl",
    "fits_en", "fits_nl",
    "url", "ali_url", "image", "item", "note_en", "note_nl", "option_en", "option_nl", "button_en", "button_nl",
    "caption_en", "caption_nl", "columns_en", "columns_nl", "row_en", "row_nl",
    "slug",
)
_KV_LISTS = {"pros_en", "pros_nl", "cons_en", "cons_nl", "row_en", "row_nl"}


def _front_matter(text):
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[3:end].splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[end + 4:].lstrip("\n")


def _kv_block(block):
    fields = {}
    current = None
    buf = []

    def flush():
        nonlocal current, buf
        if current is None:
            return
        text = " ".join(part.strip() for part in buf if part.strip()).strip()
        if current in _KV_LISTS:
            fields.setdefault(current, [])
            if text:
                fields[current].append(text)
        else:
            fields[current] = text
        current = None
        buf = []

    for line in block.splitlines():
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match and match.group(1) in _KV_KEYS:
            flush()
            current = match.group(1)
            buf = [match.group(2)]
        elif current is not None:
            buf.append(line)
    flush()
    return fields


def _bits(value):
    chunks = value if isinstance(value, list) else [value or ""]
    out = []
    for chunk in chunks:
        out.extend(part.strip() for part in str(chunk).split("|") if part.strip())
    return out


def _layer_meta(key):
    for item in BRIEF_LAYERS:
        if item[0] == key:
            return item
    return None


def layer_tag(key, lang):
    meta = _layer_meta(key)
    if not meta:
        return ""
    _key, href, tone, name = meta
    return f'<a class="ltag ltag-{tone}" href="{url(lang, href)}">{esc(name)}</a>'


def _markdown_docs(folder, include_hidden=False):
    root = ROOT / "content" / folder
    docs = []
    if not root.is_dir():
        return docs
    for path in sorted(root.glob("*.md")):
        hidden = path.name.startswith("_")
        if hidden and not include_hidden:
            continue
        meta, body = _front_matter(path.read_text(encoding="utf-8"))
        docs.append({
            "slug": path.stem.lstrip("_") or path.stem,
            "meta": meta,
            "body": body,
            "template": hidden or str(meta.get("template") or "").lower() in ("1", "true", "yes"),
        })
    return docs


def _parse_brief_layers(body):
    layers = []
    for chunk in re.split(r"(?m)^##\s+", body):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        key = lines[0].strip().lower()
        if not _layer_meta(key):
            continue
        items = []
        for part in re.split(r"(?m)^###\s+item\s*$", "\n".join(lines[1:])):
            fields = _kv_block(part)
            if fields.get("title_en") or fields.get("en"):
                items.append(fields)
        if items:
            layers.append((key, items))
    return layers


def load_briefings():
    """Published issues only. Underscore files and template: true stay out of the site."""
    docs = []
    for doc in _markdown_docs("briefings", include_hidden=False):
        if doc["template"]:
            continue
        doc["layers"] = _parse_brief_layers(doc["body"])
        docs.append(doc)
    docs.sort(key=lambda doc: doc["meta"].get("date") or "", reverse=True)
    return docs


def _parse_guide(body):
    pieces = []
    lines = body.splitlines()
    index = 0
    buf = []
    while index < len(lines):
        line = lines[index]
        if line.startswith(":::"):
            if any(part.strip() for part in buf):
                pieces.append(("prose", _kv_block("\n".join(buf))))
            buf = []
            kind = line[3:].strip() or "prose"
            index += 1
            block = []
            while index < len(lines) and lines[index].strip() != ":::":
                block.append(lines[index])
                index += 1
            pieces.append((kind, _kv_block("\n".join(block))))
        else:
            buf.append(line)
        index += 1
    if any(part.strip() for part in buf):
        pieces.append(("prose", _kv_block("\n".join(buf))))
    return pieces


def load_guides():
    docs = _markdown_docs("guides", include_hidden=INCLUDE_EXAMPLES)
    for doc in docs:
        doc["pieces"] = _parse_guide(doc["body"])
    return docs


def load_promises():
    path = ROOT / "content" / "data" / "promises.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    rows = []
    for row in data.get("rows") or []:
        if not isinstance(row, dict) or not _layer_meta(str(row.get("layer") or "")):
            continue
        if str(row.get("status") or "") not in PROMISE_STATUS:
            continue
        promise = row.get("promise") if isinstance(row.get("promise"), dict) else {}
        if not str(promise.get("en") or promise.get("nl") or "").strip():
            continue
        rows.append(row)
    return rows


def guide_amazon(href, lang="nl"):
    """amazon.nl links carry the Associates tag and open in the page language."""
    if not href.startswith("https://") or href.count("/") < 2:
        return href
    host = href.split("/")[2].lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "amazon.nl":
        return href
    tag = affiliate_tag("nl")
    if tag:
        href = _query_set(href, "tag", tag)
    return _query_set(href, "language", "en_GB" if lang == "en" else "nl_NL")


def disclosure_line(lang, klass="afftop"):
    href = url(lang, disclosure_path(lang))
    if lang == "en":
        text = ("Affiliate disclosure: if you buy through a link on this page, TrendingTesla may earn a commission "
                "from Amazon.nl or AliExpress, at no extra cost to you.")
        more = "How this works"
    else:
        text = ("Affiliate-melding: koop je via een link op deze pagina, dan kan TrendingTesla een commissie ontvangen "
                "via Amazon.nl of AliExpress. Voor jou kost het niets extra.")
        more = "Zo werkt dat"
    return f'<p class="{klass}">{esc(text)} <a href="{href}">{esc(more)}</a>.</p>'


def newsletter_pitch(lang):
    briefing = url(lang, "briefing/")
    privacy = url(lang, "privacy/")
    if lang == "en":
        return (
            "<p>One email a week: the briefing. It walks the seven layers, Tesla, Tesla Energy, SpaceX, "
            "Starlink, SpaceXSI, Neuralink and The Boring Company, with one line on why each item matters.</p>"
            f'<p>Double opt-in, and you can unsubscribe from any email. <a href="{privacy}">Privacy</a>.</p>'
            f'<p><a href="{briefing}">Weekly briefing</a>.</p>')
    return (
        "<p>Eén mail per week: de briefing. Die loopt de zeven lagen langs, Tesla, Tesla Energy, SpaceX, "
        "Starlink, SpaceXSI, Neuralink en The Boring Company, met één regel over waarom elk punt ertoe doet.</p>"
        f'<p>Dubbele bevestiging, en afmelden kan vanuit elke e-mail. <a href="{privacy}">Privacy</a>.</p>'
        f'<p><a href="{briefing}">Weekbriefing</a>.</p>')


def nl_sticky(lang):
    """Dismissible signup on articles. sessionStorage is tab-only UI state, not a cookie."""
    L = LANGS[lang]
    fid = f"nlstick-email-{lang}"
    dismiss = "Not now" if lang == "en" else "Niet nu"
    return (
        f'<aside class="nlstick" hidden>'
        f'<form class="nlbar-form" {ml_form_attrs(lang)}>'
        f'<label class="nlbar-h" for="{fid}">{esc(L["bar_h"])}</label>'
        f'<input id="{fid}" type="email" name="fields[email]" required maxlength="200" '
        f'autocomplete="email" inputmode="email" placeholder="{esc(L["news_email"])}">'
        f'<div class="nlstick-actions"><button type="submit">{esc(L["news_btn"])}</button>'
        f'<button type="button" class="nlstick-x">{esc(dismiss)}</button></div>'
        f'{ml_hidden()}<p class="nlbar-msg" role="status" hidden></p></form></aside>'
        "<script>(function(){var bar=document.querySelector('.nlstick');if(!bar)return;"
        "var key='tt-nlstick';try{if(sessionStorage.getItem(key))return;}catch(e){}"
        "bar.hidden=false;function place(){var c=document.getElementById('consent');"
        "var base=(c&&!c.hidden)?c.offsetHeight+16:12;"
        "bar.style.bottom='calc('+base+'px + env(safe-area-inset-bottom))';}place();"
        "bar.querySelector('.nlstick-x').addEventListener('click',function(){bar.hidden=true;"
        "try{sessionStorage.setItem(key,'1')}catch(e){}});"
        "var end=document.querySelector('aside.nlbar');"
        "if(end&&'IntersectionObserver' in window){new IntersectionObserver(function(es){"
        "es.forEach(function(ev){bar.classList.toggle('is-quiet',ev.isIntersecting);});}"
        ").observe(end);}})();</script>"
        f"{ML_BAR_JS}"
    )


def briefing_index_body(docs, lang):
    if lang == "en":
        title = "Weekly briefing"
        intro = "One issue a week across the seven layers. Each item is what happened, plus one line on why it matters."
        empty = "First briefing coming soon"
    else:
        title = "Weekbriefing"
        intro = "Eén editie per week over de zeven lagen. Elk punt is wat er gebeurde, plus één regel over waarom het ertoe doet."
        empty = "De eerste briefing volgt binnenkort"
    if docs:
        lis = []
        for doc in docs:
            name = doc["meta"].get(f"title_{lang}") or doc["meta"].get("title_en") or doc["slug"]
            when = fmt_date(doc["meta"]["date"], lang) if doc["meta"].get("date") else ""
            lis.append(
                f'<li><a href="{url(lang, "briefing/" + doc["slug"] + "/")}"><strong>{esc(name)}</strong>'
                f'<span>{esc(when)}</span></a></li>')
        cards = f'<ul class="brief-list">{"".join(lis)}</ul>'
        signup = (f'<div class="brief-cta">{ml_bar(lang, "-a")}</div>{cards}'
                  f'<div class="brief-cta">{ml_bar(lang, "-b")}</div>')
    else:
        cards = f'<p class="prom-empty">{esc(empty)}</p>'
        signup = f'{cards}<div class="brief-cta">{ml_bar(lang)}</div>'
    return (
        f'<article class="narrow brief"><h1>{esc(title)}</h1>{signup}</article>'), title, intro


def briefing_issue_body(doc, lang):
    L = LANGS[lang]
    title = doc["meta"].get(f"title_{lang}") or doc["meta"].get("title_en") or doc["slug"]
    dek = doc["meta"].get(f"dek_{lang}") or doc["meta"].get("dek_en") or ""
    banner = ""
    if doc["template"]:
        note = ("Template. This is not a published briefing." if lang == "en"
                else "Sjabloon. Dit is geen gepubliceerde briefing.")
        banner = f'<p class="tplnote">{esc(note)}</p>'
    dated = f'<p class="meta">{fmt_date(doc["meta"]["date"], lang)}</p>' if doc["meta"].get("date") else ""
    sections = []
    why_label = "Why it matters." if lang == "en" else "Waarom het ertoe doet."
    for key, items in doc["layers"]:
        lis = []
        for item in items:
            heading = item.get(f"title_{lang}") or item.get("title_en") or ""
            slug = str(item.get("slug") or "").strip()
            if slug and heading:
                heading_html = f'<a href="{url(lang, slug + "/")}">{esc(heading)}</a>'
            else:
                heading_html = esc(heading)
            text = item.get(lang) or item.get("en") or ""
            why = item.get(f"why_{lang}") or item.get("why_en") or ""
            why_html = f'<p class="brief-why"><b>{esc(why_label)}</b> {esc(why)}</p>' if why else ""
            lis.append(f"<li><h3>{heading_html}</h3><p>{esc(text)}</p>{why_html}</li>")
        sections.append(f'<section class="brief-layer"><h2>{layer_tag(key, lang)}</h2><ol>{"".join(lis)}</ol></section>')
    top = f'<div class="brief-cta">{ml_bar(lang, "-a")}</div>'
    end = f'<div class="brief-cta">{ml_bar(lang, "-b")}</div>'
    body = (
        f'<article class="narrow brief"><h1>{esc(title)}</h1>{banner}'
        f'<p class="byline"><a href="{url(lang, "editorial/")}">{esc(L["byline"])}</a></p>{dated}'
        f'<p class="lead">{esc(dek)}</p>{top}{"".join(sections)}{end}</article>')
    return body, title, dek or title


def promises_body(rows, lang):
    if lang == "en":
        title = "Promises"
        intro = "A register of public promises from the seven layers: what was said, when it was due, and what happened."
        empty = "The register is not open yet."
        headers = ("Layer", "Promise", "Date made", "Deadline", "Status", "Source")
        any_layer, any_status, source = "Any layer", "Any status", "Source"
        labels = {"delivered": "Delivered", "late": "Late", "pending": "Pending", "abandoned": "Abandoned"}
    else:
        title = "Beloftes"
        intro = "Een register van publieke beloftes uit de zeven lagen: wat er is gezegd, wanneer het zou gebeuren, en wat ervan kwam."
        empty = "Het register is nog niet open."
        headers = ("Laag", "Belofte", "Datum", "Deadline", "Status", "Bron")
        any_layer, any_status, source = "Elke laag", "Elke status", "Bron"
        labels = {"delivered": "Geleverd", "late": "Te laat", "pending": "Open", "abandoned": "Afgeblazen"}
    layer_opts = f'<option value="">{esc(any_layer)}</option>' + "".join(
        f'<option value="{key}">{esc(name)}</option>' for key, _href, _tone, name in BRIEF_LAYERS)
    status_opts = f'<option value="">{esc(any_status)}</option>' + "".join(
        f'<option value="{key}">{esc(label)}</option>' for key, label in labels.items())
    body_rows = []
    for row in rows:
        key = str(row["layer"])
        promise = row.get("promise") if isinstance(row.get("promise"), dict) else {}
        text = str(promise.get(lang) or promise.get("en") or "").strip()
        made = str(row.get("made") or "")
        due = str(row.get("deadline") or "")
        made_s = fmt_date(made, lang) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", made) else ""
        due_s = fmt_date(due, lang) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", due) else ""
        status = str(row["status"])
        href = str(row.get("source") or "")
        status_href = str(row.get("status_source") or "")
        bits = []
        if href.startswith("https://"):
            bits.append(f'<a href="{esc(href)}" rel="noopener noreferrer" target="_blank">{esc(source)}</a>')
        if status_href.startswith("https://"):
            status_label_link = "Status" if lang == "en" else "Stand"
            bits.append(
                f'<a href="{esc(status_href)}" rel="noopener noreferrer" target="_blank">{esc(status_label_link)}</a>')
        src = " · ".join(bits)
        body_rows.append(
            f'<tr data-layer="{esc(key)}" data-status="{esc(status)}"><td>{layer_tag(key, lang)}</td>'
            f'<td>{esc(text)}</td><td>{esc(made_s)}</td><td>{esc(due_s)}</td>'
            f'<td>{esc(labels[status])}</td><td>{src}</td></tr>')
    none_hidden = "" if not body_rows else " hidden"
    script = (
        "<script>(function(){var root=document.querySelector('[data-prom]');if(!root)return;"
        "var rows=[].slice.call(document.querySelectorAll('.prom tbody tr'));"
        "var empty=document.querySelector('.prom-empty');"
        "function apply(){var layer=root.querySelector('[data-filter=layer]').value;"
        "var status=root.querySelector('[data-filter=status]').value;var n=0;"
        "rows.forEach(function(tr){var ok=(!layer||tr.getAttribute('data-layer')===layer)"
        "&&(!status||tr.getAttribute('data-status')===status);tr.hidden=!ok;if(ok)n++;});"
        "if(empty)empty.hidden=n!==0;}"
        "root.addEventListener('change',apply);apply();})();</script>")
    layer_label = "Layer" if lang == "en" else "Laag"
    status_label = "Status"
    return (
        f'<article class="narrow"><h1>{esc(title)}</h1><div class="prose"><p>{esc(intro)}</p></div>'
        f'<div class="prom-filters" data-prom>'
        f'<label>{esc(layer_label)}<select data-filter="layer">{layer_opts}</select></label>'
        f'<label>{esc(status_label)}<select data-filter="status">{status_opts}</select></label></div>'
        f'<div class="prom-wrap"><table class="prom"><thead><tr>{"".join(f"<th>{esc(h)}</th>" for h in headers)}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></div>'
        f'<p class="prom-empty"{none_hidden}>{esc(empty)}</p>{script}</article>'), title, intro


def _guide_product(fields, lang):
    name = fields.get(f"name_{lang}") or fields.get("name_en") or ""
    if not name:
        return ""
    pros = _bits(fields.get(f"pros_{lang}") or fields.get("pros_en"))[:3]
    fits = (fields.get(f"fits_{lang}") or fields.get("fits_en")
            or fields.get(f"cons_{lang}") or fields.get("cons_en") or "")
    href = guide_amazon(str(fields.get("url") or ""), lang)
    who = "Who it fits" if lang == "en" else "Voor wie het past"
    amazon_host = ""
    if href.startswith("https://") and href.count("/") >= 2:
        amazon_host = href.split("/")[2].lower()
    amazon_ok = amazon_host in ("www.amazon.nl", "amazon.nl")
    ali = ali_href(fields.get("ali_url"), lang)
    if amazon_ok and ali:
        amazon_only = dict(fields)
        amazon_only.pop("ali_url", None)
        ali_only = dict(fields)
        ali_only.pop("url", None)
        return _guide_product(amazon_only, lang) + _guide_product(ali_only, lang)
    button = "Bekijk op Amazon" if lang == "nl" else "Check out Amazon"
    ali_label = "Bekijk op AliExpress" if lang == "nl" else "Check out AliExpress"
    lists = ""
    if pros:
        lists = f'<ul>{"".join(f"<li>{esc(item)}</li>" for item in pros)}</ul>'
    note = fields.get(f"note_{lang}") or fields.get("note_en") or ""
    note_html = f'<p>{esc(note)}</p>' if str(note).strip() else ""
    option = fields.get(f"option_{lang}") or fields.get("option_en") or ""
    option_html = f'<p class="popt">{esc(option)}</p>' if str(option).strip() else ""
    fit_html = f'<p class="fits"><b>{esc(who)}.</b> {esc(fits)}</p>' if str(fits).strip() else ""
    link = ""
    if amazon_ok or ali:
        parts = []
        if amazon_ok:
            parts.append(f'<a class="btn amazon-go" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{esc(button)}</a>')
        if ali:
            parts.append(f'<a class="btn" href="{esc(ali)}" rel="sponsored nofollow noopener" target="_blank">{esc(ali_label)}</a>')
        link = f'<div class="store-btns">{"".join(parts)}</div>'
    local = guide_local_image(fields)
    photo_href = ""
    remote = False
    item_id = str(fields.get("item") or "").strip()
    ali_item = re.search(r"ali-(\d{8,})", str(fields.get("image") or ""))
    if not item_id and ali_item:
        item_id = ali_item.group(1)
    ali_remote = ALI_GALLERIES.get(item_id, []) if item_id else []
    if ali_remote:
        srcs = ali_remote
        photo_href = ali or ""
        remote = bool(photo_href)
    elif local:
        srcs = local_gallery(local)
        if ali and not amazon_ok:
            photo_href = ali
            remote = True
    elif amazon_ok:
        srcs = list(AMAZON_GALLERIES.get(_product_asin(href), []))
        photo_href = href
        remote = True
    else:
        licensed = licensed_card_photo(href)
        srcs = [licensed] if licensed else []
    img = gallery_html(srcs, name, photo_href, remote, lang)
    if amazon_ok:
        price_key = _product_asin(href)
    else:
        price_key = f"ali:{item_id}" if item_id else ""
    cost = price_html(price_key, lang) if price_key else ""
    stars = rating_html(price_key, lang) if price_key else ""
    klass = "gbox" if img else "gbox noimg"
    return (f'<aside class="{klass}">{img}<div><h2>{esc(name)}</h2>{lists}{note_html}{fit_html}'
            f'{option_html}{stars}{cost}{link}</div></aside>')


def _guide_hero(doc, lang):
    """Official video of that exact product, or nothing. No stand-in photo and no credit line."""
    video = GUIDE_VIDEO.get(doc.get("slug") or "")
    if not video:
        return ""
    vid = video["id"]
    alt = (video.get("alt") or {}).get(lang) or ""
    label = "Play the video" if lang == "en" else "Speel de video"
    thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return (
        f'<figure class="avid long"><button class="avb" type="button" data-vid="{esc(vid)}" '
        f'aria-label="{esc(label)}">'
        f'<img src="{esc(thumb)}" alt="{esc(alt)}" width="480" height="360" '
        f'fetchpriority="high" decoding="async">'
        f'<span class="shp" aria-hidden="true"></span></button></figure>')


def _guide_table(fields, lang):
    columns = _bits(fields.get(f"columns_{lang}") or fields.get("columns_en"))
    rows = fields.get(f"row_{lang}") or fields.get("row_en") or []
    if isinstance(rows, str):
        rows = [rows]
    if not columns:
        return ""
    caption = fields.get(f"caption_{lang}") or fields.get("caption_en") or ""
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    head = "".join(f"<th>{esc(col)}</th>" for col in columns)
    body = []
    for row in rows:
        cells = [part.strip() for part in str(row).split("|")]
        while len(cells) < len(columns):
            cells.append("")
        body.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in cells[:len(columns)]) + "</tr>")
    return f'<table class="gtable">{cap}<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def guide_body(doc, lang):
    title = doc["meta"].get(f"title_{lang}") or doc["meta"].get("title_en") or doc["slug"]
    desc = doc["meta"].get(f"description_{lang}") or doc["meta"].get("description_en") or title
    banner = ""
    if doc["template"]:
        note = ("Template. This is not a published guide." if lang == "en"
                else "Sjabloon. Dit is geen gepubliceerde gids.")
        banner = f'<p class="tplnote">{esc(note)}</p>'
    prose, products = [], []
    for kind, fields in doc["pieces"]:
        if kind == "product":
            products.append(_guide_product(fields, lang))
        elif kind == "compare":
            continue
        else:
            text = fields.get(lang) or fields.get("en") or ""
            if text:
                prose.append(f"<p>{esc(text)}</p>")
    chunks = [banner, *prose, *products]
    byline = f'<p class="byline"><a href="{url(lang, "editorial/")}">{esc(LANGS[lang]["byline"])}</a></p>'
    hero = _guide_hero(doc, lang)
    body = (f'<article class="narrow">{hero}<h1>{esc(title)}</h1>{byline}'
            f'<div class="prose">{"".join(chunks)}</div></article>')
    return body, title, desc


def guides_index_body(docs, lang):
    real = [doc for doc in docs if not doc["template"]]
    if lang == "en":
        title = "Buying guides"
        intro = ("Guides for things you can buy, with what each one is for. Prices change, so check the current price."
                 if real else "Guides for things you can buy. None are published yet.")
        sample = "Layout template"
    else:
        title = "Koopgidsen"
        intro = ("Gidsen voor dingen die je kunt kopen, met waar elk voor dient. Prijzen veranderen, dus kijk de actuele prijs na."
                 if real else "Gidsen voor dingen die je kunt kopen. Er is er nog geen gepubliceerd.")
        sample = "Opmaakvoorbeeld"
    items = ""
    if real:
        lis = []
        for doc in real:
            name = doc["meta"].get(f"title_{lang}") or doc["meta"].get("title_en") or doc["slug"]
            lis.append(f'<li><a href="{url(lang, guides_path(lang) + doc["slug"] + "/")}">{esc(name)}</a></li>')
        items = f'<ul class="brief-list">{"".join(lis)}</ul>'
    else:
        empty = "No buying guide is published yet." if lang == "en" else "Er is nog geen koopgids gepubliceerd."
        items = f'<p class="prom-empty">{esc(empty)}</p>'
    samples = [doc for doc in docs if doc["template"]]
    sample_link = ""
    if samples:
        sample_link = (
            f'<p><a href="{url(lang, guides_path(lang) + samples[0]["slug"] + "/")}">{esc(sample)}</a></p>')
    body = (
        f'<article class="narrow"><h1>{esc(title)}</h1>'
        f'<div class="prose"><p>{esc(intro)}</p></div>{items}{sample_link}</article>')
    return body, title, intro


def advertise_body(lang):
    contact = url(lang, "contact/")
    if lang == "en":
        title = "Advertise"
        desc = "How to talk to TrendingTesla about a placement."
        html_body = (
            f"<p>TrendingTesla is independent. A placement, in the weekly briefing or beside a guide, "
            f"is labeled so readers can see it is paid.</p>"
            f'<p>For a conversation, use the <a href="{contact}">contact form</a>.</p>')
    else:
        title = "Adverteren"
        desc = "Hoe je TrendingTesla spreekt over een plaatsing."
        html_body = (
            f"<p>TrendingTesla is onafhankelijk. Een plaatsing, in de weekbriefing of bij een gids, "
            f"krijgt een label zodat lezers zien dat die betaald is.</p>"
            f'<p>Voor een gesprek gebruik je het <a href="{contact}">contactformulier</a>.</p>')
    return (
        f'<article class="narrow"><h1>{esc(title)}</h1><div class="prose">{html_body}</div></article>'), title, desc


def disclosure_body(lang):
    contact = url(lang, "contact/")
    if lang == "en":
        title = "Affiliate disclosure"
        desc = "When TrendingTesla may earn a commission from a link."
        html_body = (
            "<p>Some pages link to Amazon.nl and, where we have one, to AliExpress. If you buy through one of "
            "those links, TrendingTesla may earn a commission. You do not pay extra. The link is marked as sponsored.</p>"
            "<p>A commission never changes what we write. We do not publish a page in order to sell a product. "
            "A product box is optional. The Amazon button names a product whose Amazon.nl page we checked. "
            "The AliExpress button is a second place to buy a similar item, and the fit line says when that item covers different years.</p>"
            f'<p>Questions go through the <a href="{contact}">contact form</a>.</p>')
    else:
        title = "Affiliate-melding"
        desc = "Wanneer TrendingTesla een commissie kan ontvangen via een link."
        html_body = (
            "<p>Sommige pagina's linken naar Amazon.nl en, waar we die hebben, naar AliExpress. Koop je via zo'n "
            "link, dan kan TrendingTesla een commissie ontvangen. Jij betaalt niets extra. De link is gemarkeerd als gesponsord.</p>"
            "<p>Een commissie verandert nooit wat we schrijven. We publiceren geen pagina om een product te verkopen. "
            "Een productvak is optioneel. De Amazon-knop noemt een product waarvan we de Amazon.nl-pagina hebben nagekeken. "
            "De AliExpress-knop is een tweede plek om een vergelijkbaar artikel te kopen, en de pasregel zegt het wanneer dat artikel andere jaren dekt.</p>"
            f'<p>Vragen gaan via het <a href="{contact}">contactformulier</a>.</p>')
    return (
        f'<article class="narrow"><h1>{esc(title)}</h1><div class="prose">{html_body}</div></article>'), title, desc


def build():
    load_money()
    load_affiliate()
    load_amazon_images()
    load_ali_images()
    load_product_prices()
    load_image_licences()
    load_shorts()
    _OPT.clear()
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
    assign_palettes(arts)
    news = [a for a in arts if a["category"] != "guides"]
    guides = [a for a in arts if a["category"] == "guides"]
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT)
    write_ticker()

    # Images
    for a in arts:
        make_cover(OUT / "img" / "v" / f"{a['slug']}.jpg", "", "", a["category"], "", "", with_text=False)
        for lang in LANGS:
            make_cover(OUT / social_img(a, lang).lstrip("/"), a[lang]["title"], CATEGORIES[a["category"]][lang],
                       a["category"], "", fmt_date(a["date"], lang))
    for lang in LANGS:
        make_cover(OUT / "img" / f"default-{lang}.jpg", LANGS[lang]["tagline"], NAME, "news", "", "trendingtesla.com")
    hero_photo = "/img/hero.jpg" if (STATIC / "img" / "hero.jpg").exists() else None
    briefing_docs = load_briefings()
    global GUIDE_DOCS
    guide_docs = load_guides()
    GUIDE_DOCS = guide_docs
    promise_rows = load_promises()

    for lang in LANGS:
        L = LANGS[lang]

        # ---------- Home ----------
        body, crumb_ld = homepage(arts, lang)
        site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "alternateName": ["Trending Tesla", "trendingtesla.com"],
                   "url": SITE + url(lang), "inLanguage": lang,
                   "publisher": {"@type": "Organization", "name": NAME, "url": SITE,
                                 "logo": {"@type": "ImageObject", "url": SITE + "/favicon-512.png", "width": 512, "height": 512},
                                 "sameAs": ["https://www.youtube.com/@TrendingTesla"]}}
        write(url(lang), page(lang, "", NAME, L["home_desc"], body,
                              extra_head=ld_script(site_ld) + ld_script(crumb_ld)))

        # ---------- Category pages ----------
        for key, c in CATEGORIES.items():
            if key in REDIRECT_CATS:
                continue
            if key == "models":
                content, crumb_ld, intro, listed_models = models_overview(lang)
                listed = [{
                    "@type": "ListItem", "position": i + 1,
                    "name": model_heading(k, lang),
                    "url": SITE + url(lang, f"model/{k}/"),
                } for i, k in enumerate(listed_models)]
                overview_ld = {
                    "@context": "https://schema.org", "@type": "CollectionPage",
                    "name": L["nav_models"], "description": intro,
                    "url": SITE + url(lang, "category/models/"), "inLanguage": lang,
                    "publisher": {"@type": "Organization", "name": NAME, "url": SITE},
                    "mainEntity": {"@type": "ItemList", "itemListElement": listed},
                }
                write(url(lang, "category/models/"),
                      page(lang, "category/models/", L["nav_models"], intro,
                           shell(content, page_side(arts, lang, "hub", "models")),
                           extra_head=ld_script(crumb_ld) + ld_script(overview_ld), active="models"))
                continue
            items = arts if key == "news" else [a for a in arts if a["category"] == key or key in a.get("also", []) or (key == "ecosystem" and a["category"] in ECO)]
            if key == "news":
                items = news
            content, crumb_ld, intro = category_hub(key, items, lang)
            kind = "guides" if key == "guides" else "hub"
            write(url(lang, f"category/{key}/"),
                  page(lang, f"category/{key}/", c[lang], intro,
                       shell(content, page_side(arts, lang, kind, key, skip=items)),
                       extra_head=ld_script(crumb_ld), active=key))

        # ---------- Model pages ----------
        for key, m in MODELS.items():
            if m.get("parent"):
                items = [a for a in arts if key in a.get("models", [])]
            else:
                family = {key} | {k for k, v in MODELS.items() if v.get("parent") == key}
                items = [a for a in arts if family & set(a.get("models", []))]
            ph = model_photo(key)
            content, crumb_ld, desc = model_hub(key, items, lang)
            name = model_heading(key, lang)
            page_facts = PAGE_FACTS.get(key)
            facts = [] if page_facts else ((INFO.get(key) or {}).get(lang, {}).get("specs") or [])
            vehicle_ld = {
                "@context": "https://schema.org", "@type": "Vehicle",
                "name": name, "description": desc,
                "url": SITE + url(lang, f"model/{key}/"), "inLanguage": lang,
                "brand": {"@type": "Brand", "name": "Tesla"},
                "manufacturer": {"@type": "Organization", "name": "Tesla, Inc."},
                "publisher": {"@type": "Organization", "name": NAME, "url": SITE},
            }
            if ph:
                vehicle_ld["image"] = SITE + ph
            props = []
            if page_facts:
                for sec in page_facts["sections"]:
                    for row in sec["rows"]:
                        label, value = row[lang]
                        # Estimated checks and missing figures stay in the table, not as vehicle specs.
                        if row["status"] not in ("unknown", "estimated"):
                            props.append((label, value))
            else:
                props = facts
            if props:
                vehicle_ld["additionalProperty"] = [
                    {"@type": "PropertyValue", "name": k, "value": v} for k, v in props]
            fact_ld = ""
            if page_facts and key.startswith("semi"):
                fact_ld = ld_script({
                    "@context": "https://schema.org", "@type": "WebPage",
                    "name": name, "description": desc,
                    "url": SITE + url(lang, f"model/{key}/"), "inLanguage": lang,
                    "dateModified": "2026-11-19",
                    "author": {"@type": "Organization", "name": NAME, "url": SITE},
                    "publisher": {"@type": "Organization", "name": NAME, "url": SITE},
                })
            write(url(lang, f"model/{key}/"),
                  page(lang, f"model/{key}/", name, desc,
                       shell(content, page_side(arts, lang, "model", key, skip=items)),
                       extra_head=ld_script(crumb_ld) + ld_script(vehicle_ld) + fact_ld, image=ph, active="models"))

        # ---------- Topic hubs, ecosystem map, Starship tracker ----------
        layer_paths = {layer["path"] for layer in LAYERS}
        for spec in HUBS:
            if spec["path"] in layer_paths:
                continue
            items = hub_articles(spec, arts)
            content, crumb_ld, intro = topic_hub(spec, items, lang)
            write(url(lang, spec["path"]), page(
                lang, spec["path"], _bi(spec["title"], lang), intro,
                shell(content, page_side(arts, lang, "hub", spec["key"], skip=items)),
                extra_head=ld_script(crumb_ld), active=spec["key"]))
        for layer in LAYERS:
            content, crumb_ld, intro, items = layer_page(layer, arts, lang)
            write(url(lang, layer["path"]), page(
                lang, layer["path"], _bi(layer["title"], lang), intro,
                shell(content, page_side(arts, lang, "hub", layer["nav"], skip=items)),
                extra_head=ld_script(crumb_ld), active=layer["nav"]))
        eco_body, eco_ld, eco_desc = ecosystem_page(lang)
        eco_path = ecosystem_path(lang)
        write(url(lang, eco_path), page(
            lang, eco_path, L["nav_eco"], eco_desc,
            shell(eco_body, page_side(arts, lang, "hub", "ecosystem")),
            extra_head=ld_script(eco_ld), active="ecosystem",
            alt_path=ecosystem_path(other(lang))))
        ship_body, ship_ld, ship_desc, ship_image = starship_page(lang, arts)
        ship_items = hub_articles({"topics": ["starship"]}, arts)
        write(url(lang, "starship/"), page(
            lang, "starship/", "All Starship flights" if lang == "en" else "Alle Starship-vluchten", ship_desc,
            shell(ship_body, page_side(arts, lang, "hub", "starship", skip=ship_items)),
            extra_head=ld_script(ship_ld), image=ship_image, active="starship"))
        for hub in load_evergreen():
            h_body, h_ld, h_intro, _h_updated, h_image = evergreen_body(hub, arts, lang)
            h_items = evergreen_articles(hub, arts)
            write(url(lang, hub["path"]), page(
                lang, hub["path"], hub["title"][lang], h_intro,
                shell(h_body, page_side(arts, lang, "hub", hub["key"], skip=h_items)),
                extra_head=ld_script(h_ld), image=h_image, active=hub["key"]))

        # ---------- Articles ----------
        for a in arts:
            t = a[lang]
            c = CATEGORIES[a["category"]]
            mod_dt, _differs = modified(a)
            og = str(a.get("og_image") or "").strip()
            if not og.startswith("/img/"):
                og = social_img(a, lang)
            cover = SITE + og
            kind = ["NewsArticle", "LiveBlogPosting"] if a.get("type") == "live" else "NewsArticle"
            ld = {
                "@context": "https://schema.org", "@type": kind,
                "headline": t["title"], "description": t["description"],
                "image": {"@type": "ImageObject", "url": cover, "width": 1200, "height": 630},
                "datePublished": published(a).isoformat(),
                "dateModified": mod_dt.isoformat(),
                "inLanguage": lang, "articleSection": c[lang],
                "mainEntityOfPage": SITE + url(lang, a["slug"] + "/"),
                "publisher": {"@type": "Organization", "name": NAME, "url": SITE,
                              "logo": {"@type": "ImageObject", "url": SITE + "/favicon-512.png", "width": 512, "height": 512}},
                "author": {"@type": "Organization", "name": EDITORIAL_ORG[lang], "url": SITE + url(lang, "editorial/")},
            }
            if a.get("type") == "live":
                rows = live_updates(a)
                ld["coverageStartTime"] = published(a).isoformat()
                if rows and not is_live(a):
                    ld["coverageEndTime"] = rows[0].get("at")
                ld["liveBlogUpdate"] = [
                    {"@type": "BlogPosting", "datePublished": row.get("at"),
                     "articleBody": str(row.get(lang) or "").strip(),
                     "headline": str(row.get(lang) or "").strip()[:110]}
                    for row in rows if str(row.get(lang) or "").strip()]
            v = video_for(a, lang)
            if v:  # video rich result in Google (video thumbnail + length in search)
                sec = int(v.get("seconds") or 0)
                ld["video"] = {"@type": "VideoObject", "name": t["title"], "description": t["description"],
                               "thumbnailUrl": [f"https://i.ytimg.com/vi/{v['id']}/maxresdefault.jpg",
                                                f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg"],
                               "uploadDate": v["published"], "duration": f"PT{sec // 60}M{sec % 60}S" if sec else None,
                               "embedUrl": f"https://www.youtube-nocookie.com/embed/{v['id']}",
                               "contentUrl": f"https://www.youtube.com/watch?v={v['id']}"}
                ld["video"] = {k: x for k, x in ld["video"].items() if x}
            nav, crumb_ld = article_crumbs(a, lang)
            body = shell(nav + pv_article("b", a, arts, lang, live=True),
                          page_side(arts, lang, "article", a, tail=ml_bar(lang))) + nl_sticky(lang)
            head = ld_script(ld) + ld_script(crumb_ld)
            write(url(lang, a["slug"] + "/"),
                  page(lang, a["slug"] + "/", t["title"], t["description"], body, "article", head,
                       image=og, active=a["category"]))

        def search_row(x):
            src, portrait = short_visual(x)
            return {"u": url(lang, x["slug"] + "/"), "t": x[lang]["title"], "d": x[lang]["description"],
                    "k": _rubric_pair(x, lang)[0], "s": _rubric_pair(x, lang)[2],
                    "c": CATEGORIES[x["category"]].get("tag", CATEGORIES[x["category"]][lang]),
                    "dt": rel_short(published(x), lang), "ts": published(x).isoformat(),
                    "i": src or site_img(x), "sp": 1 if portrait else 0, "sb": 1 if src else 0}
        idx = [search_row(x) for x in arts]
        (OUT / f"search-{lang}.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        # ---------- Archive: all articles, newest first, paginated ----------
        # every archive page holds PER_PAGE (60) articles so the rows are always full; page 1 = the newest 60
        rest_arch = arts[PER_PAGE:]
        pages = 1 + max(1, -(-len(rest_arch) // PER_PAGE))
        for pi in range(pages):
            chunk = arts[:PER_PAGE] if pi == 0 else rest_arch[(pi - 1) * PER_PAGE:pi * PER_PAGE]
            path = "archive/" if pi == 0 else f"archive/{pi + 1}/"
            prev = (url(lang, "") + "#meer" if pi == 1 else url(lang, f"archive/{pi}/")) if pi else ""
            nxt = url(lang, f"archive/{pi + 2}/") if pi + 1 < pages else ""
            left = f'<a href="{prev}">‹ {L["newer"]}</a>' if prev else "<span></span>"
            right = f'<a href="{nxt}">{L["older"]} ›</a>' if nxt else "<span></span>"
            pager = f'<nav class="pager">{left}<span>{L["page"]} {pi + 1} / {pages}</span>{right}</nav>'
            title = L["archive"] + (f' · {L["page"]} {pi + 1}' if pi else "")
            body = (f'<section class="wide"><h1 class="st archh">{title}</h1><div class="grid2 gall wide">'
                    + "".join(gcard(a, lang) for a in chunk)
                    + ("".join(gcard(a, lang).replace('<div class="card"', '<div class="card xtra"', 1)
                               for a in (rest_arch[pi * PER_PAGE:pi * PER_PAGE + XTRA] if nxt else [])))
                    + f'</div>{pager}</section>')
            write(url(lang, path), page(lang, path, title, L["tagline"],
                                         shell(body, page_side(arts, lang, "archive", skip=list(chunk) + (
                                             rest_arch[pi * PER_PAGE:pi * PER_PAGE + XTRA] if nxt else []))), active="news"))
        ARCH_PAGES[0] = pages

        # ---------- Saved articles (filled in the browser from localStorage) ----------
        body = (f'<section class="wide"><h1 class="st archh">{L["saved"]}</h1>'
                f'<div class="grid2 gall wide savedlist" data-empty="{esc(L["saved_empty"])}"></div></section>')
        write(url(lang, "saved/"), page(lang, "saved/", L["saved"], L["saved"],
                                         shell(body, page_side(arts, lang, "saved")),
                                         robots="noindex, follow"))

        # ---------- YouTube Shorts (content/shorts.json, kept up to date by tools/sync_shorts.py) ----------
        sf = ROOT / "content" / "shorts.json"
        shorts = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else []
        by_slug = {a["slug"]: a for a in arts}
        en = lang == "en"
        cards = ""
        shown = []
        for sh in shorts:
            a = by_slug.get(sh.get("slug"))
            if a:
                shown.append(a)
            t = a[lang]["title"] if a else sh["title"]
            dt = sh["published"]
            cap = (f'<a class="sht" href="{url(lang, a["slug"] + "/")}">{esc(card_title(a, lang) if a else t)}</a>' if a else f'<span class="sht">{esc(t)}</span>')
            tone = layer_tone(a) if a else ""
            stamp = when(a, lang) if a else f'<time class="ago" datetime="{esc(dt)}">{fmt_date(dt[:10], lang)}</time>'
            line = rubric_line(a, lang, stamp)
            if not a:
                guess = t.lower()
                if "starlink" in guess:
                    name = "Starlink"
                elif "spacex" in guess or "starship" in guess or "falcon" in guess:
                    name = "SpaceX"
                elif "neuralink" in guess:
                    name = "Neuralink"
                elif "boring" in guess:
                    name = "Boring Co"
                else:
                    name = "Tesla"
                line = f'<span class="lmeta"><span class="lname">{esc(name)}</span> · {stamp}</span>'
            thumb = short_poster(sh) or f"https://i.ytimg.com/vi/{esc(sh['id'])}/hqdefault.jpg"
            tw, th = (1080, 1920) if short_poster(sh) else (480, 360)
            cards += (f'<div class="shc {tone}"><button class="shv zimg" type="button" data-id="{esc(sh["id"])}" aria-label="{"Play" if en else "Afspelen"}: {esc(t)}">'
                      f'<img src="{esc(thumb)}" alt="{esc(t)}" loading="lazy" width="{tw}" height="{th}">'
                      f'<span class="shp" aria-hidden="true"></span></button>'
                      f'{line}{cap}</div>')
        intro = ("Tesla news in under a minute. New Shorts appear here as soon as they are live on YouTube."
                 if en else "Tesla-nieuws in minder dan een minuut. Nieuwe Shorts verschijnen hier zodra ze live staan op YouTube.")
        empty = "No Shorts yet, check back soon." if en else "Nog geen Shorts, kijk binnenkort nog eens."
        body = (f'<section class="wide"><h1 class="st archh">Shorts</h1>'
                f'<div class="shgrid">{cards or f"<p class=shintro>{empty}</p>"}</div></section>'
                "<script>(function(){var m,last;function close(){if(!m)return;m.remove();m=null;document.documentElement.style.overflow='';if(last)last.focus()}"
                "document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.shv');if(!b)return;last=b;close();last=b;"
                "m=document.createElement('div');m.className='shm';m.setAttribute('role','dialog');m.setAttribute('aria-modal','true');"
                "m.innerHTML='<div class=\"shbox\"><iframe src=\"https://www.youtube-nocookie.com/embed/'+b.dataset.id+'?autoplay=1'+(matchMedia('(pointer:coarse)').matches?'':'&playsinline=1')+'&rel=0\" title=\"YouTube\" "
                "allow=\"autoplay; encrypted-media; picture-in-picture; fullscreen\" allowfullscreen></iframe></div>"
                "<button class=\"shx\" type=\"button\" aria-label=\"'+(document.documentElement.lang=='nl'?'Sluiten':'Close')+'\"></button>';"
                "m.addEventListener('click',function(ev){if(ev.target===m||ev.target.classList.contains('shx'))close()});"
                "document.body.appendChild(m);document.documentElement.style.overflow='hidden';m.querySelector('.shx').focus()});"
                "document.addEventListener('keydown',function(e){if(e.key==='Escape')close()})})()</script>")
        write(url(lang, "shorts/"), page(lang, "shorts/", "Shorts", intro,
                                          shell(body, page_side(arts, lang, "videos", skip=shown)), active="videos"))

        # ---------- Long videos, plus a page for every long video and every Short ----------
        vbody, vtitle, vintro, vshown = videos_index(arts, lang)
        write(url(lang, "videos/"), page(lang, "videos/", vtitle, vintro,
                                          shell(vbody, page_side(arts, lang, "videos", skip=vshown)), active="videos"))
        for item in clip_items(arts):
            if item["kind"] == "article":
                continue
            cbody, chead, cdesc = clip_page(item, arts, lang)
            write(url(lang, item["path"]), page(
                lang, item["path"], item["title"], cdesc,
                shell(cbody, page_side(arts, lang, "videos", current=item.get("article"))),
                extra_head=chead))

        # ---------- Static pages ----------
        for key, p in PAGES.items():
            title, desc, content = p[lang]
            content = with_affiliate_disclosure(key, lang, content)
            write(url(lang, key + "/"), page(lang, key + "/", title, desc,
                  shell(f'<article class="narrow"><h1>{esc(title)}</h1><div class="prose">{content}</div></article>',
                        page_side(arts, lang, "static"))))

        # ---------- Newsletter (different slug per language) ----------
        npath = signup_path(lang)
        nbody = (
            f'<article class="narrow"><h1>{esc(L["signup_h"])}</h1>'
            f'<div class="prose nlpitch">{newsletter_pitch(lang)}</div>'
            f'{ml_signup(lang, heading=False)}</article>')
        write(url(lang, npath), page(
            lang, npath, L["signup"], L["signup_desc"],
            shell(nbody, page_side(arts, lang, "static", signup=False)), alt_path=signup_path(other(lang))))

        # ---------- Briefing, promises, buying guides, advertise ----------
        b_body, b_title, b_desc = briefing_index_body(briefing_docs, lang)
        write(url(lang, "briefing/"), page(
            lang, "briefing/", b_title, b_desc,
            shell(b_body, page_side(arts, lang, "static")), active="briefing"))
        for doc in briefing_docs:
            if doc.get("template"):
                continue
            i_body, i_title, i_desc = briefing_issue_body(doc, lang)
            write(url(lang, f"briefing/{doc['slug']}/"), page(
                lang, f"briefing/{doc['slug']}/", i_title, i_desc,
                shell(i_body, page_side(arts, lang, "static")),
                active="briefing", robots="noindex" if doc["template"] else None))
        p_body, p_title, p_desc = promises_body(promise_rows, lang)
        write(url(lang, promises_path(lang)), page(
            lang, promises_path(lang), p_title, p_desc,
            shell(p_body, page_side(arts, lang, "static")),
            active="promises", alt_path=promises_path(other(lang))))
        g_body, g_title, g_desc = guides_index_body(guide_docs, lang)
        write(url(lang, guides_path(lang)), page(
            lang, guides_path(lang), g_title, g_desc,
            shell(g_body, page_side(arts, lang, "static")) + disclosure_line(lang, "affend"),
            active="buyguides", alt_path=guides_path(other(lang))))
        for doc in guide_docs:
            body, title, desc = guide_body(doc, lang)
            gpath = guides_path(lang) + doc["slug"] + "/"
            write(url(lang, gpath), page(
                lang, gpath, title, desc,
                shell(body, page_side(arts, lang, "static", current=doc["slug"], shop=True))
                + disclosure_line(lang, "affend"),
                active="buyguides", robots="noindex" if doc["template"] else None,
                alt_path=guides_path(other(lang)) + doc["slug"] + "/"))
        d_body, d_title, d_desc = disclosure_body(lang)
        write(url(lang, disclosure_path(lang)), page(
            lang, disclosure_path(lang), d_title, d_desc,
            shell(d_body, page_side(arts, lang, "static")), active="affiliate"))
        a_body, a_title, a_desc = advertise_body(lang)
        write(url(lang, advertise_path(lang)), page(
            lang, advertise_path(lang), a_title, a_desc,
            shell(a_body, page_side(arts, lang, "static")),
            active="advertise", alt_path=advertise_path(other(lang))))

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

    # 404 (served for missing URLs, so it has no canonical of its own and must not be indexed)
    L, N = LANGS["en"], LANGS["nl"]
    write("/404.html", page("en", "", L["notfound"], L["notfound_text"],
          shell(f'<article class="narrow"><h1>{L["notfound"]}</h1><p class="lead">{L["notfound_text"]}</p>'
                f'<p lang="nl"><strong>{N["notfound"]}.</strong> {N["notfound_text"]}</p>'
                f'<p><a href="/">{L["back"]}</a> · <a href="/nl/" hreflang="nl" lang="nl">{N["back"]}</a></p></article>',
                page_side(arts, "en", "static")),
          robots="noindex", canonical=False))

    # Sitemap. lastmod is a real content date, never the day this file was generated.
    def category_items(key):
        if key == "news":
            return [a for a in arts if a["category"] != "guides"]
        if key == "ecosystem":
            return [a for a in arts if a["category"] == key or key in a.get("also", []) or a["category"] in ECO]
        return [a for a in arts if a["category"] == key or key in a.get("also", [])]

    def model_items(key):
        m = MODELS[key]
        if m.get("parent"):
            return [a for a in arts if key in a.get("models", [])]
        family = {key} | {k for k, v in MODELS.items() if v.get("parent") == key}
        return [a for a in arts if family & set(a.get("models", []))]

    def archive_chunk(pi):
        rest = arts[PER_PAGE:]
        if pi == 0:
            return arts[:PER_PAGE]
        return rest[(pi - 1) * PER_PAGE:pi * PER_PAGE]

    short_dates = []
    for sh in shorts:
        raw = str(sh.get("published") or "")[:10]
        if len(raw) == 10:
            short_dates.append(raw)
    ship_raw = str(load_data("starship.json").get("updated") or "")[:10]
    ship_mod = ship_raw if len(ship_raw) == 10 else None
    brief_dates = [str(d["meta"].get("date") or "")[:10] for d in briefing_docs if not d.get("template") and d["meta"].get("date")]

    entries = [("", latest_stamp(arts))]
    entries += [(a["slug"] + "/", article_stamp(a)) for a in arts]
    entries += [(f"category/{k}/", latest_stamp(category_items(k))) for k in CATEGORIES if k not in REDIRECT_CATS]
    def model_mod(key):
        stamp = latest_stamp(model_items(key))
        if key in PAGE_FACTS:
            fact = "2026-11-19"
            if not stamp or fact > stamp:
                return fact
        return stamp

    entries += [(f"model/{k}/", model_mod(k)) for k in MODELS]
    # Standing pages have no article date. Leave lastmod off rather than stamp the build day.
    entries += [(k + "/", None) for k in PAGES]
    entries += [("shorts/", max(short_dates) if short_dates else None)]
    video_rows = json.loads((ROOT / "content" / "videos.json").read_text(encoding="utf-8"))
    video_dates = []
    for row in video_rows:
        vid = row.get("id")
        raw = str(row.get("published") or "")[:10]
        if not vid:
            continue
        if len(raw) == 10:
            video_dates.append(raw)
        entries.append((f"videos/{vid}/", raw if len(raw) == 10 else None))
    entries.append(("videos/", max(video_dates) if video_dates else None))
    for sh in shorts:
        vid = sh.get("id")
        raw = str(sh.get("published") or "")[:10]
        if vid:
            entries.append((f"shorts/{vid}/", raw if len(raw) == 10 else None))
    seen_hubs = set()
    for spec in HUBS:
        seen_hubs.add(spec["path"])
        entries.append((spec["path"], latest_stamp(hub_articles(spec, arts))))
    for layer in LAYERS:
        if layer["path"] in seen_hubs:
            continue
        entries.append((layer["path"], latest_stamp(_layer_articles(layer, arts))))
    if not any(path == "starship/" for path, _mod in entries):
        entries.append(("starship/", ship_mod))
    for hub in load_evergreen():
        entries.append((hub["path"], str(load_data("evergreen.json").get("updated") or "")[:10] or None))
    entries += [("archive/" if i == 0 else f"archive/{i + 1}/", latest_stamp(archive_chunk(i))) for i in range(ARCH_PAGES[0])]

    def emit(loc_lang, loc_path, mod, en_path, nl_path):
        paths = {"en": en_path, "nl": nl_path}
        alts = "".join(
            f'<xhtml:link rel="alternate" hreflang="{l}" href="{SITE + url(l, paths[l])}"/>' for l in LANGS)
        alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE + url("en", en_path)}"/>'
        last = f"<lastmod>{mod}</lastmod>" if mod else ""
        return f"<url><loc>{SITE + url(loc_lang, loc_path)}</loc>{last}{alts}</url>"

    urls = ""
    for path, mod in entries:
        for lang in LANGS:
            urls += emit(lang, path, mod, path, path)
    brief_index = max(brief_dates) if brief_dates else None
    for lang in LANGS:
        urls += emit(lang, signup_path(lang), None, signup_path("en"), signup_path("nl"))
        urls += emit(lang, ecosystem_path(lang), latest_stamp(arts), ecosystem_path("en"), ecosystem_path("nl"))
        urls += emit(lang, "briefing/", brief_index, "briefing/", "briefing/")
        for doc in briefing_docs:
            if doc["template"]:
                continue
            slug = f"briefing/{doc['slug']}/"
            urls += emit(lang, slug, str(doc["meta"].get("date") or "")[:10] or None, slug, slug)
        urls += emit(lang, promises_path(lang), None, promises_path("en"), promises_path("nl"))
        urls += emit(lang, guides_path(lang), None, guides_path("en"), guides_path("nl"))
        for doc in guide_docs:
            if doc["template"]:
                continue
            urls += emit(
                lang, guides_path(lang) + doc["slug"] + "/", None,
                guides_path("en") + doc["slug"] + "/", guides_path("nl") + doc["slug"] + "/")
        urls += emit(lang, disclosure_path(lang), None, disclosure_path("en"), disclosure_path("nl"))
        urls += emit(lang, advertise_path(lang), None, advertise_path("en"), advertise_path("nl"))
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
          f"{urls}</urlset>")
    # Google News sitemap: articles published in the last 48 hours
    from zoneinfo import ZoneInfo
    cutoff = datetime.now(timezone.utc).timestamp() - 2 * 86400
    news = ""
    for a in arts:
        try:
            dt = datetime.strptime(a["date"] + " " + a.get("time", "12:00"), "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Europe/Amsterdam"))
        except ValueError:
            continue
        if dt.timestamp() < cutoff:
            continue
        for lang in LANGS:
            news += (f"<url><loc>{SITE + url(lang, a['slug'] + '/')}</loc><news:news><news:publication><news:name>{NAME}</news:name>"
                     f"<news:language>{lang}</news:language></news:publication><news:publication_date>{dt.isoformat()}</news:publication_date>"
                     f"<news:title>{esc(a[lang]['title'])}</news:title></news:news></url>")
    write("/news-sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">'
          f"{news}</urlset>")
    write("/898140fa5384efdf934027b6d7051b19.txt", "898140fa5384efdf934027b6d7051b19")
    write("/robots.txt",
          "User-agent: *\n"
          "Allow: /\n"
          "Allow: /img/\n"
          "Allow: /fonts/\n"
          "Disallow: /api/\n"
          "\n"
          f"Sitemap: {SITE}/sitemap.xml\n"
          f"Sitemap: {SITE}/news-sitemap.xml\n")
    # Same policy the worker applies. HTML is not listed, so it stays revalidated.
    write("/_headers", "\n".join([
        "# Long cache for static files. The worker sets the same Cache-Control on the response.",
        "/img/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
        "/fonts/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
        "/*.css",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
        "/*.js",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
    ]))
    write("/favicon.svg",
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#e22822"/>'
          '<text x="32" y="45" font-family="system-ui,sans-serif" font-size="38" font-weight="800" fill="#fff" text-anchor="middle">T</text></svg>')
    client = publisher_client()
    if client:
        (OUT / "ads.txt").write_text(f"google.com, {client[3:]}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    write_redirects()
    audit_index()
    print(f"Built {len(arts)} article(s) in {len(LANGS)} languages -> {OUT}")


def audit_index():
    """Fail the build if the sitemap, canonicals, or internal links drift."""
    from collections import Counter
    from urllib.parse import unquote, urlparse
    sm = (OUT / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>(.*?)</loc>", sm)
    paths = [unquote(urlparse(loc).path or "/") for loc in locs]
    dupes = [p for p, n in Counter(paths).items() if n > 1]
    problems = []
    if dupes:
        problems.append(f"sitemap duplicate locs: {dupes[:8]}")
    for loc, mod in re.findall(r"<loc>(.*?)</loc>(?:<lastmod>(.*?)</lastmod>)?", sm):
        if mod and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", mod):
            problems.append(f"bad lastmod {mod} on {loc}")
    redirects = {}
    for line in (OUT / "_redirects").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        src, dest, *_rest = line.split()
        redirects[src] = dest

    def file_path(path):
        if path == "/":
            return OUT / "index.html"
        if path.endswith("/"):
            return OUT / path.strip("/") / "index.html"
        return OUT / path.lstrip("/")

    pages = {}
    for f in OUT.rglob("*.html"):
        rel = f.relative_to(OUT).as_posix()
        if rel == "index.html":
            path = "/"
        elif rel.endswith("/index.html"):
            path = "/" + rel[: -len("index.html")]
        else:
            path = "/" + rel
        raw = f.read_text(encoding="utf-8", errors="replace")
        head = raw.split("</head>", 1)[0]
        robots = re.findall(r'<meta name="robots" content="([^"]*)"', head)
        canonical = re.findall(r'<link rel="canonical" href="([^"]*)"', head)
        hrefs = re.findall(r'href="(/[^"#]*)"', raw)
        bare = []
        for href in re.findall(r'href="([^"]*)"', raw):
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:", "//")):
                continue
            if href.startswith(("http://", "https://")):
                continue
            if "+" in href or "'" in href:
                continue
            if not href.startswith("/"):
                bare.append(href)
        pages[path] = {"robots": robots, "canonical": canonical, "hrefs": hrefs,
                       "bare": bare,
                       "noindex": any("noindex" in r.lower() for r in robots)}
    indexable = {p for p, d in pages.items() if not d["noindex"]}
    sm_set = set(paths)
    missing = sorted(indexable - sm_set)
    extra = sorted(sm_set - indexable)
    if missing:
        problems.append(f"indexable missing from sitemap ({len(missing)}): {missing[:8]}")
    if extra:
        problems.append(f"sitemap not indexable ({len(extra)}): {extra[:8]}")
    for p, d in pages.items():
        cans = d["canonical"]
        if d["noindex"] and p == "/404.html":
            if cans:
                problems.append("404 has a canonical")
            continue
        if len(cans) != 1 or not cans[0].startswith(SITE + "/"):
            problems.append(f"canonical {cans} on {p}")
            continue
        if unquote(urlparse(cans[0]).path or "/") != p:
            problems.append(f"canonical is not self on {p} -> {cans[0]}")
        if len(d["robots"]) != 1:
            problems.append(f"{len(d['robots'])} robots tags on {p}")
    for p, d in pages.items():
        if d.get("bare"):
            problems.append(f"{p} has relative internal link {d['bare'][0]}")
    for p, d in pages.items():
        if d["noindex"]:
            continue
        for href in d["hrefs"]:
            path = unquote(urlparse(href).path or "/")
            if path in redirects:
                problems.append(f"{p} links to redirect {path}")
                break
            if not path.endswith("/") and path != "/" and (path + "/") in pages:
                problems.append(f"{p} links to {path} instead of {path}/")
                break
            if path in pages:
                continue
            leaf = path.rsplit("/", 1)[-1]
            if "." in leaf:
                if not (OUT / path.lstrip("/")).is_file():
                    problems.append(f"{p} links to missing file {path}")
                    break
                continue
            slashed = path if path.endswith("/") else path + "/"
            if slashed not in pages and slashed not in redirects and not file_path(slashed).is_file():
                problems.append(f"{p} links to missing {path}")
                break
    if problems:
        raise SystemExit("indexing audit failed:\n" + "\n".join(problems[:30]))
    noindex = sorted(p for p, d in pages.items() if d["noindex"])
    with_mod = len(re.findall(r"<lastmod>", sm))
    print(f"Index audit: {len(pages)} html, {len(sm_set)} sitemap ({with_mod} lastmod), "
          f"{len(noindex)} noindex {noindex}, {len(redirects)} redirects")


def write_redirects():
    """301 map for removed articles. Cloudflare static assets read public/_redirects;
    the worker applies the same pairs from worker/redirects.js before that."""
    src = ROOT / "content" / "redirects.json"
    if not src.exists():
        return
    rows = json.loads(src.read_text(encoding="utf-8"))
    lines = ["# Removed articles. Source of truth: content/redirects.json"]
    seen = set()

    def add(frm, to):
        if frm in seen or frm == to:
            return
        seen.add(frm)
        lines.append(f"{frm} {to} 301")

    for row in rows:
        frm, to = row["from"], row["to"]
        add(frm, to)
        if frm.endswith("/") and frm != "/":
            add(frm[:-1], to)
    for key, dest in REDIRECT_CATS.items():
        for prefix in ("", "/nl"):
            frm = f"{prefix}/category/{key}/"
            to = f"{prefix}/{dest}"
            add(frm, to)
            add(frm[:-1], to)
    # Labels people type as URLs. The real pages are /agi/ and /guides/.
    add("/agi-race/", "/agi/")
    add("/agi-race", "/agi/")
    add("/nl/agi-race/", "/nl/agi/")
    add("/nl/agi-race", "/nl/agi/")
    add("/buying-guides/", "/guides/")
    add("/buying-guides", "/guides/")
    add("/nl/buying-guides/", "/nl/gidsen/")
    add("/nl/buying-guides", "/nl/gidsen/")
    # Host and scheme redirects are not allowed here. Workers static assets only
    # accept a path as the source (2,000 static rules, 100 dynamic). www, http,
    # and the trailing slash are 301s in worker/index.js.
    (OUT / "_redirects").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
