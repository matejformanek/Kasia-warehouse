# Nastavení / Settings

## Purpose
A small, calm place for the few configuration items that affect how the
system talks to the outside world — chiefly the dodací list e-mail
delivery and the identity block printed on the dodací list PDF. Not a
preferences gallery: Kasia is a small operation and there should be
very little to fiddle with here.

## Who uses it
- Petr and Karolína only. Desktop. Rare; mainly at first setup and
  whenever the accountant changes or the SMTP credential expires.

## What it shows
- Header "Nastavení".
- A **Společnost / hlavička dokumentu** section — what appears on every
  dodací list:
  - Název firmy: "Kasia vera s.r.o." (default, editable).
  - IČO: 25756729 (default, editable).
  - DIČ.
  - Adresa sídla (Říčany u Prahy).
  - Telefon, e-mail kontaktu.
  - Logo (the brand mark; uploadable).
  - Optional footer text.
- A **Odeslání dodacích listů** section:
  - SMTP konfigurace: server, port, šifrování, uživatel, heslo,
    odesílatel ("from") adresa a jméno. (Passwords are write-only —
    never displayed back.) Hodnoty z DB mají přednost před hodnotami
    v `.env` na serveru; prázdné pole znamená použít hodnotu z
    `.env` (per
    [`decisions/0049-smtp-source-of-truth.md`](../decisions/0049-smtp-source-of-truth.md)).
  - "Otestovat odeslání" — sends a test e-mail to the current user
    and reports success or failure.
  - **Příjemci dodacího listu** per
    [`decisions/0052-n-list-recipients-supersedes-0031.md`](../decisions/0052-n-list-recipients-supersedes-0031.md)
    (supersedes the fixed-pair UI from
    [`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md)
    in part; the "internal only / never to customers" intent stands):
    repeatable list of rows. Each row has e-mail, popisek, aktivní
    checkbox, "Souhrn dochází zboží" checkbox, pořadí. Operator clicks
    "+ Přidat příjemce" to add a row; per-row "× Smazat" to remove.
    Every dodák ships to all active rows; the daily low-stock summary
    ships only to rows with "Souhrn dochází zboží" zaškrtnuté. At
    least one active row must exist or výdej refuses. No per-customer
    remembered list, no ad-hoc additions on issue or re-send.
- A **Dodací list — formát** section:
  - **Číslování** is fixed at `<BRANCH>-<YYYY>-<NNNN>` per
    [`decisions/0008-dodaci-list-numbering.md`](../decisions/0008-dodaci-list-numbering.md);
    not user-configurable (the format is part of the schema invariant).
    The current per-branch counters are shown read-only for sanity
    checking ("Týniště: posledně TYN-2026-0042; Sez. Ústí: posledně
    SEZ-2026-0018"). Manually setting a counter is **not** exposed
    in the UI — a future support task if a counter ever needs reset.
  - **PDF šablona** — structural template described below; visual
    finalisation is Matej-ratified (typography family, signature-line
    wording, footer text, e-mail templates) and now waits only on
    Petr's logo files. See open questions.
- A **Pobočky** section — read-only list of branches with:
  - Stable three-letter **branch code** per
    [`decisions/0008-dodaci-list-numbering.md`](../decisions/0008-dodaci-list-numbering.md):
    `TYN` for Týniště nad Orlicí, `SEZ` for Sezimovo Ústí. Codes are
    set at first install and **cannot be changed** after the first
    dodací list is issued from that branch.
  - Branch name (Czech).
  - Address.
  - Říčany shown as a footnote ("HQ; bez evidence skladu" per
    [`../warehouses.md`](../warehouses.md); seeded as the default
    odběratel on výdej per
    [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md),
    not as a `Branch` row).
  - Editing branch identities beyond name/address is not in MVP.

- A **PDF šablona — struktura** subsection (under the dodací list
  formát section above) — describes the structural rules of the
  generated PDF. Structural rules and Matej-ratified visual defaults
  are locked here (2026-06-03); only Petr's logo file is still open.
  - A4 portrait, single-column. Continuation pages when lines
    overflow, with the header block repeating on each page.
  - **Typography**: sans-serif typeface with full Czech-diacritic
    coverage, embeddable in PDF, free for commercial use (ratified
    by Matej 2026-06-03 as the MVP default; the concrete font name
    follows from the eventual stack/PDF-library choice — examples
    that meet the criteria: DejaVu Sans, Source Sans, Inter).
  - **Hlavička**: logo + company identity (název, IČO, DIČ, adresa,
    kontakt) from the Společnost / hlavička dokumentu section above.
    **Logo area falls back to a text placeholder** (`Kasia vera s.r.o.`)
    until Petr supplies the logo files (Matej-ratified 2026-06-04 as
    the MVP default; not a hard blocker). When the SVG/PDF logos are
    slotted into the Společnost section, the placeholder is replaced
    on the next render.
  - **Document block**: "Dodací list <číslo>", datum vystavení,
    pobočka odeslání. The `[OPRAVA]` marker per
    [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md)
    appears under the číslo when the dodák has been corrected (with
    the version count).
  - **Odběratel block**: name, IČO, DIČ (if set), billing/delivery
    address.
  - **Line table** with columns: pořadí, **product** (e.g. "Oregano"
    per
    [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md)),
    množství v kg, šarže (column rendered only when at least one
    line has šarže recorded per
    [`decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md)),
    poznámka (rendered only when at least one line has a note).
    **No price column** per
    [`decisions/0029-no-prices-supersedes-0011.md`](../decisions/0029-no-prices-supersedes-0011.md)
    and
    [`decisions/0010-prices-on-dodaci-list.md`](../decisions/0010-prices-on-dodaci-list.md).
  - **Podpisová řádka**: ratified wording **"Předal / Převzal"** with
    `datum` and `podpis` fields under each label (Matej ratified
    2026-06-03 as the MVP default; standard CZ B2B convention).
    Editable in the company section if Petr later prefers different
    wording.
  - **Patička**: page "Strana N z M" plus the footer text from the
    company section. **Default footer text** (ratified by Matej
    2026-06-03): `Kasia vera s.r.o. · IČO 25756729 · Říčany u Prahy`.
    Pre-seeded into the Optional footer text field on first install;
    editable. A longer footer (telefon, web, e-mail) is available if
    Petr later wants a contact patička.
