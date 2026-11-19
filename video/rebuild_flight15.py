"""Rebuild the Flight 15 long video on the existing narration. No new speech.

Picture is Starship, Super Heavy, the tower, or a diagram. No Falcon 9.
"""
import json
import subprocess
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CLIPS = Path("/tmp/starship-clips")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H, FPS = 1920, 1080, 30
CYAN = (0, 212, 255)
BG = (8, 14, 22)
MUTED = (186, 204, 214)

# Each entry is one shot. dur is seconds. Clips are named files in CLIPS.
# A file is used at most twice. Diagrams are unique.
SHOTS = [
    (8, "clip", "ift5-launch-catch.webm", 1.0, "right",
     "Flight 5 stack beside the Starbase tower, before liftoff. Not Flight 15.",
     "SpaceX caught Starship after 22 hours."),
    (8, "diagram", "claim", None, None,
     "Diagram. The 22-hour figure is SpaceX's Flight 15 timeline.",
     "The ship left Friday and was back on Saturday."),
    (8, "clip", "ift5-aerostat.webm", 0.5, "center",
     "Flight 5, 13 Oct 2024. Full Starship stack lifting off beside the tower. CBP aerial camera.",
     "Those arms had never closed on a ship from orbit."),
    (8, "diagram", "twist", None, None,
     "Diagram. Flight 15's booster did not come back to the tower.",
     "The booster did not come home."),
    (8, "diagram", "wait", None, None,
     "Diagram. The ship coasted for most of a day.",
     "The ship stayed up. The reason comes later."),
    (9, "diagram", "flightid", None, None,
     "Diagram. Flight 15, Pad 2, Starbase.",
     "This was Flight 15, from Pad 2 at Starbase."),
    (9, "diagram", "clock", None, None,
     "Diagram. Catch marked at 22:32:34.",
     "SpaceX puts the catch at 22 hours, 32 minutes, 34 seconds."),
    (9, "diagram", "names", None, None,
     "Diagram. Serial numbers are from the press, not the SpaceX page.",
     "The press calls them Ship 42 and Booster 22."),
    (9, "diagram", "parts", None, None,
     "Diagram. The four parts of this film.",
     "The minutes. The wait. The arms. What it changes."),
    (8, "diagram", "maxq", None, None,
     "Diagram. Liftoff, then Max Q at 58 seconds.",
     "Liftoff is zero. Max Q is 58 seconds."),
    (8, "clip", "ift1-nasa.webm", 112.0, "center",
     "Starship IFT-1, 20 Apr 2023, NASA WB-57. The full stack climbing on its engines. Not Flight 15.",
     "Most of the booster's 33 engines are still burning."),
    (8, "diagram", "engines", None, None,
     "Diagram of 33 Raptor engines. Not a photograph.",
     "Thirty-three Raptors. Then the ship lights six of its own."),
    (8, "clip", "ift5-aerostat.webm", 38.0, "center",
     "Flight 5 ascent, the stack still together, engines lit. Second use of the CBP aerial clip.",
     "That is hot-staging. The ship is on its own path."),
    (8, "diagram", "hotstage", None, None,
     "Diagram. Hot-staging: ship engines on, stages separate.",
     "Two seconds after engine cutoff, the stages separate."),
    (8, "diagram", "boostback", None, None,
     "Diagram. Boostback: 32 of 33 engines, ended early.",
     "The boostback burn ends early. Low fuel mass."),
    (8, "diagram", "investigate", None, None,
     "Diagram. SpaceX says the root cause is still open.",
     "The root cause is still under investigation."),
    (8, "clip", "ift5-booster-cc0.webm", 22.0, "left",
     "Flight 5 Super Heavy on its landing burn, engines down, still in the sky. Not a catch, and not Flight 15.",
     "The booster flies a landing burn over the Gulf."),
    (8, "diagram", "abort", None, None,
     "Diagram. Guidance abort, offshore, then flight termination.",
     "It aborts the catch and is lost offshore."),
    (8, "diagram", "timeline", None, None,
     "Diagram. The 6:35 catch line is the plan, not the result.",
     "The timeline still says catch. The report says it did not."),
    (8, "diagram", "shipgoes", None, None,
     "Diagram. The ship's ascent is nominal.",
     "The ship continues. SpaceX calls the ascent nominal."),
    (8, "diagram", "insert", None, None,
     "Diagram. One Raptor, about 20 seconds, into orbit.",
     "One engine burns for about 20 seconds and the ship is in orbit."),
    (9, "diagram", "sats", None, None,
     "Diagram. 26 Starlink V3 satellites leave the ship.",
     "Twenty-six Starlink satellites leave. Contact is made with every one."),
    (9, "diagram", "orbits", None, None,
     "Diagram. A long coast. Spaceflight Now counts 14 orbits.",
     "Then a long coast. The catch is still many hours away."),
    (9, "diagram", "checks", None, None,
     "Diagram. Return checks near Hawaii, Chile, then Hawaii again.",
     "Hawaii. Chile. Hawaii again. Earlier ways down are not used."),
    (9, "diagram", "monitor", None, None,
     "Diagram. More than 20 hours of monitoring, not a reported failure.",
     "SpaceX says the team watched the ship for more than 20 hours."),
    (9, "diagram", "deorbit", None, None,
     "Diagram. Deorbit burn, about 10 seconds.",
     "One sea-level engine fires for about 10 seconds."),
    (9, "diagram", "entry", None, None,
     "Diagram. Entry, then transonic, then subsonic.",
     "Entry. Then transonic. Then subsonic, in under a minute."),
    (8, "diagram", "step", None, None,
     "Diagram. Landing burn: three engines, then two, then one.",
     "Three engines, then two, then one."),
    (9, "diagram", "arms", None, None,
     "Diagram of a ship between tower arms. Not a Flight 15 webcast frame.",
     "The arms close. SpaceX says that was the first time for the ship."),
    (8, "diagram", "nosea", None, None,
     "Diagram. Engines and arms. No parachute. No splashdown of the ship.",
     "No parachute. The ship does not splash down."),
    (8, "clip", "ift5-booster-cc0.webm", 36.0, "center",
     "Flight 5 Super Heavy returning to the tower on its engines. An earlier booster catch, not Flight 15's ship.",
     "Super Heavy had already been caught on three earlier flights."),
    (8, "clip", "ift5-launch-catch.webm", 49.0, "right",
     "Flight 5, from the ground: the booster back at the tower on a landing burn. Second use of this file.",
     "The new event is the ship, coming back from orbit."),
    (9, "diagram", "falcon", None, None,
     "Diagram. Falcon 9 keeps its booster and loses the upper stage. No Falcon 9 picture.",
     "Falcon 9 brings the booster home and throws the upper stage away."),
    (9, "diagram", "notmars", None, None,
     "Diagram. Not a Moon landing and not a Mars landing.",
     "This is not a date, and it is not a landing on Mars."),
    (9, "diagram", "callback", None, None,
     "Diagram. The claim and the twist, side by side.",
     "The ship came home. The booster did not."),
    (8, "diagram", "close", None, None,
     "Diagram. Catch real. Double catch not.",
     "The catch was real. The double catch was not."),
]


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(text, width=46):
    return textwrap.wrap(text, width=width)[:2]


