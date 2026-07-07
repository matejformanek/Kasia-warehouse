# 0074 — Event-driven low-stock alert e-mail (replaces the daily cron)

**Date:** 2026-07-05
**Decider:** Matej (relaying Petr's ask)
**Status:** Active
**Supersedes:** [`0045`](./0045-low-stock-summary-email.md) (daily-cron summary
model — the § "(1) Daily summary, not per-event", § "(3) Cron wiring", and the
`mail_low_stock_summary` command it unblocked). Implicitly supersedes the
"mailing untouched" clause of [`0072`](./0072-reorder-threshold-not-null.md).
**Builds on:** [`0043`](./0043-reorder-threshold.md) (threshold + `effective_kg`),
[`0044`](./0044-reservations-planned-states.md) (reservations feeding
`effective_kg`), [`0072`](./0072-reorder-threshold-not-null.md) (Katalog grouping
predicate).

## Context

The "Dochází zboží" e-mail from [`0045`](./0045-low-stock-summary-email.md) was a
**daily summary** meant to run from cron — but it was **never automated**. The
only cron on the box is the nightly DB backup (`compose.yaml`); no systemd timer
or crontab entry for `mail_low_stock_summary` was ever added (the provisioning
handoff only *noted* a crontab line "to add later"). The command only ever fired
when someone ran `make mail-low-stock` locally. Result: the owner received zero
low-stock e-mails in over a week of prod uptime — not broken, just never scheduled.

Petr's actual want, restated: **the moment a stock movement pushes a product
below its reorder threshold when it wasn't before, send an e-mail immediately** —
one e-mail per movement listing every product that just crossed. No cron, no
daily digest. (This is the "per-event trigger" option 0045 rejected in 2026-06 as
too complex; a week of silence changed the trade-off.)

SMTP is confirmed working on prod (dodací-list e-mails arrive), so the alert
reuses the same working send path — no new infrastructure.

## Options considered

1. **Wire the existing daily cron.** Add the crontab entry the handoff describes.
   Rejected: doesn't match "the moment stock changes"; a morning digest is a
   day late and the owner already found the silence surprising.
2. **Event-driven alert at the movement chokepoints, transition-only.** Fire when
   a (product, branch) pair crosses *into* the alert set on a movement. **Chosen.**
3. **Event-driven with a last-alerted-state / cooldown model.** A per-pair
   `last_alerted_at` to suppress re-sends. Rejected as over-scale — the
   above→below *transition* check is already the idempotency (an already-low
   product dropping further does not re-alert), so no extra model is needed for
   ~6 users. `right-sized-for-small-business.md`.

## Choice

### (1) Trigger at the two movement chokepoints

`apply_movement` (DONE branch only) and `edit_movement` in
`inventory/services/movement.py` — the two functions every real stock-down path
funnels through. This covers direct výdej, mixing consume (internal výdej via
`apply_movement` — the alert still fires; only the *dodák* is skipped for
internal counterparties), transfer legs, stock adjustments / inventura (synthetic
movements via `apply_movement`), and mixing finish/cancel (via `edit_movement`).

Planned-príjem confirmation (`confirm_planned_receipt`) is `+1`-only — it can only
*raise* stock, so it is not instrumented. **Reservation-only actions** (planning a
mixing job / transfer) are out of scope by design: they are plans, not movements.
A planned transfer's reservation already lowers `effective` at plan time, so
*executing* it nets to no new crossing.

### (2) Crossing = per-`(product, branch)` transition into the alert set

Evaluated **per pair** with `effective_kg(product, branch)` (= `Stock.quantity −
reserved_kg`) — the same per-pair unit as `low_stock_rows()` and the dashboard
"Dochází zboží" panel, **not** the Katalog's product-aggregated `effective_total`.
The membership predicate (the union of the Katalog "Prázdné" + "Dochází" groups,
i.e. NOT "V pořádku", per 0072):

```
below_alert(effective, threshold) := effective <= 0
                                     OR (threshold is not None AND effective < threshold)
```

This is broader than `low_stock_rows`' bare `effective < threshold` on purpose: it
also catches a product hitting exactly 0 when its threshold is 0 (the Prázdné
case). The alert fires only when `below_alert` is **False before** and **True
after** — so a product that was already low and drops further does **not**
re-alert. That transition check *is* the idempotency; no cooldown/last-alert model.

### (3) Snapshot-before / recompute-at-commit

Mirrors the dodák pattern `_send_dodaci_on_commit`; avoids mid-transaction
reserved double-counting:

1. Before mutating, `capture_low_stock_state(pairs)` records
   `{(product_id, branch_id): below_alert(...)}` for every affected pair (query
   sees pre-mutation stock).
2. After the atomic block, a `transaction.on_commit(...)` callback re-queries
   current `effective`/`threshold` (post-commit, final state) and e-mails the
   pairs now below that weren't before. A rollback discards the callback.

### (4) No double-e-mail on multi-`apply_movement` operations

A transfer runs two `apply_movement` calls in one outer transaction → two
callbacks register, but the stock-*raising* leg (target-branch príjem, `+1`)
computes an empty crossing set and sends nothing; only the depleting leg can
produce content. Mixing consume is a single `apply_movement` with multiple
component lines → one e-mail listing all crossed components. So **at most one
content-bearing e-mail per user operation**.

### (5) Template reuse, no migration; fail-silent

The alert reuses the existing `Settings.template_low_stock_subject/body`
(placeholders `<datum>` + `<seznam>` = the crossed rows) and the
`_active_low_stock_recipients` / `_smtp_connection_from_settings` /
`_format_low_stock_list` helpers. **No new `Settings` fields, no migration.**
Recipients are active `SettingsRecipient` rows with `is_low_stock_recipient=True`;
no subscribers → skip silently. The send runs post-commit in an `on_commit`
callback, so it is wrapped in `try/except` + `logging` and never raises into the
request (same swallow-and-log posture as `send_dodaci_list_email`).

## Rationale

- **Matches "the moment stock changes."** The alert lands with the movement, not
  the next morning.
- **Stateless idempotency.** The above→below transition check needs no
  `last_alerted_at` column — the pre-mutation snapshot is the whole state.
- **Reuses proven paths.** Same SMTP, same templates, same recipient model, same
  `on_commit` deferral the dodák already uses. No cron, no new infra, no migration.
- **One source of truth for membership.** `_below_alert` ties to the 0072 Katalog
  grouping and the dashboard `low_stock_rows` per-pair `effective`.

## Date & by-whom

2026-07-05 — Matej (relaying Petr's ask).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `inventory/services/reorder.py` gains `_below_alert`, `capture_low_stock_state`,
  `send_low_stock_alert_for_crossings`, and `_send_low_stock_alert_email` (leaf
  layer — `movement → reorder` respects the 0068 layering, no cycle).
- `apply_movement` / `edit_movement` snapshot before mutating and register the
  `on_commit` alert callback alongside the existing dodák one.

**Removes:**

- `send_low_stock_summary` (from `reorder.py` + the services `__init__` exports).
- `inventory/management/commands/mail_low_stock_summary.py` and the
  `make mail-low-stock` Makefile target.
- The "add a crontab entry" step in `context/hetzner-provisioning-handoff.md`.

**Forecloses (without follow-on decision):**

- A cooldown / last-alerted-state model. To open, supersede this with a concrete
  noise complaint from real use.
- Reservation-time (plan-time) crossings triggering an alert. To open, instrument
  the planning services too.

**Resolves:**

- The zero-e-mail-in-a-week gap: the low-stock alert now sends without any cron.

**Cross-cutting:**

- `right-sized-for-small-business.md` — no new alerts rule file; a single e-mail
  path at ~6 users does not warrant one. This decision is the authoritative record.
