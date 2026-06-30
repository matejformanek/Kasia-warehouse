# 0054 — Adopt UI directions: sklad sidebar/sharp/green + public centered/curvy/green

> **Superseded by [0058](./0058-public-redesign-and-produkty-page.md) for the PUBLIC surface only** — the public site moves to the "mono × centered, green-sections" system (green `#006634` nav bar, Space Grotesk + Inter, deep forest-green `#0a3b20` section bands). The **sklad** sidebar/sharp/green direction below is unchanged.

## Context

The `/navrhy/` design gallery (decision [`0047`](./0047-design-gallery.md))
explored multiple visual directions for both surfaces of the system:
the **public marketing site** (`web` app at `/`) and the **login-gated
warehouse app** (`inventory` + `accounts` under `/sklad/…`), split per
decisions [`0050`](./0050-public-site-and-sklad-split.md) /
[`0051`](./0051-public-site-ia-and-content.md) /
[`0052`](./0052-kontakt-info-only-drop-contactinquiry.md).

Until now the live templates carried a generic, undirected look (system-ui,
blue `--accent`, top-nav). Petr needs to see the chosen visual language live
on the box (`91.98.47.1`) so he can react to real screens, not just mockups.
This decision records the directions Matej picked from the gallery and ports
into the real templates. It is an **intermediate live state**, not the final
polish pass — copy, imagery, and per-page refinement continue afterwards.

Front-end *design direction and layout* is a non-trivial choice with
long-lived consequences (every screen inherits it, and the shared CSS class
contract + JS/HTMX hooks must stay stable), so it is recorded here rather
than left implicit in templates — see the amended
[`no-premature-tech-choices.md`](../../.claude/rules/no-premature-tech-choices.md)
and the new [`design-system.md`](../../.claude/rules/design-system.md).

## Options considered

- **Keep the generic look.** Cheapest, but gives Petr nothing to react to and
  leaves the two surfaces visually identical despite serving opposite
  audiences (anonymous prospects vs. trained operators).
- **One shared system for both surfaces.** Simpler CSS, but a calm marketing
  site and a dense operator tool want opposite things (whitespace + warmth vs.
  density + scannability). Rejected — the surfaces are already split at the
  app + URL level (0050); the visual split follows.
- **Two divergent systems (chosen).** Public = centered/curvy/green; sklad =
  sharp/technical/green. Same brand (green + jpg logo) bridges them.

## Choice

Port the gallery directions into the real Django templates:

**Public** (`kasia/templates/web/base.html` + page templates) — port the
*visual language* of `design-options/public/11-centered-modern.html` onto the
existing richer content (0051/0052):
- Centered hero (eyebrow pill, large **Sora** headline, stat block 369+/236,
  pill CTAs) over hand-authored **green SVG hero art** (`web/art-hero.svg`,
  with a commented real-photo slot).
- Curvy cards (radius 18px), pill buttons/badges (999px), soft shadows,
  company green palette (`--green:#235c33` family), **Sora** (headings) +
  **Inter** (body) via Google Fonts.
- All existing sections preserved: "Co děláme" ×6, "Komu dodáváme" ×3,
  "Proč Kasia" ×6, teasers; green SVG line-icons added to cards.

**Sklad** (`kasia/templates/base.html` + page templates) — combine
`13-sidebar-app` (left sidebar shell), `02-swiss-grid` / `01-mono-minimal`
(sharp, **radius 0**), and `15-data-numerals` (KPI strip), recoloured to
**brand green** (not the mockups' blue):
- Sticky left **sidebar** (jpg logo + `KASIA / sklad`, vertical nav with
  vlastník-only items, user e-mail + Odhlásit pinned bottom); collapses to a
  sticky top bar + scroll-nav under 720px.
- Sharp surfaces (0 radius everywhere), **Inter** (UI) + **IBM Plex Mono**
  (numerals/codes/kg/dates, tabular-nums).
- **KPI strip** on the owner dashboard (K vyřešení / Produktů skladem /
  Celková zásoba kg / Dochází zboží) and an equivalent per-branch KPI header
  on the branch dashboard.

**Both:** jpg Kasia logo top-left (`brand/kasia-logo.jpg`); imagery is
hand-authored green SVG/CSS + marked photo slots (no raster generation).

The shared CSS **class names** and the **JS/HTMX hooks** in both base
templates are a stable contract — see `design-system.md`.

## Rationale

- The two surfaces serve opposite audiences; divergent systems let each do its
  job while one brand (green + logo) ties them together.
- Sharp/0-radius + mono numerals reads as a precise operator tool; curvy/green
  reads as a warm, established family supplier — both true to Kasia.
- Restyling **in place against the existing class names** means every child
  template inherits the new look without a rewrite, and the formset
  delete-toggle / whole-row-click / stock-warn HTMX wiring keeps working.
- SVG/CSS art ships in git, survives build-time `collectstatic`, and leaves
  clearly marked slots for Petr's real photos later.

## Date & by-whom

2026-06-29, Matej (deciding for Petr; intermediate live state for review).

## Consequences

- Front-end design direction is now decision-gated (this file). Structural
  redesigns of either base template — or renaming the shared classes / moving
  the JS-HTMX hooks — need a new decision. Restyling within the system does
  not.
- `kasia/templates/base.html` `:root` adds `--ok-soft` (the 0053 carry-chip
  referenced it before it existed) and a sharp/green token set; child inline
  styles keep resolving because the referenced vars (`--fg-soft`, `--warn`,
  `--ok`, `--error`, `--accent`, `--ok-soft`) are all defined.
- Two new web font stacks load from Google Fonts on each surface (Inter +
  IBM Plex Mono on sklad; Sora + Inter on public).
- New static asset `kasia/static/web/art-hero.svg` is committed to git so
  `collectstatic` (manifest storage) finds it at build time; the `navrhy`
  gallery `STATICFILES_DIRS` entry keeps collecting.
- Not covered here: WeasyPrint PDF (`inventory/dodaci_list.html`) and e-mail
  templates keep their print/inbox-specific styling — out of scope.

Supersedes nothing; builds on 0047 (gallery), 0050/0051/0052 (public site),
and 0018 (htmx + WhiteNoise, the delivery mechanism).
