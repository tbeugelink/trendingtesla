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
  "image": "topics/optimus.jpg",                   # optional: specific photo (path inside static/img/)
  "sources": [{"title": "...", "url": "https://..."}],
  "en": {"title": "...", "description": "...", "body": "<p>...</p>"},
  "nl": {"title": "...", "description": "...", "body": "<p>...</p>"},
  "products": [                                # optional; omit the key when there is nothing to link. No prices.
    {"name": {"en": "...", "nl": "..."}, "image": "/img/topics/example.jpg",
     "specs": {"en": ["..."], "nl": ["..."]},
     "button": {"en": "View on Amazon", "nl": "Bekijk bij Amazon"},
     "url": {"en": "https://www.amazon.com/dp/...", "nl": "https://www.amazon.nl/dp/..."}}
  ]
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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from covers import make_cover
from model_info import INFO

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content" / "articles"
STATIC = ROOT / "static"
OUT = ROOT / "public"
SITE = "https://trendingtesla.com"
NAME = "TrendingTesla"
# Author shown on articles and in NewsArticle JSON-LD. An organization, never a named person.
EDITORIAL_ORG = {"en": "TrendingTesla Editorial Team", "nl": "Redactie TrendingTesla"}
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
        "switch": "NL", "switch_full": "Nederlands", "i_specs": "Specifications", "i_watch": "Points to watch", "i_special": "What makes it special", "i_acc": "Accessories", "i_acc_soon": "Coming soon: accessories that fit this version, tested and explained.", "slogan": "Daily Tesla news &amp; trends", "nav_eco": "Ecosystem", "nav_tesla": "Tesla", "search": "Search the ecosystem", "none": "Nothing found", "home": "Home", "toc": "On this page", "prev": "Previous", "next": "Next", "ad": "Advertisement", "videos": "Shorts", "see_all": "See all", "read_story": "Read the story", "nav_models": "Tesla models", "nav_energy": "Energy", "nav_fsd": "FSD / Robotaxi", "nav_space": "SpaceX / Starlink", "nav_xai": "xAI", "nav_more": "More", "start_here": "Start here", "start_p": "Guides that stay useful: practical explainers for owning and buying a Tesla.", "all_guides": "All guides", "articles": "Articles", "cookie": "Cookie settings", "news_h": "One email a week with the best explainers", "news_p": "One email a week with the best explainers. Unsubscribe any time.", "news_btn": "Subscribe", "news_email": "Email address", "bar_h": "The weekly briefing, in one email", "bar_ok": "Check your inbox to confirm", "bar_err": "Could not subscribe. Please try again.", "bar_fine": "Unsubscribe any time.", "signup": "Newsletter", "signup_h": "Get the TrendingTesla newsletter", "signup_lead": "One email a week with the best explainers. Double opt-in, and you can unsubscribe from any email.", "signup_fallback": "Open the newsletter form", "signup_desc": "One email a week with the best explainers. Double opt-in, and you can unsubscribe from any email.", "aff": "Affiliate disclosure: if you buy through this link, TrendingTesla may earn a commission, at no extra cost to you.", "aff_btn": "View product", "handy_h": "Handy for your Tesla", "handy_p": "A few accessories owners look for. Each link opens an Amazon.nl search, not one specific product.", "handy_note": "As an Amazon Associate we earn from qualifying purchases.", "watch": "Watch the video", "watch_short": "Watch the Short", "consent_p": "Visit counts are cookieless and anonymous. Consent is only for ads. YouTube loads when you press play.", "consent_yes": "Accept", "consent_no": "Refuse", "consent_more": "Privacy policy", "collapse": "Close menu", "like": "Like", "save": "Save", "saved_btn": "Saved", "saved": "Saved articles", "saved_empty": "You have not saved any articles yet. Tap Save under an article title to keep it here. Saved articles stay in this browser on this device.", "archive": "All news", "newer": "Newer", "older": "Older", "page": "Page", "d_topics": "Topics", "d_models": "Models", "d_more": "More", "menu": "Menu", "tip_h": "A 22 kW charger won't charge your Tesla any faster", "tip_p": "Most Tesla models charge at home at up to 11 kW AC.", "tip_btn": "Read why", "tips": [("HW4", "Buying a used Model 3? Check the hardware first", "The Highland has HW4, older cars HW3. It decides what FSD can do.", "How to check", "used-model-3-highland-vs-classic-hw3-hw4-buying-guide"), ("−20%", "Losing range in winter? It doesn't have to be", "Preconditioning and the right settings save you kilometers.", "9 winter tips", "tesla-winter-range-tips-cold-weather")],
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
        "switch": "EN", "switch_full": "English", "i_specs": "Specificaties", "i_watch": "Aandachtspunten", "i_special": "Bijzonderheden", "i_acc": "Accessoires", "i_acc_soon": "Binnenkort: accessoires die op deze uitvoering passen, getest en uitgelegd.", "slogan": "Iedere dag het laatste nieuws &amp; trends", "nav_eco": "Ecosysteem", "nav_tesla": "Tesla", "search": "Zoek in het ecosysteem", "none": "Niets gevonden", "home": "Home", "toc": "Op deze pagina", "prev": "Vorig", "next": "Volgend", "ad": "Advertentie", "videos": "Shorts", "see_all": "Alles bekijken", "read_story": "Lees het verhaal", "nav_models": "Tesla-modellen", "nav_energy": "Energie", "nav_fsd": "FSD / Robotaxi", "nav_space": "SpaceX / Starlink", "nav_xai": "xAI", "nav_more": "Meer", "start_here": "Begin hier", "start_p": "Gidsen die bruikbaar blijven: praktische uitleg voor wie een Tesla heeft of er een wil kopen.", "all_guides": "Alle gidsen", "articles": "Artikelen", "cookie": "Cookie-instellingen", "news_h": "Eén mail per week met de beste uitleg", "news_p": "Eén mail per week met de beste uitleg. Afmelden kan altijd.", "news_btn": "Aanmelden", "news_email": "E-mailadres", "bar_h": "De weekbriefing, in één mail", "bar_ok": "Check je inbox om te bevestigen", "bar_err": "Aanmelden is niet gelukt. Probeer het opnieuw.", "bar_fine": "Afmelden kan altijd.", "signup": "Nieuwsbrief", "signup_h": "Ontvang de TrendingTesla-nieuwsbrief", "signup_lead": "Eén mail per week met de beste uitleg. Dubbele bevestiging, en afmelden kan vanuit elke e-mail.", "signup_fallback": "Open het nieuwsbriefformulier", "signup_desc": "Eén mail per week met de beste uitleg. Dubbele bevestiging, en afmelden kan vanuit elke e-mail.", "aff": "Affiliate-melding: koop je via deze link, dan kan TrendingTesla een commissie ontvangen. Voor jou kost het niets extra.", "aff_btn": "Bekijk het product", "handy_h": "Handig voor je Tesla", "handy_p": "Een paar accessoires waar rijders naar zoeken. Elke link opent een zoekopdracht bij Amazon.nl, niet één specifiek product.", "handy_note": "Als Amazon-partner verdienen wij aan in aanmerking komende aankopen.", "watch": "Bekijk de video", "watch_short": "Bekijk de Short", "consent_p": "Bezoekcijfers zijn anoniem en zonder cookies. Toestemming is alleen voor advertenties. YouTube laadt pas als je op afspelen drukt.", "consent_yes": "Accepteren", "consent_no": "Weigeren", "consent_more": "Privacybeleid", "collapse": "Inklappen", "like": "Vind ik leuk", "save": "Bewaren", "saved_btn": "Bewaard", "saved": "Bewaarde artikelen", "saved_empty": "Je hebt nog geen artikelen bewaard. Tik op Bewaren onder de titel van een artikel om het hier terug te vinden. Bewaarde artikelen blijven in deze browser op dit apparaat.", "archive": "Alle nieuws", "newer": "Nieuwer", "older": "Ouder", "page": "Pagina", "d_topics": "Onderwerpen", "d_models": "Modellen", "d_more": "Meer", "menu": "Menu", "tip_h": "Een 22 kW-laadpaal laadt je Tesla niet sneller", "tip_p": "Veel Tesla-modellen laden thuis met maximaal 11 kW AC.", "tip_btn": "Lees waarom", "tips": [("HW4", "Tweedehands Model 3 kopen? Check eerst de hardware", "De Highland heeft HW4, oudere Model 3's HW3. Dat bepaalt wat FSD kan.", "Zo check je het", "used-model-3-highland-vs-classic-hw3-hw4-buying-guide"), ("−20%", "Minder bereik in de winter? Dat hoeft niet", "Met voorverwarmen en de juiste instellingen houd je meer kilometers over.", "9 wintertips", "tesla-winter-range-tips-cold-weather")],
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
    "roadster":          {"name": "Roadster",           "photo": "rd-4.jpg", "menu": "menu-roadster.jpg", "gallery": ["rd-4.jpg", "rd-5.jpg", "rd-6.jpg", "rd-7.jpg", "rd-8.jpg", "rd-9.jpg", "rd-10.jpg", "rd-11.jpg", "rd-12.jpg", "rd-13.jpg", "rd-14.jpg", "rd-15.jpg", "rd-16.jpg", "rd-17.jpg", "rd-18.jpg", "rd-19.jpg", "rd-20.jpg", "rd-21.jpg", "rd-22.jpg", "rd-23.jpg", "rd-24.jpg", "rd-25.jpg"]},
    "semi":              {"name": "Semi",               "photo": "semi.jpg", "menu": "menu-semi.jpg", "gallery": ["semi.jpg", "semi-6.jpg", "semi-4.jpg", "semi-7.jpg", "semi-2.jpg", "semi-5.jpg", "semi-3.jpg"]},
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
:root{--bg:#04060a;--surface:#212121;--surface2:#272727;--border:#272727;--border2:#3f3f3f;--fg:#e8eef5;--head:#fff;--muted:#b9c4d2;--dim:#8f9db0;--red:#e22822;--red2:#b81e19;--blue:#00d4ff;--edge:#3a4a60;--blue2:#5fe3ff;--max:1160px;color-scheme:dark}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:150px;background:#04060a}
html,body{overflow-x:clip;max-width:100%}
body{background:linear-gradient(180deg,rgba(15,15,15,0) 0,rgba(15,15,15,0) 35%,#0f0f0f 100%) top left/100% 900px no-repeat,linear-gradient(160deg,#2b2b2b 0%,#1d1d1d 35%,#141414 70%,#0f0f0f 100%) top left/100% 900px no-repeat,#0f0f0f;min-height:100vh;color:var(--fg);font:17px/1.42 Manrope,"Manrope Fallback",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main,footer{position:relative;z-index:1}
a{color:var(--head)}
img{display:block;max-width:100%;height:auto}picture{display:contents}
h1,h2,h3{color:#ebebeb;font-weight:800}
.wrap{max-width:var(--max);margin:0 auto;padding:0 12px}
.narrow{max-width:740px;margin:0 auto}
.read{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:13px;align-items:start;margin-top:0}
.grid2{display:grid;grid-template-columns:1fr;gap:13px;margin-top:20px}
.grid2>.card{display:grid;grid-template-columns:254px 1fr;gap:11px;align-items:start}.grid2>.card .body{padding:0;line-height:1}.grid2>.card .body .tag,.grid2>.card .body .meta{line-height:1;vertical-align:top}.grid2>.card h3{font-size:1.12rem;line-height:1.3;margin:8px 0 6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.grid2>.card p{-webkit-line-clamp:1;line-height:1.42}.grid2>.card .im{height:142px;width:254px}.grid2>.card .im img{height:100%;aspect-ratio:auto}
.grid2 .card{padding:8px;margin:-8px;border-radius:10px;transition:background .15s}.grid2>.card{align-content:start}
.grid2 .card:hover{background:#272727}.below{margin-top:17px}.below>.tip{margin-top:0}.grid2.gall.wide{grid-template-columns:repeat(auto-fill,minmax(max(250px,calc((100% - 72px) / 7 + 1px)),1fr));gap:22px 12px;margin-top:14px}.wide .empty{grid-column:1/-1}.grid2.gall{grid-template-columns:repeat(3,minmax(0,1fr));gap:18px 12px}.gall>.card{grid-template-columns:1fr;gap:0}.gall>.card .im{width:auto;height:auto}.gall>.card .im img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}.gall>.card .body{padding:8px 0 0;line-height:1.3}.gall>.card h2,.gall>.card h3{font-size:.92rem;font-weight:700;line-height:1.3;margin:0 0 5px;color:#ebebeb;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.gall>.card p{font-size:.8rem;line-height:1.35;-webkit-line-clamp:1;margin-bottom:5px}.gall>.card .meta{font-size:.74rem}
.span2{grid-column:1/-1}.span2 .tip{margin:0}
.read article{padding-top:0}
.rside .rh{font-size:1.15rem;margin:0 0 22px;padding-bottom:12px;border-bottom:1px solid var(--border)}
.sr{position:absolute;left:-9999px}
/* header */
.top{position:sticky;top:0;z-index:40;background:transparent;transition:background-color .2s}.top.solid{background:#161616}.bar .search{height:38px}.bar .search input,.bar .search>button{box-sizing:border-box;height:38px;padding-top:0;padding-bottom:0}
.bar{display:flex;align-items:center;gap:14px;height:66px}
.brand{display:flex;align-items:baseline;gap:14px;min-width:0}
.logo{font-weight:800;font-size:1.4rem;letter-spacing:-.02em;color:#ebebeb;text-decoration:none;white-space:nowrap}
.logo span{color:var(--red);font-size:calc(1em + 1px);position:relative;top:1px}
.slogan{font-size:.86rem;font-weight:600;color:var(--muted);white-space:nowrap}
.burger{flex:none;width:40px;height:40px;margin-left:-8px;border-radius:10px;border:0;background:transparent;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;cursor:pointer}
.burger span{width:18px;height:2px;border-radius:2px;background:#ebebeb}
.burger:hover{background:var(--surface2)}
.search{position:relative;flex:0 1 auto;width:calc((100% - 13px) * 0.63 - 230px);margin-left:28px;margin-right:auto;display:flex}
.search input{flex:1;min-width:0;background:#121212;border:1px solid #303030;border-right:0;border-radius:10px 0 0 10px;color:var(--head);font:inherit;font-size:.92rem;padding:9px 18px;outline:none}
.search input::placeholder{color:var(--dim)}
.search input:focus{border-color:#1c62b9}
.search input:focus-visible{outline:2px solid #5fe3ff;outline-offset:2px}
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
@media (max-width:1000.98px){.rside .cats9 a{padding-left:3px;padding-right:3px}}@media (max-width:904.98px) and (min-width:700px){.rside .mini{gap:2px}.rside .mini>div:not(.th){padding-top:0}.rside .mini h3{margin-top:-2px}.rside .mini .mdesc{margin-bottom:0}.rside .mini .meta{display:block;margin-top:2px;line-height:1.3}.rside .side{row-gap:24px}.read{grid-template-columns:minmax(0,2.68fr) minmax(0,1fr)}.rside .cats9{display:none}.rside .mini{grid-template-columns:1fr;gap:6px}.rside .mini img{aspect-ratio:1200/630}}@media (max-width:699.98px){.read{grid-template-columns:minmax(0,1fr);gap:36px}.read:not(.topic) .rside .side{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:22px 16px}.read:not(.topic) .rside .mini{grid-template-columns:1fr;gap:6px;margin:-6px}.read:not(.topic) .rside .mini .th{width:auto}.read:not(.topic) .rside .mini img{aspect-ratio:1200/630}.read:not(.topic) .rside .mini h3{font-size:1rem;margin-top:2px}.read:not(.topic) .rside .mini .mdesc{font-size:.9rem}.rside .cats9,.rside .mnav{display:none}.read.topic .rside{display:none}}
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
.drawer .di{display:flex;align-items:center;gap:12px;padding:9px 10px;border-radius:10px;color:var(--fg);text-decoration:none;font-weight:700;font-size:.92rem}
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
.mini{padding:6px;margin:-6px;border-radius:10px;transition:background .15s}.mini:hover{background:#272727}.mini>div{padding:2px 4px 2px 0}.mini>.th{padding-top:0}
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
.card h3{font-size:1.08rem;line-height:1.3;margin:6px 0 6px}.card h3{font-weight:700;color:#ebebeb}.grid2>.card h3{font-size:1rem}.mini h3{font-weight:700;font-size:.9rem;color:#ebebeb}.mini h3{margin-top:0}.meta>time.ago::before{content:'';display:inline-block;width:.62em;height:.72em;margin-right:.42em;vertical-align:-.04em;background:currentColor;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 12'%3E%3Cpath d='M1.2 1.2v9.6L9 6z' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 12'%3E%3Cpath d='M1.2 1.2v9.6L9 6z' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E") center/contain no-repeat}.smeta time.ago::before{content:none}.mini .mdesc{margin-bottom:0}.mini .meta{display:block;margin-top:3px;line-height:1.3}@media (min-width:905px){.rside .mini>div:not(.th){padding-top:0;contain:size;overflow:visible}.rside .mini h3{margin-top:0;line-height:1.22}.rside .mini .mdesc{line-height:1.25}.rside .mini .meta{margin-top:2px}}.mdesc{color:var(--muted);font-size:.8rem;line-height:1.35;margin:0 0 4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}@media (max-width:904.98px){.rside .mini h3{-webkit-line-clamp:2}.rside .mini .mdesc{-webkit-line-clamp:1}}.shintro{color:var(--muted);margin:4px 0 18px;font-size:.95rem}.shintro a{color:inherit}.shgrid{margin-top:14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:22px 14px}.shc{display:flex;flex-direction:column;gap:6px;min-width:0}.shv{position:relative;display:block;width:100%;aspect-ratio:9/16;padding:0;border:0;border-top:3px solid #444;border-radius:10px;overflow:hidden;background:#000;cursor:pointer}.shc.tesla .shv{border-top-color:#E31937}.shc.energy .shv{border-top-color:#4CD964}.shc.spacex .shv{border-top-color:#FF7A00}.shc.link .shv{border-top-color:#00D1FF}.shc.spacexsi .shv{border-top-color:#FFC400}.shc.neural .shv{border-top-color:#FF2D95}.shc.boring .shv{border-top-color:#2F6BFF}.shv img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}.shv:hover img{transform:scale(1.04)}.dur .dv{display:inline-flex;align-items:center;gap:3px;font-style:normal;margin-left:5px;padding-left:6px;border-left:1px solid rgba(255,255,255,.35)}.dur.dvo .dv{margin-left:0;padding-left:0;border-left:0}.vpl{position:absolute;left:50%;top:50%;width:15cqw;height:15cqw;min-width:38px;min-height:38px;max-width:84px;max-height:84px;transform:translate(-50%,-50%);border-radius:50%;background:rgba(0,0,0,.55);box-shadow:0 0 0 2px rgba(255,255,255,.9);pointer-events:none;z-index:2}.vpl::after{content:"";position:absolute;left:54%;top:50%;transform:translate(-50%,-50%);border-left:.62em solid #fff;border-top:.4em solid transparent;border-bottom:.4em solid transparent;font-size:clamp(20px,6.5cqw,40px)}.hi[data-vid]{cursor:pointer}.hi[data-vid]:hover .vpl{background:rgba(220,30,30,.85)}.hi.on{aspect-ratio:16/9;background:#000;border-radius:10px;overflow:hidden}@media (max-width:600.98px){.read .hi.on{border-radius:0}}.hi.on iframe{position:absolute;inset:0;width:100%;height:100%;border:0}iframe:fullscreen,iframe:-webkit-full-screen{width:100vw!important;height:100vh!important;inset:0!important}.avid{margin:18px 0 22px}.avb{position:relative;display:block;width:100%;aspect-ratio:16/9;padding:0;border:0;border-radius:12px;overflow:hidden;background:#000;cursor:pointer}.avb img{width:100%;height:100%;object-fit:cover;display:block}.avb iframe{position:absolute;inset:0;width:100%;height:100%;border:0}.avb .shp{width:68px;height:68px;margin:-34px 0 0 -34px}.avb .shp::after{left:26px;top:20px;border-left-width:22px;border-top-width:14px;border-bottom-width:14px}.avid figcaption{color:var(--muted);font-size:.8rem;margin-top:6px}.shm{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center}.shbox{height:min(92vh,1100px);aspect-ratio:9/16;max-width:100vw;border-radius:12px;overflow:hidden;background:#000}.shbox iframe{width:100%;height:100%;border:0;display:block}.shx{position:absolute;top:14px;right:14px;width:44px;height:44px;border-radius:50%;border:0;background:rgba(40,40,40,.85);cursor:pointer}.shx::before,.shx::after{content:"";position:absolute;left:12px;top:21px;width:20px;height:2px;background:#fff;border-radius:2px;transform:rotate(45deg)}.shx::after{transform:rotate(-45deg)}.shx:hover{background:#444}@media (max-width:600.98px){.shm{background:#000;align-items:flex-end}.shbox{width:100vw;height:calc(100vh - 56px);height:calc(100dvh - 56px);aspect-ratio:auto;border-radius:0}.shx{top:6px;right:8px}}.shp{position:absolute;left:50%;top:50%;width:54px;height:54px;margin:-27px 0 0 -27px;border-radius:50%;background:rgba(0,0,0,.55);box-shadow:0 0 0 2px rgba(255,255,255,.85)}.shp::after{content:"";position:absolute;left:21px;top:16px;border-left:17px solid #fff;border-top:11px solid transparent;border-bottom:11px solid transparent}.sht{font-weight:700;font-size:.92rem;line-height:1.3;color:#ebebeb;text-decoration:none;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}a.sht:hover{text-decoration:underline}.shc .meta{font-size:.74rem}@media (max-width:600.98px){.shgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 10px}}.mini .meta{font-size:.74rem}
.card p{color:var(--muted);font-size:.9rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.empty{color:var(--muted);background:var(--surface);border:1px dashed var(--border2);border-radius:10px;padding:28px;text-align:center}
/* models */
.models{display:grid;grid-template-columns:repeat(7,1fr);gap:24px}
.model{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--edge);border-radius:10px;overflow:hidden;text-decoration:none;color:var(--head);transition:border-color .2s,transform .2s}
.model:hover{border-color:var(--blue);transform:translateY(-3px)}
.model .ph{aspect-ratio:3/2;background:#000;display:flex;align-items:center;justify-content:center}
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
article{padding:36px 0 8px}
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
.sources li{margin-bottom:4px}article .prose h2,article .prose li,article h1,article .lead{text-align:left}@media (min-width:601px){article .prose>p{text-align:justify;-webkit-hyphens:auto;hyphens:auto;hyphenate-limit-chars:7 3 3}}article .prose,article .lead{max-width:none;box-sizing:border-box;padding-left:3vw;padding-right:3vw}article .lead{padding-left:calc(3vw + 14px);padding-right:calc(3vw + 14px)}@media (max-width:600.98px){article .prose,article .lead{padding-left:0;padding-right:0}article .lead{padding-left:14px;padding-right:14px}}article .sources{padding-bottom:20px;border-bottom:1px solid var(--border2)}@media(min-width:601px){.tip{padding-top:37px;padding-bottom:37px}}
.sources a{color:var(--muted)}
/* footer */
footer{border-top:1px solid var(--border);margin-top:14px;padding:15px 0 40px;font-size:.85rem;color:var(--dim)}
footer .fbrand{margin-bottom:22px}
footer .fgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:22px 18px}
footer details.fcol{min-width:0}
footer summary.flabel{cursor:pointer}
footer summary.flabel::-webkit-details-marker{display:none}
footer a.tone-tesla{color:#ff8a9b}footer a.tone-energy{color:#b8ffc6}footer a.tone-spacex{color:#ffc48a}footer a.tone-link{color:#a6f4ff}footer a.tone-spacexsi{color:#ffe28a}footer a.tone-neural{color:#ffb3d6}footer a.tone-boring{color:#b3c8ff}
@media (min-width:700px){footer summary.flabel{pointer-events:none}}
footer a{color:var(--muted);text-decoration:none}
footer a:hover{color:var(--head)}
footer .flabel{font-size:.7rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--blue);margin:6px 0 12px}
footer .flist{display:grid;gap:7px 18px}footer .flist.two{grid-template-columns:1fr 1fr}
footer .fbrand p{margin-top:12px;max-width:340px;line-height:1.5}
footer .fcopy{margin-top:32px;padding-top:18px;border-top:1px solid var(--border)}
@media (max-width:1000.98px){.grid{grid-template-columns:repeat(2,1fr);gap:48px 40px}.leadside{grid-column:span 2;flex-direction:row}.leadside .card{flex:1}.tops{grid-template-columns:1fr}.arch{grid-template-columns:minmax(0,1fr);gap:36px}.why{grid-template-columns:repeat(2,1fr)}.models{grid-template-columns:repeat(4,1fr);gap:20px}}
@media (max-width:860.98px){.search{display:none}.sbtn{display:grid}.sopen .search{display:flex;position:absolute;left:0;right:0;top:0;bottom:0;height:auto!important;width:auto!important;margin-left:0!important;max-width:none;z-index:41;padding:9px 12px;background:#161616;align-items:center}.sopen .search input,.sopen .search>button{height:38px}.sopen .search input{background:#121212}html.hass .bar .search{display:flex;position:relative;left:auto;right:auto;top:auto}html.hass .bar .sbtn{display:none}html.hass .bar .savedlink{margin-left:auto}html.hass .bar .search{margin-right:0;flex-shrink:0}html.hass .bar .brand{flex-shrink:0}html.hass .bar .savedlink{transform:none}.tip{flex-wrap:wrap;gap:14px 20px}.tip .btn{margin-left:0}}
@media (max-width:1100.98px){footer .fgrid{grid-template-columns:1fr 1fr;gap:22px 28px}}
@media (max-width:600.98px){.wrap{padding:0 12px}
.bar{gap:4px;height:56px}.drawer,.scrim{top:56px}.burger{margin-left:-14px}.logo{font-size:1.15rem}.brand{margin-left:2px}
.sbtn{margin-left:auto;width:36px;height:36px;border:0;background:transparent}.savedlink{margin-left:-2px;width:34px;height:34px}.lang{margin-left:0;margin-right:-10px;font-size:.7rem;padding:3px 9px}
.read .hi{margin:0 -12px 6px}.read .hi .hero-img{border-radius:0;border:0}.hi .dur{right:12px}
article .st{font-size:1rem;line-height:1.25}.srow{flex-wrap:nowrap;gap:8px}.srow .acts{display:flex;gap:6px}.srow .smeta{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}.toc{float:none;width:auto;max-width:none;margin:0 0 0 14px}footer .fgrid{grid-template-columns:1fr 1fr;gap:18px 16px}footer .fgrid>*{min-width:0}footer a{overflow-wrap:anywhere}footer summary.flabel{pointer-events:auto}.act{padding:7px 10px 6px}article .lead{font-size:1.02rem}.smeta{font-size:.82rem}
article .prose{font-size:16px}article .prose h2{font-size:1.08rem}.grid2{grid-template-columns:1fr;gap:59px}.grid2.gall{grid-template-columns:1fr;gap:40px}.gall>.card h2,.gall>.card h3{font-size:1rem}.gall>.card p{font-size:.9rem}.side{gap:29px}.grid2>.card{grid-template-columns:1fr;gap:0}.grid2>.card .im{height:auto;width:auto}.grid2>.card .im img{aspect-ratio:1200/630}.grid2>.card .body{padding:7px 0 0}.card.lead{grid-column:auto}.leadside{grid-column:auto;flex-direction:column;gap:40px}.leadside .card p{display:-webkit-box}.mini{grid-template-columns:1fr;gap:6px;height:auto}.mini>div{height:auto}.th{width:100%;height:auto}.mini img{width:100%;height:auto;aspect-ratio:1200/630}#news .h2{margin-top:16px}.grid{grid-template-columns:1fr;gap:40px}.why{grid-template-columns:1fr 1fr;gap:10px}.why div{padding:14px}.why p{font-size:.8rem}
 .models{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;margin:0 -24px;padding:0 24px 4px}.models::-webkit-scrollbar{display:none}.models{gap:14px}.model{flex:0 0 46%;scroll-snap-align:start}
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
.res a,.sopen .search .res a{display:flex!important;gap:12px;align-items:center}.res img,.sopen .search .res img{margin:0;flex:none;max-width:none;aspect-ratio:auto}.res a>span{flex:1;min-width:0}
.res small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.drawer .dmodels{display:none}.drawer .dmodels.show{display:block}
.dpri{display:flex;flex-direction:column;gap:2px;padding:0 4px 4px}
.pnav{display:none}
@media (min-width:700px){.pnav{display:flex;align-items:center;gap:2px;height:44px;margin:0 0 8px;overflow-x:auto;scrollbar-width:none}.pnav::-webkit-scrollbar{display:none}}
.pn{display:flex;align-items:center;height:36px;padding:0 10px;border-radius:10px;color:var(--fg);text-decoration:none;font-size:.84rem;font-weight:700;white-space:nowrap}
.pn:hover{background:#272727;color:#fff}
.pn.on,.pdrop.on>.pn,header.hb .mdrop>button.pn.on{background:#ebebeb;color:#111;border-radius:8px}
.pdrop{position:relative;display:flex;align-items:center}
.pmenu{display:none;position:absolute;top:calc(100% - 4px);left:0;min-width:210px;z-index:50;background:#161616;border:1px solid #3a4a60;border-radius:10px;padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.55)}
.pdrop:hover .pmenu,.pdrop:focus-within .pmenu,.pdrop.is-open .pmenu{display:grid}
.pdrop.tone-tesla{--accent:#e31937;--accent-ink:#ff8a9b}
.pdrop.tone-energy{--accent:#4cd964;--accent-ink:#b8ffc6}
.pdrop.tone-spacex{--accent:#ff7a00;--accent-ink:#ffc48a}
.pdrop.tone-link{--accent:#00d1ff;--accent-ink:#a6f4ff}
.pdrop.tone-spacexsi{--accent:#ffc400;--accent-ink:#ffe28a}
.pdrop.tone-neural{--accent:#ff2d95;--accent-ink:#ffb3d6}
.pdrop.tone-boring{--accent:#2f6bff;--accent-ink:#b3c8ff}
.pdrop .pmenu{border-top:3px solid var(--accent,#00d1ff)}
.pdrop:hover>a.pn,.pdrop:focus-within>a.pn,.pdrop.is-open>a.pn{color:var(--accent-ink,#fff)}
.pmenu a.child{padding-left:26px;font-weight:650;color:#b7c0cc}
.dlayer{margin:0 0 8px}
.drawer a.tone-tesla{color:#ff8a9b}.drawer a.tone-energy{color:#b8ffc6}.drawer a.tone-spacex{color:#ffc48a}.drawer a.tone-link{color:#a6f4ff}.drawer a.tone-spacexsi{color:#ffe28a}.drawer a.tone-neural{color:#ffb3d6}.drawer a.tone-boring{color:#b3c8ff}
.dsub{display:flex;flex-direction:column;gap:1px;padding:2px 0 4px 12px}
.dsub a{display:block;padding:6px 10px;border-radius:8px;color:var(--muted);text-decoration:none;font-weight:700;font-size:.86rem}
.dsub a.child{padding-left:22px;font-weight:650;font-size:.82rem}
.dsub a:hover{background:#272727;color:#fff}
.dsub a.on{background:#ebebeb;color:#111}
.drawer a.dmap{margin-top:8px;border-top:1px solid #2a2a2a;padding-top:12px}
.pdrop:last-child .pmenu{left:auto;right:0}
.pmenu a{padding:8px 12px;border-radius:8px;color:#ebebeb;text-decoration:none;font-size:.86rem;font-weight:700;white-space:nowrap}
.pmenu a:hover{background:#272727}
.pmenu a.on,.pmenu a.on:hover{background:#ebebeb;color:#111}
.crumbs{margin:-2px 0 4px;font-size:.82rem;color:var(--dim)}
.crumbs ol{display:flex;flex-wrap:wrap;gap:6px 0;list-style:none;padding:0;margin:0}
.crumbs li{display:flex;align-items:center;gap:6px;min-width:0}
.crumbs li:not(:last-child)::after{content:"/";color:var(--dim);margin-left:6px}
.crumbs a{color:var(--muted);text-decoration:none}
.crumbs a:hover{color:var(--head)}
.crumbs [aria-current]{color:var(--fg)}
.hubhead{padding:18px 0 6px}
.hubhead h1{font-size:clamp(1.8rem,4vw,2.7rem);letter-spacing:-.03em;line-height:1.08;margin:0 0 10px}
.hubhead .lead{font-size:1.08rem;line-height:1.55;color:var(--muted);max-width:none;margin:0 0 16px 1px}
.mgrid{display:grid;grid-template-columns:1fr;gap:22px 16px;margin:0 0 28px}
@media (min-width:700px){.mgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:1100px){.mgrid{grid-template-columns:repeat(3,minmax(0,1fr))}}
.mcard{display:flex;flex-direction:column;align-items:flex-start;gap:10px;min-width:0;text-decoration:none;color:inherit}
.mcard:focus,.mcard:focus-visible{outline:none}
.mcard .mim{display:block;width:100%;border-radius:12px;overflow:hidden;border:1px solid var(--edge);background:#000;aspect-ratio:16/9}
.mcard .mim img{width:100%;height:100%;object-fit:cover}
.mcard .mname{font-weight:800;font-size:1.08rem;line-height:1.2}
.mcard:hover .mim,.mcard:focus .mim,.mcard:focus-visible .mim{border-color:var(--blue);box-shadow:0 0 0 2px var(--blue)}
.mcard:hover .mname,.mcard:focus .mname,.mcard:focus-visible .mname{text-decoration:underline;text-underline-offset:3px}
.mhero{margin:0 0 16px;border-radius:12px;overflow:hidden;border:1px solid var(--edge);background:#000}
.mhero img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
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
article.money{padding-top:6px}
article.money h1.atitle{font-size:clamp(1.85rem,4.5vw,2.7rem);line-height:1.14;letter-spacing:-.025em;margin:8px 0 10px;max-width:18em}
article.money .lead{font-size:1.16rem;line-height:1.55;max-width:40em}
article.money .prose{font-size:1.075rem;line-height:1.75;max-width:68ch}
article.money .prose p{margin-bottom:1.15em}
article.money .toc{float:none;width:auto;max-width:68ch;margin:4px 0 20px}
article.money .prose h2{scroll-margin-top:130px}
.leadstory{display:flex;flex-direction:column;gap:14px;margin:10px 0 8px;padding:0}
.leadstory .lead{padding:0;max-width:65ch}
.leadstory .leadim{display:block;border-radius:12px;overflow:hidden;border:1px solid var(--edge);background:#000}
.leadstory img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.leadstory .ltitle{font-size:clamp(1.35rem,2vw,1.7rem);line-height:1.2;letter-spacing:-.02em;margin:8px 0 12px 1px;font-weight:800}
.leadstory .btn{margin-bottom:22px}
.leadstory .ltitle a{color:inherit;text-decoration:none}
.leadstory .ltitle a:hover{text-decoration:underline;text-underline-offset:3px}
.leadstory .lead{font-size:1.08rem;line-height:1.55;color:var(--muted);max-width:none;margin:0 0 18px}
.hsec{margin:34px 0 8px}
.topics3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px 14px}
.topics3>.card{display:flex;flex-direction:column;min-width:0}
.topics3 .im{border-radius:10px;overflow:hidden;border:1px solid var(--edge)}
.topics3 .im img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.topics3 h3{font-size:1.02rem;line-height:1.3;margin:8px 0 4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.topics3 p{font-size:.88rem;-webkit-line-clamp:2}
.vstrip{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding:2px 0 12px;scrollbar-width:thin}
.vcard{flex:0 0 240px;scroll-snap-align:start;text-decoration:none;color:inherit;min-width:0}
.vcard .vim{position:relative;display:block;aspect-ratio:16/9;border-radius:10px;overflow:hidden;border:1px solid var(--edge);border-top:3px solid #444;background:#000;container-type:inline-size}
.vcard.tesla .vim{border-top-color:#E31937}.vcard.energy .vim{border-top-color:#4CD964}.vcard.spacex .vim{border-top-color:#FF7A00}.vcard.link .vim{border-top-color:#00D1FF}.vcard.spacexsi .vim{border-top-color:#FFC400}.vcard.neural .vim{border-top-color:#FF2D95}.vcard.boring .vim{border-top-color:#2F6BFF}
.vcard img{width:100%;height:100%;object-fit:cover}
.vcard strong{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:.9rem;line-height:1.3;margin-top:8px;font-weight:700}
@media (max-width:800.98px){
.topics3{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:12px;padding-bottom:8px}
.topics3>.card{flex:0 0 82%;scroll-snap-align:start}
.vcard{flex-basis:78vw}
}
article.money .avid{max-width:68ch}
.avid.short{max-width:280px}
.avid.short .avb{aspect-ratio:9/16}
.adslot{margin:20px 0;max-width:68ch;display:flex;flex-direction:column;align-items:stretch;background:rgba(255,255,255,.03);border:1px dashed var(--border2);border-radius:8px;overflow:hidden}
.adlab{font-size:.65rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);padding:8px 12px 0}
.adslot ins{display:block;width:100%}
.pbox{margin:22px 0;max-width:68ch}
.pbox-in{display:grid;grid-template-columns:168px minmax(0,1fr);gap:16px;align-items:start;padding:14px;border:1px solid var(--border2);border-radius:12px;background:#161616}
.pbox img{width:100%;height:auto;aspect-ratio:4/3;object-fit:cover;border-radius:8px}
.pbox h3{font-size:1.05rem;line-height:1.3;margin:0 0 8px}
.pbox ul{margin:0 0 12px;padding-left:18px}
.pbox li{margin:0 0 4px;color:var(--muted);font-size:.92rem}
.affnote{margin:8px 0 0;font-size:.75rem;line-height:1.45;color:var(--dim)}
.nform{margin:26px 0;padding:16px 16px 14px;border:1px solid var(--border2);border-radius:12px;background:rgba(255,255,255,.03);max-width:68ch}
.nform h2{font-size:1.15rem;margin:0 0 6px}
.nform p{color:var(--muted);font-size:.9rem;line-height:1.45;margin:0 0 12px}
.nrow{display:flex;gap:8px}
.nrow input{flex:1;min-width:0;background:#121212;border:1px solid #3a4a60;border-radius:10px;color:var(--head);font:inherit;font-size:1rem;padding:10px 12px}
.nrow button{background:var(--red);color:#fff;border:0;border-radius:10px;font:inherit;font-weight:800;padding:10px 16px;cursor:pointer;white-space:nowrap}
.nrow button:hover{background:var(--red2)}
footer .nform{margin:14px 0 0;padding:0;border:0;background:transparent;max-width:340px}
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
.hb-find .hb-search:hover,.hb-find .hb-search:focus-within{outline:2px solid var(--blue2);outline-offset:2px}
header.hb .sbtn{display:grid;width:36px;height:36px;margin-left:auto;border:0;background:transparent;color:#ebebeb}
header.hb .sbtn:focus-visible{outline:2px solid var(--blue2);outline-offset:2px}
html.find-open header.hb .sbtn{background:#272727;border-radius:8px}
@media (prefers-reduced-motion:reduce){.hb-find,.hb-find .hb-search{transition:none}}
header.hb .savedlink{margin-left:6px}
header.hb ~ .drawer,header.hb ~ .scrim{top:66px}
@media (min-width:900px){header.hb .pnav{display:flex;flex-wrap:nowrap;overflow:visible;align-items:baseline}header.hb .id{align-items:baseline;gap:16px}header.hb .bar{position:relative;z-index:3;align-items:center}header.hb .logo{line-height:1}header.hb .logo span{top:0}header.hb .bar .burger{display:flex}}
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
.pv-lead{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:14px;align-items:center;margin:0 0 6px;text-decoration:none;color:inherit}
.pv-lead .im{position:relative;border-radius:10px;overflow:hidden;border:1px solid var(--edge);background:#000}
.pv-lead img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.pv-kicker{font-size:.72rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--blue)}
.pv-lead h1,.pv-lead h2{font-size:clamp(1.25rem,2.2vw,1.7rem);line-height:1.18;margin:4px 0 8px}
.pv-lead p{color:var(--muted);font-size:.92rem;line-height:1.45;margin:0}
.pv-day{font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin:8px 0 2px;padding-top:6px;border-top:1px solid var(--border)}
.pv-row{display:grid;grid-template-columns:52px minmax(0,1fr) 46px;gap:8px;align-items:center;padding:3px 0;border-bottom:1px solid #242424;text-decoration:none;color:inherit}
.pv-row.hasth{grid-template-columns:52px 64px minmax(0,1fr) 46px}
.pv-row time{font-variant-numeric:tabular-nums;font-size:.8rem;font-weight:800;color:var(--dim)}
.pv-th{position:relative;container-type:inline-size;border-radius:6px;overflow:hidden;border:1px solid var(--edge);background:#000}
.pv-th img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.pv-hl{min-width:0}
.pv-hl b{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;white-space:normal;font-size:.95rem;line-height:1.3;font-weight:400;color:var(--blue)}
.pv-min{justify-self:end;min-width:42px;text-align:center;border:1px solid var(--border2);border-radius:8px;padding:1px 0;line-height:1}
.pv-min b{display:block;color:var(--red);font-size:.85rem;line-height:1}
.pv-min small{display:block;color:var(--dim);font-size:.58rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;line-height:1}
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
.pv-side a:hover,.pv-side a:focus-visible{color:var(--blue)}
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
/* One centered frame for every page: reading column plus a right sidebar. */
.sheet{display:grid;grid-template-columns:minmax(0,1fr) 292px;gap:26px;align-items:start}
.sheet-main{min-width:0}
.sheet .leadstory{margin-top:1px;align-items:start}
.pv-side{margin-top:1px}
.sheet:has(.leadstory)>.pv-side{margin-top:3px}
/* Homepage: the top block and the red rule above Latest news share one top edge. */
.sheet.front .leadstory,.sheet.front .layerrow{margin-top:0}
.sheet.front>.pv-side,.sheet.front:has(.leadstory)>.pv-side{margin-top:0}
.layerrow{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 22px;align-items:stretch}
.lcard{display:flex;flex-direction:column;min-width:0;height:100%;text-decoration:none;color:inherit;background:#141414;border:1px solid #2a2a2a;border-top:3px solid #444;border-radius:8px;overflow:hidden}
.layerrow .lcard:last-child{grid-column:1 / -1}
.lcard .lim{display:block;aspect-ratio:16/9;background:#101010;overflow:hidden}
.lcard .lim img{width:100%;height:100%;object-fit:cover}
.lcard .lbody{display:flex;flex-direction:column;gap:4px;padding:8px 10px 10px;min-width:0;flex:1}
.lcard .lmeta{display:flex;flex-wrap:wrap;gap:4px 6px;align-items:baseline;padding:8px 10px 0;font-size:.68rem;font-weight:700;line-height:1.3;color:var(--dim)}
.lcard .lname{font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--blue)}
.lcard strong{font-size:.92rem;line-height:1.28;font-weight:800;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.leadstory .ltitle{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.lcard.tesla{border-top-color:#E31937}
.lcard.energy{border-top-color:#4CD964}
.lcard.spacex{border-top-color:#FF7A00}
.lcard.link{border-top-color:#00D1FF}
.lcard.spacexsi{border-top-color:#FFC400}
.lcard.neural{border-top-color:#FF2D95}
.lcard.boring{border-top-color:#2F6BFF}
.lcard.empty{border-color:rgba(255,45,149,.55);background:linear-gradient(165deg,#ff2d95 0%,#c41878 38%,#3a0824 100%)}
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
.sheet-main article.money h1{font-size:clamp(1.55rem,2.6vw,2.1rem);line-height:1.16;margin:6px 0 8px}
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
@media (max-width:600.98px){.sheet-main article.money .avid.long .avb,.pv-art .avid.long .avb,.sheet-main article.money>.hi,.pv-art article.money>.hi,.sheet-main article.money .avid.short .avb,.pv-art .avid.short .avb{width:calc(100% - 28px);margin-left:14px;margin-right:14px}}
.sheet-main article.narrow>h1,.sheet-main article.money>h1,.sheet-main article.money>.meta,.sheet-main article.money>.byline{margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}
.sheet-main article.brief>h1,.sheet-main article.brief>.byline,.sheet-main article.brief>.meta,.sheet-main article.brief>.tplnote,.sheet-main article.brief>.lead{margin-left:0;margin-right:0}
.sheet-main article.brief>.lead{padding-left:0;padding-right:0}
@media (max-width:600.98px){.sheet-main article.narrow>h1,.sheet-main article.money>h1,.sheet-main article.money>.meta,.sheet-main article.money>.byline,.sheet-main article.money .toc,.sheet-main article.money .sources,.sheet-main article.money .imgnote,.sheet-main article.money nav.seq,.sheet-main article.money .pbox,.sheet-main article.money .nform,.sheet-main article.money .avid figcaption{margin-left:14px;margin-right:14px}.sheet-main article.brief>h1,.sheet-main article.brief>.byline,.sheet-main article.brief>.meta,.sheet-main article.brief>.tplnote,.sheet-main article.brief>.lead{margin-left:0;margin-right:0}}
.sheet-main article.money .mlbox,.sheet-main article.narrow .mlbox{margin-left:calc(3vw + 14px);margin-right:calc(3vw + 14px)}
@media (max-width:600.98px){.sheet-main article.money .mlbox,.sheet-main article.narrow .mlbox{margin-left:14px;margin-right:14px}}
@media (max-width:900px){
.pv-grid,.pv-art,.pv-art.pv-c,.sheet{grid-template-columns:1fr}
.pv-lead{grid-template-columns:1fr}
.pv-c .toc{position:static}
.pv-row.hasth{grid-template-columns:46px 52px minmax(0,1fr) 40px}
}
/* Related and the rest of the sidebar share one rail. The article must not
   span two rows of that rail: auto rows then grow with the story and open a gap
   between Related and Start here. The bar stays a full-width row underneath. */
.sheet:has(.arel){grid-template-areas:"main rail" "bar bar";align-items:start}
.sheet:has(.arel)>.sheet-main{grid-area:main}
.sheet:has(.arel)>.sheet-rail{grid-area:rail;display:flex;flex-direction:column;justify-content:flex-start;align-items:stretch;align-self:start;min-width:0;gap:0}
.sheet:has(.arel)>.nlbar{grid-area:bar}
.sheet>.nlbar{grid-column:1 / -1}
@media (max-width:900px){
.sheet:has(.arel){grid-template-columns:1fr;grid-template-areas:"main" "side" "bar" "rest"}
.sheet:has(.arel)>.sheet-rail{display:contents}
.sheet:has(.arel) .arel{grid-area:side}
.sheet:has(.arel) .pv-side:not(.arel){grid-area:rest}
.nlside{display:none}
}
.eco-bit{min-width:0}
.eco-sources{margin:0 0 12px;padding-left:1.1rem}
.eco-sources li{margin:0 0 6px}
.eco-sources a{color:#9ad7ff}
.ss-wrap{overflow-x:auto}
.byline{margin:0 0 12px;color:var(--dim);font-size:.86rem}
.hubh{font-size:1.15rem;margin:8px 0 4px}
.hubcount{margin:0 0 12px;color:var(--dim);font-size:.84rem}
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
a.eco-node:hover,a.eco-node:focus-visible,.card:hover,.card:focus-visible,.eco-card:hover,.eco-card:focus-visible,.eco-co:hover,.eco-co:focus-visible,.lcard:hover,.lcard:focus-visible,.leadstory:hover .leadim,.leadstory:focus-within .leadim,.vcard:hover .vim,.vcard:focus-visible .vim{border-color:var(--blue);box-shadow:0 0 0 2px var(--blue),0 0 16px rgba(0,212,255,.35);outline:none}
.lcard.tesla:hover,.lcard.tesla:focus-visible{border-top-color:#E31937}.lcard.energy:hover,.lcard.energy:focus-visible{border-top-color:#4CD964}.lcard.spacex:hover,.lcard.spacex:focus-visible{border-top-color:#FF7A00}.lcard.link:hover,.lcard.link:focus-visible{border-top-color:#00D1FF}.lcard.spacexsi:hover,.lcard.spacexsi:focus-visible{border-top-color:#FFC400}.lcard.neural:hover,.lcard.neural:focus-visible{border-top-color:#FF2D95}.lcard.boring:hover,.lcard.boring:focus-visible{border-top-color:#2F6BFF}
.vcard.tesla:hover .vim,.vcard.tesla:focus-visible .vim{border-top-color:#E31937}.vcard.energy:hover .vim,.vcard.energy:focus-visible .vim{border-top-color:#4CD964}.vcard.spacex:hover .vim,.vcard.spacex:focus-visible .vim{border-top-color:#FF7A00}.vcard.link:hover .vim,.vcard.link:focus-visible .vim{border-top-color:#00D1FF}.vcard.spacexsi:hover .vim,.vcard.spacexsi:focus-visible .vim{border-top-color:#FFC400}.vcard.neural:hover .vim,.vcard.neural:focus-visible .vim{border-top-color:#FF2D95}.vcard.boring:hover .vim,.vcard.boring:focus-visible .vim{border-top-color:#2F6BFF}
@media (max-width:560px){
.eco-node .eco-k{font-size:.78rem}
.eco-node li{font-size:.62rem;line-height:1.2}
.eco-core{font-size:.84rem}
}
@media (min-width:1100px){header.hb .id{gap:24px}}
@media (min-width:1320px){header.hb .id{gap:80px}}
@media (min-width:1200px){
header.hb .pn,header.hb .mdrop>button.pn{font-size:14px;padding:6px 8px}
}
@media (min-width:1000px) and (max-width:1199.98px){
header.hb .pn,header.hb .mdrop>button.pn{font-size:13px;padding:5px 5px}
}
@media (min-width:900px) and (max-width:999.98px){
header.hb .id{gap:6px}
header.hb .pn,header.hb .mdrop>button.pn{font-size:12.5px;padding:5px 3px}
}
.adhold{display:block;width:100%}
.ad-sidebar{margin:0 0 16px;max-width:none}
@media (max-width:900px){.ad-sidebar{display:none}}
.tplnote{margin:0 0 14px;padding:10px 12px;border:1px dashed #ffc400;border-radius:8px;color:#ffe28a;font-weight:700;font-size:.92rem;line-height:1.4}
.ltag{display:inline-block;font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--blue);border-radius:8px;padding:2px 8px;text-decoration:none;color:var(--blue)}
.brief-layers{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 16px}
.brief-list{list-style:none;margin:0 0 18px;padding:0}
.brief-list a{display:block;padding:12px 14px;border:1px solid #3a4a60;border-radius:8px;text-decoration:none;color:inherit;margin:0 0 8px}
.brief-list a:hover{border-color:var(--blue)}
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
.gbox{margin:16px 0;padding:14px;border:1px solid #3a4a60;border-radius:8px;background:#161616;display:grid;grid-template-columns:168px minmax(0,1fr);gap:14px}
.gbox.noimg{grid-template-columns:1fr}
.gbox img{width:100%;height:auto;aspect-ratio:4/3;object-fit:cover;border-radius:8px}
.gbox h2{margin:0 0 8px;font-size:1.12rem}
.gbox h3{margin:8px 0 4px;font-size:.78rem;letter-spacing:.04em;text-transform:uppercase;color:var(--dim)}
.gbox ul{margin:0;padding-left:1.1em}
.gbox li{margin:0 0 3px}
.gbox .btn{display:inline-block;margin-top:10px;background:var(--red);color:#fff;text-decoration:none;font-weight:800;border-radius:8px;padding:10px 14px}
.gtable{width:100%;border-collapse:collapse;margin:8px 0 16px;font-size:.92rem}
.gtable th,.gtable td{padding:8px 10px;border:1px solid #3a4a60;text-align:left}
.gtable caption{text-align:left;font-weight:800;margin:0 0 6px}
.afftop{margin:0 0 14px;font-size:.84rem;line-height:1.45;color:var(--dim)}
.afftop a{color:#9ad7ff}
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
@media (max-width:600.98px){.gbox{grid-template-columns:1fr}}
"""

# Classes left over from retired layouts. They are not emitted by the pages build() writes.
# Ads, the newsletter form, product boxes and the Shorts player stay: those render when configured.
_DEAD_CSS = frozenset("""
act acts arch aread below beside big btns cats9 chips dm eyebrow feature grid h2 hero home
hsec leadside mcell mdesc mini model models morelink nextread pblock ph phead pimg ptop ptxt
pv-art pv-block pv-c pv-grid pv-guide pv-kicker pv-lead pv-note pv-off pv-tabs read rh rside
side sideh slogan soon span2 sr srow starthere sub tdb tdc tdd tdl th tip topic topics3 tops why
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


def when(a, lang):
    """Date for list items; JS turns it into '5 uur geleden' (under 48 h) or '3 dagen geleden'."""
    return f'<time class="ago" datetime="{published(a).isoformat()}">{fmt_date(a["date"], lang)}</time>'


def published(a):
    """Timezone-aware publication datetime (defaults to 08:00 local)."""
    return datetime.strptime(f"{a['date']} {a.get('time', '08:00')}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


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
    if p and (STATIC / "img" / "models" / p).exists():
        return f"/img/models/{p}"
    return model_photo(m["parent"], for_article) if m.get("parent") else None


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
    fsections = "".join(
        f'<details class="fcol" open><summary class="flabel">{esc(title)}</summary>'
        f'<div class="flist">{html}</div></details>'
        for title, html in foot_cols)
    cats = " · ".join(f'<a href="{url(lang, "category/" + k + "/")}">{c[lang]}</a>' for k, c in CATEGORIES.items() if c["menu"])
    mods = " · ".join(f'<a href="{url(lang, "model/" + k + "/")}">{m["name"]}</a>' for k, m in MODELS.items() if not m.get("parent") or k in MODEL_STRIP)
    search = (f'<form class="search hb-search" role="search" action="{url(lang)}" '
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
              f'<div class="id">{brand}{primary_nav(lang, active)}</div>'
              f'<button class="sbtn" type="button" aria-label="{find_label}" aria-expanded="false" aria-controls="site-search">{SEARCH_SVG}</button>'
              f'{tools}</div></div>'
              f'<div class="hb-find" id="site-search" inert><div class="wrap">{search}</div></div></header>')
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
<div class="fbrand"><a class="logo" href="{url(lang)}">Trending<span>Tesla</span></a><p>{L['tagline']} {L['disclaimer']}</p>{newsletter(lang, "foot")}</div>
<div class="fgrid">{fsections}</div>
<p class="fcopy">&copy; {datetime.now().year} {NAME} · <a href="https://www.youtube.com/@TrendingTesla" rel="noopener" target="_blank">YouTube</a> · <button type="button" class="flink" data-consent-open>{L['cookie']}</button> · <a href="{url(lang, 'feed.xml')}">RSS</a> · <a href="{url(alt, switch)}">{L['switch_full']}</a></p>
</div></footer>
{consent_bar(lang)}
<script>{JS}</script>
</body>
</html>
"""


SEARCH_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/></svg>'
CHEV_SVG = '<svg class="chev" width="11" height="11" viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M2.1 4.2 6 8.1 9.9 4.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
HEART_SVG = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.4 4.5 7 4.5c2 0 3.6 1.1 5 2.9 1.4-1.8 3-2.9 5-2.9 3.6 0 5.6 3.5 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z"/></svg>'
BOOK_SVG = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"><path d="M6 3.5h12v17l-6-4.2-6 4.2z"/></svg>'
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
            f'<a href="{url(lang, "model/" + k + "/")}">Tesla {MODELS[k]["name"]}</a>' for k in a["models"]) + "</div>"
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
            src = f"/img/models/{img}" if img and (STATIC / "img" / "models" / img).exists() else ""
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
        g += c.replace('<a class="card"', '<a class="card xtra"', 1) if no_left and i >= MAX_HOME_GRID else c
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


JS = r"""(function(){function f(){var t=document.querySelector('header.top');if(t)t.classList.toggle('solid',scrollY>0||document.documentElement.classList.contains('dopen'))}addEventListener('scroll',f,{passive:true});document.addEventListener('DOMContentLoaded',f);f()})();(function(){var Q='main h1,main h2,main h3,main p,main li,main tr,main .card,main .gcard,main .mini,main .im,main .hi',K='tt-lswap';try{if('scrollRestoration' in history)history.scrollRestoration='manual'}catch(e){}document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a.lang');if(!a)return;var R=innerHeight*.33,els=document.querySelectorAll(Q),i=-1,off=0;for(var k=0;k<els.length;k++){var r=els[k].getBoundingClientRect();if(r.height>0&&r.top<=R&&r.bottom>R){i=k;off=(R-r.top)/r.height}}var H=document.documentElement.scrollHeight-innerHeight;try{sessionStorage.setItem(K,JSON.stringify({i:i,o:off,r:H>0?scrollY/H:0,y:scrollY,n:els.length,p:location.pathname,t:Date.now()}))}catch(x){}},true);function go(){var d;try{d=JSON.parse(sessionStorage.getItem(K)||'null')}catch(x){}if(!d||Date.now()-d.t>15000||d.p==location.pathname)return;var els=document.querySelectorAll(Q);if(d.i>=0&&els.length==d.n&&els[d.i]){var r=els[d.i].getBoundingClientRect();scrollTo(0,r.top+scrollY+d.o*r.height-innerHeight*.33)}else if(d.y<10){scrollTo(0,0)}else{scrollTo(0,d.r*(document.documentElement.scrollHeight-innerHeight))}}document.addEventListener('DOMContentLoaded',go);addEventListener('load',function(){go();setTimeout(function(){go();try{sessionStorage.removeItem(K)}catch(x){}},350)})})();function ttKK(){var M={a:[6.6,10.5],c:[8,6.2],n:[10,5.8],r:[7.4,7.4]};document.querySelectorAll('.kk').forEach(function(k){var p=k.parentElement,W=p.clientWidth;if(!W)return;var d=p.querySelector('.dur'),A=(d?d.offsetLeft:W)-k.offsetLeft-.026*W,t=(k.className.match(/t-(\w)/)||[])[1]||'a',m=M[t]||M.a,f=[];[].forEach.call(k.children,function(b,i){var s=(k.children.length==1?m[1]:m[i])*W/100;b.style.fontSize=s+'px';for(var j=0;j<3;j++){var w=b.getBoundingClientRect().width;if(w>A){s*=A/w*.995;b.style.fontSize=s+'px'}}f.push(s)});if(f.length==2){if(t=='a'){var w0=k.children[0].getBoundingClientRect().width,w1=k.children[1].getBoundingClientRect().width;if(w1>w0*1.04){var g=Math.max(f[1]*w0/w1,f[0]*1.18);if(g<f[1]){f[1]=g;k.children[1].style.fontSize=g+'px'}}if(f[0]>f[1]*.85)k.children[0].style.fontSize=f[1]*.85+'px'}if(t=='c'&&f[1]>f[0]*.9)k.children[1].style.fontSize=f[0]*.9+'px';if(t=='n'&&f[1]>f[0]*.62)k.children[1].style.fontSize=f[0]*.62+'px'}})}addEventListener('load',ttKK);document.addEventListener('submit',function(e){var f=e.target;if(!f.classList||!f.classList.contains('cform'))return;e.preventDefault();var b=f.querySelector('button'),st=f.querySelector('.cstatus'),d={};new FormData(f).forEach(function(v,k){d[k]=v});d.lang=document.documentElement.lang;d.page=location.pathname;b.disabled=true;st.textContent='…';fetch('/api/contact',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(d)}).then(function(r){return r.json().then(function(j){if(!r.ok||!j.ok)throw 0;st.textContent=f.dataset.ok;f.reset()})}).catch(function(){st.textContent=f.dataset.err;b.disabled=false})});function ttRow(){document.querySelectorAll('.gall').forEach(function(g){var x=g.querySelectorAll(':scope>.xtra');if(!x.length)return;x.forEach(function(e){e.classList.remove('on')});var c=getComputedStyle(g).gridTemplateColumns.split(' ').length,n=g.children.length-x.length,need=(c-n%c)%c;for(var i=0;i<need&&i<x.length;i++)x[i].classList.add('on')})}ttRow();addEventListener('resize',ttRow);document.addEventListener('DOMContentLoaded',ttRow);addEventListener('resize',ttKK);if(document.fonts)document.fonts.ready.then(ttKK);document.addEventListener('DOMContentLoaded',ttKK);function mq(n){return matchMedia('(min-width:'+n+'px)').matches}function ttAgo(){var nl=document.documentElement.lang=='nl';document.querySelectorAll('time.ago').forEach(function(t){var h=(Date.now()-Date.parse(t.dateTime))/36e5;if(!(h>=0))return;if(!t.dataset.d)t.dataset.d=t.textContent;var d=h/24,n,k;if(h<48){n=Math.max(1,Math.floor(h));k=0}else if(d<7){n=Math.floor(d);k=1}else if(d<30.44){n=Math.floor(d/7);k=2}else if(d<365.25){n=Math.floor(d/30.44);k=3}else{n=Math.floor(d/365.25);k=4}var one=n==1,L=nl?[['uur','uur'],['dag','dagen'],['week','weken'],['maand','maanden'],['jaar','jaar']]:[['hour','hours'],['day','days'],['week','weeks'],['month','months'],['year','years']],S=nl?['uur','dgn','wkn','mnd','jr']:['h','d','wk','mo','yr'],end=nl?' geleden':' ago';t.textContent=n+' '+L[k][one?0:1]+end;var m=t.closest('.smeta');if(m&&m.scrollWidth>m.clientWidth+1)t.textContent=n+(nl?' ':'')+(nl&&one&&k==1?'dag':S[k])+end})}ttAgo();setInterval(ttAgo,60000);function ttSearch(){var s=document.querySelector('.bar .search'),h=document.documentElement;if(!s)return;document.querySelector('.bar .lang').style.height='';h.classList.remove('hasdd');document.querySelector('.bar .savedlink').style.marginLeft='';var bar=s.parentNode,br=bar.querySelector('.brand')||bar.querySelector('.logo'),sv=bar.querySelector('.savedlink');var m=!mq(601)?12:28,L=br.getBoundingClientRect().right+m,R=sv.getBoundingClientRect().left-14,l=document.querySelector('.read .lcol');if(l&&mq(700))R=Math.min(R,l.getBoundingClientRect().right);else if(!l&&mq(905)){var b=bar.getBoundingClientRect();R=Math.min(R,b.left+(b.width-13)*1.7/2.7)}s.style.marginLeft=m+'px';h.classList.add('hass');s.style.width='200px';var w=R-s.getBoundingClientRect().left;if(w>=200){s.style.width=w+'px';s.style.setProperty('--k',Math.min(1,w/520).toFixed(3))}else{h.classList.remove('hass');s.style.width=''}}function ttDD(){var d=document.querySelector('.bar .tdd'),s=document.querySelector('.bar .search'),h=document.documentElement;if(!d)return;h.classList.remove('hasdd','ddend');if(!mq(700)||!h.classList.contains('hass'))return;var bn=d.parentNode,bar=bn.getBoundingClientRect(),L,R,rs=document.querySelector('.read .rside'),ph=rs&&[].slice.call(rs.querySelectorAll('.mini .th img')).filter(function(x){return x.offsetParent})[0];if(ph){var q=ph.getBoundingClientRect();L=q.left;R=q.right}else{var W=bar.width,rw=mq(905)?(W-13)/2.7:(W-13)/3.68;L=bar.right-rw;R=mq(905)?L+(rw-26)*2/3+7:bar.right}var end=!mq(905),sv=document.querySelector('.bar .savedlink'),lg=document.querySelector('.bar .lang');if(!end){var a=sv.getBoundingClientRect(),c=lg.getBoundingClientRect();R=Math.min(R,bar.right-(c.right-a.left)-28)}R=Math.min(R,bar.right);if(R-L<140)return;h.classList.add('hasdd');if(end)h.classList.add('ddend');d.dataset.l=L;d.style.width=(R-L)+'px';function al(){d.style.marginLeft='0px';for(var i=0;i<2;i++)d.style.marginLeft=(parseFloat(d.style.marginLeft)+L-d.getBoundingClientRect().left)+'px'}if(end){for(var k=0;k<2;k++){var gap=L-14-lg.getBoundingClientRect().right;s.style.width=Math.max(160,s.getBoundingClientRect().width+gap)+'px';d.style.marginLeft='14px'}}al();var ov=bn.scrollWidth-bn.clientWidth;if(ov>0){d.style.width=(R-L-ov)+'px';al()}d.querySelector('.tdb').style.height=s.getBoundingClientRect().height+'px'}function ttCenter(){var h=document.documentElement,s=document.querySelector('.bar .search');if(!s||!h.classList.contains('hass'))return;var d=document.querySelector('.bar .tdd'),dd=h.classList.contains('hasdd'),end=h.classList.contains('ddend'),sv=document.querySelector('.bar .savedlink'),br=document.querySelector('.bar .brand');for(var i=0;i<3;i++){if(!dd&&i==0)s.style.width='120px';var bl=br.getBoundingClientRect().right,lg=document.querySelector('.bar .lang').getBoundingClientRect(),lc=document.querySelector('.read .lcol'),wide=dd&&!end,rn=end?(+d.dataset.l)-14-(lg.right-sv.getBoundingClientRect().left):wide?(lc?lc.getBoundingClientRect().right:(+d.dataset.l)-13):sv.getBoundingClientRect().left,G=Math.max(10,Math.min(24,(rn-bl-160)/2)),off=Math.min(10,G-6),w=Math.max(160,wide?rn-bl-G-off:rn-bl-2*G);s.style.width=w+'px';s.style.setProperty('--k',Math.min(1,w/520).toFixed(3));s.style.marginLeft=(parseFloat(getComputedStyle(s).marginLeft)+bl+G+off-s.getBoundingClientRect().left)+'px';if(end)sv.style.marginLeft=(parseFloat(getComputedStyle(sv).marginLeft)+s.getBoundingClientRect().right+G-off-sv.getBoundingClientRect().left)+'px';if(dd)d.style.marginLeft=(parseFloat(getComputedStyle(d).marginLeft)+(+d.dataset.l)-d.getBoundingClientRect().left)+'px'}var lgb=document.querySelector('.bar .lang');lgb.style.height=s.getBoundingClientRect().height+'px';if(d){var sb=s.querySelector('button');d.style.setProperty('--bw',sb.getBoundingClientRect().width+'px');d.querySelector('.tdb').style.height=s.getBoundingClientRect().height+'px'}}addEventListener('resize',function(){ttSearch();ttDD();ttCenter()});document.addEventListener('DOMContentLoaded',function(){var d=document.querySelector('.bar .tdd');if(!d)return;var b=d.querySelector('.tdb'),l=d.querySelector('.tdl');function set(o){l.hidden=!o;b.setAttribute('aria-expanded',o)}b.addEventListener('click',function(e){e.stopPropagation();set(l.hidden)});document.addEventListener('click',function(e){if(!d.contains(e.target))set(false)});document.addEventListener('keydown',function(e){if(e.key=='Escape')set(false)})});document.addEventListener('DOMContentLoaded',function(){ttSearch();ttDD();ttCenter();if(window.ResizeObserver){var rq=0,lw=0;new ResizeObserver(function(e){var w=e[0].contentRect.width;if(Math.abs(w-lw)<0.5)return;lw=w;cancelAnimationFrame(rq);rq=requestAnimationFrame(function(){ttSearch();ttDD();ttCenter()})}).observe(document.querySelector('.bar'))}if(document.fonts)document.fonts.ready.then(function(){ttSearch();ttDD();ttCenter()})});addEventListener('load',function(){ttSearch();ttDD();ttCenter()});addEventListener('resize',ttAgo);(function(){var tip=document.createElement('div');tip.className='agotip';document.addEventListener('mouseover',function(ev){var t=ev.target.closest&&ev.target.closest('time.ago');if(!t||!t.dataset.d){tip.remove();return}tip.textContent=t.dataset.d;document.body.appendChild(tip);var r=t.getBoundingClientRect();tip.style.left=Math.max(4,Math.min(innerWidth-tip.offsetWidth-4,r.left+r.width/2-tip.offsetWidth/2))+'px';tip.style.top=(r.bottom+6)+'px'});addEventListener('scroll',function(){tip.remove()},{passive:true})})();(function(){function fit(){var t=document.querySelector('.prose .toc'),b=document.querySelector('.beside');if(t&&b&&getComputedStyle(t).float!='none'){var n;while(b.offsetHeight<t.offsetHeight-8&&(n=b.nextElementSibling)&&!n.classList.contains('pblock')&&!(n.tagName=='H2'&&n.nextElementSibling&&n.nextElementSibling.classList.contains('pblock'))){b.appendChild(n);if(n.tagName=='H2'&&(n=b.nextElementSibling)&&!n.classList.contains('pblock'))b.appendChild(n)}}document.querySelectorAll('.pblock').forEach(function(k){var x=k.querySelector('.ptxt'),f=k.querySelector('.pimg'),W=k.offsetWidth,mx=W*(!mq(601)?.36:.45),w;for(var i=0;i<6;i++){w=Math.min(mx,x.offsetHeight*.75);f.style.width=w+'px'}f.style.height=Math.max(x.offsetHeight-5,w*4/3)+'px';f.querySelector('img').style.aspectRatio='auto'})}addEventListener('load',fit);addEventListener('resize',fit);var d=document.documentElement,o=document.querySelector('.scrim');
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
function setFind(open,opts){opts=opts||{};var panel=document.getElementById('site-search'),btn=document.querySelector('header.hb .sbtn');if(!panel||!btn)return;d.classList.toggle('find-open',open);btn.setAttribute('aria-expanded',open?'true':'false');if(open){panel.inert=false;if(opts.focus!==false){var input=panel.querySelector('input');if(input)input.focus({preventScroll:true})}var show=function(ev){if(ev&&ev.target!==panel)return;d.classList.add('find-ready')};panel.addEventListener('transitionend',show,{once:true});setTimeout(function(){d.classList.add('find-ready')},280)}else{d.classList.remove('find-ready');if(r)r.hidden=true;panel.inert=true;if(opts.restore)btn.focus({preventScroll:true})}}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){t(false);d.classList.remove('sopen');if(d.classList.contains('find-open'))setFind(false,{restore:true})}});
var f=document.querySelector('.search'),i=f.querySelector('input'),r=f.querySelector('.res'),idx=null;
function e(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function load(){return idx?Promise.resolve(idx):fetch(f.dataset.idx).then(function(x){return x.json()}).then(function(j){idx=j;return j})}
i.addEventListener('focus',load);
i.addEventListener('input',function(){var q=i.value.trim().toLowerCase();if(q.length<2){r.hidden=true;return}
load().then(function(){var w=q.split(/\s+/),h=idx.filter(function(a){var s=(a.t+' '+a.d+' '+a.c).toLowerCase();return w.every(function(x){return s.indexOf(x)>-1})}).slice(0,8);
r.innerHTML=h.length?h.map(function(a){return '<a href="'+a.u+'"><img src="'+a.i+'" alt="'+e(a.t)+'" width="160" height="84" decoding="async"><span><b>'+e(a.t)+'</b><small>'+e(a.c)+' · '+e(a.dt)+'</small></span></a>'}).join(''):'<p>'+e(f.dataset.none)+'</p>';r.hidden=false;window.ttFit=function(){[].forEach.call(document.querySelectorAll('.res a'),function(x){var im=x.querySelector('img'),t=x.querySelector('span');if(!im||!t)return;var m=(x.clientWidth-12)/2;im.style.width=m+'px';var h=t.offsetHeight,w=h*1200/630;if(w>m){w=m;h=w*630/1200}im.style.width=w+'px';im.style.height=h+'px'})};ttFit();if(!window.ttR){window.ttR=1;addEventListener('resize',function(){window.ttFit()})}})});
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
document.querySelectorAll('[data-save]').forEach(function(b){var s=b.dataset.save;function st(){var on=LS.get('tt_saved').indexOf(s)>-1;b.setAttribute('aria-pressed',on);b.title=SAVE[on?1:0];b.setAttribute('aria-label',SAVE[on?1:0])}st();
b.onclick=function(){var l=LS.get('tt_saved'),i=l.indexOf(s);if(i>-1)l.splice(i,1);else l.unshift(s);LS.set('tt_saved',l);st();badge()}});
var lb=[].slice.call(document.querySelectorAll('[data-like]'));if(lb.length){var liked=LS.get('tt_liked');
fetch('/api/likes?s='+lb.map(function(b){return b.dataset.like}).join(',')).then(function(r){return r.json()}).then(function(j){lb.forEach(function(b){var n=j[b.dataset.like]||0;b.querySelector('span').textContent=n})}).catch(function(){});
lb.forEach(function(b){var s=b.dataset.like;b.setAttribute('aria-pressed',liked.indexOf(s)>-1);b.onclick=function(){var l=LS.get('tt_liked'),i=l.indexOf(s),d=i>-1?-1:1;if(d>0)l.push(s);else l.splice(i,1);LS.set('tt_liked',l);b.setAttribute('aria-pressed',d>0);
var sp=b.querySelector('span');sp.textContent=Math.max(0,(+sp.textContent||0)+d);fetch('/api/likes',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({slug:s,d:d})}).then(function(r){return r.json()}).then(function(j){if(j.n!=null)sp.textContent=j.n}).catch(function(){})}})}
var sl=document.querySelector('.savedlist');if(sl){var keep=LS.get('tt_saved');if(!keep.length){sl.innerHTML='<p class="empty">'+e(sl.dataset.empty)+'</p>'}else{load().then(function(){var m={};idx.forEach(function(a){var k=a.u.replace(/\/$/,'').split('/').pop();m[k]=a});
sl.innerHTML=keep.filter(function(k){return m[k]}).map(function(k){var a=m[k];return '<a class="card" href="'+a.u+'"><div class="im"><img src="'+a.i+'" alt="'+e(a.t)+'" width="1200" height="630" decoding="async"></div><div class="body"><h3>'+e(a.t)+'</h3><p>'+e(a.d)+'</p><span class="meta">'+'<time class="ago" datetime="'+a.ts+'">'+e(a.dt)+'</time></span></div></a>'}).join('');ttAgo()})}}window.addEventListener('resize',bal);bal();
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
    """Visible section name and the hub it links to."""
    info = TOPIC_LABEL.get(a.get("topic") or "")
    if info:
        href = ecosystem_path(lang) if a.get("topic") == "ecosystem" else info["href"]
        return info[lang], href
    cat = CATEGORIES[a["category"]]
    return cat.get("tag", cat[lang]), "category/" + a["category"] + "/"


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
    return (f'<a class="{cls}" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="im">{resp_img(site_img(a), t["title"], SIZES_CARD)}{dur(a, lang)}{ovl(a, lang)}</div>'
            f'<div class="body">{label(a, lang)} <span class="meta">· {when(a, lang)}</span>'
            f'<h3>{esc(card_title(a, lang))}</h3><p>{esc(t["description"])}</p></div></a>')


def gcard(a, lang, eager=False):
    """Topic list under the lead: photo on top, then title, summary and date."""
    t = a[lang]
    return (f'<a class="card" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="im">{resp_img(site_img(a), t["title"], SIZES_GRID, high=eager, lazy=not eager)}{dur(a, lang)}{ovl(a, lang)}</div>'
            f'<div class="body"><h2>{esc(card_title(a, lang))}</h2><p>{esc(t["description"])}</p>'
            f'<span class="meta">{when(a, lang)}</span></div></a>')


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
    return (f'<a class="mini" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="th">{resp_img(site_img(a), t["title"], SIZES_CARD)}{dur(a, lang)}{ovl(a, lang)}</div>'
            f'<div><h3>{esc(card_title(a, lang))}</h3><p class="mdesc">{esc(t["description"])}</p><span class="meta">{when(a, lang)}</span></div></a>')


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
        filed = FILING.get(a["slug"])
        if filed:
            a["layer"] = filed["layer"]
            a["topic"] = filed["topic"]
            if filed.get("card"):
                a["card"] = filed["card"]
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
    path = ROOT / "content" / "shorts.json"
    if not path.exists():
        return
    for sh in json.loads(path.read_text(encoding="utf-8")):
        slug, vid = sh.get("slug"), sh.get("id")
        if slug and vid and slug not in SHORTS:
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


def product_boxes(a, lang):
    """Optional affiliate box. Articles opt in with a products list. Prices are never shown."""
    products = a.get("products") or []
    if not isinstance(products, list):
        return ""
    L = LANGS[lang]
    blocks = []
    for product in products:
        if not isinstance(product, dict):
            continue
        name = str(_loc(product.get("name"), lang)).strip()
        href = str(_loc(product.get("url"), lang)).strip()
        if not name or not href.startswith("https://"):
            continue
        specs = _loc(product.get("specs"), lang)
        if isinstance(specs, str):
            specs = [specs]
        if not isinstance(specs, list):
            specs = []
        specs = [str(item).strip() for item in specs if str(item).strip()][:6]
        button = str(_loc(product.get("button"), lang)).strip() or L["aff_btn"]
        image = str(product.get("image") or "").strip()
        img = ""
        if image.startswith("/img/") and ".." not in image:
            img = f'<img src="{esc(image)}" alt="{esc(name)}" width="640" height="480" loading="lazy" decoding="async">'
        lis = "".join(f"<li>{esc(item)}</li>" for item in specs)
        ul = f"<ul>{lis}</ul>" if lis else ""
        blocks.append(
            f'<aside class="pbox"><div class="pbox-in">{img}<div><h3>{esc(name)}</h3>{ul}'
            f'<a class="btn" href="{esc(with_amazon_tag(href, lang))}" rel="sponsored nofollow noopener" target="_blank">{esc(button)}</a>'
            f'<p class="affnote">{esc(L["aff"])}</p></div></div></aside>')
    return "".join(blocks)


AFFILIATE = {}
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
    "@media (max-width:600.98px){.sheet-main article.money .handy{margin-left:14px;margin-right:14px}"
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
    return "https://www.amazon.nl/s?" + urlencode({"k": query, "tag": tag})


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
            '<a href="https://www.amazon.nl/privacy" rel="nofollow noopener" target="_blank">'
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
        '<a href="https://www.amazon.nl/privacy" rel="nofollow noopener" target="_blank">Amazon.nl privacy notice</a>. '
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
        f'{ml_noscript(lang)}{ML_BAR_JS}</aside>'
    )


def rail_signup(lang, script=False):
    """Rail block that posts with the same handler as the article bar.
    CSS hides it while the rail stacks under the story."""
    L = LANGS[lang]
    fid = f"nlside-email-{lang}"
    note = (f'<p class="nlnote">{esc(L["bar_fine"])} '
            f'<a href="{url(lang, "privacy/")}">{esc(L["privacy"])}</a>.</p>')
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
            {"key": "starship", "href": "starship/", "en": "Starship tracker", "nl": "Starship-tracker"},
            {"key": "falcons", "href": "falcons/", "en": "Falcons", "nl": "Falcons"},
        ],
    },
    {
        "key": "starlink", "tone": "link", "href": "starlink/",
        "label": {"en": "Starlink", "nl": "Starlink"},
        "plain": True,
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


def crumbs(lang, parts):
    """Structured breadcrumb only. The visible trail is not rendered."""
    chain = [(LANGS[lang]["home"], "")] + list(parts)
    ld_items = []
    for i, (name, path) in enumerate(chain, 1):
        href = url(lang, path)
        ld_items.append({"@type": "ListItem", "position": i, "name": name, "item": SITE + href})
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


def version_bar(key, lang, populated=None):
    L = LANGS[lang]
    m = MODELS[key]
    root = m.get("parent", key)
    versions = [k for k, v in MODELS.items() if v.get("parent") == root]
    if populated is not None:
        versions = [k for k in versions if k in populated]
    if not versions:
        return ""
    btns = [(root, L["all_versions"])] + [
        (k, MODELS[k]["label"][lang] if isinstance(MODELS[k]["label"], dict) else MODELS[k]["label"])
        for k in versions]
    return '<div class="versions"><span>' + esc(L["your_version"]) + "</span>" + "".join(
        f'<a href="{url(lang, "model/" + k + "/")}"{" class=\"on\"" if k == key else ""}>{esc(lbl)}</a>'
        for k, lbl in btns) + "</div>"


MODEL_ORDER = ["model-s", "model-3", "model-x", "model-y", "cybertruck", "roadster", "semi", "cybercab"]


def models_overview(lang):
    """Grid of the models the site covers. Not an article feed."""
    L = LANGS[lang]
    nav, ld = crumbs(lang, [(L["nav_models"], "category/models/")])
    intro = ({
        "en": "Every Tesla the site covers. Open a model for the facts and the articles about it.",
        "nl": "Elke Tesla die de site volgt. Open een model voor de feiten en de artikelen erover.",
    })[lang]
    cards = []
    for i, key in enumerate(MODEL_ORDER):
        m = MODELS[key]
        ph = model_photo(key) or ""
        # First row is on screen at desktop widths; the first card is the phone LCP image.
        eager = i < 4
        img = ""
        if ph:
            w, h = img_size(ph)
            img = resp_img(ph, "Tesla " + m["name"], SIZES_MODEL, high=(i == 0), lazy=not eager, width=w, height=h)
        cards.append(
            f'<a class="mcard" href="{url(lang, "model/" + key + "/")}">'
            f'<span class="mim">{img}</span><span class="mname">{esc(m["name"])}</span></a>')
    body = (f'{nav}<header class="hubhead"><h1>{esc(L["nav_models"])}</h1>'
            f'<p class="lead">{esc(intro)}</p></header><div class="mgrid">{"".join(cards)}</div>')
    return body, ld, intro


def model_hub(key, items, lang, populated=None):
    """Model page: photo, sourced facts and the articles. Not a news lead."""
    m = MODELS[key]
    L = LANGS[lang]
    inf = INFO.get(key)
    intro = inf[lang]["intro"] if inf and inf.get(lang, {}).get("intro") else L["model_intro"].format(m["name"])
    parts = [(L["nav_models"], "category/models/")]
    parent = m.get("parent")
    if parent:
        parts.append((MODELS[parent]["name"], f"model/{parent}/"))
    parts.append((m["name"], f"model/{key}/"))
    nav, ld = crumbs(lang, parts)
    ph = model_photo(key)
    hero = (f'<figure class="mhero">{resp_img(ph, "Tesla " + m["name"], "(max-width: 900px) 100vw, 820px", high=True, lazy=False, width=1600, height=900)}</figure>'
            if ph else "")
    specs = ""
    rows = (inf or {}).get(lang, {}).get("specs") or []
    if rows:
        label = "Key facts" if lang == "en" else "Kernfeiten"
        body_rows = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows)
        specs = f'<section class="mfacts"><h2>{label}</h2><table class="specs">{body_rows}</table></section>'
    ordered = sorted(items, key=published, reverse=True)
    heading = ("Articles about " if lang == "en" else "Artikelen over ") + m["name"]
    if ordered:
        listing = f'<h2 class="rubh">{esc(heading)}</h2>{hub_cards(ordered, lang)}'
    elif parent:
        back = "Articles about this version are listed with the model." if lang == "en" else "Artikelen over deze uitvoering staan bij het model."
        listing = (f'<p class="hubnote">{esc(back)} <a href="{url(lang, "model/" + parent + "/")}">'
                   f'{esc(MODELS[parent]["name"])}</a>.</p>')
    else:
        listing = f'<p class="empty">{esc(L["empty"])}</p>'
    body = (f'{nav}<header class="hubhead"><h1>Tesla {esc(m["name"])}</h1></header>'
            f'{hero}<p class="mintro">{esc(intro)}</p>{specs}{version_bar(key, lang, populated)}{listing}')
    desc = re.sub(r"\s+", " ", intro).strip()
    if len(desc) > 180:
        desc = desc[:179].rsplit(" ", 1)[0] + "…"
    return body, ld, desc


def video_for(a, lang):
    return VIDEOS.get((a["slug"], lang)) or VIDEOS.get((a["slug"], "en"))


def player(vid, kind, label, poster, priority, title=""):
    w, h = (1200, 630) if kind == "long" else (360, 640)
    sizes = SIZES_HERO if kind == "long" else "(max-width: 800px) 70vw, 280px"
    # The first picture on the page is the LCP image: eager and high priority.
    photo = resp_img(poster, title or label, sizes, high=priority, lazy=not priority, width=w, height=h)
    return (f'<figure class="avid {kind}"><button class="avb" type="button" data-vid="{esc(vid)}" aria-label="{esc(label)}">'
            f'{photo}<span class="shp" aria-hidden="true"></span></button><figcaption>{esc(label)}</figcaption></figure>')


def article_media(a, lang):
    poster = site_img(a)
    video = video_for(a, lang)
    # A long video stands in for the Short on the article. The Short stays on /shorts/.
    short = None if video else SHORTS.get(a["slug"])
    blocks = []
    if video:
        blocks.append(player(video["id"], "long", LANGS[lang]["watch"], poster, True, a[lang]["title"]))
    if short:
        blocks.append(player(short["id"], "short", LANGS[lang]["watch_short"], poster, True, a[lang]["title"]))
    if blocks:
        return "".join(blocks)
    return f'<div class="hi">{resp_img(poster, a[lang]["title"], SIZES_HERO, high=True, lazy=False, cls="hero-img")}</div>'


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
    nav, ld = crumbs(lang, [
        (section, section_href),
        (t["title"], a["slug"] + "/"),
    ])
    toc, body = enrich(a, lang, with_toc=True)
    body = insert_mid(body, ad_html("mid_article", lang))
    chips = ""
    if a.get("models"):
        chips = '<div class="chips">' + "".join(
            f'<a href="{url(lang, "model/" + k + "/")}">Tesla {MODELS[k]["name"]}</a>' for k in a["models"]) + "</div>"
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
        f'<div class="prose">{body}</div>{product_boxes(a, lang)}{handy_box(a, lang)}{ad_html("end", lang)}'
        f'{article_sources(a, lang)}</article>')
    col = f'{nav}{article}{prev_next(a, arts, lang)}{related_block(a, arts, lang)}{ml_bar(lang)}'
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
    """Featured story: photo, headline, excerpt. The full article stays on its own page."""
    L = LANGS[lang]
    t = a[lang]
    section, section_href = topic_meta(a, lang)
    href = url(lang, a["slug"] + "/")
    tag = "h1" if title_tag == "h1" else "h2"
    return (f'<article class="leadstory">'
            f'<p class="meta smeta"><a class="tag" href="{url(lang, section_href)}">{esc(section)}</a>'
            f' · {when(a, lang)} · {read_time(a, lang)} {L["min"]}</p>'
            f'<a class="leadim" href="{href}">'
            f'{resp_img(site_img(a), t["title"], SIZES_LEAD, high=True, lazy=False, width=1600, height=900)}</a>'
            f'<div>'
            f'<{tag} class="ltitle"><a href="{href}">{esc(card_title(a, lang))}</a></{tag}>'
            f'<p class="lead">{esc(t["description"])}</p>'
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


def home_videos(arts, lang, n=8, skip_ids=()):
    """Compact strip of the newest stories that have a long video or a Short. Links to the article."""
    by = {a["slug"]: a for a in arts}
    rows = []
    seen = set()
    banned = set(skip_ids)
    for (slug, vlang), video in VIDEOS.items():
        if vlang not in ("en", lang) or slug not in by or slug in seen or id(by[slug]) in banned:
            continue
        seen.add(slug)
        rows.append((by[slug], video.get("seconds") or 0, False))
    for slug, short in SHORTS.items():
        if slug not in by or slug in seen or id(by[slug]) in banned:
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
        cards.append(
            f'<a class="vcard {tone}" href="{href}"><span class="vim">'
            f'{resp_img(site_img(a), t["title"], SIZES_VIDEO, width=480, height=270)}'
            f'<span class="vpl" aria-hidden="true"></span>'
            f'<span class="dur dvo">{esc(badge)}</span></span>'
            f'<strong>{esc(card_title(a, lang))}</strong></a>')
    return "".join(cards), [a for a, _, _ in rows]


def home_topics(arts, shown, lang):
    L = LANGS[lang]
    out = []
    for _key, label_key, path, keys in HOME_TOPICS:
        pool = [a for a in arts if _in_topics(a, keys)]
        if not pool:
            continue
        fresh = [a for a in pool if id(a) not in shown]
        pick = (fresh + [a for a in pool if id(a) in shown])[:3]
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


def page_side(arts, lang, kind="home", current=None, skip=None, tail="", signup=True):
    """Right column. Sections with nothing to show are left out, and no article is listed twice."""
    L = LANGS[lang]
    C = pv_copy(lang)
    # skip: articles already visible in the main column.
    main_ids = {id(x) for x in (skip or [])}
    if kind == "article" and current is not None:
        main_ids.add(id(current))
    lead_id = id(arts[0]) if arts else None
    start = []
    if kind != "guides":
        # Guides stay in Start here even when the hub column already lists them.
        guides = sorted(
            (x for x in arts if x["category"] == "guides" and x is not current),
            key=lambda x: words(x, "en"), reverse=True)
        start = guides[:6]
    start_ids = {id(x) for x in start}
    # The news list is not the guide list, not the homepage lead, and not the main column.
    show_latest = kind in ("home", "static", "videos", "model", "saved", "hub", "guides", "article", "archive")
    if kind == "hub" and current == "news":
        show_latest = False
    latest = []
    if show_latest:
        ban = set(main_ids) | start_ids
        if lead_id is not None:
            ban.add(lead_id)
        for x in arts:
            if x["category"] == "guides" or id(x) in ban:
                continue
            latest.append(x)
            if len(latest) == 5:
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
            parts.append(_side_section(L["latest"], _side_ul(lang, latest, "latest")))
        if start:
            parts.append(_side_section(C["start"], _side_ol(lang, start)))
    else:
        if latest:
            parts.append(_side_section(L["latest"], _side_ul(lang, latest, "latest")))
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
    if news:
        parts.append(news)
    aside = f'<aside class="pv-side">{"".join(parts)}</aside>' if parts else ""
    if tail and kind == "article":
        if related_html:
            return f'<div class="sheet-rail">{related_html}{aside}</div>{tail}'
        return f"{aside}{tail}"
    return aside


def shell(main, side, extra=""):
    """Same centered content column and sidebar on every page."""
    klass = f"sheet {extra}".strip()
    return f'<div class="{klass}"><div class="sheet-main">{main}</div>{side}</div>'


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
            f'<a class="lcard {tone}" href="{url(lang, pick["slug"] + "/")}">'
            f'<span class="lmeta"><span class="lname">{esc(name)}</span> · {when(pick, lang)}</span>'
            f'<span class="lim">{resp_img(site_img(pick), t["title"], "(max-width: 699px) 46vw, 220px", lazy=False, width=640, height=360)}</span>'
            f'<span class="lbody"><strong>{esc(card_title(pick, lang))}</strong></span></a>')
    label = "Latest from each layer" if lang == "en" else "Het laatste per laag"
    return f'<section class="layerrow" aria-label="{esc(label)}">{"".join(cards)}</section>', shown


def homepage(arts, lang):
    """A card from each ecosystem layer, then the video strip and the rest of the day's list."""
    L = LANGS[lang]
    if not arts:
        return shell(f'<h1>{esc(NAME)}</h1><p class="empty">{L["empty"]}</p>', page_side(arts, lang, "home"))
    row, shown = layer_latest(arts, lang)
    videos, strip_arts = home_videos(arts, lang, 8, skip_ids={id(a) for a in shown})
    strip = f'<div class="vstrip">{videos}</div>' if videos else ""
    used = {id(a) for a in shown} | {id(a) for a in strip_arts}
    feed = [x for x in arts if id(x) not in used][:14]
    main = (f'<h1 class="visually-hidden">{esc(NAME)}</h1>{row}{strip}{pv_feed(feed, lang, thumbs=2)}')
    return shell(main, page_side(arts, lang, "home", skip=[*shown, *strip_arts, *feed]), "front")


def pv_copy(lang):
    en = lang == "en"
    return {
        "all": "All" if en else "Alles",
        "note": "Layout preview. Not indexed. The live site is unchanged." if en else "Voorbeeld van de indeling. Niet geïndexeerd. De live site blijft zoals hij is.",
        "open": "Sample article" if en else "Voorbeeldartikel",
        "live": "Live homepage" if en else "Live homepagina",
        "guides": "Guides" if en else "Gidsen",
        "start": "Start here" if en else "Begin hier",
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
        im = (f'<span class="pv-th">{resp_img(site_img(a), t["title"], "(max-width: 700px) 22vw, 64px", width=256, height=144)}'
              f'{ovl(a, lang)}</span>')
    mins = read_time(a, lang)
    label = f'{mins} {LANGS[lang]["min"]}'
    shown = card_title(a, lang)
    return (f'<a class="pv-row{" hasth" if thumb else ""}" href="{href}" title="{esc(t["title"])}">'
            f'<time datetime="{published(a).isoformat()}">{published(a).strftime("%H:%M")}</time>{im}'
            f'<span class="pv-hl"><b>{esc(shown)}</b></span>'
            f'<span class="pv-min" title="{esc(label)}"><b>{mins}</b><small>min</small></span></a>')


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
        f'{resp_img(site_img(x), "", "72px", width=144, height=81)}<span>{esc(x[lang]["title"])}</span></a>'
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
    c = CATEGORIES[a["category"]]
    return (f'<a class="pv-lead" href="{href}">'
            f'<span class="im">{resp_img(site_img(a), t["title"], SIZES_LEAD, high=True, lazy=False)}{ovl(a, lang)}</span>'
            f'<span><span class="pv-kicker">{esc(c.get("tag", c[lang]))} · {published(a).strftime("%H:%M")}</span>'
            f'<h1>{esc(t["title"])}</h1><p>{esc(t["description"])}</p></span></a>')


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
        main += pv_lead(lead, lang, sample) + pv_feed([x for x in arts if x is not lead][:24], lang, thumbs=4)
    elif variant == "b":
        videos, _strip_arts = home_videos(arts, lang, 8)
        strip = f'<div class="vstrip">{videos}</div>' if videos else ""
        main += home_lead(lead, lang) + strip + pv_feed([x for x in arts if x is not lead][:14], lang, thumbs=2)
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
                f'<a class="pv-lead" href="{url(lang, head["slug"] + "/")}"><span class="im">'
                f'{resp_img(site_img(head), "", SIZES_CARD)}{ovl(head, lang)}</span>'
                f'<span><span class="pv-kicker">{published(head).strftime("%H:%M")}</span>'
                f'<h2>{esc(head[lang]["title"])}</h2></span></a>{rows}</section>')
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
    section, section_href = topic_meta(a, lang)
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
        f'<article class="money"><p class="meta smeta"><a class="tag" href="{url(lang, section_href)}">{esc(section)}</a>'
        f' · <time datetime="{published(a).isoformat()}">{published(a).strftime("%H:%M")}</time>'
        f' · {read_time(a, lang)} {L["min"]}</p>'
        f'<h1>{esc(t["title"])}</h1>'
        f'<p class="byline"><a href="{url(lang, "editorial/")}">{L["byline"]}</a></p>'
        f'<p class="lead">{esc(t["description"])}</p>'
        f'{media}{toc_here}'
        f'<div class="prose">{body}</div>{product_boxes(a, lang)}{handy_box(a, lang)}{ad_html("end", lang)}'
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


def hub_articles(spec, arts):
    """Articles filed under this hub's topics. Keyword matching is not used."""
    topics = set(spec.get("topics") or [])
    if topics:
        out = [a for a in arts if a.get("topic") in topics]
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


def _article_list(items, lang, title, path):
    """Breadcrumb, a hidden page title, then the lead photo and the other articles."""
    nav, ld = crumbs(lang, [(title, path)])
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
    body, ld = _article_list(items, lang, title, spec["path"])
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
    core.style.top = pass.cy + "px";
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
      line.setAttribute("stroke-width", "1.6");
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
            {"en": "Starship tracker", "nl": "Starship-tracker", "href": "starship/"},
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
        "key": "starlink", "path": "starlink/", "tone": "link", "nav": "starlink", "hub": "starlink",
        "kicker": {"en": "4 · Starlink", "nl": "4 · Starlink"},
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
        "key": "spacexsi", "path": "spacexsi/", "tone": "spacexsi", "nav": "spacexsi",
        "kicker": {"en": "5 · SpaceXSI", "nl": "5 · SpaceXSI"},
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
    """How the seven layers hand work to each other. No figures that are not already sourced."""
    if lang == "en":
        title = "How the ecosystem fits together"
        paragraphs = [
            "Elon Musk's companies are separate businesses that share a few loops. This map draws those loops as seven layers. A car, a rocket, a satellite dish and a chatbot belong to different companies, and the work still runs from one layer into the next.",
            "Tesla is the car and robot layer. The cars, the Semi, the Robotaxi service, supervised FSD and the Optimus robot all live here. The fleet's cameras are the pictures FSD and Robotaxi train on. Tesla does not publish how much video that is, so this page does not invent a figure.",
            "Tesla Energy is the power layer beside the cars. Megapacks, the charging network, home chargers and solar sit here. The same Megapacks that store power for the grid are the batteries that can feed a datacenter. In 2025 Tesla booked $430.1 million of business with xAI, mostly Megapacks. That figure is in Tesla's own related-party disclosure, as Electrek reported it on 1 May 2026.",
            "SpaceX is the launch layer. Falcon flies the regular missions. Starship is the larger vehicle, and the Starship tracker follows each flight on its own. SpaceX also puts Starlink's satellites into orbit. Starlink is the connectivity layer: dishes on the ground talk to that constellation, for homes and for businesses. SpaceX's quarterly filing is the public record for how many subscribers and satellites that network has reached.",
            "SpaceXSI is the intelligence layer, formerly xAI and then SpaceXAI. It covers the models, including Grok, the compute that trains them, the datacenters that house that compute, and the chips meant to build more of it. That same intelligence is what Tesla is building into supervised FSD and into Optimus. Nobody has demonstrated AGI, and a model ranking is not a filing.",
            "Neuralink is the brain-computer layer, its own company beside the stack. An implant can move a cursor. Studies aim at speech and at sight. It does not sit inside the car or the rocket.",
            "Boring Co is the tunnel layer, also its own company. It digs car tunnels and runs Loop transit through them, often with Tesla vehicles. The public projects include Vegas, Nashville, Dubai and the tunnel at Gigafactory Texas.",
            "Four things keep handing work to each other: energy, compute, launch and connectivity. Energy feeds compute. Compute feeds the models. A launch puts connectivity in orbit. Connectivity and the models come back down into the cars, the robots and the tunnels.",
        ]
    else:
        title = "Hoe het ecosysteem in elkaar zit"
        paragraphs = [
            "De bedrijven van Elon Musk zijn aparte ondernemingen die een paar lussen delen. Deze kaart tekent die lussen als zeven lagen. Een auto, een raket, een schotel en een chatbot horen bij verschillende bedrijven, en het werk loopt toch van de ene laag naar de volgende.",
            "Tesla is de laag van de auto en de robot. De auto's, de Semi, de robotaxidienst, begeleide FSD en de robot Optimus horen hier. De camera's van de vloot leveren de beelden waarmee FSD en Robotaxi trainen. Tesla publiceert niet hoeveel beeld dat is, dus deze pagina verzint geen getal.",
            "Tesla Energy is de stroomlaag naast de auto's. Megapacks, het laadnetwerk, thuisladers en zonne-energie horen hier. Dezelfde Megapacks die stroom bewaren voor het net zijn de batterijen die een datacenter kunnen voeden. In 2025 boekte Tesla $430,1 miljoen aan zaken met xAI, vooral Megapacks. Dat cijfer staat in Tesla's eigen opgave van transacties met verbonden partijen, zoals Electrek die op 1 mei 2026 weergaf.",
            "SpaceX is de lanceerlaag. Falcon vliegt de gewone missies. Starship is het grotere voertuig, en de Starship-tracker volgt elke vlucht apart. SpaceX brengt ook de satellieten van Starlink in een baan. Starlink is de verbindingslaag: schotels op de grond praten met die constellatie, voor thuis en voor bedrijven. Het kwartaalverslag van SpaceX is het openbare stuk over hoeveel abonnees en satellieten dat netwerk heeft.",
            "SpaceXSI is de intelligentielaag, eerder xAI en daarna SpaceXAI. Het gaat om de modellen, waaronder Grok, de rekenkracht die ze traint, de datacenters waar die rekenkracht staat, en de chips die meer van die rekenkracht moeten bouwen. Diezelfde intelligentie is wat Tesla in begeleide FSD en in Optimus bouwt. Niemand heeft AGI aangetoond, en een modelranglijst is geen filing.",
            "Neuralink is de brein-computerlaag, een eigen bedrijf naast de stapel. Een implantaat kan een cursor bewegen. Studies richten zich op spraak en op zicht. Het zit niet in de auto en niet in de raket.",
            "Boring Co is de tunnellaag, ook een eigen bedrijf. Het graaft autotunnels en laat er Loop-vervoer door rijden, vaak met Tesla-voertuigen. De openbare projecten zijn Vegas, Nashville, Dubai en de tunnel bij Gigafactory Texas.",
            "Vier dingen geven werk aan elkaar door: energie, rekenkracht, lancering en verbinding. Energie voedt rekenkracht. Rekenkracht voedt de modellen. Een lancering zet verbinding in een baan. Verbinding en de modellen komen terug in de auto's, de robots en de tunnels.",
        ]
    body = "".join(f"<p>{esc(p)}</p>" for p in paragraphs)
    return f'<section class="eco-explain"><h2>{esc(title)}</h2>{body}</section>'


def ecosystem_page(lang):
    data = load_data("ecosystem.json")
    L = LANGS[lang]
    title = L["nav_eco"]
    intro = _bi(data["intro"], lang)
    _nav, ld = crumbs(lang, [(title, ecosystem_path(lang))])
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
        f'<h1 class="visually-hidden">{esc(title)}</h1>'
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


def starship_page(lang, arts):
    data = load_data("starship.json")
    L = LANGS[lang]
    flights = sorted(data["flights"], key=lambda f: f["number"])
    latest = flights[-1]
    title = "Starship tracker" if lang == "en" else "Starship-tracker"
    intro = ("Every full-stack Starship flight: the date, the outcome, and whether the booster, the ship and a payload made it. "
             "The page is rendered from a data file, so a new flight is a new row."
             if lang == "en" else
             "Elke volledige Starship-vlucht: de datum, de afloop, en of de booster, het schip en een lading het haalden. "
             "De pagina komt uit een databestand, dus een nieuwe vlucht is een nieuwe rij.")
    nav, ld = crumbs(lang, [(title, "starship/")])
    updated = ("Last updated" if lang == "en" else "Laatst bijgewerkt") + " " + fmt_date(data["updated"], lang) + "."
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
    rel = ""
    if related:
        rel = (f'<h2 class="hubh">{esc(labels[10])}</h2>'
               f'<p class="hubcount">{esc(_count_label(len(related), lang))}.</p>'
               + hub_cards(related, lang))
    body = (
        f'{nav}<header class="hubhead"><h1>{esc(title)}</h1>'
        f'<p class="byline">{esc(L["byline"])}</p>'
        f'<p class="lead">{esc(intro)}</p>'
        f'<p class="hubcount">{esc(updated)} '
        f'<a href="{url(lang, ecosystem_path(lang))}">'
        + ("See the ecosystem map" if lang == "en" else "Zie de kaart van het ecosysteem")
        + "</a></p></header>"
        f'<div class="ss-board">'
        f'<article class="ss-card latest"><p class="k">{esc(labels[0])}</p>'
        f'<h2>{"Flight" if lang == "en" else "Vlucht"} {latest["number"]}</h2>'
        f'<p>{esc(_flight_when(latest, lang))}. {esc(_bi(latest["outcome"], lang))}</p>'
        f'<div class="ss-pills">{pills}</div>{_src_links(latest.get("sources"))}</article>'
        f'<article class="ss-card next"><p class="k">{esc(labels[1])}</p>'
        f'<h2>{next_main}</h2><p>{esc(_bi(nxt.get("note"), lang))}</p>{_src_links(nxt.get("sources"))}</article>'
        f'</div>'
        f'<h2 class="hubh">{esc(labels[3])}</h2>'
        f'<div class="ss-wrap"><table class="ss-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        f'{rel}'
    )
    return body, ld, intro


BRIEF_LAYERS = (
    ("tesla", "tesla/", "tesla", "Tesla"),
    ("energy", "tesla-energy/", "energy", "Tesla Energy"),
    ("spacex", "spacex/", "spacex", "SpaceX"),
    ("starlink", "starlink/", "link", "Starlink"),
    ("spacexsi", "spacexsi/", "spacexsi", "SpaceXSI"),
    ("neuralink", "neuralink/", "neural", "Neuralink"),
    ("boring", "boring/", "boring", "Boring"),
)
PROMISE_STATUS = ("delivered", "late", "pending", "abandoned")
_KV_KEYS = (
    "title_en", "title_nl", "en", "nl", "why_en", "why_nl",
    "name_en", "name_nl", "pros_en", "pros_nl", "cons_en", "cons_nl",
    "url", "image", "button_en", "button_nl",
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


def guide_amazon(href):
    """amazon.nl links carry the Associates tag already stored for the site."""
    tag = affiliate_tag("nl")
    if not href.startswith("https://") or not tag or re.search(r"[?&]tag=", href):
        return href
    host = href.split("/")[2].lower() if href.count("/") >= 2 else ""
    if not host.endswith("amazon.nl"):
        return href
    sep = "&" if "?" in href else "?"
    return f"{href}{sep}tag={quote(tag, safe='')}"


def disclosure_line(lang):
    href = url(lang, disclosure_path(lang))
    if lang == "en":
        text = ("Affiliate disclosure: if you buy through a link on this page, TrendingTesla may earn a commission, "
                "at no extra cost to you.")
        more = "How this works"
    else:
        text = ("Affiliate-melding: koop je via een link op deze pagina, dan kan TrendingTesla een commissie ontvangen. "
                "Voor jou kost het niets extra.")
        more = "Zo werkt dat"
    return f'<p class="afftop">{esc(text)} <a href="{href}">{esc(more)}</a>.</p>'


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
    pros = _bits(fields.get(f"pros_{lang}") or fields.get("pros_en"))
    cons = _bits(fields.get(f"cons_{lang}") or fields.get("cons_en"))
    image = str(fields.get("image") or "")
    img = ""
    klass = "gbox noimg"
    if image.startswith("/img/") and ".." not in image:
        klass = "gbox"
        img = f'<img src="{esc(image)}" alt="" width="640" height="480" loading="lazy" decoding="async">'
    plus = "Pros" if lang == "en" else "Pluspunten"
    minus = "Cons" if lang == "en" else "Minpunten"
    lists = ""
    if pros:
        lists += f'<h3>{plus}</h3><ul>{"".join(f"<li>{esc(item)}</li>" for item in pros)}</ul>'
    if cons:
        lists += f'<h3>{minus}</h3><ul>{"".join(f"<li>{esc(item)}</li>" for item in cons)}</ul>'
    href = guide_amazon(str(fields.get("url") or ""))
    button = fields.get(f"button_{lang}") or fields.get("button_en") or (
        "View on Amazon" if lang == "en" else "Bekijk bij Amazon")
    link = ""
    if href.startswith("https://"):
        link = (f'<a class="btn" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">'
                f'{esc(button)}</a>')
    return f'<aside class="{klass}">{img}<div><h2>{esc(name)}</h2>{lists}{link}</div></aside>'


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
    chunks = [disclosure_line(lang), banner]
    for kind, fields in doc["pieces"]:
        if kind == "product":
            chunks.append(_guide_product(fields, lang))
        elif kind == "compare":
            chunks.append(_guide_table(fields, lang))
        else:
            text = fields.get(lang) or fields.get("en") or ""
            if text:
                chunks.append(f"<p>{esc(text)}</p>")
    body = (f'<article class="narrow"><h1>{esc(title)}</h1><div class="prose">{"".join(chunks)}</div></article>')
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
        f'<article class="narrow"><h1>{esc(title)}</h1>{disclosure_line(lang)}'
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
            "<p>Some pages link to Amazon.nl. If you buy through one of those links, TrendingTesla may earn "
            "a commission. You do not pay extra. The link is marked as sponsored.</p>"
            "<p>A commission never changes what we write. We do not publish a guide in order to sell a product, "
            "and a product box does not appear until a guide is published.</p>"
            f'<p>Questions go through the <a href="{contact}">contact form</a>.</p>')
    else:
        title = "Affiliate-melding"
        desc = "Wanneer TrendingTesla een commissie kan ontvangen via een link."
        html_body = (
            "<p>Sommige pagina's linken naar Amazon.nl. Koop je via zo'n link, dan kan TrendingTesla een "
            "commissie ontvangen. Jij betaalt niets extra. De link is gemarkeerd als gesponsord.</p>"
            "<p>Een commissie verandert nooit wat we schrijven. We publiceren geen gids om een product te verkopen, "
            "en een productvak verschijnt pas als er een gids is.</p>"
            f'<p>Vragen gaan via het <a href="{contact}">contactformulier</a>.</p>')
    return (
        f'<article class="narrow"><h1>{esc(title)}</h1><div class="prose">{html_body}</div></article>'), title, desc


def build():
    load_money()
    load_affiliate()
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
    guide_docs = load_guides()
    promise_rows = load_promises()

    for lang in LANGS:
        L = LANGS[lang]

        # ---------- Home ----------
        body = homepage(arts, lang)
        site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "alternateName": ["Trending Tesla", "trendingtesla.com"],
                   "url": SITE + url(lang), "inLanguage": lang,
                   "publisher": {"@type": "Organization", "name": NAME, "url": SITE,
                                 "logo": {"@type": "ImageObject", "url": SITE + "/favicon-512.png", "width": 512, "height": 512},
                                 "sameAs": ["https://www.youtube.com/@TrendingTesla"]}}
        write(url(lang), page(lang, "", NAME, L["home_desc"], body,
                              extra_head=f'<script type="application/ld+json">{json.dumps(site_ld, ensure_ascii=False)}</script>'))

        # ---------- Category pages ----------
        for key, c in CATEGORIES.items():
            if key in REDIRECT_CATS:
                continue
            if key == "models":
                content, crumb_ld, intro = models_overview(lang)
                listed = [{
                    "@type": "ListItem", "position": i + 1,
                    "name": "Tesla " + MODELS[k]["name"],
                    "url": SITE + url(lang, f"model/{k}/"),
                } for i, k in enumerate(MODEL_ORDER)]
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
        populated = {k for k, mv in MODELS.items() if mv.get("parent") and any(k in a.get("models", []) for a in arts)}
        for key, m in MODELS.items():
            if m.get("parent"):
                items = [a for a in arts if key in a.get("models", [])]
            else:
                family = {key} | {k for k, v in MODELS.items() if v.get("parent") == key}
                items = [a for a in arts if family & set(a.get("models", []))]
            ph = model_photo(key)
            content, crumb_ld, desc = model_hub(key, items, lang, populated)
            facts = (INFO.get(key) or {}).get(lang, {}).get("specs") or []
            vehicle_ld = {
                "@context": "https://schema.org", "@type": "Vehicle",
                "name": f"Tesla {m['name']}", "description": desc,
                "url": SITE + url(lang, f"model/{key}/"), "inLanguage": lang,
                "brand": {"@type": "Brand", "name": "Tesla"},
                "manufacturer": {"@type": "Organization", "name": "Tesla, Inc."},
                "publisher": {"@type": "Organization", "name": NAME, "url": SITE},
            }
            if ph:
                vehicle_ld["image"] = SITE + ph
            if facts:
                vehicle_ld["additionalProperty"] = [
                    {"@type": "PropertyValue", "name": k, "value": v} for k, v in facts]
            write(url(lang, f"model/{key}/"),
                  page(lang, f"model/{key}/", f"Tesla {m['name']}", desc,
                       shell(content, page_side(arts, lang, "model", key, skip=items)),
                       extra_head=ld_script(crumb_ld) + ld_script(vehicle_ld), image=ph, active="models"))

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
        ship_body, ship_ld, ship_desc = starship_page(lang, arts)
        ship_items = hub_articles({"topics": ["starship"]}, arts)
        write(url(lang, "starship/"), page(
            lang, "starship/", "Starship tracker" if lang == "en" else "Starship-tracker", ship_desc,
            shell(ship_body, page_side(arts, lang, "hub", "starship", skip=ship_items)),
            extra_head=ld_script(ship_ld), active="starship"))

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
                              "logo": {"@type": "ImageObject", "url": SITE + "/favicon-512.png", "width": 512, "height": 512}},
                "author": {"@type": "Organization", "name": NAME, "url": SITE},
            }
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
            body = shell(pv_article("b", a, arts, lang, live=True),
                          page_side(arts, lang, "article", a, tail=ml_bar(lang))) + nl_sticky(lang)
            _, crumb_ld = crumbs(lang, [
                (c.get("tag", c[lang]), f"category/{a['category']}/"),
                (t["title"], a["slug"] + "/"),
            ])
            head = ld_script(ld) + ld_script(crumb_ld)
            write(url(lang, a["slug"] + "/"),
                  page(lang, a["slug"] + "/", t["title"], t["description"], body, "article", head,
                       image=social_img(a, lang), active=a["category"]))

        idx = [{"u": url(lang, x["slug"] + "/"), "t": x[lang]["title"], "d": x[lang]["description"],
                "c": CATEGORIES[x["category"]].get("tag", CATEGORIES[x["category"]][lang]), "dt": fmt_date(x["date"], lang), "ts": published(x).isoformat(), "i": site_img(x)} for x in arts]
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
                    + ("".join(gcard(a, lang).replace('<a class="card"', '<a class="card xtra"', 1)
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
                                         shell(body, page_side(arts, lang, "saved"))).replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1))

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
            cap = (f'<a class="sht" href="{url(lang, a["slug"] + "/")}">{esc(t)}</a>' if a else f'<span class="sht">{esc(t)}</span>')
            tone = layer_tone(a) if a else ""
            cards += (f'<div class="shc {tone}"><button class="shv" type="button" data-id="{esc(sh["id"])}" aria-label="{"Play" if en else "Afspelen"}: {esc(t)}">'
                      f'<img src="https://i.ytimg.com/vi/{esc(sh["id"])}/hqdefault.jpg" alt="{esc(t)}" loading="lazy" width="480" height="360">'
                      f'<span class="shp" aria-hidden="true"></span></button>{cap}'
                      f'<span class="meta"><time class="ago" datetime="{esc(dt)}">{fmt_date(dt[:10], lang)}</time></span></div>')
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
            shell(g_body, page_side(arts, lang, "static")),
            active="buyguides", alt_path=guides_path(other(lang))))
        for doc in guide_docs:
            body, title, desc = guide_body(doc, lang)
            gpath = guides_path(lang) + doc["slug"] + "/"
            write(url(lang, gpath), page(
                lang, gpath, title, desc,
                shell(body, page_side(arts, lang, "static")),
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

    # Sitemap
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = ([("", today)] + [(a["slug"] + "/", a.get("updated", a["date"])[:10]) for a in arts]
               + [(f"category/{k}/", today) for k in CATEGORIES if k not in REDIRECT_CATS]
               + [(f"model/{k}/", today) for k in MODELS]
               + [(k + "/", today) for k in PAGES]
               + [("shorts/", today)]
               + [(h["path"], today) for h in HUBS]
               + [(layer["path"], today) for layer in LAYERS if layer["path"] not in {h["path"] for h in HUBS}]
               + [("starship/", today)]
               + [("archive/" if i == 0 else f"archive/{i + 1}/", today) for i in range(ARCH_PAGES[0])])
    def emit(loc_lang, loc_path, mod, en_path, nl_path):
        paths = {"en": en_path, "nl": nl_path}
        alts = "".join(
            f'<xhtml:link rel="alternate" hreflang="{l}" href="{SITE + url(l, paths[l])}"/>' for l in LANGS)
        alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE + url("en", en_path)}"/>'
        return f"<url><loc>{SITE + url(loc_lang, loc_path)}</loc><lastmod>{mod}</lastmod>{alts}</url>"

    urls = ""
    for path, mod in entries:
        for lang in LANGS:
            urls += emit(lang, path, mod, path, path)
    for lang in LANGS:
        urls += emit(lang, signup_path(lang), today, signup_path("en"), signup_path("nl"))
        urls += emit(lang, ecosystem_path(lang), today, ecosystem_path("en"), ecosystem_path("nl"))
        urls += emit(lang, "briefing/", today, "briefing/", "briefing/")
        for doc in briefing_docs:
            if doc["template"]:
                continue
            slug = f"briefing/{doc['slug']}/"
            urls += emit(lang, slug, (doc["meta"].get("date") or today)[:10], slug, slug)
        urls += emit(lang, promises_path(lang), today, promises_path("en"), promises_path("nl"))
        urls += emit(lang, guides_path(lang), today, guides_path("en"), guides_path("nl"))
        for doc in guide_docs:
            if doc["template"]:
                continue
            urls += emit(
                lang, guides_path(lang) + doc["slug"] + "/", today,
                guides_path("en") + doc["slug"] + "/", guides_path("nl") + doc["slug"] + "/")
        urls += emit(lang, disclosure_path(lang), today, disclosure_path("en"), disclosure_path("nl"))
        urls += emit(lang, advertise_path(lang), today, advertise_path("en"), advertise_path("nl"))
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
          f"{urls}</urlset>")
    # Google News sitemap: articles from the last 2 days
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
    write("/robots.txt", f"User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {SITE}/sitemap.xml\nSitemap: {SITE}/news-sitemap.xml\n")
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
    print(f"Built {len(arts)} article(s) in {len(LANGS)} languages -> {OUT}")


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
