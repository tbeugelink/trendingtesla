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
  "also": ["optimus"],                             # optional: extra categories where the article also appears
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
:root{--bg:#04060a;--surface:#212121;--surface2:#272727;--border:#272727;--border2:#3f3f3f;--fg:#e8eef5;--head:#fff;--muted:#b9c4d2;--dim:#8f9db0;--red:#e22822;--red2:#b81e19;--blue:#00d4ff;--edge:#3a4a60;--blue2:#5fe3ff;--max:1920px;color-scheme:dark}
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
.grid2>.card{display:grid;grid-template-columns:254px 1fr;gap:11px;align-items:start}.grid2>.card .body{padding:0;line-height:1}.grid2>.card .body .tag,.grid2>.card .body .meta{line-height:1;vertical-align:top}.grid2>.card h3{font-size:1.12rem;line-height:1.3;margin:8px 0 6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.grid2>.card p{-webkit-line-clamp:1;line-height:1.42}.grid2>.card .im{height:142px;width:254px}.grid2>.card .im img{height:100%;aspect-ratio:auto}
.grid2 .card{padding:8px;margin:-8px;border-radius:10px;transition:background .15s}.grid2>.card{align-content:start}
.grid2 .card:hover{background:#272727}.below{margin-top:17px}.below>.tip{margin-top:0}.grid2.gall.wide{grid-template-columns:repeat(auto-fill,minmax(max(250px,calc((100% - 72px) / 7 + 1px)),1fr));gap:22px 12px;margin-top:14px}.wide .empty{grid-column:1/-1}.grid2.gall{grid-template-columns:repeat(3,minmax(0,1fr));gap:18px 12px}.gall>.card{grid-template-columns:1fr;gap:0}.gall>.card .im{width:auto;height:auto}.gall>.card .im img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}.gall>.card .body{padding:8px 0 0;line-height:1.3}.gall>.card h3{font-size:.92rem;margin:0 0 5px;-webkit-line-clamp:2}.gall>.card p{font-size:.8rem;line-height:1.35;-webkit-line-clamp:1;margin-bottom:5px}.gall>.card .meta{font-size:.74rem}
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
@media (max-width:699.98px){.bar{gap:4px}.bar .burger{margin-left:-11px}.bar .brand{transform:none;margin-left:3px}.bar .logo{font-size:1.15rem}}@media (min-width:601px) and (max-width:699.98px){.drawer,.scrim{top:66px}}@media (min-width:700px){.drawer,.scrim,.bar .burger{display:none}}
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
.savedlink i{position:absolute;top:3px;right:2px;min-width:14px;height:14px;border-radius:10px;background:var(--red);color:#fff;font:800 .58rem/14px Manrope,sans-serif;font-style:normal;text-align:center;padding:0 3px}
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
.drawer button.di{width:100%;border:0;background:transparent;font:inherit;font-weight:700;font-size:.92rem;text-align:left;cursor:pointer}
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
.sideh{font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:var(--blue);margin:11px 0 -2px;padding-top:9px;border-top:1px solid var(--border2)}
.hi,.th,.im{position:relative}.hi{margin:0 0 8px}.hi .hero-img{margin:0}
.dur{display:inline-flex;align-items:center;gap:4px;position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.8);color:#fff;font-size:.74rem;font-weight:700;line-height:1;padding:4px 6px;border-radius:10px;cursor:help}.agotip{position:fixed;z-index:60;pointer-events:none;background:rgba(0,0,0,.88);color:#fff;font-size:.74rem;font-weight:700;line-height:1;padding:5px 7px;border-radius:10px;white-space:nowrap}time.ago{cursor:help}.im,.th,.hi{container-type:inline-size}.kk{position:absolute;left:2.6cqw;bottom:2.6cqw;z-index:2;pointer-events:none;font-family:Inter,Manrope,system-ui,sans-serif;font-weight:900;letter-spacing:-.01em;text-transform:uppercase;line-height:1}.kk b{display:table;font-weight:900;white-space:nowrap}.kk b+b{margin-top:.1em}.kk i{font-style:normal;display:inline-block}.kk .yo{color:#ffd400;text-shadow:-.16cqw -.16cqw 0 #d61a1a,.16cqw -.16cqw 0 #d61a1a,-.16cqw .16cqw 0 #d61a1a,.16cqw .16cqw 0 #d61a1a,0 .2cqw 0 #d61a1a,0 -.2cqw 0 #d61a1a,.2cqw 0 0 #d61a1a,-.2cqw 0 0 #d61a1a,0 .5cqw 1.2cqw rgba(0,0,0,.45)}.kk .bk i{background:#d61a1a;color:#fff;padding:.13em .24em .12em;box-shadow:0 .4cqw 1.2cqw rgba(0,0,0,.35)}.kk.p-bw .bk i,.kk.p-by .bk i{background:#1d5cff}.kk.p-gy .bk i{background:#12a150}.kk.p-yk .bk i{background:#ffd400;color:#111}.kk.p-gy .yo{color:#ffd400;text-shadow:0.16cqw 0.16cqw 0 #0b6b34,-0.16cqw 0.16cqw 0 #0b6b34,0.16cqw -0.16cqw 0 #0b6b34,-0.16cqw -0.16cqw 0 #0b6b34,0cqw 0.2cqw 0 #0b6b34,0cqw -0.2cqw 0 #0b6b34,0.2cqw 0cqw 0 #0b6b34,-0.2cqw 0cqw 0 #0b6b34,0 .5cqw 1.4cqw rgba(0,0,0,.5)}.kk.p-wb .bk i{background:#fff;color:#1d5cff}.kk.p-bw .yo{color:#fff;text-shadow:0.16cqw 0.16cqw 0 #0b2f8f,-0.16cqw 0.16cqw 0 #0b2f8f,0.16cqw -0.16cqw 0 #0b2f8f,-0.16cqw -0.16cqw 0 #0b2f8f,0 .2cqw 0 #0b2f8f,0 -.2cqw 0 #0b2f8f,.2cqw 0 0 #0b2f8f,-.2cqw 0 0 #0b2f8f,0 .5cqw 1.4cqw rgba(0,0,0,.6)}.kk.p-wb .yo{color:#3d7bff;text-shadow:0.16cqw 0.16cqw 0 #fff,-0.16cqw 0.16cqw 0 #fff,0.16cqw -0.16cqw 0 #fff,-0.16cqw -0.16cqw 0 #fff,0 .2cqw 0 #fff,0 -.2cqw 0 #fff,.2cqw 0 0 #fff,-.2cqw 0 0 #fff,0 .5cqw 1.4cqw rgba(0,0,0,.5)}.kk.p-by .yo{color:#ffd400;text-shadow:0.16cqw 0.16cqw 0 #0b2f8f,-0.16cqw 0.16cqw 0 #0b2f8f,0.16cqw -0.16cqw 0 #0b2f8f,-0.16cqw -0.16cqw 0 #0b2f8f,0 .2cqw 0 #0b2f8f,0 -.2cqw 0 #0b2f8f,.2cqw 0 0 #0b2f8f,-.2cqw 0 0 #0b2f8f,0 .5cqw 1.4cqw rgba(0,0,0,.5)}.kk .nb{font-size:1.32em}.kk .bk .nb{font-size:1.22em}.kk .l1{font-size:6.4cqw}.kk .l2{font-size:8cqw}.th .dur{right:6px;bottom:6px;font-size:.68rem;padding:3px 5px}.th .dur svg{width:12px;height:12px}
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
.card h3{font-size:1.08rem;line-height:1.3;margin:6px 0 6px}.card h3{font-weight:700;color:#ebebeb}.grid2>.card h3{font-size:1rem}.mini h3{font-weight:700;font-size:.9rem;color:#ebebeb}.mini h3{margin-top:0}.meta>time.ago::before{content:'';display:inline-block;width:.62em;height:.72em;margin-right:.42em;vertical-align:-.04em;background:currentColor;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 12'%3E%3Cpath d='M1.2 1.2v9.6L9 6z' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 12'%3E%3Cpath d='M1.2 1.2v9.6L9 6z' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E") center/contain no-repeat}.smeta time.ago::before{content:none}.mini .mdesc{margin-bottom:0}.mini .meta{display:block;margin-top:3px;line-height:1.3}@media (min-width:905px){.rside .mini>div:not(.th){padding-top:0;contain:size;overflow:visible}.rside .mini h3{margin-top:0;line-height:1.22}.rside .mini .mdesc{line-height:1.25}.rside .mini .meta{margin-top:2px}}.mdesc{color:var(--muted);font-size:.8rem;line-height:1.35;margin:0 0 4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.mini .meta{font-size:.74rem}
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
article .lead{font-size:1.02rem;line-height:1.38;color:var(--muted);margin:0 0 22px}
article .hero-img{border-radius:10px;margin:0 0 26px;aspect-ratio:1200/630;width:100%;object-fit:cover;border:1px solid var(--edge)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:-8px 0 24px}
.chips a{font-size:.78rem;font-weight:700;color:var(--muted);text-decoration:none;border:1px solid var(--border2);border-radius:10px;padding:3px 10px}
.chips a:hover{color:var(--head);border-color:var(--head)}
.prose h2{font-size:1.15rem;line-height:1.3;letter-spacing:-.015em;margin:26px 0 10px}
article .prose{font-size:15px}article .prose,article .lead{max-width:860px}article .prose p,article .prose ul,article .prose ol{margin-right:14px}article .prose h2{clear:right}.beside{display:flow-root;margin-bottom:22px}.beside>:last-child{margin-bottom:0}.beside+*{clear:left}article .prose p,article .prose ul,article .prose ol{margin-left:14px}article .prose ul{list-style:none;padding-left:0}article .prose ul>li{position:relative;padding-left:15px}article .prose ul>li::before{content:"";position:absolute;left:0;top:.68em;width:6px;height:6px;border-radius:50%;background:var(--blue)}article .prose ol{padding-left:18px}article .prose h2{border-left:3px solid var(--blue);padding-left:11px;scroll-margin-top:84px}.toc{float:left;width:max-content;max-width:44%;margin:4px 22px 12px 14px;padding:12px 16px;border:1px solid var(--border2);border-radius:10px;background:rgba(255,255,255,.03)}.toc b{display:block;font-size:.7rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--blue);margin-bottom:8px}.toc ol{margin:0;padding-left:20px;font-size:.88rem;line-height:1.5}.toc li{margin:3px 0}.toc li::marker,article .prose .toc li::marker{color:var(--dim)}.toc a,.prose .toc a{color:var(--fg);text-decoration:none}article .prose .toc ol{margin:0;padding-left:20px}.toc a:hover{color:var(--blue)}.pblock{display:flex;gap:20px;align-items:flex-start;margin-bottom:22px}.ptxt{flex:1;min-width:0}.ptxt>:last-child{margin-bottom:0}.pimg{flex:none;width:33%;margin:5px 0 0}.pimg img{width:100%;height:100%;aspect-ratio:3/4;object-fit:cover;object-position:center;border-radius:10px;border:1px solid var(--edge);display:block}html{scroll-behavior:smooth}article .prose{line-height:1.5}.prose p,.prose ul,.prose ol{margin-bottom:22px}
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
.sources li{margin-bottom:4px}@media(min-width:400px){article .prose>p{text-align:justify;-webkit-hyphens:auto;hyphens:auto;hyphenate-limit-chars:7 3 3}}article .sources{padding-bottom:20px;border-bottom:1px solid var(--border2)}@media(min-width:601px){.tip{padding-top:37px;padding-bottom:37px}}
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
@media (max-width:1000.98px){.grid{grid-template-columns:repeat(2,1fr);gap:48px 40px}.leadside{grid-column:span 2;flex-direction:row}.leadside .card{flex:1}.tops{grid-template-columns:1fr}.arch{grid-template-columns:minmax(0,1fr);gap:36px}.why{grid-template-columns:repeat(2,1fr)}.models{grid-template-columns:repeat(4,1fr);gap:20px}}
@media (max-width:860.98px){.search{display:none}.sbtn{display:grid}.sopen .search{display:flex;position:absolute;left:16px;right:16px;top:12px;max-width:none;z-index:41}.sopen .search input{background:#121212}html.hass .bar .search{display:flex;position:relative;left:auto;right:auto;top:auto}html.hass .bar .sbtn{display:none}html.hass .bar .savedlink{margin-left:auto}html.hass .bar .search{margin-right:0;flex-shrink:0}html.hass .bar .brand{flex-shrink:0}html.hass .bar .savedlink{transform:none}.tip{flex-wrap:wrap;gap:14px 20px}.tip .btn{margin-left:0}}
@media (max-width:860.98px){footer .fgrid{grid-template-columns:1fr 1fr;gap:28px}footer .fbrand{grid-column:1/-1}}
@media (max-width:600.98px){.wrap{padding:0 12px}
.bar{gap:4px;height:56px}.drawer,.scrim{top:56px}.burger{margin-left:-14px}.logo{font-size:1.15rem}.brand{margin-left:2px}
.sbtn{margin-left:auto;width:36px;height:36px;border:0;background:transparent}.savedlink{margin-left:-2px;width:34px;height:34px}.lang{margin-left:0;margin-right:-10px;font-size:.7rem;padding:3px 9px}
.read .hi{margin:0 -12px 6px}.read .hi .hero-img{border-radius:0;border:0}.hi .dur{right:12px}
article .st{font-size:1rem;line-height:1.25}.srow{flex-wrap:nowrap;gap:8px}.srow .acts{display:flex;gap:6px}.srow .smeta{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}.toc{float:none;width:auto;max-width:none;margin:0 0 0 14px}footer .fgrid{grid-template-columns:1fr;gap:24px}footer .fgrid>*{min-width:0}footer a{overflow-wrap:anywhere}.act{padding:7px 10px 6px}article .lead{font-size:.95rem}.smeta{font-size:.82rem}
article .prose{font-size:15px}article .prose h2{font-size:.98rem}.grid2{grid-template-columns:1fr;gap:59px}.grid2.gall{grid-template-columns:1fr;gap:40px}.gall>.card h3{font-size:1rem}.gall>.card p{font-size:.9rem}.side{gap:29px}.grid2>.card{grid-template-columns:1fr;gap:0}.grid2>.card .im{height:auto;width:auto}.grid2>.card .im img{aspect-ratio:1200/630}.grid2>.card .body{padding:7px 0 0}.card.lead{grid-column:auto}.leadside{grid-column:auto;flex-direction:column;gap:40px}.leadside .card p{display:-webkit-box}.mini{grid-template-columns:1fr;gap:6px;height:auto}.mini>div{height:auto}.th{width:100%;height:auto}.mini img{width:100%;height:auto;aspect-ratio:1200/630}#news .h2{margin-top:16px}.grid{grid-template-columns:1fr;gap:40px}.why{grid-template-columns:1fr 1fr;gap:10px}.why div{padding:14px}.why p{font-size:.8rem}
 .models{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;margin:0 -24px;padding:0 24px 4px}.models::-webkit-scrollbar{display:none}.models{gap:14px}.model{flex:0 0 46%;scroll-snap-align:start}
 body{font-size:16.5px}.h2{margin-top:20px}.hero{min-height:0}.hero .in{padding:26px 20px}.hero .btn{flex:1;white-space:nowrap;padding:11px 12px}
 .phead{flex-direction:column-reverse;align-items:flex-start}.phead img{width:100%}}

/* wider than the page (e.g. zoomed far out): framed page, black outside */
@media (min-width:1946px){html{background:#000}body{max-width:1944px;margin:0 auto;border-left:1px solid #2e2e2e;border-right:1px solid #2e2e2e;box-shadow:0 0 0 1px #000,0 0 60px rgba(255,255,255,.04)}}

.gall>.xtra{display:none}.gall>.xtra.on{display:grid}

/* header controls: same border colour as the photos */
.bar .search input,.bar .search>button,.bar .tdd .tdb,.bar .tdd .tdl,.bar .lang,.sbtn{border-color:#3a4a60}
"""


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
{topicdd(lang, active)}
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


def enrich(a, lang):
    """Article body extras: anchors + table of contents from the subheadings, and a second photo halfway."""
    body = a[lang]["body"]
    heads = []

    def anchor(m):
        heads.append(re.sub(r"<[^>]+>", "", m.group(1)))
        return f'<h2 id="s{len(heads)}">{m.group(1)}</h2>'
    body = re.sub(r"<h2>(.*?)</h2>", anchor, body)
    toc = ""  # TOC box and mid-article photo removed on request (2026-10-23)
    return toc, body


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
    toc, body = enrich(a, lang)
    return (f'<article>'
            f'<div class="hi"><img class="hero-img" src="{site_img(a)}" alt="{esc(t["title"])}" width="1200" height="630" fetchpriority="high">{dur(a, lang)}{ovl(a, lang)}</div>'
            f'<{tag} class="st">{title}</{tag}>'
            f'<div class="srow"><p class="meta smeta"><a class="tag" href="{url(lang, "category/" + a["category"] + "/")}">{c.get("tag", c[lang])}</a> · {when(a, lang)}</p>'
            f'<div class="acts"><button class="act like" type="button" data-like="{a["slug"]}" aria-pressed="false" title="{L["like"]}">{HEART_SVG}<span>0</span></button>'
            f'<button class="act save" type="button" data-save="{a["slug"]}" aria-pressed="false" title="{L["save"]}" aria-label="{L["save"]}">{BOOK_SVG}</button></div></div>'
            f'<p class="lead">{esc(t["description"])}</p>{toc}'
            f'<div class="prose">{body}</div>{src}</article>')


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
    if no_left:
        # home / news: newest news on the right, the same news continues as a grid under the tip bar
        right_items, left_items = list(rest), list(rest)[:MAX_HOME_GRID + XTRA]
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
    if no_left and len(rest) > MAX_HOME_GRID:
        L = LANGS[lang]
        more_link = (f'<nav class="pager"><span></span><span>{L["page"]} 1 / {1 + -(-(len(rest) + 1 - MAX_HOME_GRID) // PER_PAGE)}</span>'
                     f'<a href="{url(lang, "archive/2/")}">{L["older"]} ›</a></nav>')
    side_more = (f'<a class="morelink moredn" href="#meer">{LANGS[lang]["d_more"]} <span aria-hidden="true">↓</span></a>' if rubh
                 else f'<a class="morelink" href="{url(lang, "archive/")}">{LANGS[lang]["archive"]} →</a>')
    return (f'<section class="read home{" topic" if topic else ""}"><div class="lcol">{lead_html}</div>'
            f'<aside class="rside">{extra_side}'
            + ("" if active == "models" and not article else f'<h2 class="sr">{side_title}</h2><div class="side">{side}</div>'
               + side_more)
            + '</aside></section>'
            f'<section class="below">{tl[0]}{rubh}{grid}{more_link}</section>')


JS = r"""(function(){function f(){var t=document.querySelector('header.top');if(t)t.classList.toggle('solid',scrollY>0||document.documentElement.classList.contains('dopen'))}addEventListener('scroll',f,{passive:true});document.addEventListener('DOMContentLoaded',f);f()})();(function(){var Q='main h1,main h2,main h3,main p,main li,main tr,main .card,main .gcard,main .mini,main .im,main .hi',K='tt-lswap';try{if('scrollRestoration' in history)history.scrollRestoration='manual'}catch(e){}document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a.lang');if(!a)return;var R=innerHeight*.33,els=document.querySelectorAll(Q),i=-1,off=0;for(var k=0;k<els.length;k++){var r=els[k].getBoundingClientRect();if(r.height>0&&r.top<=R&&r.bottom>R){i=k;off=(R-r.top)/r.height}}var H=document.documentElement.scrollHeight-innerHeight;try{sessionStorage.setItem(K,JSON.stringify({i:i,o:off,r:H>0?scrollY/H:0,y:scrollY,n:els.length,p:location.pathname,t:Date.now()}))}catch(x){}},true);function go(){var d;try{d=JSON.parse(sessionStorage.getItem(K)||'null')}catch(x){}if(!d||Date.now()-d.t>15000||d.p==location.pathname)return;var els=document.querySelectorAll(Q);if(d.i>=0&&els.length==d.n&&els[d.i]){var r=els[d.i].getBoundingClientRect();scrollTo(0,r.top+scrollY+d.o*r.height-innerHeight*.33)}else if(d.y<10){scrollTo(0,0)}else{scrollTo(0,d.r*(document.documentElement.scrollHeight-innerHeight))}}document.addEventListener('DOMContentLoaded',go);addEventListener('load',function(){go();setTimeout(function(){go();try{sessionStorage.removeItem(K)}catch(x){}},350)})})();function ttKK(){var M={a:[6.6,10.5],c:[8,6.2],n:[10,5.8],r:[7.4,7.4]};document.querySelectorAll('.kk').forEach(function(k){var p=k.parentElement,W=p.clientWidth;if(!W)return;var d=p.querySelector('.dur'),A=(d?d.offsetLeft:W)-k.offsetLeft-.026*W,t=(k.className.match(/t-(\w)/)||[])[1]||'a',m=M[t]||M.a,f=[];[].forEach.call(k.children,function(b,i){var s=(k.children.length==1?m[1]:m[i])*W/100;b.style.fontSize=s+'px';for(var j=0;j<3;j++){var w=b.getBoundingClientRect().width;if(w>A){s*=A/w*.995;b.style.fontSize=s+'px'}}f.push(s)});if(f.length==2){if(t=='a'){var w0=k.children[0].getBoundingClientRect().width,w1=k.children[1].getBoundingClientRect().width;if(w1>w0*1.04){var g=Math.max(f[1]*w0/w1,f[0]*1.18);if(g<f[1]){f[1]=g;k.children[1].style.fontSize=g+'px'}}if(f[0]>f[1]*.85)k.children[0].style.fontSize=f[1]*.85+'px'}if(t=='c'&&f[1]>f[0]*.9)k.children[1].style.fontSize=f[0]*.9+'px';if(t=='n'&&f[1]>f[0]*.62)k.children[1].style.fontSize=f[0]*.62+'px'}})}addEventListener('load',ttKK);function ttRow(){document.querySelectorAll('.gall').forEach(function(g){var x=g.querySelectorAll(':scope>.xtra');if(!x.length)return;x.forEach(function(e){e.classList.remove('on')});var c=getComputedStyle(g).gridTemplateColumns.split(' ').length,n=g.children.length-x.length,need=(c-n%c)%c;for(var i=0;i<need&&i<x.length;i++)x[i].classList.add('on')})}ttRow();addEventListener('resize',ttRow);document.addEventListener('DOMContentLoaded',ttRow);addEventListener('resize',ttKK);if(document.fonts)document.fonts.ready.then(ttKK);document.addEventListener('DOMContentLoaded',ttKK);function mq(n){return matchMedia('(min-width:'+n+'px)').matches}function ttAgo(){var nl=document.documentElement.lang=='nl';document.querySelectorAll('time.ago').forEach(function(t){var h=(Date.now()-Date.parse(t.dateTime))/36e5;if(!(h>=0))return;if(!t.dataset.d)t.dataset.d=t.textContent;var d=h/24,n,k;if(h<48){n=Math.max(1,Math.floor(h));k=0}else if(d<7){n=Math.floor(d);k=1}else if(d<30.44){n=Math.floor(d/7);k=2}else if(d<365.25){n=Math.floor(d/30.44);k=3}else{n=Math.floor(d/365.25);k=4}var one=n==1,L=nl?[['uur','uur'],['dag','dagen'],['week','weken'],['maand','maanden'],['jaar','jaar']]:[['hour','hours'],['day','days'],['week','weeks'],['month','months'],['year','years']],S=nl?['uur','dgn','wkn','mnd','jr']:['h','d','wk','mo','yr'],end=nl?' geleden':' ago';t.textContent=n+' '+L[k][one?0:1]+end;var m=t.closest('.smeta');if(m&&m.scrollWidth>m.clientWidth+1)t.textContent=n+(nl?' ':'')+(nl&&one&&k==1?'dag':S[k])+end})}ttAgo();setInterval(ttAgo,60000);function ttSearch(){var s=document.querySelector('.bar .search'),h=document.documentElement;if(!s)return;document.querySelector('.bar .lang').style.height='';h.classList.remove('hasdd');document.querySelector('.bar .savedlink').style.marginLeft='';var bar=s.parentNode,br=bar.querySelector('.brand')||bar.querySelector('.logo'),sv=bar.querySelector('.savedlink');var m=!mq(601)?12:28,L=br.getBoundingClientRect().right+m,R=sv.getBoundingClientRect().left-14,l=document.querySelector('.read .lcol');if(l&&mq(700))R=Math.min(R,l.getBoundingClientRect().right);else if(!l&&mq(905)){var b=bar.getBoundingClientRect();R=Math.min(R,b.left+(b.width-13)*1.7/2.7)}s.style.marginLeft=m+'px';h.classList.add('hass');s.style.width='200px';var w=R-s.getBoundingClientRect().left;if(w>=200){s.style.width=w+'px';s.style.setProperty('--k',Math.min(1,w/520).toFixed(3))}else{h.classList.remove('hass');s.style.width=''}}function ttDD(){var d=document.querySelector('.bar .tdd'),s=document.querySelector('.bar .search'),h=document.documentElement;if(!d)return;h.classList.remove('hasdd','ddend');if(!mq(700)||!h.classList.contains('hass'))return;var bn=d.parentNode,bar=bn.getBoundingClientRect(),L,R,rs=document.querySelector('.read .rside'),ph=rs&&[].slice.call(rs.querySelectorAll('.mini .th img')).filter(function(x){return x.offsetParent})[0];if(ph){var q=ph.getBoundingClientRect();L=q.left;R=q.right}else{var W=bar.width,rw=mq(905)?(W-13)/2.7:(W-13)/3.68;L=bar.right-rw;R=mq(905)?L+(rw-26)*2/3+7:bar.right}var end=!mq(905),sv=document.querySelector('.bar .savedlink'),lg=document.querySelector('.bar .lang');if(!end){var a=sv.getBoundingClientRect(),c=lg.getBoundingClientRect();R=Math.min(R,bar.right-(c.right-a.left)-28)}R=Math.min(R,bar.right);if(R-L<140)return;h.classList.add('hasdd');if(end)h.classList.add('ddend');d.dataset.l=L;d.style.width=(R-L)+'px';function al(){d.style.marginLeft='0px';for(var i=0;i<2;i++)d.style.marginLeft=(parseFloat(d.style.marginLeft)+L-d.getBoundingClientRect().left)+'px'}if(end){for(var k=0;k<2;k++){var gap=L-14-lg.getBoundingClientRect().right;s.style.width=Math.max(160,s.getBoundingClientRect().width+gap)+'px';d.style.marginLeft='14px'}}al();var ov=bn.scrollWidth-bn.clientWidth;if(ov>0){d.style.width=(R-L-ov)+'px';al()}d.querySelector('.tdb').style.height=s.getBoundingClientRect().height+'px'}function ttCenter(){var h=document.documentElement,s=document.querySelector('.bar .search');if(!s||!h.classList.contains('hass'))return;var d=document.querySelector('.bar .tdd'),dd=h.classList.contains('hasdd'),end=h.classList.contains('ddend'),sv=document.querySelector('.bar .savedlink'),br=document.querySelector('.bar .brand');for(var i=0;i<3;i++){if(!dd&&i==0)s.style.width='120px';var bl=br.getBoundingClientRect().right,lg=document.querySelector('.bar .lang').getBoundingClientRect(),lc=document.querySelector('.read .lcol'),wide=dd&&!end,rn=end?(+d.dataset.l)-14-(lg.right-sv.getBoundingClientRect().left):wide?(lc?lc.getBoundingClientRect().right:(+d.dataset.l)-13):sv.getBoundingClientRect().left,G=Math.max(10,Math.min(24,(rn-bl-160)/2)),off=Math.min(10,G-6),w=Math.max(160,wide?rn-bl-G-off:rn-bl-2*G);s.style.width=w+'px';s.style.setProperty('--k',Math.min(1,w/520).toFixed(3));s.style.marginLeft=(parseFloat(getComputedStyle(s).marginLeft)+bl+G+off-s.getBoundingClientRect().left)+'px';if(end)sv.style.marginLeft=(parseFloat(getComputedStyle(sv).marginLeft)+s.getBoundingClientRect().right+G-off-sv.getBoundingClientRect().left)+'px';if(dd)d.style.marginLeft=(parseFloat(getComputedStyle(d).marginLeft)+(+d.dataset.l)-d.getBoundingClientRect().left)+'px'}var lgb=document.querySelector('.bar .lang');lgb.style.height=s.getBoundingClientRect().height+'px';if(d){var sb=s.querySelector('button');d.style.setProperty('--bw',sb.getBoundingClientRect().width+'px');d.querySelector('.tdb').style.height=s.getBoundingClientRect().height+'px'}}addEventListener('resize',function(){ttSearch();ttDD();ttCenter()});document.addEventListener('DOMContentLoaded',function(){var d=document.querySelector('.bar .tdd');if(!d)return;var b=d.querySelector('.tdb'),l=d.querySelector('.tdl');function set(o){l.hidden=!o;b.setAttribute('aria-expanded',o)}b.addEventListener('click',function(e){e.stopPropagation();set(l.hidden)});document.addEventListener('click',function(e){if(!d.contains(e.target))set(false)});document.addEventListener('keydown',function(e){if(e.key=='Escape')set(false)})});document.addEventListener('DOMContentLoaded',function(){ttSearch();ttDD();ttCenter();if(window.ResizeObserver){var rq=0,lw=0;new ResizeObserver(function(e){var w=e[0].contentRect.width;if(Math.abs(w-lw)<0.5)return;lw=w;cancelAnimationFrame(rq);rq=requestAnimationFrame(function(){ttSearch();ttDD();ttCenter()})}).observe(document.querySelector('.bar'))}if(document.fonts)document.fonts.ready.then(function(){ttSearch();ttDD();ttCenter()})});addEventListener('load',function(){ttSearch();ttDD();ttCenter()});addEventListener('resize',ttAgo);(function(){var tip=document.createElement('div');tip.className='agotip';document.addEventListener('mouseover',function(ev){var t=ev.target.closest&&ev.target.closest('time.ago');if(!t||!t.dataset.d){tip.remove();return}tip.textContent=t.dataset.d;document.body.appendChild(tip);var r=t.getBoundingClientRect();tip.style.left=Math.max(4,Math.min(innerWidth-tip.offsetWidth-4,r.left+r.width/2-tip.offsetWidth/2))+'px';tip.style.top=(r.bottom+6)+'px'});addEventListener('scroll',function(){tip.remove()},{passive:true})})();(function(){function fit(){var t=document.querySelector('.prose .toc'),b=document.querySelector('.beside');if(t&&b&&getComputedStyle(t).float!='none'){var n;while(b.offsetHeight<t.offsetHeight-8&&(n=b.nextElementSibling)&&!n.classList.contains('pblock')&&!(n.tagName=='H2'&&n.nextElementSibling&&n.nextElementSibling.classList.contains('pblock'))){b.appendChild(n);if(n.tagName=='H2'&&(n=b.nextElementSibling)&&!n.classList.contains('pblock'))b.appendChild(n)}}document.querySelectorAll('.pblock').forEach(function(k){var x=k.querySelector('.ptxt'),f=k.querySelector('.pimg'),W=k.offsetWidth,mx=W*(!mq(601)?.36:.45),w;for(var i=0;i<6;i++){w=Math.min(mx,x.offsetHeight*.75);f.style.width=w+'px'}f.style.height=Math.max(x.offsetHeight-5,w*4/3)+'px';f.querySelector('img').style.aspectRatio='auto'})}addEventListener('load',fit);addEventListener('resize',fit);var d=document.documentElement,o=document.querySelector('.scrim');
function t(x){var was=d.classList.contains('dopen'),B=document.body;if(x&&!was){var y=scrollY;B.dataset.y=y;B.style.top=-y+'px'}d.classList.toggle('dopen',x);if(!x&&was){var y2=+B.dataset.y||0;B.style.top='';scrollTo({top:y2,behavior:'instant'})}document.querySelectorAll('.burger').forEach(function(b){b.setAttribute('aria-expanded',x)})}
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
sl.innerHTML=keep.filter(function(k){return m[k]}).map(function(k){var a=m[k];return '<a class="card" href="'+a.u+'"><div class="im"><img src="'+a.i+'" alt=""></div><div class="body"><h3>'+e(a.t)+'</h3><p>'+e(a.d)+'</p><span class="meta">'+'<time class="ago" datetime="'+a.ts+'">'+e(a.dt)+'</time></span></div></a>'}).join('');ttAgo()})}}window.addEventListener('resize',bal);bal();
})();"""


def label(a, lang):
    return f'<span class="tag">{CATEGORIES[a["category"]].get("tag", CATEGORIES[a["category"]][lang])}</span>'


def card(a, lang, lead=False):
    t = a[lang]
    cls = "card lead" if lead else "card"
    return (f'<a class="{cls}" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="im"><img src="{site_img(a)}" alt="" width="1200" height="630" loading="lazy" decoding="async">{dur(a, lang)}{ovl(a, lang)}</div>'
            f'<div class="body">{label(a, lang)} <span class="meta">· {when(a, lang)}</span>'
            f'<h3>{esc(t["title"])}</h3><p>{esc(t["description"])}</p></div></a>')


def gcard(a, lang):
    """Topic list under the lead: photo on top, then title, summary and date."""
    t = a[lang]
    return (f'<a class="card" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="im"><img src="{site_img(a)}" alt="" width="1200" height="630" loading="lazy" decoding="async">{dur(a, lang)}{ovl(a, lang)}</div>'
            f'<div class="body"><h3>{esc(t["title"])}</h3><p>{esc(t["description"])}</p>'
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
    secs = max(10, round(len(html.unescape(re.sub(r"<[^>]+>", " ", a[lang]["body"])).split()) / 220 * 60))
    lbl = {"en": "Reading time", "nl": "Leestijd"}[lang]
    return (f'<span class="dur" title="{lbl}" aria-label="{lbl}: {-(-secs // 60)} min">'
            f'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<path d="M2 4h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7z"/></svg>'
            f'{-(-secs // 60)} min</span>')


def mini(a, lang):
    t = a[lang]
    return (f'<a class="mini" href="{url(lang, a["slug"] + "/")}">'
            f'<div class="th"><img src="{site_img(a)}" alt="" width="1200" height="630" loading="lazy" decoding="async">{dur(a, lang)}{ovl(a, lang)}</div>'
            f'<div><h3>{esc(t["title"])}</h3><p class="mdesc">{esc(t["description"])}</p><span class="meta">{when(a, lang)}</span></div></a>')


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

    for lang in LANGS:
        L = LANGS[lang]

        # ---------- Home ----------
        body = f'<h1 class="sr">{NAME} — {L["tagline"]}</h1>'
        if news:
            top = news[0]
            body += feed(top, story(top, lang, "h2"), [a for a in arts if a is not top], lang, "news", L["latest"], no_left=True)
        else:
            body += section(L["latest"], f'<p class="empty">{L["empty"]}</p>', anchor="news")
        write(url(lang), page(lang, "", NAME, L["tagline"], body))
        home_body = body

        # ---------- Category pages ----------
        for key, c in CATEGORIES.items():
            items = arts if key == "news" else [a for a in arts if a["category"] == key or key in a.get("also", []) or (key == "ecosystem" and a["category"] in ECO)]
            if key == "news":
                items = news
            intro = L["eco_intro"] if key in ECO else L["cat_intro"].format(c[lang])
            head = f'<h1 class="sr">{c[lang]}</h1>'
            content = home_body.split("</h1>", 1)[1] if key == "news" else listing(items, lang, key)
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
            same = sorted((x for x in arts if (x["category"] == a["category"] or a["category"] in x.get("also", [])) and x is not a), key=published, reverse=True)
            others = [x for x in arts if x is not a]
            body = feed(a, story(a, lang), others, lang, a["category"], L["latest"], left_exact=same, left_pad=pad_grid(a, same), article=True)
            write(url(lang, a["slug"] + "/"),
                  page(lang, a["slug"] + "/", t["title"], t["description"], body, "article", head,
                       image=social_img(a, lang), active=a["category"]))

        idx = [{"u": url(lang, x["slug"] + "/"), "t": x[lang]["title"], "d": x[lang]["description"],
                "c": CATEGORIES[x["category"]].get("tag", CATEGORIES[x["category"]][lang]), "dt": fmt_date(x["date"], lang), "ts": published(x).isoformat(), "i": site_img(x)} for x in arts]
        (OUT / f"search-{lang}.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        # ---------- Archive: all articles, newest first, paginated ----------
        # page 1 is the news grid on the home page (MAX_HOME_GRID articles after the lead); archive/2/ continues from there
        rest_arch = arts[1 + MAX_HOME_GRID:]
        pages = 1 + max(1, -(-len(rest_arch) // PER_PAGE))
        for pi in range(pages):
            chunk = arts[:1 + MAX_HOME_GRID] if pi == 0 else rest_arch[(pi - 1) * PER_PAGE:pi * PER_PAGE]
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