def draw_base():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 8], fill=CYAN)
    return im, d


def label(d, text):
    f = font(FONT, 22)
    d.text((64, 36), text, font=f, fill=CYAN)


def draw_card(d, kicker, headlines, subs):
    """One diagram: a short kicker, a headline, a line of support. Not a title card."""
    label(d, kicker)
    y = 200
    for line in headlines:
        d.text((64, y), line, font=font(FONTB, 58), fill=(255, 255, 255))
        y += 78
    y += 24
    d.rectangle([64, y, 280, y + 6], fill=CYAN)
    y += 36
    for line in subs:
        d.text((64, y), line, font=font(FONT, 32), fill=MUTED)
        y += 50


# Sentence diagrams. Drawn diagrams (engines, arms, hot-staging) stay in diagram().
CARDS = {
    "claim": ("FLIGHT 15", ["Friday out.", "Saturday back."],
              ["22 hours, 32 minutes, 34 seconds.", "SpaceX's own timeline."]),
    "twist": ("THE OTHER HALF", ["The booster", "did not come home."],
              ["The return burn ended early.", "The catch was aborted."]),
    "abort": ("OFFSHORE", ["Catch aborted.", "Booster lost."],
              ["Engines cut off while it hovered.", "Then the flight termination system."]),
    "wait": ("MOST OF A DAY", ["The ship stayed up."],
             ["Earlier ways down were not taken.", "Why it waited comes later."]),
    "flightid": ("FLIGHT 15", ["Pad 2, Starbase."],
                 ["Texas. Friday liftoff.", "No host. No sponsor."]),
    "clock": ("22:32:34", ["After liftoff."],
              ["Also written as 22 and a half hours.", "That is the 22 hours in the title."]),
    "when": ("TWO CLOCKS", ["Friday, 4:47 p.m.", "Saturday, 3:20 p.m."],
             ["Texas time, as the press reports it.", "Space.com gives the same catch time."]),
    "names": ("THE NAMES", ["Ship 42.", "Booster 22."],
              ["Spaceflight Now and Space.com.", "SpaceX's flight page does not print them."]),
    "record": ("THE RECORD", ["Burns. Satellites.", "An abort. A catch."],
               ["What follows is that record,", "in four parts."]),
    "parts": ("FOUR PARTS", ["The minutes.", "The wait.", "The arms.", "What changes."], []),
    "maxq": ("THE MINUTES", ["Liftoff is zero."],
             ["Max Q at 58 seconds.", "Most booster engines off at 2:19."]),
    "notower": ("NOT THIS TOWER", ["The booster does not", "come back."],
                ["Guidance sends it offshore.", "The plan was the tower. The flight was not."]),
    "gulf": ("THE GULF", ["It ends at sea."],
             ["Spaceflight Now: an explosion.", "The commentator: it was not in the right place."]),
    "fault": ("THE FAULT", ["Not the guidance system."],
              ["SpaceX's stated cause is the early", "shutdown, from low fuel mass."]),
    "plan": ("THE 6:35 LINE", ["The table still says catch."],
             ["It is marked approximate.", "It is the plan, not the result."]),
    "contradict": ("READ IT IN ORDER", ["The report says aborted."],
                   ["Calling 6:35 a catch would", "contradict SpaceX's own account."]),
    "shipgoes": ("THE SHIP", ["Ascent: nominal."],
                 ["Engine cutoff at 8:09.", "Then a short coast of its own."]),
    "deploy": ("PAYLOAD", ["About 43 minutes."],
               ["Deploy starts at 35 minutes.", "It is marked done at 1 hour 18."]),
    "gap": ("STILL HOURS AWAY", ["The satellites are done."],
            ["The catch is not.", "14 orbits is the press count, not the timeline."]),
    "ballistic": ("TWO RETURNS", ["The booster never", "reached orbit."],
                  ["It was still on a path toward the Gulf.", "The ship does not get that option."]),
    "orbitroad": ("IN ORBIT", ["Not a road", "you turn around on."],
                  ["Leaving it takes a planned burn,", "at a planned place."]),
    "hold": ("LEFT UNUSED", ["Hawaii. Chile. Hawaii."],
             ["Splashdowns there were possible.", "Spaceflight Now: they were not used."]),
    "breakorbit": ("TEN SECONDS", ["That burn breaks the orbit."],
                   ["One sea-level Raptor.", "Then about half an hour of falling."]),
    "entrytimes": ("THE AIR", ["Transonic, then subsonic."],
                   ["Less than a minute between them.", "The landing burn is two minutes later."]),
    "burnstart": ("22:32:16", ["Landing burn starts."],
                  ["Two minutes after it goes subsonic.", "Eighteen seconds from here to the arms."]),
    "watched": ("NOT A DELAY", ["The ship was watched."],
                ["Not weather. Not a reported failure.", "The earlier options stayed unused."]),
    "decision": ("THE DECISION", ["The deorbit burn", "points it at Texas."],
                 ["From that burn to the arms: under an hour.", "The rest of the 22 hours was the coast."]),
    "splash": ("ALREADY LOST", ["This booster splashed."],
               ["It did not survive.", "That was hours before the ship arrived."]),
    "delivery": ("A DELIVERY", ["Contact with every satellite."],
                 ["They were raising their orbits.", "That stands even if the catch had failed."]),
    "otherclaim": ("THE OTHER CLAIM", ["The catch is separate."],
                   ["The satellites were already away", "before the ship was committed."]),
    "inspect": ("IN PRINCIPLE", ["No second flight reported."],
                ["This booster was not recovered.", "The claim is the size of one ship."]),
    "notboth": ("NOT BOTH", ["Not a catch of both stages."],
                ["The 6-minute line is the plan.", "The flight did not fly that plan."]),
    "rate": ("NO DATE", ["A ship that can come back."],
             ["No Moon landing in this flight.", "No Mars landing either."]),
    "ending": ("THE SHIP'S ENDING", ["Twenty hours of watching."],
               ["The unused earlier returns.", "Then a 10-second deorbit burn."]),
    "sources": ("THE SOURCES", ["The numbers are SpaceX's."],
                ["Read the article", "on trendingtesla.com."]),
}


