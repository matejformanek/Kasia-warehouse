# Screens — index and map

This directory holds the **screen-by-screen functional design** for the Kasia
warehouse tool. One file per screen. Each file describes what a user sees,
what they can do, where they came from, and where they can go.

These files are deliberately **functional only**. No frameworks, no
components, no endpoints, no database tables. If a future agent finds itself
about to write "form field of type X" or "API call to Y", that belongs in a
later layer, not here.

The vocabulary is Czech-first (see [`../domain-glossary.md`](../domain-glossary.md)).
The audience is the owner (Petr) and the future implementer reading these
files in order, not a developer's spec.

## How to read a screen file

Every screen uses the structure laid out in [`_template.md`](_template.md):

- **Purpose** — what user problem the screen solves.
- **Who uses it** — roles, devices, frequency.
- **What it shows** — visible information.
- **What you can do here** — available actions.
- **What it links to / from** — navigation in and out.
- **Business rules & validation** — what's required, forbidden, auto-filled.
- **States** — empty, normal, error, post-action.
- **What this screen explicitly does NOT do** — boundary statements.
- **Open questions for this screen** — deferred items, cross-referenced to
  [`../open-questions.md`](../open-questions.md).

## Screen list

### Authentication & home

- [01 — Přihlášení / Login](01-prihlaseni.md)
- [02 — Přehled vlastníka / Owner dashboard](02-prehled-vlastnik.md)
- [03 — Přehled pobočky / Branch stock view](03-prehled-pobocky.md)

### Catalogue

- [04 — Katalog produktů / Product catalogue](04-katalog-produktu.md)
- [05 — Detail produktu / Product detail](05-detail-produktu.md)

### Daily movements

- [06 — Příjem zboží / Receive goods](06-prijem-zbozi.md)
- [07 — Výdej zboží / Issue goods](07-vydej-zbozi.md) — default
  odběratel = Říčany per
  [`../decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md);
  no separate "Převod do Říčan" screen.

### Dodací listy

- [08 — Seznam dodacích listů / Delivery notes list](08-seznam-dodacich-listu.md)
- [09 — Detail dodacího listu / Delivery note detail](09-detail-dodaciho-listu.md)

### History and corrections

- [10 — Historie pohybů / Movement history](10-historie-pohybu.md)
- [11 — Úprava pohybu / Edit historical movement](11-uprava-pohybu.md)

### Administration

- [13 — Správa uživatelů / User management](13-sprava-uzivatelu.md)
- [14 — Nastavení / Settings](14-nastaveni.md)

### Production

- [15 — Míchání směsi / Mixing job](15-michani.md) — in MVP per
  [`../decisions/0032-mixing-in-mvp.md`](../decisions/0032-mixing-in-mvp.md).

### Support & help

- [16 — Podpora / Support](16-podpora.md) — in-app docs + feedback
  log per [`../decisions/0046-support-page.md`](../decisions/0046-support-page.md).

### Future (documented, not in MVP)

- [Future — Export pro účetní / Accountant export](future-export-uctarne.md)
- [Future — Skartace / Write-off](future-skart-skarty.md)

## Screen map (reachability)

A rough text map of how a user moves between screens. Arrows mean "this
action takes you to that screen". Dashed lines mean "available from any
screen via the main navigation".

```
                  [01 Přihlášení]
                         |
                         v
            +------------+------------+
            |                         |
      role: owner / Karolína      role: branch staff
            |                         |
            v                         v
  [02 Přehled vlastníka]     [03 Přehled pobočky]
            |                         |
            +-----------+-------------+
                        |
                  (main navigation, available everywhere)
                        |
   .--------------------+---------------------.
   |          |              |        |       |
   v          v              v        v       v
[04 Katalog] [06 Příjem] [07 Výdej] [08 DL list] [10 Historie]
   |              |        |            |          |
   v              |        +---> [09 DL detail]    v
[05 Detail]       |                            [11 Úprava pohybu]
                  |
                  |
   (owner / Karolína only)
   |       |        |        |
   v       v        v        v
[13 Uživatelé]  [14 Nastavení]  [15 Míchání směsi]

Future, not in MVP:
   [future-export-uctarne]   [future-skart-skarty]
```

Notes on the map:

- After login, owner and Karolína land on [02](02-prehled-vlastnik.md);
  branch staff land on [03](03-prehled-pobocky.md) for their own branch.
- [07 Výdej](07-vydej-zbozi.md) ends at
  [09 Detail dodacího listu](09-detail-dodaciho-listu.md). Internal
  výdeje to Říčany also use [07](07-vydej-zbozi.md) — Říčany is the
  default odběratel per
  [`../decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md),
  not a separate screen.
- [11 Úprava pohybu](11-uprava-pohybu.md) is reachable only from
  [10 Historie pohybů](10-historie-pohybu.md), and only for owner /
  Karolína.
- [15 Míchání směsi](15-michani.md) is in MVP per
  [`../decisions/0032-mixing-in-mvp.md`](../decisions/0032-mixing-in-mvp.md).
- [13](13-sprava-uzivatelu.md) and [14](14-nastaveni.md) are admin-only.
- Future screens are not reachable from MVP navigation. They are
  documented so the data model and earlier screens do not paint
  themselves into a corner.

## Forward-reference reconciliation

Foundational context files written earlier — particularly
[`../workflows.md`](../workflows.md) and
[`../product-ideology.md`](../product-ideology.md) — reference a handful of
screen filenames that **do not exist** in this directory:

- `08-odberatele.md`
- `09-dodaci-list-preview.md`
- `11-detail-pohybu.md`
- `12-audit-log.md`
- `05-katalog.md`
- `future-mixing-job.md`
- `future-export-ucetni.md`
- `future-odpis.md`

Those filenames were placeholders from a parallel writing pass before the
final screen list was settled. The canonical screen names are the ones in
the index above. Mapping for anyone following an old breadcrumb:

| Placeholder (in older context files) | Canonical screen in this directory                           |
|--------------------------------------|--------------------------------------------------------------|
| `05-katalog.md`                      | [`04-katalog-produktu.md`](04-katalog-produktu.md)           |
| `08-odberatele.md`                   | Folded into [`07-vydej-zbozi.md`](07-vydej-zbozi.md) (customer picker is part of the issue flow in MVP; standalone customer-management screen is not in MVP) |
| `09-dodaci-list-preview.md`          | [`09-detail-dodaciho-listu.md`](09-detail-dodaciho-listu.md) |
| `11-detail-pohybu.md`                | Merged into [`11-uprava-pohybu.md`](11-uprava-pohybu.md) (movement detail and edit are the same screen) |
| `12-audit-log.md`                    | Folded into [`10-historie-pohybu.md`](10-historie-pohybu.md) as an "edited" filter; a standalone audit-log viewer is deferred |
| `future-mixing-job.md`               | [`15-michani.md`](15-michani.md) (promoted from `future-misseni.md` per [`../decisions/0032-mixing-in-mvp.md`](../decisions/0032-mixing-in-mvp.md)) |
| `future-export-ucetni.md`            | [`future-export-uctarne.md`](future-export-uctarne.md)       |
| `future-odpis.md`                    | [`future-skart-skarty.md`](future-skart-skarty.md)           |

If you are updating the older context files, prefer to rewrite their
forward references to the canonical names above. If you are reading them
as-is, use this table as the lookup.
