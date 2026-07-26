# 0099 — Auto-notify branch obsluha when a vlastník issues a výdej

**Date:** 2026-07-26
**Decider:** Matej (standing in for Petr)
**Status:** Active

## Context

Per [`0096`](./0096-manual-first-send-of-dodaky.md) every výdej creates its
dodací list in `WAITING` and sends **no** e-mail; whoever created it later clicks
„Odeslat e-mail zákazníkovi" to send the customer mail and flip `WAITING → SENT`.
Per [`0081`](./0081-per-flag-recipient-opt-ins.md) that send is also copied to the
issuer (`movement.created_by`).

A **vlastník / správce** (owner-level; no branch of their own, per
[`0074`](./0074-event-driven-low-stock-alert.md)/[`0075`](./0075-unified-email-log.md)
context) often needs a branch to physically fulfil a výdej. There is currently no
signal to the branch staff that this work is waiting — the obsluha would only find
the pending dodák by scanning the „Čeká na odeslání" list (0096).

## Options considered

1. **Opt-in checkbox on the výdej form** („požádat pobočku o vyřízení"), persisted
   as a `Movement`/`DodaciList` flag. Rejected — a vlastník issuing a customer
   výdej for a branch essentially *always* wants the branch to handle it; the
   checkbox is friction and a schema field for no real branch in behaviour.
2. **Automatic on every vlastník-created výdej.** No checkbox, no persisted flag,
   no form change — the notify is a pure side effect of the save. **Chosen.**
3. **A distinct „done" completion e-mail back to the vlastník** once the obsluha
   sends. Rejected — the existing 0081 issuer-copy of the customer send already
   lands in the vlastník's inbox and is the natural "done" signal; a second mail
   is redundant. **Rely on the 0081 copy.**

## Choice

- On `apply_movement`, when the creating user **`is_vlastnik`** and the výdej
  produced a dodák (i.e. a non-internal customer výdej), auto-e-mail that
  branch's active obsluha: "[requester] created this výdej for your branch and
  asks you to handle it", with the dodák number, customer, and a clickable detail
  link. Fired in a post-commit `on_commit` callback alongside the low-stock alert.
- No new completion e-mail on the send side — the "done" notice to the creator is
  the existing 0081 issuer-copy of the customer send.
- Logged through `send_and_log` (0075) as a new `EmailLog.Category.VYDEJ_REQUEST`.
  The row is **not** linked to the dodák (`dodaci_list=None`) — a standalone
  internal notification like `send_feedback_resolved_notification` (0098), so it
  never injects a phantom row into the dodák's „Verze a odeslání" table.

## Rationale

Automatic keeps the common case frictionless and needs no schema change. Relying
on the 0081 copy avoids a redundant second mail. Routing through `send_and_log`
keeps the send logged + failure-swallowing, so a mail outage can't roll back the
výdej. Recipients are the branch's obsluha Users (`User.branch` + `obsluha`
group), resolved fresh at send time — not a standing `SettingsRecipient` opt-in,
because the audience is definitionally "the staff of the fulfilling branch".

## Consequences

- **New `EmailLog.Category.VYDEJ_REQUEST`** („žádost o vyřízení výdeje"), riding
  an AlterField-only migration `0032`. It surfaces in the vlastník „E-maily"
  outbox by category; a resend re-sends the stored subject/body (generic path).
- **Not `SettingsRecipient`-routed** — a *third* such path alongside Oznámení
  (0097) and FEEDBACK_RESOLVED (0098). The per-flag Nastavení table (0081) does
  not gate it; recipients come from `_active_branch_obsluha_recipients(branch)`.
- **`is_vlastnik` is True for superusers *and* unassigned users** (the default,
  per [`0034`](./0034-roles-and-default-owner.md)), so *their* výdeje trigger the
  notify too. This is deliberate — the trigger is role-based (owner-level), not
  branch-scoped; an owner-level account issuing a branch výdej is exactly the case
  we want to signal. The issuing vlastník is never in the obsluha recipient list,
  so there is no self-notify.
- A branch with **no** active obsluha gets no mail and nothing logged (defensive
  early-return) — no crash, no empty send.
- No form / template / model-field / GET-endpoint change; the mail is a side
  effect of the existing výdej POST, so `EXCLUDED_URL_NAMES` needs no entry. An
  on-screen "branch notified" indicator on the dodák is out of scope (it can't
  reuse the `email_logs` FK — see Choice).