def diagram(kind):
    im, d = draw_base()
    title = font(FONTB, 48)
    body = font(FONT, 32)
    small = font(FONT, 26)
    if kind in CARDS:
        draw_card(d, *CARDS[kind])
        return im
    label(d, "DIAGRAM")
    if kind == "claim":
        d.text((64, 160), "22 h  32 min  34 s", font=font(FONTB, 72), fill=(255, 255, 255))
        d.text((64, 270), "Flight 15  ·  ship catch", font=title, fill=CYAN)
        d.text((64, 380), "SpaceX timeline, marked approximate.", font=body, fill=MUTED)
        d.rounded_rectangle([64, 520, 1600, 548], radius=8, fill=(24, 44, 58))
        d.rounded_rectangle([64, 520, 1500, 548], radius=8, fill=CYAN)
    elif kind == "twist":
        d.text((64, 180), "Booster", font=title, fill=(255, 120, 110))
        d.text((64, 250), "Catch aborted. Lost offshore.", font=body, fill=MUTED)
        d.line([(200, 700), (900, 420), (1500, 760)], fill=(255, 120, 110), width=6)
        d.ellipse([1476, 736, 1524, 784], outline=(255, 120, 110), width=6)
    elif kind == "wait":
        d.text((64, 180), "Most of a day in orbit", font=title, fill=(255, 255, 255))
        d.text((64, 270), "The reason for the wait comes later.", font=body, fill=MUTED)
        d.ellipse([760, 420, 1160, 820], outline=CYAN, width=4)
        d.ellipse([900, 560, 1020, 680], fill=(30, 90, 140))
    elif kind == "flightid":
        d.text((64, 180), "Flight 15", font=font(FONTB, 80), fill=(255, 255, 255))
        d.text((64, 300), "Pad 2  ·  Starbase, Texas", font=title, fill=CYAN)
        d.text((64, 400), "Friday 13 November liftoff.", font=body, fill=MUTED)
        d.text((64, 460), "Saturday 14 November return.", font=body, fill=MUTED)
    elif kind == "clock":
        d.text((64, 200), "22 : 32 : 34", font=font(FONTB, 92), fill=CYAN)
        d.text((64, 340), "after liftoff, on SpaceX's timeline", font=body, fill=MUTED)
        d.text((64, 420), "The page also says 22 and a half hours.", font=body, fill=MUTED)
    elif kind == "names":
        d.text((64, 180), "Ship 42    Booster 22", font=title, fill=(255, 255, 255))
        d.text((64, 280), "Those serials are in Spaceflight Now and Space.com.", font=body, fill=MUTED)
        d.text((64, 340), "SpaceX's own flight page does not print them.", font=body, fill=MUTED)
    elif kind == "parts":
        items = ["1   The minutes", "2   The wait", "3   The arms", "4   What changes"]
        y = 200
        for item in items:
            d.text((80, y), item, font=title, fill=(255, 255, 255))
            y += 140
    elif kind == "maxq":
        d.text((64, 180), "0:00   liftoff", font=title, fill=(255, 255, 255))
        d.text((64, 280), "0:58   Max Q", font=title, fill=CYAN)
        d.text((64, 380), "2:19   most booster engines off", font=body, fill=MUTED)
        d.text((64, 450), "Times are approximate.", font=small, fill=MUTED)
    elif kind == "engines":
        d.text((64, 80), "33 sea-level Raptors", font=title, fill=(255, 255, 255))
        cols, rows = 7, 5
        for i in range(33):
            r, c = divmod(i, cols)
            x = 620 + c * 90
            y = 240 + r * 90
            if r == 4 and c > 4:
                continue
            d.ellipse([x, y, x + 48, y + 48], outline=CYAN, width=3)
        d.text((64, 860), "The ship then lights six of its own.", font=body, fill=MUTED)
    elif kind == "hotstage":
        d.text((64, 160), "Hot-staging", font=title, fill=CYAN)
        d.rectangle([860, 280, 1060, 520], outline=(230, 230, 230), width=4)
        d.rectangle([900, 540, 1020, 860], outline=CYAN, width=4)
        d.text((1120, 360), "ship  ·  6 engines", font=body, fill=(255, 255, 255))
        d.text((1120, 660), "booster turns back", font=body, fill=CYAN)
    elif kind == "boostback":
        d.text((64, 180), "Boostback", font=title, fill=(255, 255, 255))
        d.text((64, 280), "32 of 33 planned engines relight.", font=body, fill=MUTED)
        d.text((64, 350), "Shutdown at 3:02. That is early.", font=body, fill=(255, 180, 120))
    elif kind == "investigate":
        d.text((64, 200), "Low fuel mass", font=title, fill=(255, 180, 120))
        d.text((64, 300), "SpaceX: root cause still under investigation.", font=body, fill=MUTED)
    elif kind == "abort":
        d.text((64, 160), "Offshore abort", font=title, fill=(255, 120, 110))
        lines = [
            "Guidance sends it away from the tower.",
            "Landing burn. Engines cut off while hovering.",
            "Flight termination system fires.",
            "Spaceflight Now: it exploded at sea.",
        ]
        y = 280
        for line in lines:
            d.text((64, y), line, font=body, fill=MUTED)
            y += 80
    elif kind == "timeline":
        d.text((64, 150), "Two lines on one page", font=title, fill=(255, 255, 255))
        d.text((64, 260), "Report: the catch was aborted.", font=body, fill=(255, 120, 110))
        d.text((64, 340), "Timeline at 6:35 still says catch.", font=body, fill=MUTED)
        d.text((64, 440), "That table is marked approximate.", font=body, fill=CYAN)
        d.text((64, 520), "It is the plan, not the result.", font=body, fill=CYAN)
    elif kind == "shipgoes":
        d.text((64, 200), "Ship ascent: nominal", font=title, fill=CYAN)
        d.text((64, 310), "Engine cutoff at 8:09.", font=body, fill=MUTED)
    elif kind == "insert":
        d.text((64, 180), "Into orbit", font=title, fill=(255, 255, 255))
        d.text((64, 290), "One Raptor, 26:10 to 26:30.", font=body, fill=CYAN)
        d.text((64, 370), "About 20 seconds.", font=body, fill=MUTED)
    elif kind == "sats":
        d.text((64, 160), "26 Starlink V3", font=title, fill=(255, 255, 255))
        for i in range(26):
            x = 80 + (i % 13) * 120
            y = 360 + (i // 13) * 80
            d.ellipse([x, y, x + 16, y + 16], fill=CYAN)
        d.text((64, 620), "Contact with every satellite.", font=body, fill=MUTED)
        d.text((64, 690), "They begin raising their orbits.", font=body, fill=MUTED)
    elif kind == "orbits":
        d.text((64, 140), "Long coast", font=title, fill=(255, 255, 255))
        d.ellipse([700, 300, 1220, 820], outline=CYAN, width=3)
        d.ellipse([900, 500, 1020, 620], fill=(30, 90, 140))
        d.text((64, 900), "Spaceflight Now: 14 orbits. Not printed on the SpaceX timeline.", font=small, fill=MUTED)
    elif kind == "checks":
        d.text((64, 150), "Return checks", font=title, fill=CYAN)
        rows = [("1:28", "Hawaii"), ("7:16", "Chile"), ("20:42", "Hawaii again")]
        y = 300
        for t, place in rows:
            d.text((80, y), t, font=title, fill=(255, 255, 255))
            d.text((360, y), place, font=title, fill=MUTED)
            y += 140
        d.text((64, 860), "Splashdowns there were possible, and not used.", font=small, fill=MUTED)
    elif kind == "monitor":
        d.text((64, 200), "More than 20 hours", font=title, fill=(255, 255, 255))
        d.text((64, 320), "Monitoring. Not a reported failure.", font=body, fill=CYAN)
    elif kind == "deorbit":
        d.text((64, 180), "Deorbit burn", font=title, fill=CYAN)
        d.text((64, 300), "21:35:57  to  21:36:07", font=title, fill=(255, 255, 255))
        d.text((64, 420), "About 10 seconds. One sea-level Raptor.", font=body, fill=MUTED)
    elif kind == "entry":
        d.text((64, 160), "Coming down", font=title, fill=(255, 255, 255))
        rows = [("22:10:46", "entry"), ("22:29:34", "transonic"), ("22:30:13", "subsonic")]
        y = 320
        for t, name in rows:
            d.text((80, y), t, font=body, fill=CYAN)
            d.text((480, y), name, font=body, fill=(255, 255, 255))
            y += 100
    elif kind == "step":
        d.text((64, 140), "Landing burn  ·  18 seconds", font=title, fill=(255, 255, 255))
        for i, (n, mark) in enumerate([("3", "22:32:16"), ("2", "22:32:26"), ("1", "22:32:33")]):
            x = 200 + i * 500
            d.text((x, 360), n, font=font(FONTB, 120), fill=CYAN)
            d.text((x, 520), mark, font=body, fill=MUTED)
        d.text((64, 760), "Shutdown and the catch: 22:32:34.", font=body, fill=(255, 255, 255))
    elif kind == "arms":
        d.text((64, 80), "Ship catch  ·  diagram", font=title, fill=CYAN)
        d.rectangle([900, 160, 1020, 860], fill=(50, 64, 78))
        d.polygon([(640, 420), (900, 500), (900, 560), (640, 500)], fill=CYAN)
        d.polygon([(1280, 420), (1020, 500), (1020, 560), (1280, 500)], fill=CYAN)
        d.polygon([(930, 260), (990, 260), (1040, 420), (880, 420)], fill=(220, 224, 228))
        d.rectangle([910, 420, 1010, 700], fill=(190, 196, 204))
        d.text((64, 900), "No licensed Flight 15 webcast frame in this cut.", font=small, fill=MUTED)
    elif kind == "nosea":
        d.text((64, 200), "Engines and arms", font=title, fill=(255, 255, 255))
        d.text((64, 320), "No parachute in the sequence SpaceX published.", font=body, fill=MUTED)
        d.text((64, 400), "The ship does not splash down.", font=body, fill=CYAN)
    elif kind == "falcon":
        d.text((64, 160), "What other rockets keep", font=title, fill=(255, 255, 255))
        d.text((64, 300), "Falcon 9 lands the booster.", font=body, fill=MUTED)
        d.text((64, 380), "Its upper stage is thrown away.", font=body, fill=MUTED)
        d.text((64, 500), "A caught ship is the other half.", font=body, fill=CYAN)
    elif kind == "notmars":
        d.text((64, 200), "Not a Mars landing", font=title, fill=(255, 255, 255))
        d.text((64, 320), "Not a date for the next launch.", font=body, fill=MUTED)
        d.text((64, 400), "The fuel investigation is still open.", font=body, fill=CYAN)
    elif kind == "callback":
        d.text((64, 200), "Ship: caught", font=font(FONTB, 64), fill=CYAN)
        d.text((64, 340), "Booster: lost", font=font(FONTB, 64), fill=(255, 120, 110))
        d.text((64, 520), "22 and a half hours.", font=body, fill=MUTED)
    elif kind == "close":
        d.text((64, 220), "The catch was real.", font=title, fill=CYAN)
        d.text((64, 340), "The double catch was not.", font=title, fill=(255, 255, 255))
        d.text((64, 500), "Read the article on trendingtesla.com.", font=body, fill=MUTED)
    else:
        n = int(kind[4:]) if kind.startswith("note") and kind[4:].isdigit() else 0
        headlines = ["Ship caught", "Booster lost", "22 hours 32 minutes", "Pad 2, Starbase", "No parachute"]
        d.text((64, 220), headlines[n % len(headlines)], font=font(FONTB, 64), fill=CYAN)
        d.rectangle([64, 330, 420, 338], fill=CYAN)
        d.text((64, 380), "Flight 15, from SpaceX's own timeline.", font=body, fill=MUTED)
        d.text((64, 460), "A diagram, not a webcast frame.", font=small, fill=MUTED)
    return im


def caption_bar(text):
    bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(bar)
    lines = wrap(text, 52)
    f = font(FONTB, 32)
    line_h = 42
    block_h = 28 + line_h * len(lines)
    top = H - 36 - block_h
    d.rectangle([200, top, W - 200, top + block_h], fill=(0, 0, 0, 150))
    y = top + 14
    for line in lines:
        tw = d.textlength(line, font=f)
        d.text(((W - tw) / 2, y), line, font=f, fill=(255, 255, 255, 255))
        y += line_h
    return bar


def run(cmd):
    subprocess.run(cmd, check=True)


def render_segment(spec, dur, dest, cap):
    kind = spec[1]
    if kind == "still":
        src = Image.open(CLIPS / "stills" / spec[2]).convert("RGB")
        # Cover the frame, then hold the vehicle above the caption. A tall photo's
        # subject is not always in the centre, so each still carries its own bias.
        scale = max(1960 / src.width, 1160 / src.height)
        resized = src.resize((int(src.width * scale) + 1, int(src.height * scale) + 1), Image.LANCZOS)
        bias = float(spec[3] if spec[3] is not None else 0.40)
        left = max(0, (resized.width - 1960) // 2)
        top = int((resized.height - 1160) * bias)
        top = max(0, min(top, resized.height - 1160))
        frame = resized.crop((left, top, left + 1960, top + 1160))
        png = dest.with_suffix(".png")
        frame.save(png, quality=92)
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{dur:.3f}", "-i", str(png),
             "-vf", "crop=1920:1080:'(iw-1920)/2':'(ih-1080)*t/{}'".format(max(dur, 0.1)),
             "-r", str(FPS), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             str(dest.with_suffix(".base.mp4"))])
        base = dest.with_suffix(".base.mp4")
    elif kind == "diagram":
        img = diagram(spec[2])
        png = dest.with_suffix(".png")
        img.save(png, quality=95)
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{dur:.3f}", "-i", str(png),
             "-vf", "scale=2048:1152,crop=1920:1080:'(iw-1920)*t/{}':'(ih-1080)*t/{}'".format(dur, dur),
             "-r", str(FPS), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             str(dest.with_suffix(".base.mp4"))])
        base = dest.with_suffix(".base.mp4")
    else:
        src = CLIPS / spec[2]
        ss = spec[3]
        focus = spec[4]
        # 0 = left, 0.5 = center, 1 = right bias
        bias = {"left": "0.15", "center": "0.5", "right": "0.72", "low": "0.5"}[focus]
        # "low" keeps a portrait clip's vehicle, which sits in the lower half.
        ybias = "0.78" if focus == "low" else "0.45"
        vf = (
            "scale=2560:-2,crop=1920:1080:"
            f"'(iw-1920)*{bias}':'(ih-1080)*{ybias}',fps={FPS},setsar=1"
        )
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(ss), "-t", f"{dur:.3f}", "-i", str(src),
             "-vf", vf, "-an", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             str(dest.with_suffix(".base.mp4"))])
        base = dest.with_suffix(".base.mp4")
    overlay = dest.with_suffix(".cap.png")
    caption_bar(cap).save(overlay)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(base), "-i", str(overlay),
         "-filter_complex", "overlay=0:0", "-pix_fmt", "yuv420p", "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "20", "-an", str(dest)])
    base.unlink(missing_ok=True)
    overlay.unlink(missing_ok=True)
    dest.with_suffix(".png").unlink(missing_ok=True)


