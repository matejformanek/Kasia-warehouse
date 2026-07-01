# 0061 — Quantities display at 1 dp with a Czech comma; native dialogs banned

**Date:** 2026-07-01
**Decider:** Matej (relaying Petr's ask via the live-app Podpora review)
**Status:** Active
**Relates to:**
- [`0054-adopt-ui-directions.md`](./0054-adopt-ui-directions.md) /
  [`design-system.md`](../../.claude/rules/design-system.md) — this pins a
  display convention and a dialog rule the design system now records.

## Context

`admin@kasia.cz` (live-app Podpora, 2026-07-01) asked for two presentation
fixes:

1. **Decimals.** Quantities render at **3 dp** today (`floatformat:"3"`), which
   is noise for kg spice amounts. Show **1 dp** with a **Czech comma**
   everywhere, including entry fields.
2. **Native browser dialogs.** Destructive actions use JS `confirm()` — the
   browser-default look, not the app's own dialog.

## Review-verified facts

- Django 5.2 with `LANGUAGE_CODE="cs"` already localizes numbers to a comma:
  `{{ v|floatformat:1 }}` → `12,3`. **No custom template filter is needed** —
  the comma comes free from the active locale.
- All quantity entry fields are `type="number"`. Per the HTML spec these submit
  a dot-decimal regardless of locale display, so the server never receives a
  comma. **No server comma-parsing change is required** (existing
  `.replace(",", ".")` calls stay as harmless defence).
- `Movement`/`Stock`/etc. keep `decimal_places=3` at the model layer. Display
  rounds to 1 dp; stored precision is unchanged. **No migration.** Values snap
  to 0.1 on the next operator save because entry `step="0.1"`.
- JS-truth attributes (`data-current="{{ row.current|unlocalize }}"`) and the
  `value=` dot strings on `type=number` inputs must keep the **dot**
  (`|unlocalize` / view f-strings like `f"{cur:.1f}"`), never a localized
  comma — the client-side stock-warn maths and native number inputs parse dots.

## Choice

- **Display convention:** quantities render at **1 dp** via `floatformat:1`.
  The Czech comma is supplied by the active `cs` locale — no custom filter.
- **Entry:** operator quantity inputs use `step="0.1"` and stay
  `type="number"` (browser shows the comma, submits a dot). No server
  comma-parsing is added.
- **Model precision unchanged** (`decimal_places=3`, no migration); values
  round to 0.1 on the next operator save.
- **JS-truth stays dot:** `data-current`/`value=` attributes keep `|unlocalize`
  or view-side `f"{x:.1f}"` dot strings.
- **Recipe-PDF percentages stay at 2 dp** (`row.pct|floatformat:"2"`) — they
  are proportions, not kg, and the PDF has its own styling (design-system
  out-of-scope).
- **Native `confirm()`/`alert()`/`prompt()` are banned in the sklad surface.**
  Every confirm/alert uses `_confirm_dialog.html` (`.js-confirm` +
  `data-confirm-*`) or `window.kasiaConfirm(...)`.

## Rationale

The heavy lifting (comma, dot-on-submit) is already handled by the locale and
the HTML number input — so the whole decimal change collapses to a mechanical
`floatformat:"3"` → `floatformat:1` sweep plus `step` tweaks, with zero new
code and zero migration risk. Banning native dialogs makes the destructive-
action UX consistent with the sharp/green sklad look the operator already sees
on the stock-adjust screen.

## Consequences

- ~15 templates lose `floatformat:"3"` on quantities in favour of
  `floatformat:1`; `step="0.001"` inputs (templates + `inventory/forms.py`
  `NumberInput` widgets) become `step="0.1"`; inventura prefill f-strings go
  `f"{cur:.3f}"` → `f"{cur:.1f}"`.
- `_confirm_dialog.html` is included globally in `base.html`; the 10 remaining
  native `confirm()` calls are migrated to `.js-confirm` buttons.
- `design-system.md` records both rules as hard constraints.
