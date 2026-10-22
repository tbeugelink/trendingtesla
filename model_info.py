"""Reference information per model and version, shown at the top of each model page.

Each entry: sources (title, url) and per language an intro, a spec table, points to watch,
what makes this version special. Accessories follow later (empty list = placeholder)."""

W_S = ("Wikipedia — Tesla Model S", "https://en.wikipedia.org/wiki/Tesla_Model_S")
W_3 = ("Wikipedia — Tesla Model 3", "https://en.wikipedia.org/wiki/Tesla_Model_3")
W_X = ("Wikipedia — Tesla Model X", "https://en.wikipedia.org/wiki/Tesla_Model_X")
W_Y = ("Wikipedia — Tesla Model Y", "https://en.wikipedia.org/wiki/Tesla_Model_Y")
W_CT = ("Wikipedia — Tesla Cybertruck", "https://en.wikipedia.org/wiki/Tesla_Cybertruck")
HW = ("Not a Tesla App — How to check HW3 or HW4", "https://notateslaapp.com/news/2173/how-to-check-if-your-tesla-has-hardware-4-ai4-or-hardware-3")
STD_EU = ("electrive — Tesla Model 3 Standard starts at €36,990", "https://www.electrive.com/2025/12/05/tesla-model-3-standard-starts-at-e36990")
STD_UK = ("Drive Tesla Canada — Model 3 and Model Y Standard in Europe and UK", "https://driveteslacanada.ca/news/tesla-expands-lineup-europe-uk-model-3-model-y-standard/")
END_SX = ("electrive — Final Tesla Model S rolls off the production line", "https://www.electrive.com/2026/05/11/final-tesla-model-s-rolls-off-the-production-line/")