ASCENT_STILLS = [f"still-{i:02d}.jpg" for i in range(8)]
BOOSTER_STILLS = [f"still-{i:02d}.jpg" for i in range(8, 18)]


def still_shot(name, shows, caption, dur=8, vbias=0.40):
    meta = json.loads((CLIPS / "stills" / name.replace(".jpg", ".json")).read_text())
    credit = (
        f"{shows} File: {meta['title']}. {meta['licence']}, Steve Jurvetson. "
        f"Not Flight 15. {meta['url']}"
    )
    return [dur, "still", name, vbias, None, credit, caption]


def build_timeline(total):
    """One shot per narration beat. Durations are the edit, not a filler pass."""

    def clip(dur, file, ss, focus, shows, cap):
        return [dur, "clip", file, ss, focus, shows, cap]

    def still(dur, name, shows, cap, vbias=0.40):
        return still_shot(name, shows, cap, dur, vbias)

    def diag(dur, kind, shows, cap):
        return [dur, "diagram", kind, None, None, shows, cap]

    shots = [
        # 0:00 hook. The picture is a Starship stack at the tower, then the twist.
        clip(8.0, "ift5-aerostat.webm", 2.0, "center",
             "Starship Flight 5, 13 Oct 2024, lifting off beside the Starbase tower. "
             "Super Heavy and Ship. Public domain, US Customs and Border Protection. "
             "https://commons.wikimedia.org/wiki/File:IFT5_Aerostat.webm",
             "SpaceX caught Starship after 22 hours."),
        diag(8.0, "claim", "Diagram. Friday liftoff, Saturday catch, 22:32:34.",
             "The ship left Friday and was back on Saturday."),
        diag(8.0, "twist", "Diagram. Flight 15's booster did not return.",
             "The booster that lifted it did not come home."),
        diag(8.0, "abort", "Diagram. This booster's catch was aborted.",
             "The burn ended early. The catch was aborted."),
        diag(8.0, "wait", "Diagram. The ship coasted for most of a day.",
             "The ship stayed up. The reason comes later."),
        # 0:40 stakes.
        diag(8.6, "flightid", "Diagram. Flight 15, Pad 2, Starbase.",
             "Flight 15, from Pad 2 at Starbase."),
        diag(8.6, "clock", "Diagram. Catch marked at 22:32:34.",
             "22 hours, 32 minutes and 34 seconds. Not a guess."),
        diag(8.6, "when", "Diagram. Liftoff 4:47 p.m., catch 3:20 p.m. Texas time.",
             "Friday at 4:47. Saturday at 3:20."),
        diag(8.6, "names", "Diagram. Ship 42 and Booster 22, from the press.",
             "The press calls them Ship 42 and Booster 22."),
        diag(8.6, "record", "Diagram. Burns, satellites, the abort, the catch.",
             "The burns, the satellites, the abort, the catch."),
        diag(8.6, "parts", "Diagram. Four parts of the film.",
             "The minutes. The wait. The arms. What it changes."),
        still(8.6, "still-04.jpg",
              "Starship stack standing in the Starbase tower the night before Flight 5.",
              "The tower, and a ship beside it, before an earlier flight."),
        diag(8.6, "parts", "Diagram. The four parts, held while they are named.",
             "Minutes, then the wait, then the arms."),
        # 1:49 ascent. 33 engines land on the stack and on the engine diagram.
        diag(8.7, "maxq", "Diagram. Liftoff, Max Q, engine cutoff.",
             "Liftoff is zero. Max Q is 58 seconds."),
        clip(8.0, "ift5-aerostat.webm", 38.0, "center",
             "Starship Flight 5, the full stack climbing on its engines. Second use of the CBP aerial. "
             "Public domain, US Customs and Border Protection.",
             "Thirty-three Raptors, climbing away from the pad."),
        still(6.5, "still-05.jpg",
              "Starship Flight 5 full stack climbing, engines lit at the base of Super Heavy.",
              "The booster's engines, on an earlier flight.", vbias=0.02),
        diag(9.0, "engines", "Diagram of 33 sea-level Raptors, then the ship's six.",
             "Most of those cut off. Then the ship lights six."),
        diag(9.2, "hotstage", "Diagram. Hot-staging. Ship engines on, stages separate.",
             "Hot-staging. The stages separate."),
        still(8.0, "still-06.jpg",
              "Starship Flight 5 at hot-staging: the bright ring as the ship pulls away.",
              "Hot-staging. The ship is on its own path."),
        diag(9.5, "boostback", "Diagram. Boostback relit 32 of 33 and shut down early.",
             "Thirty-two of thirty-three relight. Shutdown is early."),
        diag(10.0, "investigate", "Diagram. Low fuel mass. Root cause still open.",
             "Low fuel mass. The cause is still under investigation."),
        # 2:57 the booster is lost. Landing-burn photo is engines-down, no tower.
        diag(8.5, "notower", "Diagram. Flight 15's booster does not reach the tower.",
             "The booster does not reach the tower."),
        still(8.0, "still-10.jpg",
              "Starship Flight 5 Super Heavy on a landing burn, engines down, no tower in frame. "
              "Not a catch, and not Flight 15.",
              "A landing burn, engines down. An earlier flight.", vbias=0.50),
        diag(8.8, "abort", "Diagram. Engines cut off, then flight termination.",
             "Engines cut off. The flight termination system fires."),
        diag(9.0, "gulf", "Diagram. Lost over the Gulf.",
             "Spaceflight Now: it exploded at sea."),
        diag(8.7, "fault", "Diagram. The stated fault is low fuel, not guidance.",
             "Guidance was not the fault. The fuel shortage was."),
        diag(8.8, "timeline", "Diagram. The report says aborted. The table still says catch.",
             "The report says aborted. The table still says catch."),
        diag(8.5, "plan", "Diagram. The 6:35 line is the plan.",
             "That line is the plan, and it is marked approximate."),
        diag(8.2, "contradict", "Diagram. Treating 6:35 as a catch would contradict the report.",
             "Calling that a catch would contradict the report."),
        # 4:06 the ship, on its own.
        clip(8.0, "ift1-nasa.webm", 112.0, "center",
             "Starship IFT-1, 20 April 2023. Full stack climbing, seen from a NASA WB-57. "
             "Public domain, NASA. Not Flight 15. "
             "https://commons.wikimedia.org/wiki/File:SpaceX_Starship_IFT-1_NASA_WB-57_Cam_0.webm",
             "The ship continues. SpaceX calls the ascent nominal."),
        diag(8.3, "shipgoes", "Diagram. Nominal ascent, engine cutoff at 8:09.",
             "Engine cutoff at 8 minutes and 9 seconds."),
        diag(8.5, "insert", "Diagram. One Raptor, about 20 seconds, into orbit.",
             "One engine, about 20 seconds, and the ship is in orbit."),
        diag(8.5, "deploy", "Diagram. Payload deploy runs about 43 minutes.",
             "The deploy itself runs for about 43 minutes."),
        diag(8.5, "sats", "Diagram. 26 Starlink V3 satellites.",
             "Twenty-six satellites leave. Contact with every one."),
        diag(8.5, "orbits", "Diagram. They raise their orbits. A long coast follows.",
             "They start raising their orbits. Then a long coast."),
        diag(8.5, "gap", "Diagram. The catch is still hours away.",
             "Fourteen orbits is the press count. The catch is still hours away."),
        diag(6.2, "gap", "Diagram. Satellites finished, ship still up.",
             "The satellites are finished. The ship is not."),
        # 5:11 why it waited.
        diag(9.6, "ballistic", "Diagram. The booster never reached orbit. The ship did.",
             "The booster never reached orbit. The ship did."),
        diag(9.6, "orbitroad", "Diagram. An orbit is not a road you turn around on.",
             "An orbit is not a road you turn around on."),
        diag(9.6, "orbitroad", "Diagram. A planned burn at a planned place.",
             "Coming down takes a planned burn, at a planned place."),
        diag(9.6, "monitor", "Diagram. More than 20 hours of monitoring, not a failure.",
             "The team watches the ship for more than 20 hours."),
        diag(9.6, "checks", "Diagram. Hawaii, then Chile, then Hawaii again.",
             "Hawaii. Then Chile. Then Hawaii again."),
        diag(9.6, "checks", "Diagram. The same three return checks, held.",
             "The ground track has to come back around."),
        diag(9.6, "hold", "Diagram. Earlier splashdowns were possible and not used.",
             "Those earlier ways down were left unused."),
        diag(9.5, "hold", "Diagram. The ship was allowed to stay up.",
             "The ship was allowed to stay up."),
        # 6:28 deorbit and entry.
        diag(9.35, "decision", "Diagram. The decision comes after the last Hawaii check.",
             "The decision comes almost an hour after Hawaii."),
        diag(9.35, "deorbit", "Diagram. Deorbit burn, 21:35:57 to 21:36:07.",
             "One sea-level engine fires for about 10 seconds."),
        diag(9.35, "breakorbit", "Diagram. That burn is what breaks the orbit.",
             "That short burn is what breaks the orbit."),
        diag(9.35, "entry", "Diagram. Entry, then 22 minutes to the catch.",
             "Entry. Then 22 minutes down to the catch."),
        diag(9.35, "entrytimes", "Diagram. Transonic, then subsonic, in under a minute.",
             "Transonic. Then subsonic. Under a minute."),
        diag(9.35, "burnstart", "Diagram. Landing burn starts at 22:32:16.",
             "The landing burn starts at 22:32:16."),
        diag(9.35, "watched", "Diagram. Not a delay. The ship was watched.",
             "Not a delay, and not a reported failure."),
        diag(9.35, "decision", "Diagram. Almost all of the 22 hours is the coast.",
             "Almost all of the 22 hours is the coast before that burn."),
        # 7:42 how the arms catch the ship. The arms drawing is on "the arms closed".
        diag(9.84, "step", "Diagram. Landing burn: three engines, then two, then one.",
             "A short burn. Three engines, then fewer."),
        diag(9.84, "step", "Diagram. Three Raptors for the flip and the descent.",
             "Three Raptors for the flip, then the descent."),
        diag(9.84, "step", "Diagram. Three engines become two.",
             "At 22:32:26 the burn goes from three engines to two."),
        diag(9.84, "step", "Diagram. Two engines become one, then shutdown.",
             "Then one engine. Then shutdown, at 22:32:34."),
        diag(9.84, "arms", "Diagram of a ship between the tower arms. Not a webcast frame.",
             "A swoosh over the Gulf, back toward the arms."),
        diag(9.84, "arms", "Diagram of the ship in the arms. No Flight 15 frame in this cut.",
             "Eighteen seconds from the relight to the arms."),
        diag(9.84, "arms", "Diagram. The arms close on the ship. First time, SpaceX says.",
             "The arms close. SpaceX says it is the first time."),
        diag(9.82, "nosea", "Diagram. No parachute. The ship does not splash down.",
             "No parachute. The ship does not splash down."),
        # 9:01 what the catch changes. Booster-catch footage starts at the earlier-catch line.
        diag(8.4, "splash", "Diagram. Flight 15's booster already splashed.",
             "The booster had already splashed, and had not survived."),
        diag(8.4, "sats", "Diagram. The 26 satellites were already away.",
             "The satellites were already away before the deorbit burn."),
        diag(8.4, "delivery", "Diagram. Contact with every satellite. The delivery stands.",
             "Contact with every one. The delivery stands either way."),
        diag(8.4, "otherclaim", "Diagram. The catch is the other claim.",
             "The catch is the other claim."),
        diag(8.5, "falcon", "Diagram only. Falcon 9 is named and not shown.",
             "Falcon 9 keeps the booster and throws the upper stage away."),
        diag(8.5, "inspect", "Diagram. No second flight of this ship has been reported.",
             "In principle it can fly again. No second flight is reported."),
        diag(9.0, "notboth", "Diagram. Not a catch of both stages.",
             "This flight was not a catch of both stages."),
        clip(8.0, "ift5-booster-cc0.webm", 32.0, "low",
             "Starship Flight 5 Super Heavy on its landing burn, approaching the Starbase tower. "
             "An earlier booster catch, not Flight 15's ship. CC0, TimBunning1. "
             "https://commons.wikimedia.org/wiki/File:Space_X_Starship_Flight_5_Booster_Landing.webm",
             "Super Heavy had already been caught, on earlier flights."),
        still(8.0, "still-13.jpg",
              "Starship Flight 5 Super Heavy in the tower arms, engines still lit. A booster catch, not the ship.",
              "In the arms, on an earlier flight. The new event is the ship."),
        diag(8.1, "rate", "Diagram. No date, no Moon landing, no Mars landing.",
             "No date in this video. Not a landing on Mars."),
        # 10:25 close.
        diag(8.5, "callback", "Diagram. Ship caught. Booster lost.",
             "The ship came home. The booster did not."),
        diag(8.5, "arms", "Diagram of the ship back between the arms.",
             "A ship back at the tower it left."),
        diag(9.5, "clock", "Diagram. 22:32:34, and 22 and a half hours.",
             "22 hours, 32 minutes, 34 seconds. 22 and a half hours."),
        diag(8.5, "twist", "Diagram. The booster did not get that ending.",
             "The booster did not get that ending."),
        diag(8.5, "ending", "Diagram. The ship did, after the long watch and a 10-second burn.",
             "The ship did, after the long watch and a 10-second burn."),
        diag(8.0, "ending", "Diagram. That is the whole flight, said once more.",
             "That is the whole flight."),
        diag(6.37, "close", "Diagram. Catch real. Double catch not. Article linked on the card.",
             "The catch was real. The double catch was not."),
    ]
    got = round(sum(s[0] for s in shots), 2)
    if abs(got - total) > 0.05:
        raise SystemExit(f"edit is {got}s and the audio is {total:.2f}s")
    # Absorb a rounding gap into the last shot without leaving the 6–10s band.
    shots[-1][0] = round(shots[-1][0] + (total - got), 2)
    for shot in shots:
        if shot[0] < 6 or shot[0] > 10:
            raise SystemExit(f"{shot[2]} is {shot[0]}s")
    return shots



