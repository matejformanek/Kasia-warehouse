# Kasia-warehouse — agent instructions

This repository is the in-progress design of a warehouse management tool for
**Kasia vera s.r.o.**, a Czech B2B spice distributor. As of this commit, the
repo contains **only context, screen-by-screen functional design, and agent
rules**. No application code exists yet.

## Read in this order

1. **`context/state.md`** — current project status (Done / In progress / Next).
   This is the cold-start anchor. Always read first.
2. **`context/README.md`** — index of all foundational context, with the
   recommended reading order.
3. **`.claude/rules/`** — load-bearing rules that govern how you work in this
   repo. Pay particular attention to `no-premature-tech-choices.md` and
   `state-file-discipline.md`.

## Hard rules (summary — full text in `.claude/rules/`)

- **No premature tech choices.** No framework, DB, container, lockfile, or
  language has been chosen. Do not write code, `pyproject.toml`, `package.json`,
  `Dockerfile`, migrations, or any code-shaped file. Surface options into
  `context/tech-options.md` instead. The only standing tech commitment is:
- **If/when Python is added, the toolchain is `uv`.** Not pip, not poetry,
  not pipenv, not rye, not conda.
- **User-facing text is Czech (`cs_CZ`).** Code, identifiers, comments, and
  commit messages are English. Domain terms use the spellings in
  `context/domain-glossary.md`.
- **Decisions are logged before they land.** Every non-trivial decision gets a
  dated file in `context/decisions/NNNN-slug.md` *before* it shows up in code
  or config.
- **`context/state.md` is updated at the end of every working session.** It
  is the next agent's first read.

## What this repo is not

It is not yet a working application, not a Django project, not an Odoo
customisation, not a JavaScript app. Any reference to a specific technology
must be confined to `context/tech-options.md` until a decision is recorded
in `context/decisions/`.
