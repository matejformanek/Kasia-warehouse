# 0007 — Auto re-issue and re-email of corrected dodáky

> **Amended by [`0096`](./0096-manual-first-send-of-dodaky.md)** — the *initial*
> issue is no longer auto-sent at výdej (the dodák waits in `send_state=WAITING`
> for an operator "Odeslat" click). The auto-reissue + `[OPRAVA]` re-send on
> correction below is **unchanged for an already-sent dodák**; it simply doesn't
> fire while the dodák is still WAITING.

> Schema specifics (three-table layout) superseded in part by
> [`0036`](./0036-dodaci-list-shape.md): the "version" lives as
> `DodaciList.current_version`, not as a separate
> `dodaci_list_version` table. Trigger semantics, `[OPRAVA]`
> e-mail behaviour, and PDF re-render rules below stand
> unchanged.

## Context

When a movement that is already on a sent dodací list is corrected via
[`screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md), the
question is whether the system should re-generate the dodací list PDF
and re-email it to the original recipients, or require manual action.

The owner's verbatim brief
([`../owner-request.md`](../owner-request.md)) explicitly names the
failure mode the system is meant to fix:

> "polovina dodáků se zapomene přeposlat"

i.e. half the dodáky get lost in the manual-forwarding chain. The same
failure mode applies to corrections.

This question was promoted into
[`../open-questions.md`](../open-questions.md) during this round and
needs to land now because [`../workflows.md`](../workflows.md) and
several screens (07, 09, 11) cannot be cleaned up while it remains
open.

## Options considered

- **(a) Auto-regenerate the PDF and auto-email to the original
  recipients.** The correction step writes the audited change and
  immediately sends an updated PDF email, subject-marked as an
  update.
- **(b) Auto-regenerate the PDF, confirm before re-sending.** The
  correction step regenerates the PDF silently; the operator
  explicitly clicks "rozeslat opravený dodák" to email it.
- **(c) Fully manual.** Correction does not touch the PDF or the
  email; operator must regenerate and resend from
  [`screens/09-detail-dodaciho-listu.md`](../screens/09-detail-dodaciho-listu.md).

## Choice

**(a) Auto-regenerate and auto-email.** When a correction lands on a
movement that is on a previously-sent dodací list, the system:

1. Re-renders the dodací list PDF using the **current template** and
   the **corrected data**.
2. Sends the new PDF to the original recipients of the prior email.
3. Records the send in the per-dodací-list audit table: timestamp,
   recipients, PDF version (a monotonic counter), reason from the
   correction (the operator's mandatory free-text reason on
   `screens/11-uprava-pohybu.md`).

The email subject is prefixed (in Czech) with `[OPRAVA]` and the
body briefly states what changed in plain Czech, e.g.

> Dodací list TYN-2026-0042 byl opraven. Důvod: oprava hmotnosti
> na ř. 2. Přiložený PDF je aktuální verze; nahrazuje verzi ze dne
> 2026-06-01.

A small audit table on
[`screens/09-detail-dodaciho-listu.md`](../screens/09-detail-dodaciho-listu.md)
shows "PDF v1 odesláno 2026-06-01, PDF v2 odesláno 2026-06-02 (oprava
hmotnosti)".

## Rationale

- **Closes the exact failure mode the brief names.** "Polovina dodáků
  se zapomene přeposlat" — manual re-send will fail the same way
  manual forwarding did. Automation is the intent of the project.
- **The accountant needs the right data for the faktura.** Karolína
  feeds the accountant from the email inbox; the accountant issues
  the invoice based on the dodací list. A silent correction would
  leave an inaccurate invoice in the pipeline.
- **Audit trail integrity.** Per Petr's audit requirement ("ať je
  vidět, kdo co změnil a kdy"), the system records every change and
  who made it. The PDF send audit is the external-facing extension of
  that: the accountant and the owner both see "what was sent and when".
- **(b) and (c) add friction.** For ~6 users, the cost of one extra
  email per correction (which is rare) is lower than the cost of a
  correction silently failing to reach the accountant.
- **Template question (Czech subject prefix, body wording).** The
  exact text can be tuned later in `screens/14-nastaveni.md`; the
  data-model commitment is the audit table and the automatic
  trigger.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `workflows.md` — the outbound and correction workflows can state
  unambiguously what happens on a correction.
- `screens/09-detail-dodaciho-listu.md` — gains a "verze a odeslání"
  audit table.
- `screens/11-uprava-pohybu.md` — the correction step warns the
  operator that saving the correction will trigger an opravený dodák
  email, but does not require explicit confirmation.
- Dodací list schema gains a `version` (monotonic int) column and a
  separate `dodaci_list_email_log` table: `(dodaci_list_id, version,
  sent_at, recipients, trigger_reason)`.
- Email template handling supports `[OPRAVA]` subject prefix and a
  short Czech body referencing the correction reason.

**Forecloses (without follow-on decisions):**

- Manual gate before re-emailing. Operators do not get to decide
  per-correction whether to resend.
- Re-rendering with the *historical* template. Per the embedded
  judgement call in `workflows.md`, PDF re-render uses the current
  template — this decision codifies that.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  MVP* › "Auto re-issue / re-email of corrected dodáky".

**Remains open (deferred to relevant screen):**

- **Recipient list policy at *original* issue** (whether the operator
  can add the customer to the recipient list, whether it persists
  per-customer) — handled on `screens/07-vydej-zbozi.md` in the Phase
  B walkthrough. The re-issue inherits whatever recipient set the
  original used.
- **PDF template specifics** (logo placement, line table layout,
  signature line) — `screens/14-nastaveni.md` and a separate
  *Decide before MVP* decision file when Phase B reaches that screen.
- **Czech subject/body wording** — settable on
  `screens/14-nastaveni.md`; the wording in this decision is the
  default.

**Affects future decisions:**

- Numbering scheme (still open in `open-questions.md`) — the version
  counter introduced here is **internal to a given dodací list**; it
  does not interact with the public numbering scheme. A dodák
  `TYN-2026-0042` corrected three times stays `TYN-2026-0042`, with
  internal versions 1, 2, 3, 4.
