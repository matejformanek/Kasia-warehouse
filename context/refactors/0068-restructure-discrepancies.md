# 0068 restructure — discrepancy log

> Companion to [`decisions/0068`](../decisions/0068-code-architecture-restructure.md)
> + [`0069`](../decisions/0069-css-externalization.md). The restructure is
> **behavior-preserving**. Centralizing duplicated code and scattered CSS will
> surface pre-existing inconsistencies (a padding that differs between two
> screens, a guard applied on one číselník but not another, a copy-paste that
> drifted). This is the log where each is recorded and its resolution decided.

## How to use this log

For every inconsistency found while consolidating:

1. **Record it** below with: where, what differs, and the two (or more) variants.
2. **Classify the resolution:**
   - **Inert** — pure code/CSS consolidation with *no* rendered/behavioral change
     (e.g. identical rules deduped). Just note it; no approval needed.
   - **Behavior/pixel change** — the consolidation would change what a user sees
     or how the app behaves. **Do NOT fold it in silently.** Flag it, pick the
     intended variant, and get **explicit approval from Matej** before landing.
     If it's out of scope for the restructure, leave the behavior as-is and note
     it as a follow-up instead.
3. Reference the resolution in the commit that touches it.

The rule: a "no-behavior-change refactor" must actually change no behavior.
Anything that would is escalated here, not absorbed.

## Log

| # | Location | Discrepancy | Variants | Resolution | Approved? |
|---|----------|-------------|----------|------------|-----------|
| 1 | `inventory/tests.py` (6 tests) | White-box tests monkeypatched `services.<helper>`/`services.EmailMessage`; after the services split the call-sites look those names up in submodule namespaces. | patch `services.X` vs patch where used | **Inert** — re-pointed 6 monkeypatch targets to `services.dodaci_list.*` / `services.email.*` (patch where the name is looked up). Assertions unchanged; no app-behavior change. | n/a (inert) |
| 2 | D5 (test static-storage override) | Plan expected the manifest storage to require a `FileSystemStorage` test override once templates emit `{% static 'css/…' %}`. | add override vs not needed | **Not needed** — verified empirically: 73 template-rendering tests pass with the manifest present AND absent (`base.html` already used `{% static %}`; the test env resolves it without collectstatic). D5 dropped. | n/a (inert) |
| 3 | Round 2 / `base-sklad.css` `@media` blocks (0070 P2) | The KPI-column responsive overrides (`.kpis`/`.kpi` in the 720px + 480px `@media`) lived in `base-sklad.css`. Moving the base `.kpi` rules to `components/kpis.css` (loaded *after* base) while leaving the media overrides in base would flip the equal-specificity cascade → media loses → responsive KPI columns break. | leave overrides in base vs move with the rules | **Inert (fixed)** — moved the KPI `@media` overrides into `components/kpis.css` too, kept after the base `.kpi` rules. Same principle as the flagged `.over-stock`/zebra trap. Proven by per-page cascade-winner diff (0 mismatches). | n/a (inert) |
| 4 | Round 2 / CSS byte-identical proof method (0070 P2) | The plan's live `make up` browser diff couldn't run: the Chrome extension was not connected and the local admin password (`heslo1234` per the Makefile comment) does not match this DB's seeded admin. | browser spot-check vs static proof | **Inert (substituted)** — proof done statically instead, which is stronger: (a) sorted set-equality diff of original `base-sklad.css` vs new base+components (nothing lost; additions = hoisted rules only); (b) per-page **cascade-winner equivalence** for home/catalogue/customer/supplier/vydej/historie/dodák → **0 winner mismatches, 0 rules lost**; (c) `collectstatic` post-processed all 791 files; (d) 406 template-rendering tests pass. Rendered HTML bodies unchanged by construction (only `base.html`'s `<head>` gained 6 `<link>` tags). | n/a (inert) |

## Follow-ups deferred (not fixed in this restructure)

- **D3 scope (right-sizing call).** Extracted the cleanly-separable phase from
  `catalogue_index` (per-row builder → `_catalogue_rows`, 121→85 LOC). The other
  long functions were evaluated and **deliberately left cohesive**:
  `edit_movement` (186), `start_mixing_job` (183), `finish_mixing_job` (120) are
  linear `transaction.atomic` orchestrators where splitting would scatter the
  transaction flow across helpers and hurt readability; `_build_rows` (257) /
  `_row_for` (131) in inventura and `_apply_date` (128) in movements are nested
  closures over view-local state — extracting them means threading many params
  for little gain and non-trivial regression risk on tested code. Per
  `right-sized-for-small-business.md` ("reject the enterprise-shaped
  suggestion"), forcing these splits is not worth it. Revisit a specific one
  only if it actually changes (a new phase gets added).
