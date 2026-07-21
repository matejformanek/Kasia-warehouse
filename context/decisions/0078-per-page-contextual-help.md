# 0078 — Per-page contextual help (in-app „?" panel)

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, sklad UX round after using the app)
**Status:** Accepted

## Context

The whole návod / „co kde najdu" / postupy guidance today lives on
**one** screen — Podpora (`support.html`, per
[`0046`](./0046-support-page.md)). It is a good full reference, but it
is out of reach at the moment a user is actually stuck: they have to
leave the screen they're on, open Podpora, find the right accordion,
read, and come back. For ~6 non-technical operators that friction is
enough that the guidance goes unread.

The ask from using the app: a small, always-present **„?"** affordance
on every screen that pops up an in-app panel explaining *how this
particular page works and where to find things* — a focused excerpt of
the Podpora guide, in reach without navigating away.

This is a new shared UI pattern (a global modal + a per-screen content
slot), so it is recorded before it lands, per
[`decision-log-discipline.md`](../../.claude/rules/decision-log-discipline.md).

## Options considered

- **A — Link each screen to the Podpora page.** Rejected: still makes
  the user leave the screen and hunt; no per-page focus.
- **B — A new help endpoint per screen (server-rendered fragment,
  htmx-loaded).** Rejected: a new GET partial per screen (each needing
  an `EXCLUDED_URL_NAMES` entry per 0077), plus a round-trip, for
  static prose. Over-built for ~6 users — the content is known at
  render time.
- **C — A single global `<dialog>` in `base.html` whose body is a
  `{% block page_help %}` each screen overrides; a fixed „?" button
  opens it.** **Chosen.** Zero new endpoints, zero per-page JS, no
  native dialog (reuses the `<dialog>.showModal()` pattern from
  [`0061`](./0061-display-1dp-comma.md) / `_confirm_dialog.html`). The
  help text lands inside the dialog markup at parse time via Django
  template block inheritance.

## Choice

**Implement option C.** Concretely:

### Mechanism (`base.html`)

- A help `<dialog id="kasia-help" class="kasia-dialog help-dialog">`
  and a fixed „?" button (`id="help-fab"`,
  `aria-label="Nápověda k této stránce"`) live **inside the
  `{% if user.is_authenticated %}` block** (not at the global
  `_confirm_dialog` include, which is outside the auth gate and would
  orphan a „?" onto the anonymous login page).
- The dialog body is `{% block page_help %}…generic fallback…{% endblock %}`.
  Child templates override the block; screens that don't fall back to a
  generic panel pointing at the Podpora page. Block overrides resolve at
  parse time regardless of the `{% if %}`.
- The FAB opens the dialog with `showModal()`. A small delegated script
  (mirroring `_confirm_dialog.html`) closes it on a „Zavřít" button, on
  `Esc` (the dialog's native `cancel`), and on a backdrop click. **No
  native `confirm()`/`alert()`/`prompt()`** (per 0061).
- Styling lives in `kasia/static/css/components/dialogs.css` (already
  `<link>`ed) as `.help-dialog` / `#help-fab` / `.help-body` — a wider,
  scrollable variant of the confirm dialog for prose. No new `<link>`,
  never inline `<style>`/`@import`. The FAB sits at `z-index: 60` (above
  the topbar/mob-nav **and** the inventura `.tallybar` at z50); on
  inventura `pages/inventura_edit.css` lifts it clear of the fixed
  tallybar (`bottom: calc(92px + 1.25rem)`) so it is never occluded.

### Per-screen content

Each main screen overrides `{% block page_help %}` with a friendly,
page-focused **walkthrough** (what the screen is for, step-by-step how
to do the main task, what each field/column means, tips) — sliced and
expanded from the existing Podpora guide („Co kde najdu" + „Postupy" +
„Tipy"). The panel body scrolls (`.help-body` `overflow-y:auto`) so it
can be as long as the screen needs. Covered screens: Přehled (home +
branch_dashboard), Katalog, Inventura, Příjem, Výdej, Míchání (create +
index), Historie, Dodací listy, Detail produktu, Úprava pohybu, Podpora
(short — the page itself is the full guide), Dodavatelé, Odběratelé,
Pobočky, Uživatelé, Nastavení, E-maily, Aktivita. Screens with no
override use the generic fallback.

### Locked hooks

`{% block page_help %}`, `#kasia-help`, `#help-fab`, `.help-dialog`,
`.help-body` are added to the „Keep stable" list in
[`design-system.md`](../../.claude/rules/design-system.md) and the
locked-hook mention in
[`frontend-and-templates.md`](../../.claude/rules/frontend-and-templates.md).
Renaming them is a new decision.

## Rationale

Block inheritance + one global dialog is the smallest thing that puts
focused help one click away on every screen with no new endpoint, no
per-page JS, and no round-trip. It reuses the already-shipped
`<dialog>` pattern and the existing dialogs.css `<link>`, so the
footprint is one dialog + one button + one close-script in `base.html`,
some CSS, and a static block per screen.

The intentional **duplication** with the Podpora page is accepted: the
per-page block is a *focused excerpt* (this screen only), the Podpora
page is the *full guide* (all screens + step-by-step postupy). At ~6
users and prose that changes only when the app changes — same commit,
same author — keeping both is cheaper than building a single-source
extraction mechanism. If drift becomes a problem, revisit.

## Consequences

**Now:**
- `base.html` gains the help dialog + FAB + close-script (auth-gated).
- `components/dialogs.css` gains `.help-dialog` / `#help-fab` /
  `.help-body`.
- ~16 screen templates gain a `{% block page_help %}` override.
- `design-system.md` + `frontend-and-templates.md` gain the new hooks.

**Blocks / unblocks:**
- Unblocks in-reach, per-screen self-service during the shadow run
  ([`0034`](./0034-shadow-run-before-go-live.md)) without escalating to
  Matej.
- Commits us to keeping each screen's `page_help` excerpt honest when
  that screen changes (same discipline as any other user-facing Czech
  text).

**Not doing:**
- No server-side help endpoint, no htmx round-trip, no per-page JS.
- No single-source extraction from the Podpora page — the duplication
  is deliberate at this scale.

## Cross-references

- [`0046-support-page.md`](./0046-support-page.md) — the full Podpora guide the excerpts are sliced from
- [`0061-display-1dp-comma.md`](./0061-display-1dp-comma.md) — the in-app `<dialog>` / no-native-dialog pattern this reuses
- [`0077-sklad-usage-tracking.md`](./0077-sklad-usage-tracking.md) — why a new GET partial would need an `EXCLUDED_URL_NAMES` entry (help avoids it — no endpoint)
- [`design-system.md`](../../.claude/rules/design-system.md) — the „Keep stable" hook list
- [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md) — why the simple version wins
