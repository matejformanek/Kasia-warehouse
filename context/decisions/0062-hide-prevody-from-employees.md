# 0062 — Hide the převody (inter-branch transfer) feature from employees

**Date:** 2026-07-01
**Decider:** Matej (relaying Petr's ask, same live-app review as 0060/0061)
**Status:** Active
**Relates to:**
- [`0044-reservations-planned-states.md`](./0044-reservations-planned-states.md)
  — planned inter-branch transfers (`PlannedTransfer`) were introduced here.
- [`0060-michani-immediate-only.md`](./0060-michani-immediate-only.md) — same
  session; the planned-reservation family is being simplified.

## Context

During the 2026-07-01 live-app review the owner decided the **převody**
(plánované převody mezi pobočkami / inter-branch transfers) feature is not
wanted for employees right now. It is not being removed — the code, URLs,
views, and templates stay in the repo — but employees must not see or use it.

## Options considered

- **Delete the převod code.** Rejected — the owner said "keep them unseen in
  the repo"; a later re-enable should be a small revert, not a re-build.
- **Hard-gate the views to 404 behind a feature flag.** Deferred — would churn
  the 22 existing `planned_transfer` test references for a "for now" toggle and
  fights the retained-code intent. Can be added later if URL-level lockout is
  required.
- **Unlink from the nav.** Chosen — the 6 warehouse users navigate by the
  sidebar; removing the "Převody" entry (desktop + mobile) makes it
  unreachable in practice, and re-enabling is re-adding two `<a>` tags.

## Choice

- **Remove the "Převody" nav links** (desktop sidebar + mobile nav in
  `kasia/templates/base.html`), leaving a one-line comment pointing here.
- **Drop the převod how-to from Podpora** (`support.html`) and its screen-list
  entry so the help no longer advertises it.
- **Keep everything else** — `planned_transfer_*` URLs, views, templates,
  services, and tests remain in the repo, dormant and green.
- `reserved_kg()` is unchanged (PlannedTransfer reservations still count for any
  legacy in-flight transfer, per 0044/0060).

## Rationale

For ~6 non-technical staff who reach features through the sidebar, unlinking is
the smallest change that satisfies "not available to employees" while honouring
"keep it in the repo." No test churn, trivially reversible.

## Consequences

- Employees can no longer reach převody from the UI. A direct URL
  (`/sklad/prevody/…`) still resolves for now — if the owner later wants a hard
  lockout, add a feature-flag gate to the `planned_transfer_*` views (a new
  decision) and update the tests accordingly.
- To re-enable: restore the two nav links and the Podpora section.