- A **Šablony e-mailů** subsection (under Odeslání dodacích listů
  above) — the default Czech wording for the two automatic e-mails,
  ratified by Matej 2026-06-03 as the MVP default. Editable per
  template; Karolína / Petr can tweak the tone in-place without a
  code change.
  - **Initial send** (nový dodací list):
    - *Předmět*: `Dodací list <číslo> — Kasia vera`
    - *Tělo*: `Dobrý den, v příloze posíláme dodací list <číslo>
      ze dne <datum>. S pozdravem, Kasia vera s.r.o.`
  - **Oprava re-send** per
    [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md):
    - *Předmět*: `[OPRAVA] Dodací list <číslo> — Kasia vera`
    - *Tělo*: `Dobrý den, opravujeme dříve zaslaný dodací list
      <číslo>. Důvod: <text zdůvodnění od operátorky>. Nová verze
      v příloze nahrazuje předchozí. S pozdravem, Kasia vera s.r.o.`
  - Placeholders (`<číslo>`, `<datum>`, `<text zdůvodnění od
    operátorky>`) are substituted by the system at send time.
- A small "Verze aplikace" footer.

## What you can do here
- Edit company / header values.
- Upload / replace logo.
- Edit SMTP configuration.
- Send a test e-mail.
- Edit the fixed dodací list recipients (Petr + Karolína).
- (When the numbering question is decided) configure the numbering
  scheme.
- Save changes per section.

## What it links to / from
- Reached from:
  - Main navigation (admin section), owner-level users only.
- Goes to:
  - Stays within settings; no outbound navigation in MVP.

## Business rules & validation
- Only owner-level users.
- Both Petr's and Karolína's e-mail addresses must look like valid
  e-mails; neither may be empty per
  [`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md).
- SMTP test result is shown inline; if it fails, the existing
  configuration remains until the user saves new values.
- Logo is an image of reasonable size; the screen rejects something
  obviously wrong (huge file, wrong format).
- Changes take effect for **future** dodací listy; historical PDFs are
  re-rendered on demand using the **current** template (per
  [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md)).
  A re-emailed historical dodák carries today's logo / footer — a
  trade-off favouring "one source of truth" over preserving
  historical visual exactness.
- The company name and IČO are pre-seeded with Kasia vera's values
  (per [`../company-profile.md`](../company-profile.md)) but are
  editable in case of legal-name changes.
- Numbering scheme is the format from
  [`decisions/0008-dodaci-list-numbering.md`](../decisions/0008-dodaci-list-numbering.md);
  no operator-facing toggle exists to switch schemes. The counters
  themselves advance automatically.

## States
- **Normal:** sections populated with current values.
- **Edit-in-progress:** "Uložit" / "Zrušit" enabled per section.
- **Validation error:** inline messages per offending field.
- **SMTP test running:** "Odesílám testovací e-mail…" state.
- **SMTP test result:** success or failure message visible until the
  user dismisses or makes a change.
- **After successful save:** stay on this screen with a transient
  per-section confirmation.

## What this screen explicitly does NOT do
- Does not configure user accounts — that is on
  [Správa uživatelů](13-sprava-uzivatelu.md).
- Does not configure catalogue items.
- Does not configure suppliers or customers (those live in their
  respective pickers).
- Does not expose per-user preferences (no themes, no language toggles
  — Czech-only in MVP).
- Does not export or back up data — operational handover concern, out
  of scope for the application surface.

## Open questions for this screen
- **PDF logo files from Petr** — Kasia vera mark + VERA GURMET mark
  (SVG/PDF preferred, largest PNG/JPG acceptable as fallback). Per
  Matej 2026-06-04: the PDF template renders with a text placeholder
  (`Kasia vera s.r.o.`) in the logo area until Petr supplies the
  files; not a hard blocker. Typography, signature-line wording,
  footer text and e-mail templates are ratified by Matej 2026-06-03
  (see the PDF šablona — struktura and Šablony e-mailů subsections
  above).
- Whether to surface a **backup / export** affordance here for
  operational reassurance — defer; depends on hosting decision (which
  comes after Petr signs off the design).

> Numbering scheme is closed by
> [`decisions/0008-dodaci-list-numbering.md`](../decisions/0008-dodaci-list-numbering.md).
> E-mail recipients model is closed by
> [`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md).

## UX refresh — Phase 2 (2026-07-03)

Nastavení restyled per mockup `16`: airy section cards + anchor chips + sticky
save bar; all radii 0, `#fbe8e8` -> `.non-form-errors`. Every real form field,
recipient formset, SMTP test, and branch tables preserved.
