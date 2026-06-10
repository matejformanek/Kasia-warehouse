# 0008 — Dodací list numbering: per-branch annual sequence

## Context

Every issued dodací list needs a unique, human-readable číslo (number).
[`../workflows.md`](../workflows.md) and
[`../screens/07-vydej-zbozi.md`](../screens/07-vydej-zbozi.md) require
this on save; the accountant Karolína forwards to receives the dodáky
by e-mail and refers to them by číslo when issuing the faktura.

The choice has to satisfy:

- Uniqueness across the system, forever.
- Human-readable enough for Petr and Karolína (and the accountant) to
  reference in conversation.
- Stable across system corrections — a corrected dodací list keeps its
  číslo (per
  [`decisions/0007-auto-reissue-corrected-dodaky.md`](./0007-auto-reissue-corrected-dodaky.md):
  versions of a single dodák share the same číslo).

This was a *Decide before MVP* item in
[`../open-questions.md`](../open-questions.md).

## Options considered

- **(a) Per-branch annual sequence:** `TYN-2026-0001`,
  `SEZ-2026-0001`. Branch prefix + year + zero-padded counter.
  Counter resets on 1 January.
- **(b) Global annual sequence:** `2026-0001`. One counter for the
  whole company; resets annually.
- **(c) Global continuous sequence:** `00000001`. One counter,
  forever, no year reset.

## Choice

**(a) Per-branch annual sequence**, format `<BRANCH>-<YYYY>-<NNNN>`:

- `<BRANCH>` is a three-letter branch code: `TYN` for Týniště nad
  Orlicí, `SEZ` for Sezimovo Ústí. Codes are stable and live on the
  branch record on `screens/14-nastaveni.md`.
- `<YYYY>` is the four-digit year of issue (the date on the dodací
  list, not the system clock at print time).
- `<NNNN>` is a four-digit zero-padded counter, **per (branch, year)**,
  starting at `0001` on 1 January of each year and incrementing by
  one per dodací list issued from that branch in that year.

Internal correction versions (per
[`decisions/0007`](./0007-auto-reissue-corrected-dodaky.md)) do not
change `<NNNN>`. A dodák `TYN-2026-0042` corrected twice stays
`TYN-2026-0042`, with internal version counter 1, 2, 3 visible on the
version+send audit table.

## Rationale

- **Per-branch prefix** makes the source visible at a glance —
  Karolína and the accountant know whether a dodák came out of Týniště
  or Sez. Ústí without opening it. Matches standard Czech practice for
  multi-branch trade entities.
- **Annual reset** aligns with how Czech accounting reads the year:
  každý rok začínáme od 0001. Continuous numbering loses that
  chronological cue.
- **Four-digit counter** comfortably exceeds the expected annual
  volume per branch (well below 9 999 dodáky/year for ~6 active
  users). If a branch ever exceeds, the format widens; legacy
  numbers remain valid.
- **Year is the date-of-issue year**, not the print-time year. This
  is the rare edge: an issue dated 30 December 2026 but saved on
  3 January 2027 keeps `TYN-2026-NNNN`, because the dodací list's
  date is the legal date the goods were issued. The system enforces
  this at save time.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `screens/07-vydej-zbozi.md` — số dodacího listu is generated atomically
  on save by reserving the next counter for `(branch, year_of_issue)`.
- `screens/08-seznam-dodacich-listu.md` — the "Číslo" column renders
  the full `TYN-2026-0042` format and sorts naturally (the
  `TYN < SEZ` alphabetic order is unimportant; year and counter sort
  numerically within the per-branch view).
- `screens/09-detail-dodaciho-listu.md` — the header reads
  "Dodací list TYN-2026-0042" verbatim.
- `screens/14-nastaveni.md` — gains a "Pobočky" section where each
  branch has a stable three-letter code (`TYN`, `SEZ`). Codes can be
  set at first install and must not change after the first dodák is
  issued.
- Schema: `dodaci_list.cislo` (string) is generated server-side and is
  unique. A `(branch_id, year, counter)` triple is also stored so the
  counter is queryable and the next number is computable.

**Forecloses (without follow-on decisions):**

- Customer-specific prefixes (some businesses prefix per major
  customer). Not in MVP.
- Mid-year reset or quarterly numbering. Not in MVP.
- Number format change after first dodák is issued. Stable for life;
  reformat would break references in the accountant's records.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  MVP* › "Dodací list numbering scheme".

**Affects future decisions:**

- A future export to the accountant
  ([`../screens/future-export-uctarne.md`](../screens/future-export-uctarne.md))
  uses číslo as the natural row identifier.
- Storno / cancellation (deferred per
  `screens/09-detail-dodaciho-listu.md`) keeps the číslo and marks the
  dodák as stornováno; no number is reused.