def expand(total):
    shots = []
    for shot in SHOTS:
        dur, kind = shot[0], shot[1]
        if kind == "diagram" and dur == 8:
            shot = (9, *shot[1:])
        shots.append(list(shot))
    # Slow pans on Flight 5 stills, only beside matching narration.
    ascent_caps = [
        "The stack leaves the tower.",
        "Engines are lit.",
        "It climbs.",
        "The full stack, before flight.",
        "Hot-staging on an earlier flight.",
        "Ignition.",
        "The same kind of tower.",
        "Ascent, seen from the ground.",
    ]
    booster_caps = [
        "An earlier Super Heavy, back at the tower.",
        "Flight 5 booster, on the way in.",
        "Landing burn, Flight 5.",
        "The arms of that tower.",
        "Booster return.",
        "Final approach.",
        "Caught on an earlier flight.",
        "Not this flight's ship.",
        "The booster, not the ship.",
        "Flight 5 again, from another frame.",
    ]
    extra = []
    for name, cap in zip(ASCENT_STILLS, ascent_caps):
        extra.append(("engines", still_shot(name, "", cap)))
    for name, cap in zip(BOOSTER_STILLS, booster_caps):
        extra.append(("falcon", still_shot(name, "", cap)))
    # insert extras just before the named key, once each, and a second pass of ascent only
    for name, cap in zip(ASCENT_STILLS, ascent_caps):
        extra.append(("shipgoes", still_shot(name, "", cap)))
    # Booster-catch stills stay next to the line about earlier catches, not the line that says this booster was lost.
    out = []
    pending = {}
    for key, shot in extra:
        pending.setdefault(key, []).append(shot)
    for shot in shots:
        key = shot[2]
        if key in pending:
            out.extend(pending.pop(key))
        out.append(shot)
    fillers = [
        ("sources", "The sources are in the description."),
        ("gulf", "The Gulf is where this booster ended."),
        ("first", "First ship catch. Not the first booster catch."),
        ("inspect", "The caught ship has not been flown again."),
        ("hold", "Same voice. A picture that matches the words."),
    ]
    for kind, cap in fillers:
        out.append([8, "diagram", kind, None, None, f"Diagram. {cap}", cap])
    gap = total - sum(s[0] for s in out)
    if gap < 0:
        raise SystemExit(f"edit is {-gap:.1f}s longer than the audio")
    # Lengthen diagrams up to 10s before adding anything new.
    for shot in out:
        if gap <= 0:
            break
        if shot[1] == "diagram" and shot[0] < 10:
            room = 10 - shot[0]
            give = min(room, gap)
            shot[0] += give
            gap -= give
    n = 0
    while gap > 10:
        cap = f"Flight 15, as SpaceX published it. Part {n + 1}."
        out.append([8, "diagram", f"note{n}", None, None, f"Diagram. {cap}", cap])
        gap -= 8
        n += 1
    if gap >= 6:
        out.append([gap, "diagram", "endcard", None, None, "Diagram. End of the narration.", "The catch was real. The double catch was not."])
    elif gap > 0:
        out[-1][0] += gap
    return out


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 10000:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "TrendingTeslaVideo/1.0 (licensed footage)"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as out:
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            out.write(block)


