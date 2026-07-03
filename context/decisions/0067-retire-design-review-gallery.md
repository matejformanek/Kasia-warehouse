# 0067 — Retire the design-review gallery (keep the files)

**Date:** 2026-07-03
**Decider:** Matej
**Status:** Active
**Supersedes:** [`0047-design-review-gallery.md`](./0047-design-review-gallery.md)

## Context

Decision 0047 served the design-option mockups (`design-options/` — the public
site explorations at the top level + `public/`, and the sklad mockups in
`sklad/`) publicly under `/static/navrhy/`, with a login-exempt `/navrhy/`
redirect, so Petr could review them on prod without an account.

The review is done: the sklad direction is adopted (Phase 2, decisions 0054 +
0064–0066) and the public site is live (0058). The gallery has served its
purpose and no longer needs to be reachable — but the mockups are worth keeping
in the repo in case we revisit a direction later.

## Choice

- **Stop serving the gallery on both surfaces**, keep the files in the repo:
  - Drop the `STATICFILES_DIRS` entry that mapped `design-options/` →
    `/static/navrhy/` (in `kasia/settings/base.py`).
  - Remove the login-exempt `/navrhy/` redirect route (in `kasia/urls.py`) and
    its now-unused `RedirectView` import.
- `design-options/` stays in version control untouched. Re-enabling the gallery
  requires a new decision.

## Rationale

The gallery was always a temporary review surface (0047). With both surfaces'
designs locked/shipped, leaving an unauthenticated static gallery on prod is
needless exposure. Deleting the files would lose the exploration history, so we
keep them in the repo and only remove the serving path.

## Consequences

- `/navrhy/` and `/static/navrhy/...` now 404 (dev and prod). No test referenced
  them. `robots.txt` still Disallows `/navrhy/` — harmless (the path is gone).
- `design-options/` remains in the repo for future reference; nothing imports it
  at runtime.
- No schema/migration change.
