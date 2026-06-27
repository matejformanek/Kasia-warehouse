"""Curated public-site content — decoupled from the warehouse DB (decision 0051).

Single source of truth for the company facts and locations rendered across the
public pages, the footer, and the JSON-LD structured data. Czech-only for the
first build; templates are i18n-ready so EN/RU can layer on later.

⚠ TYN/SEZ street addresses + per-branch phones are NOT in the repo. They carry
explicit "doplnit od Petra" placeholders — do not invent addresses (decision
0051, context/warehouses.md).
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
    "email": "info@kasia.cz",
    "hours": "Po–Pá 7:00–15:00",
    # Proof stat from the business (company-profile.md / old kasia.cz).
    "spice_count": "369",
    "product_count": "236",
}

# --- Provozovny (context/warehouses.md) -------------------------------------
# `address` / `phone` left as None where the repo does not have the data →
# the template renders a "doplnit od Petra" note instead of a fabricated value.
PROVOZOVNY = [
    {
        "name": "Říčany u Prahy",
        "role": "Sídlo společnosti",
        "street": "Nádražní 1202/5",
        "city": "Říčany u Prahy",
        "postal_code": "251 01",
        "phone": "+420 323 601 422",
        "hours": "Po–Pá 7:00–15:00",
        "note": "",
        "map_query": "Kasia vera, Nádražní 1202/5, Říčany u Prahy",
    },
    {
        "name": "Týniště nad Orlicí",
        "role": "Provozní sklad",
        "street": None,
        "city": "Týniště nad Orlicí",
        "postal_code": None,
        "phone": None,
        "hours": "Po–Pá 7:00–15:00",
        "note": "Přesnou adresu a telefon doplníme od Petra.",
        "map_query": "Týniště nad Orlicí",
    },
    {
        "name": "Sezimovo Ústí",
        "role": "Provozní sklad",
        "street": None,
        "city": "Sezimovo Ústí",
        "postal_code": None,
        "phone": None,
        "hours": "Po–Pá 7:00–15:00",
        "note": "Přesnou adresu a telefon doplníme od Petra.",
        "map_query": "Sezimovo Ústí",
    },
]

# --- Public navigation (leaves clean room for deferred pages) ---------------
NAV = [
    {"label": "Domů", "url_name": "web:home"},
    {"label": "O nás", "url_name": "web:o_nas"},
    {"label": "Provozovny", "url_name": "web:provozovny"},
    {"label": "Kontakt", "url_name": "web:kontakt"},
]