def ensure_assets():
    """The runner does not have the footage. Skip anything already downloaded."""
    files = {
        "ift5-aerostat.webm":
            "https://upload.wikimedia.org/wikipedia/commons/5/56/IFT5_Aerostat.webm",
        "ift1-nasa.webm":
            "https://upload.wikimedia.org/wikipedia/commons/e/e9/SpaceX_Starship_IFT-1_NASA_WB-57_Cam_0.webm",
        "ift5-booster-cc0.webm":
            "https://upload.wikimedia.org/wikipedia/commons/1/12/Space_X_Starship_Flight_5_Booster_Landing.webm",
    }
    stills = {
        "still-04.jpg": (
            "File:SpaceX Starship before IFT-5.jpg", "CC BY 2.0",
            "https://upload.wikimedia.org/wikipedia/commons/0/09/SpaceX_Starship_before_IFT-5.jpg"),
        "still-05.jpg": (
            "File:SpaceX Starship during IFT-5.jpg", "CC BY 2.0",
            "https://upload.wikimedia.org/wikipedia/commons/b/b3/SpaceX_Starship_during_IFT-5.jpg"),
        "still-06.jpg": (
            "File:SpaceX Starship hot staging IFT-5.jpg", "CC BY 2.0",
            "https://upload.wikimedia.org/wikipedia/commons/c/cb/SpaceX_Starship_hot_staging_IFT-5.jpg"),
        "still-10.jpg": (
            "File:SpaceX Starship landing burn IFT-5.jpg", "CC BY 2.0",
            "https://upload.wikimedia.org/wikipedia/commons/e/eb/SpaceX_Starship_landing_burn_IFT-5.jpg"),
        "still-13.jpg": (
            "File:Starship 5 Booster Landing on Mechzilla.jpg", "CC BY 2.0",
            "https://upload.wikimedia.org/wikipedia/commons/4/42/Starship_5_Booster_Landing_on_Mechzilla.jpg"),
    }
    for name, url in files.items():
        fetch(url, CLIPS / name)
    for name, (title, licence, url) in stills.items():
        fetch(url, CLIPS / "stills" / name)
        meta = CLIPS / "stills" / name.replace(".jpg", ".json")
        if not meta.exists():
            meta.write_text(json.dumps({"title": title, "licence": licence, "url": url, "file": name}) + "\n",
                            encoding="utf-8")