INFO = {
# ---------------------------------------------------------------- Model S
"model-s": {"sources": [W_S, END_SX], "en": {
  "intro": "Tesla's first in-house designed car and the one that made electric cars desirable. Built in Fremont from 2012 until production ended in May 2026.",
  "specs": [("Built", "2012–2026, Fremont (California)"), ("Body", "5-door liftback, 5 seats"), ("Generations", "2012–2020 · 2021+ refresh · Plaid"),
            ("Range", "about 210 to 410 miles EPA, depending on version"), ("Power", "302 hp up to 1,020 hp (Plaid)"),
            ("Cargo", "750 L trunk + 150 L frunk"), ("Status", "Out of production; Tesla keeps servicing and updating")],
  "watch": ["The generation matters more than the year: 2021+ cars have a new interior, faster computer and newer battery.",
            "Check which Autopilot computer the car has (HW2.5, HW3 or HW4) under Settings › Software.",
            "Free Supercharging on older cars is usually tied to the first owner."],
  "special": ["17-inch screen and over-the-air updates long before other carmakers.", "Huge cargo space thanks to the liftback and the frunk."]},
 "nl": {
  "intro": "De eerste auto die Tesla volledig zelf ontwierp, en de auto die elektrisch rijden begeerlijk maakte. Gebouwd in Fremont van 2012 tot de productie in mei 2026 stopte.",
  "specs": [("Gebouwd", "2012–2026, Fremont (Californië)"), ("Carrosserie", "5-deurs liftback, 5 zitplaatsen"), ("Generaties", "2012–2020 · 2021+ · Plaid"),
            ("Bereik", "ongeveer 340 tot 660 km (EPA), afhankelijk van de versie"), ("Vermogen", "302 pk tot 1.020 pk (Plaid)"),
            ("Bagageruimte", "750 l achter + 150 l voorin"), ("Status", "Niet meer in productie; Tesla blijft onderhoud en updates leveren")],
  "watch": ["De generatie telt meer dan het bouwjaar: vanaf 2021 heb je een nieuw interieur, snellere computer en nieuwere accu.",
            "Check welke Autopilot-computer erin zit (HW2.5, HW3 of HW4) onder Instellingen › Software.",
            "Gratis Superchargen bij oudere auto's hoort meestal bij de eerste eigenaar."],
  "special": ["Een scherm van 17 inch en updates via internet, jaren voor andere merken.", "Enorm veel bagageruimte dankzij de grote achterklep en de frunk."]}},
"model-s-classic": {"sources": [W_S, HW], "en": {
  "intro": "The original Model S with the vertical 17-inch screen. Many battery and motor versions were sold, from the 60 to the P100D.",
  "specs": [("Built", "2012–2020"), ("Battery", "60 to 100 kWh"), ("Range", "about 210 to 400 miles EPA"), ("Power", "302 to 762 hp"),
            ("Drive", "Rear-wheel drive (early) or dual-motor AWD ('D' versions)"), ("Infotainment", "MCU1 (Nvidia) until 2018, then MCU2 (Intel)"),
            ("Autopilot", "HW1 from 2014, HW2/2.5 from late 2016, HW3 from 2019"), ("Cargo", "750 L + 150 L frunk")],
  "watch": ["MCU1 cars: the screen's memory chip can wear out; many cars were fixed or upgraded to MCU2 — ask for proof.",
            "Retracting door handles and air suspension are known weak spots on older cars.",
            "Very old Autopilot hardware (HW1, HW2.5) no longer gets meaningful updates.",
            "2012 cars were part of the Takata airbag recall; check it was done."],
  "special": ["Performance versions with Ludicrous mode were among the quickest cars of their time.", "Some early cars have optional rear-facing child seats in the trunk."]},
 "nl": {
  "intro": "De originele Model S met het staande scherm van 17 inch. Er zijn veel accu- en motorversies verkocht, van de 60 tot de P100D.",
  "specs": [("Gebouwd", "2012–2020"), ("Accu", "60 tot 100 kWh"), ("Bereik", "ongeveer 340 tot 640 km (EPA)"), ("Vermogen", "302 tot 762 pk"),
            ("Aandrijving", "Achterwiel (vroeg) of vierwielaandrijving met twee motoren ('D'-versies)"), ("Infotainment", "MCU1 (Nvidia) tot 2018, daarna MCU2 (Intel)"),
            ("Autopilot", "HW1 vanaf 2014, HW2/2.5 vanaf eind 2016, HW3 vanaf 2019"), ("Bagageruimte", "750 l + 150 l voorin")],
  "watch": ["MCU1-auto's: de geheugenchip van het scherm kan slijten; veel auto's zijn gerepareerd of naar MCU2 opgewaardeerd — vraag om bewijs.",
            "Uitschuivende deurgrepen en luchtvering zijn bekende zwakke plekken bij oudere auto's.",
            "Heel oude Autopilot-hardware (HW1, HW2.5) krijgt geen wezenlijke updates meer.",
            "Auto's uit 2012 vielen onder de Takata-airbagactie; check of die is uitgevoerd."],
  "special": ["Performance-versies met Ludicrous-modus hoorden bij de snelste auto's van hun tijd.", "Sommige vroege auto's hebben optionele kinderzitjes achterstevoren in de kofferbak."]}},
"model-s-2021": {"sources": [W_S, HW], "en": {
  "intro": "The 2021 refresh brought a completely new interior, a horizontal screen and a faster AMD computer.",
  "specs": [("Built", "2021–2026"), ("Long Range", "670 hp, up to 405–410 miles EPA"), ("Aerodynamics", "Cd 0.208"),
            ("Screens", "17-inch horizontal + 8-inch rear screen"), ("Computer", "AMD Ryzen infotainment; HW3, HW4 from 2023"),
            ("Steering", "Yoke or round wheel")],
  "watch": ["Early cars came with the yoke steering wheel only; try it before you buy.", "Cars from about 2023 have HW4; older ones HW3.",
            "Tesla stopped production in 2026 but promises service, parts and updates."],
  "special": ["Very quiet and efficient for its size.", "Rear-seat screen for passengers."]},
 "nl": {
  "intro": "De vernieuwing van 2021 bracht een compleet nieuw interieur, een liggend scherm en een snellere AMD-computer.",
  "specs": [("Gebouwd", "2021–2026"), ("Long Range", "670 pk, tot 650–660 km (EPA)"), ("Luchtweerstand", "Cw 0,208"),
            ("Schermen", "17 inch liggend + 8 inch achterin"), ("Computer", "AMD Ryzen-infotainment; HW3, HW4 vanaf 2023"),
            ("Stuur", "Yoke of rond stuur")],
  "watch": ["Vroege auto's hadden alleen het yoke-stuur; probeer het voordat je koopt.", "Auto's vanaf ongeveer 2023 hebben HW4, oudere HW3.",
            "Tesla stopte de productie in 2026, maar belooft service, onderdelen en updates."],
  "special": ["Heel stil en zuinig voor zijn formaat.", "Scherm voor de achterpassagiers."]}},
"model-s-plaid": {"sources": [W_S], "en": {
  "intro": "The three-motor top version: one of the fastest-accelerating production cars ever built.",
  "specs": [("Built", "2021–2026"), ("Power", "1,020 hp, three motors"), ("0–60 mph", "1.99 s (Tesla, with rollout)"),
            ("Top speed", "200 mph with Track Package, otherwise lower"), ("Battery", "about 95 kWh"), ("Range", "about 390 miles EPA")],
  "watch": ["Tires and brakes wear quickly if you use the performance.", "Insurance is expensive.", "Check for the Track Package if top speed matters to you."],
  "special": ["Carbon-sleeved rotors in the motors.", "Supercar acceleration in a five-seat family car."]},
 "nl": {
  "intro": "De topversie met drie motoren: een van de snelst optrekkende productieauto's ooit.",
  "specs": [("Gebouwd", "2021–2026"), ("Vermogen", "1.020 pk, drie motoren"), ("0–96 km/u", "1,99 s (Tesla, met rollout)"),
            ("Topsnelheid", "322 km/u met Track Package, anders lager"), ("Accu", "ongeveer 95 kWh"), ("Bereik", "ongeveer 630 km (EPA)")],
  "watch": ["Banden en remmen slijten snel als je de prestaties gebruikt.", "Verzekering is duur.", "Check of het Track Package erop zit als topsnelheid belangrijk is."],
  "special": ["Rotoren met carbon omhulling in de motoren.", "Supercar-acceleratie in een gezinsauto met vijf zitplaatsen."]}},
# ---------------------------------------------------------------- Model 3
"model-3": {"sources": [W_3, STD_EU], "en": {
  "intro": "Tesla's compact sedan and the car that made Tesla a volume manufacturer. Two generations: the original (2017–2023) and Highland (2023+), plus Standard and Performance versions.",
  "specs": [("Built", "since 2017, Fremont and Shanghai"), ("Body", "4-door sedan, 5 seats"), ("Range", "up to 750 km WLTP (Premium RWD)"),
            ("0–60 mph", "2.9 s (Performance) to 6+ s"), ("Charging", "11 kW AC, up to 250 kW DC"), ("Price (DE)", "from €36,990 (Standard)")],
  "watch": ["HW3 (original) or HW4 (Highland) decides which FSD features you get.", "LFP batteries in the base versions: charge to 100% regularly."],
  "special": ["Very efficient: one of the lowest energy uses per km of any EV.", "Glass roof as standard."]},
 "nl": {
  "intro": "Tesla's compacte sedan en de auto die van Tesla een volumemerk maakte. Twee generaties: het origineel (2017–2023) en de Highland (2023+), plus Standard- en Performance-versies.",
  "specs": [("Gebouwd", "sinds 2017, Fremont en Shanghai"), ("Carrosserie", "4-deurs sedan, 5 zitplaatsen"), ("Bereik", "tot 750 km WLTP (Premium RWD)"),
            ("0–100 km/u", "3,1 s (Performance) tot ruim 6 s"), ("Laden", "11 kW AC, tot 250 kW DC"), ("Prijs (NL/DE)", "vanaf € 36.990 (Standard)")],
  "watch": ["HW3 (origineel) of HW4 (Highland) bepaalt welke FSD-functies je krijgt.", "LFP-accu's in de basisversies: regelmatig tot 100% laden."],
  "special": ["Heel zuinig: een van de laagste verbruiken per km van alle EV's.", "Glazen dak standaard."]}},
"model-3-classic": {"sources": [W_3, HW], "en": {
  "intro": "The original Model 3, sold in many versions from Standard Range to Performance.",
  "specs": [("Built", "2017–2023"), ("Battery", "50 to 82 kWh"), ("Range", "220 to 358 miles EPA"), ("0–60 mph", "3.1 s (Performance) to 5.8 s"),
            ("DC charging", "170 to 250 kW"), ("AC charging", "11 kW (Europe)"), ("Autopilot", "HW2.5 until spring 2019, then HW3"),
            ("Towing (EU)", "up to 1,000 kg")],
  "watch": ["HW3: gets FSD v14 Lite but no future major FSD versions.", "Firm ride, especially on 19- and 20-inch wheels.",
            "Check the trunk seals for water ingress.", "Heat pump only from the 2021 model year."],
  "special": ["Huge used market, so good prices and plenty of choice.", "Minimalist interior with one 15-inch screen."]},
 "nl": {
  "intro": "De originele Model 3, verkocht in veel versies van Standard Range tot Performance.",
  "specs": [("Gebouwd", "2017–2023"), ("Accu", "50 tot 82 kWh"), ("Bereik", "350 tot 575 km (EPA)"), ("0–96 km/u", "3,1 s (Performance) tot 5,8 s"),
            ("Snelladen", "170 tot 250 kW"), ("AC-laden", "11 kW (Europa)"), ("Autopilot", "HW2.5 tot voorjaar 2019, daarna HW3"),
            ("Trekgewicht (EU)", "tot 1.000 kg")],
  "watch": ["HW3: krijgt FSD v14 Lite, maar geen toekomstige grote FSD-versies.", "Stug weggedrag, vooral op 19- en 20-inch velgen.",
            "Controleer de rubbers van de kofferbak op lekkage.", "Warmtepomp pas vanaf modeljaar 2021."],
  "special": ["Grote occasionmarkt, dus goede prijzen en veel keus.", "Minimalistisch interieur met één scherm van 15 inch."]}},
"model-3-highland": {"sources": [W_3, HW], "en": {
  "intro": "The 2023 refresh: quieter, more comfortable and with Hardware 4 as standard.",
  "specs": [("Built", "since late 2023"), ("Versions", "RWD · Premium RWD · Premium AWD · Performance"),
            ("Range", "534 km (RWD) up to 750 km WLTP (Premium RWD)"), ("0–60 mph", "5.8 s (RWD) · 4.2 s (Premium AWD)"),
            ("Aerodynamics", "Cd 0.219"), ("Autopilot", "HW4"), ("Comfort", "ventilated front seats, rear screen, acoustic glass")],
  "watch": ["Many cars have no turn-signal stalk (buttons on the wheel); stalks return for 2026 cars.", "Interior accessories for the original Model 3 often don't fit."],
  "special": ["Ambient lighting and an 8-inch screen for rear passengers.", "Noticeably quieter than the original."]},
 "nl": {
  "intro": "De vernieuwing van 2023: stiller, comfortabeler en standaard met Hardware 4.",
  "specs": [("Gebouwd", "sinds eind 2023"), ("Versies", "RWD · Premium RWD · Premium AWD · Performance"),
            ("Bereik", "534 km (RWD) tot 750 km WLTP (Premium RWD)"), ("0–96 km/u", "5,8 s (RWD) · 4,2 s (Premium AWD)"),
            ("Luchtweerstand", "Cw 0,219"), ("Autopilot", "HW4"), ("Comfort", "geventileerde voorstoelen, scherm achterin, akoestisch glas")],
  "watch": ["Veel auto's hebben geen knipperlichthendel (knoppen op het stuur); vanaf 2026 komt de hendel terug.", "Interieuraccessoires voor de originele Model 3 passen vaak niet."],
  "special": ["Sfeerverlichting en een scherm van 8 inch voor achterpassagiers.", "Merkbaar stiller dan het origineel."]}},
"model-3-standard": {"sources": [STD_EU, STD_UK], "en": {
  "intro": "The entry-level Model 3, launched in Europe in December 2025 as the cheapest way into a Tesla sedan.",
  "specs": [("Price (Germany)", "from €36,990 + €980 delivery"), ("Range", "534 km WLTP"), ("0–100 km/h", "6.2 s"), ("Top speed", "201 km/h"),
            ("Drive", "rear-wheel drive"), ("Wheels", "18-inch 'Prismata'"), ("Colours", "3: Pearl White, Diamond Black, Stealth Grey"),
            ("Tow hitch", "optional, up to 1,000 kg"), ("Built", "Shanghai")],
  "watch": ["Simpler seats and always a black interior.", "Fewer options than Premium; compare the configurator columns before ordering.",
            "Accessories: check they explicitly support the Standard version."],
  "special": ["Keeps the glass roof, Supercharger access and over-the-air updates.", "About €8,000 cheaper than the cheapest Premium."]},
 "nl": {
  "intro": "De instap-Model 3, in december 2025 in Europa gelanceerd als goedkoopste weg naar een Tesla-sedan.",
  "specs": [("Prijs (DE/NL)", "vanaf € 36.990 + afleverkosten"), ("Bereik", "534 km WLTP"), ("0–100 km/u", "6,2 s"), ("Topsnelheid", "201 km/u"),
            ("Aandrijving", "achterwielaandrijving"), ("Velgen", "18 inch 'Prismata'"), ("Kleuren", "3: Pearl White, Diamond Black, Stealth Grey"),
            ("Trekhaak", "optioneel, tot 1.000 kg"), ("Gebouwd", "Shanghai")],
  "watch": ["Eenvoudigere stoelen en altijd een zwart interieur.", "Minder opties dan Premium; vergelijk de kolommen in de configurator.",
            "Accessoires: check of ze de Standard-versie uitdrukkelijk ondersteunen."],
  "special": ["Behoudt het glazen dak, Supercharger-toegang en updates via internet.", "Ongeveer € 8.000 goedkoper dan de goedkoopste Premium."]}},
"model-3-performance": {"sources": [W_3], "en": {
  "intro": "The sporty Model 3. The Highland-based Performance (2024+) added adaptive suspension and much more power.",
  "specs": [("Built", "Performance since 2018; new version since 2024"), ("0–60 mph", "2.9 s (2024+) · 3.1 s (before)"), ("Top speed", "163 mph (262 km/h)"),
            ("Battery", "78.1 kWh"), ("Range", "309 miles EPA · 571 km WLTP"), ("Chassis", "adaptive dampers, 20-inch wheels"), ("Weight", "about 1,850 kg")],
  "watch": ["Tires wear faster, and 20-inch tires are expensive.", "Firmer ride than the other versions."],
  "special": ["Sports seats, carbon spoiler and a track mode.", "Quicker than most sports cars at a fraction of the price."]},
 "nl": {
  "intro": "De sportieve Model 3. De Performance op basis van de Highland (2024+) kreeg adaptieve demping en veel meer vermogen.",
  "specs": [("Gebouwd", "Performance sinds 2018; nieuwe versie sinds 2024"), ("0–96 km/u", "2,9 s (2024+) · 3,1 s (eerder)"), ("Topsnelheid", "262 km/u"),
            ("Accu", "78,1 kWh"), ("Bereik", "497 km EPA · 571 km WLTP"), ("Onderstel", "adaptieve demping, 20-inch velgen"), ("Gewicht", "ongeveer 1.850 kg")],
  "watch": ["Banden slijten sneller, en 20-inch banden zijn duur.", "Stugger weggedrag dan de andere versies."],
  "special": ["Sportstoelen, carbon spoiler en een circuitmodus.", "Sneller dan de meeste sportwagens, voor een fractie van de prijs."]}},
# ---------------------------------------------------------------- Model X
"model-x": {"sources": [W_X, END_SX], "en": {
  "intro": "Tesla's large SUV with falcon-wing rear doors, built from 2015 until production ended in May 2026.",
  "specs": [("Built", "2015–2026, Fremont"), ("Seats", "5, 6 or 7"), ("Range", "about 200 to 371 miles EPA"), ("0–60 mph", "2.5 s (Plaid)"),
            ("Towing", "up to 2,250 kg (5,000 lb)"), ("Cargo", "up to about 2,500 L"), ("Status", "Out of production; successor: Model Y L")],
  "watch": ["Falcon-wing doors: test them several times and check the seals.", "Air suspension and heavy weight wear tires quickly."],
  "special": ["Panoramic windshield that runs up over the front seats.", "One of the few EVs that can tow 2,250 kg."]},
 "nl": {
  "intro": "Tesla's grote SUV met valkvleugeldeuren achter, gebouwd van 2015 tot de productie in mei 2026 stopte.",
  "specs": [("Gebouwd", "2015–2026, Fremont"), ("Zitplaatsen", "5, 6 of 7"), ("Bereik", "ongeveer 320 tot 600 km (EPA)"), ("0–96 km/u", "2,5 s (Plaid)"),
            ("Trekgewicht", "tot 2.250 kg"), ("Bagageruimte", "tot ongeveer 2.500 l"), ("Status", "Niet meer in productie; opvolger: Model Y L")],
  "watch": ["Valkvleugeldeuren: test ze een paar keer en controleer de rubbers.", "Luchtvering en het hoge gewicht laten banden snel slijten."],
  "special": ["Panoramische voorruit die tot boven de voorstoelen doorloopt.", "Een van de weinige EV's die 2.250 kg mag trekken."]}},
"model-x-classic": {"sources": [W_X, HW], "en": {
  "intro": "The original Model X with the vertical screen, from the 60D to the P100D.",
  "specs": [("Built", "2015–2020"), ("Battery", "60 to 100 kWh"), ("Range", "about 200 to 371 miles EPA"), ("0–60 mph", "2.9 s (P100D) to about 6 s"),
            ("Seats", "5, 6 or 7"), ("Towing", "up to 2,250 kg"), ("Infotainment", "MCU1 until early 2018, then MCU2")],
  "watch": ["Early falcon-wing doors had sensor, latch and leak problems.", "Windows that don't fully close were a known issue.",
            "MCU1 screen memory can fail; ask whether it was replaced or upgraded.", "2016 third-row seat and 2017 parking brake recalls: check they were done."],
  "special": ["Seven seats in a fast, quiet electric SUV.", "Huge windshield and a very airy cabin."]},
 "nl": {
  "intro": "De originele Model X met het staande scherm, van de 60D tot de P100D.",
  "specs": [("Gebouwd", "2015–2020"), ("Accu", "60 tot 100 kWh"), ("Bereik", "ongeveer 320 tot 600 km (EPA)"), ("0–96 km/u", "2,9 s (P100D) tot ongeveer 6 s"),
            ("Zitplaatsen", "5, 6 of 7"), ("Trekgewicht", "tot 2.250 kg"), ("Infotainment", "MCU1 tot begin 2018, daarna MCU2")],
  "watch": ["Vroege valkvleugeldeuren hadden problemen met sensoren, sloten en lekkage.", "Ramen die niet helemaal sluiten waren een bekende kwaal.",
            "Het geheugen van het MCU1-scherm kan kapotgaan; vraag of het is vervangen of opgewaardeerd.", "Terugroepacties voor de derde zitrij (2016) en de parkeerrem (2017): check of ze zijn uitgevoerd."],
  "special": ["Zeven zitplaatsen in een snelle, stille elektrische SUV.", "Enorme voorruit en een heel ruim gevoel binnen."]}},
"model-x-2021": {"sources": [W_X, HW], "en": {
  "intro": "The 2021 refresh with the new interior, horizontal screen and AMD computer.",
  "specs": [("Built", "2021–2026"), ("Long Range", "670 hp, about 352 miles EPA"), ("Seats", "5, 6 or 7"), ("Towing", "up to 2,250 kg"),
            ("Weight", "about 2,335 kg"), ("Screens", "17-inch horizontal + rear screen"), ("Autopilot", "HW3; HW4 from 2023")],
  "watch": ["Yoke steering on early cars; round wheel available later.", "Heavy car: budget for tires."],
  "special": ["Quiet, comfortable long-distance SUV.", "Falcon-wing doors that open in tight parking spaces."]},
 "nl": {
  "intro": "De vernieuwing van 2021 met nieuw interieur, liggend scherm en AMD-computer.",
  "specs": [("Gebouwd", "2021–2026"), ("Long Range", "670 pk, ongeveer 566 km (EPA)"), ("Zitplaatsen", "5, 6 of 7"), ("Trekgewicht", "tot 2.250 kg"),
            ("Gewicht", "ongeveer 2.335 kg"), ("Schermen", "17 inch liggend + scherm achterin"), ("Autopilot", "HW3; HW4 vanaf 2023")],
  "watch": ["Yoke-stuur bij vroege auto's; later ook een rond stuur.", "Zware auto: reken op bandenkosten."],
  "special": ["Stille, comfortabele SUV voor lange afstanden.", "Valkvleugeldeuren die ook in krappe parkeervakken opengaan."]}},
"model-x-plaid": {"sources": [W_X], "en": {
  "intro": "The three-motor Model X: a seven-seat SUV that accelerates like a supercar.",
  "specs": [("Built", "2021–2026"), ("Power", "1,020 hp, three motors"), ("0–60 mph", "2.5 s"), ("Quarter mile", "9.9 s"),
            ("Range", "about 335 miles EPA"), ("Weight", "about 2,380 kg")],
  "watch": ["Tires and brakes wear fast.", "Insurance and parts are expensive."],
  "special": ["Probably the quickest seven-seater ever built."]},
 "nl": {
  "intro": "De Model X met drie motoren: een zevenzits SUV die optrekt als een supercar.",
  "specs": [("Gebouwd", "2021–2026"), ("Vermogen", "1.020 pk, drie motoren"), ("0–96 km/u", "2,5 s"), ("Kwartmijl", "9,9 s"),
            ("Bereik", "ongeveer 539 km (EPA)"), ("Gewicht", "ongeveer 2.380 kg")],
  "watch": ["Banden en remmen slijten snel.", "Verzekering en onderdelen zijn duur."],
  "special": ["Waarschijnlijk de snelste zevenzitter ooit gebouwd."]}},
# ---------------------------------------------------------------- Model Y
"model-y": {"sources": [W_Y], "en": {
  "intro": "Tesla's best-selling car and one of the best-selling cars in the world. The original (2020–2024) was replaced by the Juniper refresh in 2025.",
  "specs": [("Built", "since 2020: Fremont, Austin, Shanghai, Berlin"), ("Body", "5-door crossover, 5 seats (7 or 6 in some versions)"),
            ("Cargo", "about 2,100 L"), ("Charging", "11 kW AC, up to 250 kW DC"), ("Towing (EU)", "up to 1,600 kg")],
  "watch": ["Original or Juniper? Interior accessories rarely fit both.", "Check HW3 or HW4 on cars built in 2023."],
  "special": ["Heat pump as standard from the start.", "Very practical: big trunk, frunk and flat floor."]},
 "nl": {
  "intro": "Tesla's best verkochte auto en een van de best verkochte auto's ter wereld. Het origineel (2020–2024) werd in 2025 vervangen door de Juniper.",
  "specs": [("Gebouwd", "sinds 2020: Fremont, Austin, Shanghai, Berlijn"), ("Carrosserie", "5-deurs crossover, 5 zitplaatsen (7 of 6 bij sommige versies)"),
            ("Bagageruimte", "ongeveer 2.100 l"), ("Laden", "11 kW AC, tot 250 kW DC"), ("Trekgewicht", "tot 1.600 kg")],
  "watch": ["Origineel of Juniper? Interieuraccessoires passen zelden op allebei.", "Check HW3 of HW4 bij auto's uit 2023."],
  "special": ["Vanaf het begin standaard een warmtepomp.", "Heel praktisch: grote kofferbak, frunk en vlakke vloer."]}},
"model-y-classic": {"sources": [W_Y, HW], "en": {
  "intro": "The original Model Y, recognizable by its separate headlights without a light bar.",
  "specs": [("Built", "2020–2024"), ("Battery", "about 60 to 81 kWh (LFP in Standard Range)"), ("Range", "244 to 357 miles EPA"),
            ("0–60 mph", "3.3 s (Performance) to 6.9 s"), ("Cargo", "2,158 L"), ("Seats", "5, optional 7 (US)"),
            ("Autopilot", "HW3; HW4 from about mid-2023")],
  "watch": ["Firm ride, especially on 20- and 21-inch wheels.", "Phantom braking was investigated by NHTSA for 2021–2022 cars.",
            "2021 cars: NHTSA is investigating rear door releases; know where the manual release is.", "LFP battery versions: charge to 100% weekly."],
  "special": ["Tesla's first heat pump (Octovalve), less range loss in winter.", "Huge used supply at attractive prices."]},
 "nl": {
  "intro": "De originele Model Y, herkenbaar aan de losse koplampen zonder lichtstreep.",
  "specs": [("Gebouwd", "2020–2024"), ("Accu", "ongeveer 60 tot 81 kWh (LFP in Standard Range)"), ("Bereik", "390 tot 575 km (EPA)"),
            ("0–96 km/u", "3,3 s (Performance) tot 6,9 s"), ("Bagageruimte", "2.158 l"), ("Zitplaatsen", "5, optioneel 7 (VS)"),
            ("Autopilot", "HW3; HW4 vanaf ongeveer medio 2023")],
  "watch": ["Stug weggedrag, vooral op 20- en 21-inch velgen.", "Spookremmen bij auto's uit 2021–2022 werd door de NHTSA onderzocht.",
            "Auto's uit 2021: de NHTSA onderzoekt de achterdeur-ontgrendeling; weet waar de noodontgrendeling zit.", "LFP-versies: wekelijks tot 100% laden."],
  "special": ["Tesla's eerste warmtepomp (Octovalve), minder bereikverlies in de winter.", "Groot aanbod tweedehands tegen aantrekkelijke prijzen."]}},
"model-y-juniper": {"sources": [W_Y], "en": {
  "intro": "The 2025 refresh with light bars front and rear, a quieter cabin and much better comfort.",
  "specs": [("Built", "since January 2025"), ("Long Range AWD", "0–100 km/h 4.8 s, up to about 600 km WLTP"), ("Top speed", "201 km/h (non-Performance)"),
            ("Screens", "15.4-inch + 8-inch rear screen"), ("Comfort", "ventilated seats, power rear seats, acoustic glass"),
            ("Autopilot", "HW4, extra front bumper camera"), ("Stalk", "turn-signal stalk retained")],
  "watch": ["Accessories for the original Model Y usually don't fit.", "Premium vs Standard: very different equipment, check the version."],
  "special": ["Far more comfortable suspension than the original.", "Full-width light bars give it a distinctive look."]},
 "nl": {
  "intro": "De vernieuwing van 2025 met lichtbalken voor en achter, een stiller interieur en veel meer comfort.",
  "specs": [("Gebouwd", "sinds januari 2025"), ("Long Range AWD", "0–100 km/u 4,8 s, tot ongeveer 600 km WLTP"), ("Topsnelheid", "201 km/u (niet-Performance)"),
            ("Schermen", "15,4 inch + 8 inch achterin"), ("Comfort", "geventileerde stoelen, elektrische achterbank, akoestisch glas"),
            ("Autopilot", "HW4, extra camera in de voorbumper"), ("Hendel", "knipperlichthendel behouden")],
  "watch": ["Accessoires voor de originele Model Y passen meestal niet.", "Premium of Standard: heel verschillende uitrusting, check de versie."],
  "special": ["Veel comfortabeler onderstel dan het origineel.", "Lichtbalken over de hele breedte geven een eigen gezicht."]}},
"model-y-standard": {"sources": [W_Y, STD_UK], "en": {
  "intro": "The cheaper Model Y, launched in October 2025 with less equipment and a lower price.",
  "specs": [("Price", "UK from £41,990 · Germany from €39,990"), ("Range", "up to 505 km WLTP"), ("Drive", "rear-wheel drive"),
            ("Wheels", "18-inch"), ("DC charging", "up to 225 kW"), ("Roof", "glass roof covered on the inside"), ("Suspension", "passive dampers")],
  "watch": ["Missing compared with Premium: e.g. ventilated seats, rear screen, ambient lighting, power-folding mirrors (varies by market).",
            "In North America Autopilot is limited to traffic-aware cruise control.", "Many Premium accessories don't fit; check compatibility."],
  "special": ["The cheapest new Model Y.", "Same space and Supercharger access as the other versions."]},
 "nl": {
  "intro": "De goedkopere Model Y, in oktober 2025 gelanceerd met minder uitrusting en een lagere prijs.",
  "specs": [("Prijs", "VK vanaf £ 41.990 · Duitsland vanaf € 39.990"), ("Bereik", "tot 505 km WLTP"), ("Aandrijving", "achterwielaandrijving"),
            ("Velgen", "18 inch"), ("Snelladen", "tot 225 kW"), ("Dak", "glazen dak aan de binnenkant afgedekt"), ("Vering", "passieve schokdempers")],
  "watch": ["Ontbreekt t.o.v. Premium: o.a. geventileerde stoelen, scherm achterin, sfeerverlichting, inklapbare spiegels (verschilt per land).",
            "In Noord-Amerika is Autopilot beperkt tot adaptieve cruise control.", "Veel Premium-accessoires passen niet; check de compatibiliteit."],
  "special": ["De goedkoopste nieuwe Model Y.", "Dezelfde ruimte en Supercharger-toegang als de andere versies."]}},
"model-y-performance": {"sources": [W_Y], "en": {
  "intro": "The Juniper-based Performance, launched in Europe in August 2025, with adaptive dampers and bidirectional charging.",
  "specs": [("Power", "460 hp (340 kW)"), ("0–100 km/h", "3.5 s"), ("Top speed", "250 km/h (155 mph)"), ("Range", "580 km WLTP"),
            ("Battery", "about 82–84 kWh usable"), ("Weight", "2,033 kg"), ("Towing", "up to 1,590 kg (3,500 lb)")],
  "watch": ["Lower ground clearance (151 mm): watch speed bumps.", "21-inch tires wear faster and cost more."],
  "special": ["First Model Y with vehicle-to-load and vehicle-to-home.", "Performance seats, carbon trim and a 16-inch screen."]},
 "nl": {
  "intro": "De Performance op basis van de Juniper, in augustus 2025 in Europa gelanceerd, met adaptieve demping en bidirectioneel laden.",
  "specs": [("Vermogen", "460 pk (340 kW)"), ("0–100 km/u", "3,5 s"), ("Topsnelheid", "250 km/u"), ("Bereik", "580 km WLTP"),
            ("Accu", "ongeveer 82–84 kWh bruikbaar"), ("Gewicht", "2.033 kg"), ("Trekgewicht", "tot 1.590 kg")],
  "watch": ["Lagere bodemvrijheid (151 mm): let op verkeersdrempels.", "21-inch banden slijten sneller en zijn duurder."],
  "special": ["Eerste Model Y met vehicle-to-load en vehicle-to-home.", "Sportstoelen, carbon afwerking en een scherm van 16 inch."]}},
"model-y-l": {"sources": [W_Y], "en": {
  "intro": "The long-wheelbase Model Y with six seats in three rows, built in Shanghai.",
  "specs": [("Launched", "China Sept 2025 · Australia/NZ 2026"), ("Length", "4,976 mm"), ("Seats", "6 (2-2-2, captain's chairs in row two)"),
            ("Cargo", "up to about 2,540 L"), ("Battery", "82–88 kWh"), ("Range", "up to 681 km WLTP (Australia/NZ)"), ("0–100 km/h", "4.5–5.0 s")],
  "watch": ["Not (yet) sold in Europe or the US; US delivery estimates stretch into 2027.", "Longer car: check your garage and parking space."],
  "special": ["Successor in spirit to the Model X as Tesla's family car.", "Third row usable by adults."]},
 "nl": {
  "intro": "De Model Y met lange wielbasis en zes stoelen in drie rijen, gebouwd in Shanghai.",
  "specs": [("Gelanceerd", "China sept. 2025 · Australië/NZ 2026"), ("Lengte", "4.976 mm"), ("Zitplaatsen", "6 (2-2-2, losse stoelen op rij twee)"),
            ("Bagageruimte", "tot ongeveer 2.540 l"), ("Accu", "82–88 kWh"), ("Bereik", "tot 681 km WLTP (Australië/NZ)"), ("0–100 km/u", "4,5–5,0 s")],
  "watch": ["(Nog) niet te koop in Europa of de VS; Amerikaanse levertijden lopen tot in 2027.", "Langere auto: check je garage en parkeerplek."],
  "special": ["Als gezinsauto de opvolger van de Model X.", "Derde zitrij bruikbaar voor volwassenen."]}},
# ---------------------------------------------------------------- Cybertruck
"cybertruck": {"sources": [W_CT], "en": {
  "intro": "Tesla's stainless-steel pickup, sold in North America, South Korea and the Middle East. Not road-legal in the EU or UK.",
  "specs": [("Built", "since late 2023, Austin"), ("Battery", "123 kWh, 800 V architecture"), ("Range", "about 300 to 340 miles EPA"),
            ("Towing", "up to 11,000 lb (4,990 kg)"), ("Bed", "6 ft, 67 cu ft"), ("Steering", "steer-by-wire with rear-wheel steering"),
            ("Price", "from $59,990 (AWD, 2026)")],
  "watch": ["Ten-plus recalls since launch; check all are done.", "Stainless steel shows marks and can show surface rust.", "Electric doors: know the manual release."],
  "special": ["Powershare outlets can power tools or a house.", "IIHS rated crashworthiness 'good' in 2025."]},
 "nl": {
  "intro": "Tesla's roestvrijstalen pick-up, te koop in Noord-Amerika, Zuid-Korea en het Midden-Oosten. Niet toegelaten in de EU en het VK.",
  "specs": [("Gebouwd", "sinds eind 2023, Austin"), ("Accu", "123 kWh, 800 V-architectuur"), ("Bereik", "ongeveer 480 tot 550 km (EPA)"),
            ("Trekgewicht", "tot 4.990 kg"), ("Laadbak", "1,8 m, 1.900 l"), ("Besturing", "steer-by-wire met meesturende achterwielen"),
            ("Prijs", "vanaf $ 59.990 (AWD, 2026)")],
  "watch": ["Meer dan tien terugroepacties sinds de lancering; check of alles is uitgevoerd.", "Roestvrij staal toont vlekken en kan oppervlakteroest laten zien.", "Elektrische deuren: weet waar de noodontgrendeling zit."],
  "special": ["Powershare-stopcontacten voor gereedschap of zelfs je huis.", "IIHS beoordeelde de botsveiligheid in 2025 als 'goed'."]}},
"cybertruck-awd": {"sources": [W_CT], "en": {
  "intro": "The dual-motor Cybertruck, since 2026 also as a cheaper base version.",
  "specs": [("Power", "600 hp, two motors"), ("0–60 mph", "4.1 s"), ("Range", "about 314–340 miles EPA"), ("Towing", "11,000 lb"),
            ("Payload", "2,200–2,500 lb"), ("Weight", "6,660 lb (3,020 kg)"), ("Price", "from $59,990")],
  "watch": ["The 2026 base AWD has fewer luxury features than the earlier AWD.", "Check the recall history by VIN."],
  "special": ["The volume Cybertruck: best balance of range, towing and price."]},
 "nl": {
  "intro": "De Cybertruck met twee motoren, sinds 2026 ook als goedkopere basisversie.",
  "specs": [("Vermogen", "600 pk, twee motoren"), ("0–96 km/u", "4,1 s"), ("Bereik", "ongeveer 505–550 km (EPA)"), ("Trekgewicht", "4.990 kg"),
            ("Laadvermogen", "1.000–1.130 kg"), ("Gewicht", "3.020 kg"), ("Prijs", "vanaf $ 59.990")],
  "watch": ["De AWD-basisversie van 2026 heeft minder luxe dan de eerdere AWD.", "Check de terugroepgeschiedenis via het VIN."],
  "special": ["De volume-Cybertruck: beste balans tussen bereik, trekvermogen en prijs."]}},
"cybertruck-cyberbeast": {"sources": [W_CT], "en": {
  "intro": "The tri-motor top version of the Cybertruck.",
  "specs": [("Power", "845 hp, three motors"), ("0–60 mph", "2.6 s"), ("Top speed", "130 mph"), ("Range", "about 301–320 miles EPA"),
            ("Payload", "2,000–2,270 lb"), ("Weight", "6,901 lb (3,130 kg)"), ("Price", "under $100,000 since 2026")],
  "watch": ["Since 2026 FSD is no longer included.", "Tires wear quickly with this much power and weight."],
  "special": ["A 3-tonne pickup that beats many sports cars off the line."]},
 "nl": {
  "intro": "De topversie van de Cybertruck met drie motoren.",
  "specs": [("Vermogen", "845 pk, drie motoren"), ("0–96 km/u", "2,6 s"), ("Topsnelheid", "209 km/u"), ("Bereik", "ongeveer 485–515 km (EPA)"),
            ("Laadvermogen", "900–1.030 kg"), ("Gewicht", "3.130 kg"), ("Prijs", "onder $ 100.000 sinds 2026")],
  "watch": ["Sinds 2026 zit FSD er niet meer standaard bij.", "Banden slijten snel door het vermogen en gewicht."],
  "special": ["Een pick-up van drie ton die veel sportwagens verslaat bij het wegrijden."]}},
# ---------------------------------------------------------------- Others
"cybercab": {"sources": [("TrendingTesla — Cybercab specs explained", "/cybercab-specs-explained-battery-range-charging/")], "en": {
  "intro": "Tesla's two-seat robotaxi without steering wheel or pedals, carrying paying passengers in Austin since September 2026.",
  "specs": [("Seats", "2"), ("Battery", "48 kWh, 4680 cells"), ("Range", "about 293 miles (472 km), preliminary EPA"), ("Power", "219 hp (163 kW)"),
            ("Weight", "1,412 kg"), ("Charging", "DC only (NACS), wireless planned"), ("Software", "unsupervised FSD on modified HW4")],
  "watch": ["Not for sale to private buyers; fleet interest only.", "NHTSA is investigating how the car was certified."],
  "special": ["Designed for the lowest possible cost per mile.", "Butterfly doors and no driver controls."]},
 "nl": {
  "intro": "Tesla's tweezits robotaxi zonder stuur of pedalen, sinds september 2026 met betalende passagiers in Austin.",
  "specs": [("Zitplaatsen", "2"), ("Accu", "48 kWh, 4680-cellen"), ("Bereik", "ongeveer 472 km, voorlopig EPA"), ("Vermogen", "219 pk (163 kW)"),
            ("Gewicht", "1.412 kg"), ("Laden", "alleen DC (NACS), draadloos gepland"), ("Software", "FSD zonder toezicht op aangepaste HW4")],
  "watch": ["Niet te koop voor particulieren; alleen interesse voor vloten.", "De NHTSA onderzoekt hoe de auto is gecertificeerd."],
  "special": ["Ontworpen voor de laagst mogelijke kosten per kilometer.", "Vlinderdeuren en geen bedieningselementen voor een bestuurder."]}},
"semi": {"sources": [("TrendingTesla — Semi factory opens", "/tesla-semi-factory-opening-first-deliveries/")], "en": {
  "intro": "Tesla's electric heavy truck, in series production in Nevada since 2026.",
  "specs": [("Long Range", "up to 500 miles (800 km), about $290,000"), ("Standard Range", "325 miles (520 km), about $260,000"),
            ("Charging", "Megacharger up to 1.2 MW"), ("Factory", "Nevada, up to 50,000 trucks a year"), ("Europe", "deliveries planned for 2027")],
  "watch": ["Needs Megacharger access along the routes.", "High-volume production has slipped to 2027."],
  "special": ["Central driving position.", "Most of the range back in about 30 minutes at a Megacharger."]},
 "nl": {
  "intro": "Tesla's elektrische vrachtwagen, sinds 2026 in serieproductie in Nevada.",
  "specs": [("Long Range", "tot 800 km, ongeveer $ 290.000"), ("Standard Range", "520 km, ongeveer $ 260.000"),
            ("Laden", "Megacharger tot 1,2 MW"), ("Fabriek", "Nevada, tot 50.000 trucks per jaar"), ("Europa", "leveringen gepland in 2027")],
  "watch": ["Heeft Megachargers langs de route nodig.", "Productie in grote aantallen is naar 2027 verschoven."],
  "special": ["Bestuurder in het midden.", "Het grootste deel van het bereik in ongeveer 30 minuten terug aan een Megacharger."]}},
"roadster": {"sources": [("TrendingTesla — Roadster unveiled", "/tesla-roadster-unveil-what-we-know/")], "en": {
  "intro": "Tesla's next-generation sports car, unveiled in October 2026 with cold-gas thrusters. Production is planned for 2028.",
  "specs": [("0–60 mph", "about 1 s (claimed)"), ("Top speed", "over 230 mph (claimed)"), ("Range", "about 300 miles (claimed)"),
            ("Versions", "Performance · Thrust · Rocket"), ("Deposit", "$50,000 (Performance)")],
  "watch": ["All figures are Tesla claims; no independent tests yet.", "The original 2017 Roadster was delayed for years."],
  "special": ["Cold-gas thrusters, developed with SpaceX."]},
 "nl": {
  "intro": "Tesla's nieuwe sportwagen, in oktober 2026 onthuld met koudgas-stuwraketjes. Productie is gepland voor 2028.",
  "specs": [("0–96 km/u", "ongeveer 1 s (claim)"), ("Topsnelheid", "ruim 370 km/u (claim)"), ("Bereik", "ongeveer 480 km (claim)"),
            ("Versies", "Performance · Thrust · Rocket"), ("Aanbetaling", "$ 50.000 (Performance)")],
  "watch": ["Alle cijfers zijn claims van Tesla; nog geen onafhankelijke tests.", "De originele Roadster uit 2017 liep jarenlang vertraging op."],
  "special": ["Koudgas-stuwraketjes, ontwikkeld samen met SpaceX."]}},
}


