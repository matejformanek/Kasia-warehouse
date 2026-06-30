"""Curated public-site content — decoupled from the warehouse DB (decision 0051).

Single source of truth for the company facts, people, and locations rendered
across the public pages, the footer, and the JSON-LD structured data. Czech-only
for the first build; templates are i18n-ready so EN/RU can layer on later.

Addresses, per-branch phones, and the executive directory are the real public
facts from kasia.cz (decision 0052 — Kontakt is now an info-only page, no form).
Map coordinates are geocoded once during development and hardcoded here; four
fixed locations don't justify a build- or run-time geocoding dependency
(right-sized-for-small-business.md).

⚠ Per-person e-mails/phones and DIČ are not public yet — they carry empty
placeholders; templates render the link only when a value exists. Do not invent
them (Matej will supply).
"""

# --- Company identity (public facts; context/company-profile.md) ------------
COMPANY = {
    "legal_name": "Kasia vera s.r.o.",
    "brand": "VERA GURMET",
    "founded_year": "1993",
    "founded_cs": "leden 1993",
    "ico": "25756729",
    "dic": "",  # doplnit od Petra, pokud je firma plátcem DPH
    "datova_schranka": "emye9prc",
    # Sídlo = Říčany u Prahy
    "street": "Nádražní 1202/5",
    "city": "Říčany u Prahy",
    "postal_code": "251 01",
    "country": "Česká republika",
    "phone_primary": "+420 323 601 422",
    "phone_secondary": "+420 323 601 424",
    "fax": "+420 323 602 077",
    "email": "info@kasia.cz",
    "hours": "Po–Pá 7:00–15:00",
    # Geocoded sídlo coordinates (Nominatim, street-level match).
    "lat": 49.9966120,
    "lng": 14.6648230,
    "map_query": "Kasia vera, Nádražní 1202/5, Říčany u Prahy",
    # Proof stat from the business (company-profile.md / old kasia.cz).
    "spice_count": "369",
    "product_count": "236",
    # Import + export/re-export reach (kasia.cz About; decision 0052 — RC Rugby
    # sponsorship omitted by Matej). Rendered as a plain list in the O nás
    # export paragraph; no per-market data beyond the country name is needed.
    "export_markets": [
        "Polsko",
        "Ukrajina",
        "Slovensko",
        "Izrael",
        "Bělorusko",
        "Nizozemsko",
    ],
}

# --- Kontaktní osoby / vedení (public directory from kasia.cz; decision 0052)-
# `email` / `phone` left "" until Matej supplies them → the template renders the
# link only when a value exists (no fabricated contacts).
EXECUTIVES = [
    {
        "name": "Ing. Jaroslav Šulc",
        "role": "Prodej",
        "email": "",
        "phone": "",
        "photo": "web/exec-sulc.jpg",
    },
    {
        "name": "Věra Kovačková",
        "role": "Administrativa",
        "email": "",
        "phone": "",
        "photo": "web/exec-kovackova.jpg",
    },
    {
        "name": "Petr Formánek",
        "role": "Nákup",
        "email": "",
        "phone": "",
        "photo": "web/exec-formanek.jpg",
    },
]

# --- Provozovny (real addresses + per-branch phones from kasia.cz) -----------
# Public content is curated and decoupled from the warehouse DB: the public site
# lists all four locations, while stock tracking stays at TYN + SEZ only
# (context/warehouses.md). `lat`/`lng` are geocoded once (Nominatim).
PROVOZOVNY = [
    {
        "name": "Říčany u Prahy",
        "role": "Sídlo společnosti",
        "is_hq": True,
        "street": "Nádražní 1202/5",
        "city": "Říčany u Prahy",
        "postal_code": "251 01",
        "phone": "+420 323 601 422",
        "hours": "Po–Pá 7:00–15:00",
        "photo": "web/branch-ricany.jpg",
        "lat": 49.9966120,
        "lng": 14.6648230,
        "map_query": "Kasia vera, Nádražní 1202/5, Říčany u Prahy",
    },
    {
        "name": "Sezimovo Ústí",
        "role": "Provozovna",
        "is_hq": False,
        "street": "Pod Kovosvitem 1096",
        "city": "Sezimovo Ústí",
        "postal_code": "391 02",
        "phone": "+420 607 190 150",
        "hours": "Po–Pá 7:00–15:00",
        "photo": "web/branch-sezimovo.jpg",
        "lat": 49.3767134,
        "lng": 14.6949753,
        "map_query": "Pod Kovosvitem 1096, 391 02 Sezimovo Ústí",
    },
    {
        "name": "Toužim",
        "role": "Provozovna",
        "is_hq": False,
        "street": "Malé náměstí 608",
        "city": "Toužim",
        "postal_code": "364 01",
        "phone": "+420 775 353 637",
        "hours": "Po–Pá 7:00–15:00",
        "photo": "web/branch-touzim.jpg",
        "lat": 50.0603089,
        "lng": 12.9890123,
        "map_query": "Malé náměstí 608, 364 01 Toužim",
    },
    {
        "name": "Týniště nad Orlicí",
        "role": "Provozovna",
        "is_hq": False,
        "street": "Turkova 77",
        "city": "Týniště nad Orlicí",
        "postal_code": "517 21",
        "phone": "+420 604 640 950",
        "hours": "Po–Pá 7:00–15:00",
        "photo": "web/branch-tyniste.jpg",
        "lat": 50.1505356,
        "lng": 16.0707600,
        "map_query": "Turkova 77, 517 21 Týniště nad Orlicí",
    },
]

# --- Embedded-map URLs (Google Maps; decision 0058) -------------------------
# Built once at import from the hardcoded coords. `output=embed` renders a Google
# Maps iframe with no API key; `map_link` opens the location in a new tab. NOTE
# (0058): Google's embed sets third-party cookies — the footer privacy note is
# worded accordingly. A consent shim is deferred (pre-launch, right-sized).
def _gmaps_embed(lat: float, lng: float) -> str:
    return f"https://maps.google.com/maps?q={lat},{lng}&z=15&hl=cs&output=embed"


def _gmaps_link(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


COMPANY["map_embed"] = _gmaps_embed(COMPANY["lat"], COMPANY["lng"])
COMPANY["map_link"] = _gmaps_link(COMPANY["lat"], COMPANY["lng"])
for _p in PROVOZOVNY:
    _p["map_embed"] = _gmaps_embed(_p["lat"], _p["lng"])
    _p["map_link"] = _gmaps_link(_p["lat"], _p["lng"])

# --- Public navigation (5 pages after 0058 promoted Sortiment/Produkty) ------
NAV = [
    {"label": "Domů", "url_name": "web:home"},
    {"label": "O nás", "url_name": "web:o_nas"},
    {"label": "Sortiment", "url_name": "web:produkty"},
    {"label": "Provozovny", "url_name": "web:provozovny"},
    {"label": "Kontakt", "url_name": "web:kontakt"},
]