def main():
    ensure_assets()
    audio = ROOT / "video/rebuild/narration.m4a"
    total = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
        text=True).strip())
    shots = build_timeline(total)
    if shots[-1][0] < 6 or shots[-1][0] > 12:
        raise SystemExit(f"closing shot is {shots[-1][0]:.2f}s; timeline does not match the audio ({total:.2f})")
    segdir = Path("/tmp/v2/segs")
    segdir.mkdir(parents=True, exist_ok=True)
    rows = []
    t = 0.0
    uses = {}
    for i, shot in enumerate(shots):
        dur, kind, key, ss, focus, shows, cap = shot
        if kind == "clip":
            uses[key] = uses.get(key, 0) + 1
            if uses[key] > 2:
                raise SystemExit(f"{key} used more than twice")
            if dur < 6 or dur > 10:
                raise SystemExit(f"clip shot {i} is {dur}s")
        dest = segdir / f"{i:03d}.mp4"
        if not dest.exists() or dest.stat().st_size < 10000:
            render_segment(shot, dur, dest, cap)
        rows.append({"t": round(t, 2), "dur": round(dur, 2), "kind": kind, "key": key,
                     "ss": ss, "shows": shows, "caption": cap})
        print(f"{t:7.1f} {dur:4.1f}s {kind:7} {key}")
        t += dur
    listing = segdir / "list.txt"
    listing.write_text("".join(f"file '{(segdir / f'{i:03d}.mp4').resolve()}'\n" for i in range(len(shots))),
                       encoding="utf-8")
    silent = Path("/tmp/v2/silent.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(silent)])
    out = Path("/tmp/v2/longform1-v2-1080.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(audio),
         "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-shortest", str(out)])
    meta = out.with_suffix(".txt")
    meta.write_text(
        "TITLE:\nSpaceX Caught Starship After 22 Hours\n\n"
        "DESCRIPTION:\n"
        "Unlisted test rebuild. Same narration as the private upload. "
        "Picture is Starship, Super Heavy, the Starbase tower, or a diagram. No Falcon 9.\n\n"
        "Flight 5 tower and booster clips are earlier catches, not Flight 15's ship.\n"
        "IFT-1 ascent is NASA WB-57, 20 April 2023.\n"
        "Diagrams are drawn for this cut. No Flight 15 webcast frame was available under a licence used here.\n\n"
        "TAGS:\nStarship, Super Heavy, Starbase\n",
        encoding="utf-8")
    Path("/tmp/v2/shots.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("OUT", out, "duration check", t)


if __name__ == "__main__":
    main()
