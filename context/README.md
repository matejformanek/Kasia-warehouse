# Context — index and reading order

This directory holds the foundational design context for the Kasia warehouse
tool. Everything here is descriptive, not prescriptive. No code lives in this
repo yet; nothing under `context/` should be read as a tech choice.

If you are an agent or human picking this up cold, read in this order.

## 1. Where the project stands

- [`state.md`](./state.md) — the cold-start anchor. Done / In progress / Next.
  Always read first. Updated at the end of every working session.

## 2. What the project is and who it is for

- [`owner-request.md`](./owner-request.md) — the original ask, in the owner's
  own words (Czech), with English translation and interpretation notes.
- [`company-profile.md`](./company-profile.md) — Kasia vera s.r.o.: what they
  do, scale, history, market position.
- [`people-and-roles.md`](./people-and-roles.md) — the humans who will use the
  system, their access scope, and a permissions matrix.
- [`warehouses.md`](./warehouses.md) — the three physical locations (Říčany
  HQ, Týniště nad Orlicí branch, Sezimovo Ústí branch) and how stock moves
  between them.

## 3. The domain

- [`domain-glossary.md`](./domain-glossary.md) — Czech ↔ English glossary of
  every term that will appear on a screen or document. Read before any screen
  file. Authoritative on spellings.
- [`workflows.md`](./workflows.md) — end-to-end narrative workflows
  (inbound, outbound + dodací list, transfer, owner correction). Names the
  screens each workflow touches.
- [`product-ideology.md`](./product-ideology.md) — the hardest open area:
  raw spices vs. mixtures, pack-size granularity, mixing jobs. Describes,
  does not decide.

## 4. What is still undecided

- [`open-questions.md`](./open-questions.md) — living list, grouped by when
  the question blocks progress (before code, before MVP, later).
- [`tech-options.md`](./tech-options.md) — the researched menu of candidate
  technologies, **explicitly not chosen**. The only standing commitment is:
  if Python is added, the toolchain is `uv`.

## 5. Provenance

- [`research-sources.md`](./research-sources.md) — public sources used to
  compile the company profile, with notes on what to re-check on refresh.

## 6. Companion directories

- [`screens/`](./screens/) — screen-by-screen functional design. Each screen
  is one file; numbered `01-…` through `14-…`, then `future-*.md` for the
  post-MVP screens. Use the glossary spellings throughout.
- [`public-site.md`](./public-site.md) — the public marketing site (`web`
  app) at `/`: IA, per-page content map, and Czech copy notes. The public
  counterpart to `screens/` (per decisions 0049 + 0050).
- [`decisions/`](./decisions/) — append-only decision log. Format described in
  [`decisions/README.md`](./decisions/README.md). As of this commit, empty.

## Conventions

- Czech-first domain language. The owner sees Czech on every screen.
- Cross-references use relative links. Forward references to files that don't
  yet exist (e.g. specific screen files) are deliberate — they are written in
  parallel.
- No emojis. No specific technology mentioned outside `tech-options.md`.
