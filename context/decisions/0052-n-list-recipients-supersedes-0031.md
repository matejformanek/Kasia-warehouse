# 0052 — N-list recipients for dodáky + low-stock summary (supersedes 0031 in part)

## Context

Karolína surfaced via `/podpora/` feedback #2 (2026-06-26): the current
"exactly Petr + Karolína" pair is too narrow. Petr has since added more
internal stakeholders (e.g. an external účetní, the Sezimovo Ústí
operator's owner cc) who want copies of every dodák. The fixed pair from
[`0031`](./0031-emails-internal-only-supersedes-0009.md) cannot
accommodate them without editing one of the two slots and losing the
original recipient.

Karolína also reported that the existing two-field UI on screen 14 felt
fragile — when she tried to swap Petr's address for a third email she
unintentionally lost the Petr address. An N-list with explicit add/remove
is the natural shape.

[`0031`](./0031-emails-internal-only-supersedes-0009.md) is intentional
about the "internal only / never to customers" intent — that intent
stands. What does not stand is the specific "exactly two slots" UI and
schema shape under [`0031`](./0031-emails-internal-only-supersedes-0009.md)
§ Choice (lines 49–53 and 65–67).

## Options considered

- **(a) Keep the fixed pair**, ask Karolína to forward by hand. Pushes
  load back onto the operator the system is supposed to free.
- **(b) Promote one of the two slots into a comma-separated list.**
  Tempting low-effort path. Rejected: comma-separated email lists are a
  classic source of silent failure (mismatched quoting, no per-address
  active toggle, no per-address subscription flags, no audit when a row
  changes), and "is this a real recipient or a typo" becomes a guess.
- **(c) Introduce a `SettingsRecipient` table with one row per
  address.** Explicit per-row `is_active`, per-row low-stock subscription
  flag, per-row ordering. Operator-facing UI is a repeating row with
  add/remove buttons. Mirrors the project's existing modelformset pattern
  (`RecipeComponentFormSet`, `ThresholdOverrideFormSet`).

## Choice

**(c) Standalone `SettingsRecipient` table with operator-explicit
subscription flags.**

Schema:

```python
class SettingsRecipient(models.Model):
    email = models.EmailField()
    label = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    is_low_stock_recipient = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_active", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="recipient_email_unique_ci"
            ),
        ]
```

Behaviour:

- **Dodák send** (`send_dodaci_list_email`): reads all rows where
  `is_active=True`, ordered by `sort_order, id`. Sends to all of them on
  every dodák (initial + `[OPRAVA]` re-send). At least one active row
  must exist — `_assert_recipients_set` raises a Czech `ValidationError`
  if not, blocking the výdej.
- **Low-stock summary** (`send_low_stock_summary`): reads all rows where
  `is_active=True AND is_low_stock_recipient=True`. Sends to all of
  them. If none match, returns `None` without sending (matches current
  behaviour when `Settings.recipient_petr` is blank).
- **Migration**: data migration in the same migration as the schema
  change creates two rows from `Settings.recipient_petr` (sort_order=0,
  is_low_stock_recipient=True, label="Petr") and
  `Settings.recipient_karolina` (sort_order=1,
  is_low_stock_recipient=False, label="Karolína"). Then drops both
  columns from `Settings`. Idempotent: skips create if email is blank or
  if any `SettingsRecipient` row already exists.
- **UI**: `/nastaveni/` "Příjemci dodacího listu" block becomes a
  modelformset (`extra=1`, `can_delete=True`) using the existing
  JS-clone `<template>` add-row pattern from `product_form.html:159-214`.
  Per-row controls: email, label, is_active, is_low_stock_recipient,
  sort_order, remove button.

Email uniqueness is case-insensitive via `UniqueConstraint(Lower("email"))`
so `petr@kasia.cz` and `PETR@kasia.cz` collide.

## Rationale

- **Operator-explicit subscription** — `is_low_stock_recipient` is a
  per-row flag, not a magic "the first recipient gets summaries" rule.
  Karolína (and any future operator) can read the page and understand
  who gets what without consulting the codebase. Mirrors
  [`0045`](./0045-low-stock-summary-email.md)'s "Petr only" current
  semantics by setting the migration's Petr=True / Karolína=False
  defaults.
- **No comma-separated lists.** Each address is a row with its own
  audit, its own activate/deactivate, its own subscription flags. A
  typo'd address is one click away from being deactivated; an inactive
  address is preserved as a historical record (it can be re-activated
  without re-typing).
- **Mirrors existing project patterns.** `modelformset_factory` is the
  established formset shape here (`forms.py:365` + `:481`); the JS-clone
  add-row template lives at `product_form.html:159-214`. No HTMX, no
  new dependency.
- **Single atomic migration** — right-sized for a 6-user single-VPS
  deploy with daily backups + immediate post-deploy verification. A
  two-step migration (add table first, drop columns later) would add
  weeks of two-source-of-truth confusion for no operational gain. If
  the migration fails we restore from yesterday's backup.
- **Case-insensitive uniqueness** matches the operator mental model:
  `Petr@kasia.cz` and `petr@kasia.cz` are the same person.
- **`_assert_recipients_set` continues to guard výdej** — at least one
  active recipient must exist, otherwise dodáky cannot be issued. This
  is the same backstop [`0031`](./0031-emails-internal-only-supersedes-0009.md)
  established; the implementation just changes from "both Settings
  columns non-blank" to "at least one active SettingsRecipient row".

## Date & by-whom

2026-06-28 — Matej (acting on Karolína's `/podpora/` feedback #2;
ratified Petr's "internal only" intent stays).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Operator-managed recipient list on `/nastaveni/`. No more developer
  edits to add/remove a stakeholder.
- Per-recipient subscription to the low-stock summary — Karolína opts
  out of the daily summary without losing her dodák cc; účetní opts in
  without seeing every dodák.
- Future schema-light additions to `SettingsRecipient` (e.g. an
  "include `[OPRAVA]` re-sends" flag) without further model-level
  rework on `Settings`.

**Forecloses (without follow-on decisions):**

- Per-customer recipient list. The intent from
  [`0031`](./0031-emails-internal-only-supersedes-0009.md) stands —
  dodáky stay internal-only, never to end customers. A future decision
  could either flip an `include_customer_email` flag or re-introduce a
  per-`Customer.default_recipients` model.
- Per-dodák ad-hoc recipients (one-off bccs). Out of scope here; if
  needed, screen 07's výdej form could grow an "+ adresa pro tento
  dodák" field reading nothing from the DB.

**Supersedes in part:**

- [`0031`](./0031-emails-internal-only-supersedes-0009.md) — the "fixed
  pair `[Petr, Karolína]` from screen 14" mechanism is replaced by an
  N-list. The "internal only / never to customers" intent (Petr's
  instruction in 0031 § Context) stands and is preserved by this
  decision.

**Resolves:**

- `/podpora/` feedback #2 ("recipients should be N-list, not hard-coded
  pair").

**Affects neighbouring decisions:**

- [`0045-low-stock-summary-email.md`](./0045-low-stock-summary-email.md)
  — semantic "Petr-only summary" is now expressed as one or more
  recipients with `is_low_stock_recipient=True`. Migration preserves
  Petr's current effective subscription.
- [`0037-settings-singleton.md`](./0037-settings-singleton.md) —
  `recipient_petr` + `recipient_karolina` columns drop from
  `Settings`. The rest of the singleton (SMTP, templates, branding)
  stands.