# Battery chemistry per model/version: (en, nl). Inserted after the battery row, or as the second row.
BATTERY_TYPE = {
    "model-s": ("Lithium-ion, 18650 cells (NCA, Panasonic)", "Lithium-ion, 18650-cellen (NCA, Panasonic)"),
    "model-s-classic": ("Lithium-ion, 18650 cells (NCA, Panasonic)", "Lithium-ion, 18650-cellen (NCA, Panasonic)"),
    "model-s-2021": ("Lithium-ion, 18650 cells (NCA, Panasonic)", "Lithium-ion, 18650-cellen (NCA, Panasonic)"),
    "model-s-plaid": ("Lithium-ion, 18650 cells (NCA, Panasonic)", "Lithium-ion, 18650-cellen (NCA, Panasonic)"),
    "model-3": ("2170 cells: LFP in base versions, nickel-based (NCA/NCM) in Long Range and Performance",
                "2170-cellen: LFP in basisversies, nikkelhoudend (NCA/NCM) in Long Range en Performance"),
    "model-3-classic": ("2170 cells: nickel-based (NCA/NCM); LFP in Standard Range Plus/RWD from 2021",
                        "2170-cellen: nikkelhoudend (NCA/NCM); LFP in Standard Range Plus/RWD vanaf 2021"),
    "model-3-highland": ("LFP (RWD); nickel-based NCA/NCM (Premium, Performance)", "LFP (RWD); nikkelhoudend NCA/NCM (Premium, Performance)"),
    "model-3-standard": ("LFP (lithium iron phosphate)", "LFP (lithium-ijzerfosfaat)"),
    "model-3-performance": ("Nickel-based lithium-ion (NCA/NCM), 2170 cells", "Nikkelhoudend lithium-ion (NCA/NCM), 2170-cellen"),
    "model-x": ("Lithium-ion, 18650 cells (NCA, Panasonic)", "Lithium-ion, 18650-cellen (NCA, Panasonic)"),
    "model-x-classic": ("Lithium-ion, 18650 cells (NCA, Panasonic)", "Lithium-ion, 18650-cellen (NCA, Panasonic)"),
    "model-x-2021": ("Lithium-ion, 18650 cells (NCA, Panasonic)", "Lithium-ion, 18650-cellen (NCA, Panasonic)"),
    "model-x-plaid": ("Lithium-ion, 18650 cells (NCA, Panasonic)", "Lithium-ion, 18650-cellen (NCA, Panasonic)"),
    "model-y": ("LFP in base versions, nickel-based (NCA/NCM) in Long Range and Performance; 4680 cells in some Texas-built cars",
                "LFP in basisversies, nikkelhoudend (NCA/NCM) in Long Range en Performance; 4680-cellen in sommige auto's uit Texas"),
    "model-y-classic": ("2170 nickel-based (NCA/NCM); LFP in Standard Range; 4680 cells in some Texas-built AWD",
                        "2170 nikkelhoudend (NCA/NCM); LFP in Standard Range; 4680-cellen in sommige AWD's uit Texas"),
    "model-y-juniper": ("LFP (RWD); nickel-based NCA/NCM (Long Range/Premium)", "LFP (RWD); nikkelhoudend NCA/NCM (Long Range/Premium)"),
    "model-y-standard": ("Lithium-ion; chemistry differs by factory (LFP or nickel-based)", "Lithium-ion; chemie verschilt per fabriek (LFP of nikkelhoudend)"),
    "model-y-performance": ("Nickel-based high-density pack (LG '5M' cells)", "Nikkelhoudend accupakket met hoge dichtheid (LG '5M'-cellen)"),
    "model-y-l": ("Nickel-based lithium-ion (NCM)", "Nikkelhoudend lithium-ion (NCM)"),
    "cybertruck": ("4680 cells, nickel-based (NCM), 800 V", "4680-cellen, nikkelhoudend (NCM), 800 V"),
    "cybertruck-awd": ("4680 cells, nickel-based (NCM), 800 V", "4680-cellen, nikkelhoudend (NCM), 800 V"),
    "cybertruck-cyberbeast": ("4680 cells, nickel-based (NCM), 800 V", "4680-cellen, nikkelhoudend (NCM), 800 V"),
    "cybercab": ("4680 cells (Tesla's own)", "4680-cellen (eigen Tesla-cellen)"),
    "semi": ("Lithium-ion (cell type not disclosed by Tesla)", "Lithium-ion (celtype niet bekendgemaakt door Tesla)"),
    "roadster": ("Not disclosed yet", "Nog niet bekendgemaakt"),
}
for _k, (_en, _nl) in BATTERY_TYPE.items():
    for _lang, _val, _lbl, _acc in (("en", _en, "Battery type", "Battery"), ("nl", _nl, "Accutype", "Accu")):
        _specs = INFO[_k][_lang]["specs"]
        _i = next((i + 1 for i, (lab, _) in enumerate(_specs) if lab == _acc), 1)
        _specs.insert(_i, (_lbl, _val))

INFO["cybercab"]["en"]["special"] = ["No steering wheel and no pedals: the car only drives itself.", "Butterfly doors.", "Designed for the lowest possible cost per mile."]
INFO["cybercab"]["nl"]["special"] = ["Geen stuur en geen pedalen: de auto rijdt alleen zelf.", "Vlinderdeuren.", "Ontworpen voor de laagst mogelijke kosten per kilometer."]
