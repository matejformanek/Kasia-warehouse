# 0050 — Public marketing site at `/`, warehouse app moves under `/sklad/`

## Context

Until now the repository is a single login-gated app:
`LoginRequiredMiddleware` protects every URL, the operator dashboard
(`inventory:home`) sits at `/`, and the only public surfaces are
`/login/`, `/reset-hesla/*`, `/healthz`, `/admin/`, and the temporary
design-review gallery at `/navrhy/` (per
[`0047`](./0047-design-review-gallery.md)).

Kasia vera s.r.o. also has a real public website at **kasia.cz** that is
dated and visually poor. The owner (Petr) wants to host **both surfaces
on one domain in the future**:

- `/` — a brand-new public marketing site (no login, for anyone).
- `/sklad/…` — the existing warehouse app (login-gated, for Petr +
  Karolína + branch staff).

Domain wiring is out of scope here — Caddy already forwards everything to
Django, so the split is done entirely in Django's URLconf. This is an
**architectural** change (a new app + a URL-prefix move), not a new
**tech-layer** choice: the public site reuses the already-decided Django
stack ([`0014`](./0014-language-python-uv.md)–[`0027`](./0027-hosting-hetzner.md)),
so the `no-premature-tech-choices.md` gate does not apply and no
`context/tech-options.md` entry is required.

The companion decision [`0051`](./0051-public-site-ia-and-content.md)
covers the public site's information architecture and content; this
decision covers the **split itself**: where the app lives, where the
public site lives, and how auth is exempted.

## Options considered

- **A — Public site at `/`, app under `/sklad/` (chosen).** Add a new
  `web` Django app mounted last at `""`; move `inventory`, `accounts`,
  and the whole auth chain (`/login`, `/logout`, `/reset-hesla`,
  `/zmena-hesla`) under a `/sklad/` prefix. Public views opt out of the
  global login middleware with `@login_not_required` (same pattern as
  `healthz` and the `/navrhy/` redirect). Because every app URL is
  reverse-resolved by name (`{% url 'inventory:…' %}`, `reverse(…)`,
  `LOGIN_URL`, `LOGIN_REDIRECT_URL`), the move is a URLconf-prefix change
  — names re-resolve to the new paths automatically.
- **B — App stays at `/`, public site under `/web/` or a subdomain.**
  Rejected: the public marketing face is the thing the world should find
  at the bare domain; burying it under a path or forcing a second
  subdomain works against the "one modern face for kasia.cz" goal.
- **C — Two separate Django projects / two deployments.** Conference-talk
  shaped for ~6 users and one box. Violates
  `right-sized-for-small-business.md` ("one Django project, one DB").
  Rejected.
- **D — A CMS (Wagtail / headless) for the public site.** Four mostly
  static Czech pages do not need a CMS. Curated templates are
  right-sized; revisit only if Kasia wants self-service content editing.
  Rejected — see [`0051`](./0051-public-site-ia-and-content.md).

## Choice

**Option A.** The public marketing site lives at `/` in a new `web` app;
the entire warehouse application moves under `/sklad/`:

- `path("sklad/", include("inventory.urls", namespace="inventory"))`
- `path("sklad/uzivatele/", include("accounts.urls", namespace="accounts"))`
- auth at `/sklad/prihlaseni/`, `/sklad/odhlaseni/`
- password reset chain at `/sklad/reset-hesla/…`
- in-app password change (Pass 8) at `/sklad/zmena-hesla/…`
- `path("", include("web.urls", namespace="web"))` — **mounted last** so
  it can never shadow `/sklad/`, `/admin/`, `/healthz`, or `/navrhy/`.

Every public view is decorated `@login_not_required` on the view function
itself (covering both the GET and POST branch of the kontakt form).
`/admin/`, `/healthz`, and `/navrhy/` are unchanged.

**Why `/sklad/` (not `/app/`):** the audience is Czech warehouse staff;
*sklad* (warehouse) is the word they use for the tool. It reads naturally
in the address bar and matches the domain language. `/app/` is
developer-shaped and English; the user-facing convention here is Czech
(`language-conventions.md`).

## Rationale

- **Name-based reverse resolution makes the move cheap where it matters.**
  Views and templates that use `{% url %}` / `reverse()` need no change.
  The churn is concentrated in hard-coded path literals in the test suite
  and any literal `hx-*`/`action` strings in templates — mechanical, and
  caught by the test run.
- **The global login middleware already has a clean opt-out
  (`@login_not_required`)** used by `healthz` and `/navrhy/`. Public views
  reuse it; no new middleware, no per-include auth machinery.
- **One project, one DB, one box** — the smallest shape that serves both
  surfaces, consistent with `right-sized-for-small-business.md` (now
  clarified to mean *one Django project*, multiple Django apps).

## Date & by-whom

2026-06-26 — Matej (owner-side decision; scope locked to the four-page
first build per [`0051`](./0051-public-site-ia-and-content.md)).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The `web` app and its public templates (see
  [`0051`](./0051-public-site-ia-and-content.md)).
- A future domain cutover where kasia.cz serves both the public site and
  the warehouse tool from one box.

**Commits us to:**

- All warehouse URLs now live under `/sklad/`. Bookmarks, the `?next=`
  login flow, and any external references to old paths change. (No real
  users are on the system yet, so there is no migration cost.)
- HTMX partials move with the app: `/_partials/*` → `/sklad/_partials/*`.

**Amendment chain (append-only):**

- **Extends [`0047`](./0047-design-review-gallery.md)** — which added the
  first intentional public surface (the static `/navrhy/` gallery). This
  adds the first public *application* surface (real Django views at `/`).
- **Second amendment of [`0020`](./0020-auth-django-builtin.md)** — whose
  "no public surface beyond /login/ and /healthz/" line was first narrowed
  by 0047 (static gallery) and is now narrowed again: the public marketing
  site at `/` is a deliberate, login-exempt application surface. 0020's
  auth posture for every warehouse screen and all real data is unchanged —
  those simply now live under `/sklad/`. **Update 0020's preamble to cite
  0050 as a second amendment.**

**Settings/doc fallout (handled in the same change):**

- `kasia/settings/base.py` — the `LoginRequiredMiddleware` comment ("no
  public surface beyond /login/ and /healthz/") is now false; updated to
  cite 0050 and the public marketing surface at `/`.
- `.claude/rules/right-sized-for-small-business.md` "one app, one DB"
  clarified to mean one Django *project* / one DB; multiple Django *apps*
  (`inventory`, `accounts`, `web`) are fine.
