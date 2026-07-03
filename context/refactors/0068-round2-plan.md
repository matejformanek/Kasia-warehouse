# 0068 restructure — Round 2 plan (post-compact handoff)

> **Read this first if you're picking up after a compact.** Round 1 (the big
> technical restructure) is **done and on PR #26**. This doc is the cold-start
> anchor for **Round 2**: a second big pass *on top of PR #26* to tune the new
> structure and find anything that can still be improved. Companion to
> [`decisions/0068`](../decisions/0068-code-architecture-restructure.md) +
> [`0069`](../decisions/0069-css-externalization.md),
> [`../architecture.md`](../architecture.md), and the
> [discrepancy log](./0068-restructure-discrepancies.md).

## Where things stand (Round 1 — done)

- **Branch:** `ft_arch_restructure` · **PR #26** (open, base `main`). Repo
  `matejformanek/Kasia-warehouse`. Merging to `main` deploys to prod.
- **14+ commits**, all green at every checkpoint. Behavior-preserving; **no
  migration, no schema, no visual change.**
- **Verification gates that MUST stay green** (run all before any Round-2 commit):
  - `uv run pytest -q` → **406 pass**
  - `uv run ruff check .` → clean
  - `uv run python manage.py check` → 0 issues
  - `uv run python manage.py makemigrations --check --dry-run` → **No changes**
  - `uv run python manage.py collectstatic --noinput` → succeeds (now also a CI gate)
  - Visual: `make up` → walk screens; render is byte-identical to prod.
- **Docker stack is UP** locally (`make up`): http://localhost/ (public),
  http://localhost/sklad/ (login `karolina@kasia.local` / `heslo1234`, or
  `admin@kasia.local`, `tyn@…`, `sez@…`, all `heslo1234`). `.env` was copied
  from the main checkout into the worktree (gitignored, not committed).

### What Round 1 delivered
- **D1** — six `inventory` monoliths → re-exporting packages
  (`models/ services/ views/ forms/ admin/ tests/`).
- **D2** — `services/counterparties.py` registry; `accounts/permissions.py`
  (`require_vlastnik` + `RequireVlastnikMixin`); `inventory/forms/base.py`
  name-validator; `services/movement.py::build_movement()`; Supplier/Customer
  CRUD → `inventory/views/_crud.py` class-based views (Branch left function-based).
- **D3** — extracted `catalogue_index` row builder; deliberately left the
  transaction orchestrators + view-state closures cohesive (see discrepancy log).
- **D4** — all inline `<style>` → `kasia/static/css/`
  (`tokens-{sklad,web}.css`, `base-{sklad,web}.css`, `pages/*.css`), `<link>`-only.
- **D5** — dropped (test static-storage override proven unnecessary).

## Round 2 — candidate improvements (the work to plan)

Round 2 is **the same shape as Round 1**: explore → plan (log decisions if any
choice is non-trivial) → implement in small tests-green checkpoints → `/pr-harden`.
Stay behavior-preserving unless a new numbered decision says otherwise. Respect
`right-sized-for-small-business.md` (don't over-engineer) and the **locked CSS
class-names + JS/HTMX hooks contract** (renaming needs a decision).

### A. CSS — finish the layering (0069 named a `components/` layer we folded in)
- `base-sklad.css` (341) + `base-web.css` (366) currently hold *all* shared
  classes. 0069's intent was a **`components/` layer** (kpis, tables, dialogs,
  filters, forms). Round 2: split the two base files into `components/*.css`
  loaded via extra `<link>`s in the base templates. Keep cascade order.
- **De-dupe across `pages/*.css`** — 22 page files (some 38–47 LOC). Hunt for
  rules repeated across pages that should hoist into `components/` or `base-*`.
- Confirm no dead CSS (classes no longer emitted by any template).

### B. Long functions still worth a look (Round 1 left these on purpose)
Reassess each — decompose only where it genuinely clarifies (not to hit a number):
- `inventory/views/inventura.py::_build_rows` (**257**, nested closure) and
  `_row_for` (**131**) — best candidates: lift to module-level helpers taking
  explicit params (branch, posted map, order map) instead of closing over view
  locals.
- `inventory/services/movement.py::edit_movement` (**186**) — the field-diff /
  line-diff / audit / dodák-resend phases could become named helpers *inside*
  the same `transaction.atomic` without scattering the transaction.
- `inventory/services/mixing.py::start_mixing_job` (**183**), `finish_mixing_job`
  (**120**) — the fresh-start vs from-PLANNED branches are separable.
- `inventory/views/catalogue.py::product_edit` (**141**) — the 3 formsets
  (recipe / threshold / branch-carry) are independent; one helper each.
- `inventory/views/mixing.py::mixing_job_create` (**124**),
  `product_detail` (**101**), `movements.py::_apply_date` (**128**).

### C. Files still > ~400 LOC (split candidates)
- Source: `views/movements.py` (832), `views/catalogue.py` (711),
  `services/mixing.py` (503), `views/inventura.py` (481), `views/mixing.py` (444).
  `movements.py` mixes history + příjem + výdej + edit — a natural split.
- Tests: several `test_*.py` are 400–786 LOC — fine for tests, but
  `test_inventura`/`test_mixing`/`test_dodaci` could split by sub-feature if it aids nav.

### D. Deeper OOP (only where state clusters — resist ceremony)
- `MixingJobService` / `DodakService` are currently module functions. Assess
  whether a class that carries the job/dodák + branch as instance state removes
  repeated param threading. If it doesn't, leave as functions (right-sizing).
- `ArchivableCRUDMixin` (`_crud.py`) currently covers Supplier/Customer. Reassess
  **Branch** onto a slug-aware CBV now that the pattern exists (Round 1 left it
  function-based — revisit only if clean).

### E. Remaining duplication sweep
- The index status-filter block (`?status=` active/archived/all) appears in
  `_crud.ArchivableIndexView` **and** `branch_index` (function) — unify if Branch
  moves to CBV (D).
- `.exclude(is_internal=True)` picker filtering, movement-line formset building,
  PDF/e-mail boilerplate — grep for repeats.

### F. Documentation completeness
- Every package `__init__` has a layer docstring — verify they're accurate after
  any moves. Keep `architecture.md` in sync. Consider per-package one-liners for
  the largest modules.

## Guardrails for Round 2 (do not regress these)
- Behavior-preserving by default; **log every surfaced inconsistency** in
  [`0068-restructure-discrepancies.md`](./0068-restructure-discrepancies.md);
  anything that changes behavior/pixels needs explicit approval.
- Keep the re-export `__init__` contract (external imports unchanged) and the
  locked CSS class-names + JS/HTMX hooks.
- New non-trivial choices → a numbered decision (`0070+`) before code.
- One tests-green checkpoint per logical change; finish with `/pr-harden`.
