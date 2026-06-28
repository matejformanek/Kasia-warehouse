**No code, no configs, no stack names until the relevant decision is recorded in `context/decisions/`.**

> **Status (2026-06-08): stack chosen in decisions [`0014`](../../context/decisions/0014-language-python-uv.md)–[`0027`](../../context/decisions/0027-hosting-hetzner.md). The blocking gate is lifted for the layers those decisions cover** — language, framework, DB, PDF, frontend, e-mail, auth, audit, container, compose, TLS proxy, IaC, CI/CD, hosting. Code in those layers is now welcome. **This rule still applies in full to any new layer that isn't in 0014–0027** (e.g. caching, background queue, observability, search). For those, surface options in `context/tech-options.md` first; record a numbered decision before code lands. **Front-end design direction/layout is decision-gated too** (see [`0054`](../../context/decisions/0054-adopt-ui-directions.md) and [`design-system.md`](./design-system.md)) — it is *not* a `context/tech-options.md` entry. The adopted directions (sklad sidebar/sharp/green; public centered/curvy/green) are locked; restyling within them is welcome, but a structural redesign of either base template — or renaming the shared CSS classes / moving the JS-HTMX hooks — needs a new decision.

This is a load-bearing rule. The project is in a deliberate pre-code phase: ~6 active users at a small Czech company means a wrong early stack choice costs months. Defer until requirements (especially product-ideology decisions in `context/product-ideology.md`) crystallise.

## Until a decision exists in `context/decisions/`, do NOT

- Write any code file — `.py`, `.ts`, `.js`, `.rb`, `.go`, `.rs`, `.sql`, `.html` (other than rendered docs), `.css`, `.vue`, `.svelte`, etc.
- Write package manifests — `pyproject.toml`, `package.json`, `Cargo.toml`, `Gemfile`, `composer.json`, `go.mod`, etc.
- Write lockfiles of any kind.
- Write a `Dockerfile`, `docker-compose.yml`, `Procfile`, Kubernetes manifests, Helm charts, Terraform files.
- Write database migrations or schema DDL.
- Write linter / formatter / test-runner configs (`.eslintrc`, `ruff.toml`, `pytest.ini`, `.prettierrc`, etc.).
- Create a folder layout for code (`apps/`, `src/`, `kasia/`, `backend/`, `frontend/`, etc.).
- Even *mention* a specific framework, ORM, DB engine, container runtime, hosting platform, or CI provider in any file other than `context/tech-options.md`.

The one exception is the pre-committed Python toolchain choice — see `python-uses-uv.md`. That rule does not imply Python will be used.

## What to do instead

- Surface candidate technologies into `context/tech-options.md` with trade-offs. Compare; do not pick.
- If the user pushes to "just pick something," respond by drafting a `context/decisions/NNNN-<slug>.md` entry (see `decision-log-discipline.md` and `context/decisions/README.md`) and asking for explicit confirmation. The decision must be merged before any code lands.
- When in doubt, write more context, not more code. Expand `context/open-questions.md`, `context/workflows.md`, or `context/domain-glossary.md` first.

## Why this rule exists

Kasia vera s.r.o. is a ~30-employee Czech B2B spice distributor with ~6 active users on this tool. The cost profile of a wrong stack choice (framework rewrites, hosting migrations, schema redesigns) dwarfs the cost of spending another week in `context/`. The product-ideology is still forming; binding it to a stack now would freeze choices that should remain open.

## How violations are recognised

If a future agent sees code, configs, or stack-specific files in this repo and cannot trace them back to a numbered file under `context/decisions/`, the agent should: stop, flag the gap, and propose either (a) drafting the missing decision or (b) reverting the premature artefact. Both are valid; the user picks.
