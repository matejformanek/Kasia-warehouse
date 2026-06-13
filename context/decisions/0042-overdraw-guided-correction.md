# 0042 — Overdraw policy: guided correction, not silent refusal

**Date:** 2026-06-13
**Decider:** Matej (relaying operational reality)
**Status:** Active

## Context

When an operator submits a výdej where the requested quantity
exceeds current stock for at least one line, the previous behaviour
was a flat refusal:

- `_apply_line_to_stock` inside `apply_movement` raised
  `ValidationError({"lines": "Nedostatek na skladě …"})` for the
  first violating line.
- The view rebound the formset to the form so the user kept their
  typed values, but they got a generic error and no path forward.

In the 2026-06-12 walkthrough Matej flagged this as a real-world
problem: stock counts drift between system and warehouse, and the
"výdej > stock" case is overwhelmingly **a sign that the system
stock is wrong**, not that the operator is trying to oversell. The
right reaction is:

> "Promptovat k tomu že musí upravit zboží, případně nabídnout
> přímo položky kterých není dostatek na úpravu, a tedy možnost
> přidání reálného stavu aktuálně."

i.e. *prompt the operator to fix the stock, and offer the specific
items that are short, with a direct path to the stock-adjustment
screen.*

## Options considered

1. **Hard refuse (status quo).** Refuse with a generic message;
   operator figures it out alone. Rejected — already in the
   walkthrough feedback as too unhelpful.
2. **Allow with "force checkbox" for vlastník.** Stock would go
   below zero but be flagged. Rejected: lets bad data accumulate;
   doesn't solve the root cause (wrong stock count). Bypasses the
   audited path we built in [`0041`](./0041-manual-stock-adjustment.md).
3. **Guided correction.** Refuse, but with a structured prompt
   listing the insufficient items + a one-click path to the stock
   adjustment screen. After the operator corrects the count, they
   re-submit the výdej. **Chosen.**
4. **Auto-create the adjustment movement inline.** "Stock says 10,
   you typed 12, so we'll +2 the stock and proceed." Rejected:
   silently writes data that's actually a manual decision; the
   operator might mean "the výdej is wrong", not "the stock is
   wrong".

## Choice

**Option 3: guided correction.**

### Mechanics

In `vydej_create` and `vydej_edit` (the two routes that touch
Stock through `apply_movement` / `edit_movement` from a form
submit), **pre-check** the requested-vs-current stock for every
line *before* calling the service:

```python
warnings = _compute_overdraw(branch, requested_lines)
if warnings:
    # Re-render form with structured `overdraw_warnings` context.
    return _render_form_with_warnings(form, formset, warnings)
```

`warnings` is a list of dicts: `{product, branch, requested,
current, shortfall}`. The template renders a "Nedostatek na
skladě" card above the form with one row per insufficient item.

### Operator affordances

Per row in the warning card:

- **Vlastník**: a "Upravit stav skladu" button that opens
  `/katalog/<product-pk>/upravit-stav/?branch=<CODE>` in a new tab
  (so the výdej form stays open). Operator fixes the count, comes
  back, re-submits.
- **Obsluha**: the same card without the button — instead a
  read-only "Kontaktujte vlastníka pro úpravu stavu" note.
  Per [`0040`](./0040-operator-crud-tiering.md) stock direct edit
  is vlastník-only.

### Atomicity preserved

The výdej still saves as one atomic operation. The pre-check is a
read-only convenience; if anything still fails inside
`apply_movement` (race condition, e.g. someone else just wrote a
parallel výdej between our pre-check and the save), the existing
`ValidationError` path catches it and surfaces a generic refusal
— but in practice that path becomes vanishingly rare.

### Why not also for míchání

`mixing_job_create` already has an HTMX live preview that shows
"nedostatek" badges per component before submit (`_partials/
mixing-preview/`). The submit path uses the same `apply_movement`
under the hood and would benefit from the same structured warning
on hard refusal. **Out of scope for 0042** — separate pass; the
mixing preview already de-facto prevents most submission
overdraws.

### Live HTMX warn vs. submit-time warn

The `stock_warn_partial` HTMX endpoint stays as the *first*
feedback line ("⚠ nedostatek (skladem N)" under the quantity
input as you type). The structured submit-time warning card from
0042 is the *second* line — operators who ignore or miss the
inline warn get a stop-the-world prompt with the correction path
already laid out.

## Rationale

- **Solves the actual problem.** Overdraw is usually a stock-count
  drift; the system points at the exact items that drifted and how
  to correct them.
- **Stays auditable.** Stock corrections still go through the
  synthetic Movement path per [`0041`](./0041-manual-stock-adjustment.md);
  no new schema, no silent direct UPDATE.
- **No data corruption.** Stock can never go negative; the
  CHECK constraint on `Stock.quantity >= 0` stands.
- **Worker-friendly without giving workers stock-write power.**
  Obsluha gets the same surfacing of the problem but not the
  correction button; their workflow is "ping Karolína with the
  list", same as it would be otherwise.

## Consequences

### Code

- New helper `_compute_overdraw(branch, lines)` in
  `inventory/views.py` (or `inventory/services.py` — placement
  decision tomorrow).
- `vydej_create` + `vydej_edit` pre-check before service call;
  template renders `overdraw_warnings` card.
- Same warning card lives next to (not replacing) the existing
  formset error display, so the operator sees both the row-level
  pointer and the structural prompt.
- New tests covering: vlastník sees correction buttons, obsluha
  sees informational message, all insufficient lines surface
  (not just the first), partial overdraw (one line short, others
  fine) refuses the whole výdej.

### Future

- Mixing job overdraw could pick up the same pattern in a follow-up.
- A future "low stock dashboard" alert can build on the same
  shortfall computation.
- If operators routinely hit overdraw during shadow-run, that's a
  signal the stock-count drift is a process problem, not a UI
  problem — `0042` doesn't prevent that diagnostic.
