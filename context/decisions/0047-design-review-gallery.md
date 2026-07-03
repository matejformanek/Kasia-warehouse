# 0047 — Design-review gallery served publicly under /static/navrhy/

> **Superseded by 0067** — the gallery is no longer served (files kept in repo).

## Context

Before adopting a new homepage look, Petr (the owner) wants to browse a set
of visual mockups and pick a direction. The mockups live in the top-level
`design-options/` directory: 18 fully self-contained HTML pages (two sets —
10 bespoke directions + 8 inspired by well-known products) plus an
`index.html` gallery, all rendering the same realistic Czech sample data so
only the *styling* differs. See `design-options/README.md`.

These are exploration artifacts, not application code: no Django, no
templates, no database, no real data — just static HTML with inline CSS and
copies of the brand logo/favicon.

Two things were wanted:

1. **Versioned** — kept in git as a design-history trail (every round of
   culling, expansion, and customer-requested change is recorded).
2. **Reachable on prod** — so Petr can open them on the live box, decide
   which to keep, and request changes, without needing a local checkout.

The app is otherwise login-gated end-to-end (LoginRequiredMiddleware; see
[`0020`](./0020-auth-django-builtin.md)), so a deliberate choice was needed
about *how* the gallery is exposed.

## Options considered

- **A — Serve via the static pipeline (chosen).** Add `design-options/` to
  `STATICFILES_DIRS` under the `navrhy` prefix; WhiteNoise serves it at
  `/static/navrhy/` *before* auth, so it is public with zero new
  application-view surface. A tiny `login_not_required` redirect at
  `/navrhy/` gives a clean shareable link.
- **B — A login-gated Django view.** Only Kasia accounts could see it. Petr
  explicitly wanted a public link he can forward to others without a login,
  so this was rejected.
- **C — A bespoke public file-serving view.** More code (path-traversal
  guard, content types) than A for no benefit; static files are exactly what
  this is.
- **D — Caddy `file_server`.** Would move the concern into infra config that
  isn't in the repo; A keeps it in the versioned Django settings.

## Choice

**Option A.** `design-options/` stays at the top level (versioned design
history) and is collected into `STATIC_ROOT/navrhy/` at build time, served
publicly by WhiteNoise at `/static/navrhy/index.html`. A `login_not_required`
`RedirectView` at `/navrhy/` is the human-friendly entry point.

## Rationale

- **Smallest, most boring change.** `/static/` is already a public surface
  (CSS, the brand logo, the htmx bundle). The gallery is just more static
  files of the same nature — no new authenticated-app surface, no
  file-serving view to harden.
- **Public, as the owner asked.** Petr gets a link he can open or forward
  without a Kasia account. The mockups contain only invented sample data, so
  the exposure is a data-free, low-risk artifact.
- **Source stays where design history belongs** — top-level `design-options/`,
  not buried inside `kasia/static/`.

## Date & by-whom

2026-06-24 — Matej (owner-side decision relayed by Petr's review request),
implemented by the agent.

## Consequences

- **Amends [`0020`](./0020-auth-django-builtin.md)** — which stated "there is
  no public surface beyond /login/ and /healthz/." That remains true for the
  *application* (views and data). This adds one intentional public surface:
  a static, data-free design-review gallery under `/static/navrhy/` (entry
  `/navrhy/`). 0020's auth posture for all real screens and data is
  unchanged.
- The gallery rides along in the production image (`design-options/` is not
  in `.dockerignore`; `collectstatic` runs at build). It is a few hundred KB.
- **This is a temporary review surface.** Once Petr picks a direction, the
  expectation is: cull the rejected mockups, iterate on the chosen one(s)
  with his requested changes, and — when the real homepage port lands — remove
  the public exposure (drop the `navrhy` `STATICFILES_DIRS` entry and the
  `/navrhy/` redirect), keeping `design-options/` in git as history only.
- The chosen direction still becomes its own decision + a separate port task
  into the real `base.html` / `home.html`; this entry only governs the
  review gallery's hosting.
