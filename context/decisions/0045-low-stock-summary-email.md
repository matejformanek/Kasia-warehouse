# 0045 — Daily low-stock summary e-mail to Petr

> **Superseded by 0074** — the daily-cron summary model here was never
> scheduled on the box; [`0074`](./0074-event-driven-low-stock-alert.md)
> replaces it with an event-driven alert that fires the moment a movement
> pushes a (product, branch) pair below threshold.

**Date:** 2026-06-14
**Decider:** Matej (relaying Petr's 2026-06-14 ask)
**Status:** Active
**Builds on:** [`0043`](./0043-reorder-threshold.md) (threshold storage
+ effective-stock helper), [`0044`](./0044-reservations-planned-states.md)
(reservations feeding `effective_kg`).

## Context

Petr's mental model: "ráno přijde e-mail s tím, co dochází". The owner
dashboard panel (0043 + 0044) is the in-app surface; the e-mail
summary is the asynchronous version Petr reads at the kitchen table
without opening the app.

## Options considered

1. **Per-event trigger.** Cross-the-threshold → send a "low oregano"
   e-mail immediately. Needs last-alerted-state tracking, snooze, and
   noisy multi-cross-per-day re-sends. Rejected: complex semantics,
   doesn't match Petr's "ráno přijde e-mail" expectation.
2. **Daily summary.** One e-mail listing all products below threshold
   somewhere. No state tracking, no snooze. **Chosen.**
3. **Real-time push / SMS.** Out of MVP and infrastructure-heavy.

## Choice

### (1) Daily summary, not per-event

A management command `mail_low_stock_summary` enumerates products
where the branch-level effective stock is below threshold somewhere
and renders **one** e-mail to `Settings.recipient_petr`. No
per-crossing trigger, no last-alerted-state tracking, no "snooze".

Rationale: simplest semantics matching Petr's mental model ("ráno
přijde e-mail s tím, co dochází").

### (2) Empty case sends nothing

No "vše v pořádku" daily. If nothing is below threshold, the command
exits 0 with `"no low stock today"` on stdout.

### (3) Cron wiring deferred to Hetzner

Locally the command is run manually via a Makefile target
(`make mail-low-stock`); the cron entry in compose / systemd lands
when the Hetzner box does. Matches
[`feedback-local-only-until-done`](../../.claude/projects/-Users-matej-Work-Kasia-warehouse/memory/feedback_local_only_until_done.md).

### (4) Templates live in `Settings`

Subject + body templates are editable like the dodák templates per
[`0037-settings-singleton.md`](./0037-settings-singleton.md).
Placeholders: `<datum>`, `<seznam>`.

Defaults:

```
subject: "Dochází zboží — <datum>"
body:    "Dobrý den, dnes je pod hranicí těchto produktů: <seznam>.
          S pozdravem, Kasia vera s.r.o."
```

`<seznam>` is rendered as a multi-line list of the form
`- <produkt> @ <branch>: efektivně <effective> kg / práh <threshold>
kg` (one row per (product, branch) below threshold).

### Recipients

Sends only to `Settings.recipient_petr` (the existing dodák recipient
field per
[`0031`](./0031-emails-internal-only-supersedes-0009.md)). Karolína is
already on every dodák; the daily summary is for Petr's morning
reading. Kept narrow to keep the operational footprint small.

## Rationale

- **One e-mail / day matches the mental model.** "Ráno přijde e-mail
  s tím, co dochází" is exactly this shape.
- **No state-machine to maintain.** Per-event would need crossing
  detection + de-dup + snooze; daily summary is stateless.
- **Reuses the `low_stock_rows()` helper.** Same rows the owner
  dashboard panel renders. One source of truth.
- **Templates editable per 0037.** Petr / Karolína can tune wording
  without a code deploy.

## Date & by-whom

2026-06-14 — Matej (relaying Petr's ask).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `inventory/management/commands/mail_low_stock_summary.py` ships.
- `inventory/services.py` gains `send_low_stock_summary() -> int |
  None` that builds the list via `low_stock_rows()` (per
  [`0044`](./0044-reservations-planned-states.md)), renders subject +
  body from `Settings.load()` templates with `<datum>` and
  `<seznam>` substituted, sends to `Settings.recipient_petr`.
  Returns count or `None` if nothing to send.
- `Settings` gains `template_low_stock_subject: CharField` and
  `template_low_stock_body: TextField` with the defaults above.
- `Makefile` gains a `mail-low-stock:` target running the command
  (uses `$(COMPOSE) run --rm web …` to match the seed/migrate
  pattern).

**Forecloses (without follow-on decision):**

- Per-event triggers / SMS / push. To open, supersede this decision
  with concrete operational justification.
- Karolína on the low-stock CC. To open, expand the recipient list
  (single-line code change once the use case is real).

**Resolves:**

- The asynchronous half of Petr's 2026-06-14 advance-warning ask.

**Cross-cutting:**

- The actual cron entry (compose / systemd) lands when the Hetzner
  box is provisioned. Locally `make mail-low-stock` is the manual
  trigger.
