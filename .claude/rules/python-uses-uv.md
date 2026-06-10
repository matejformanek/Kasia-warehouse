**Python is in use per [`decisions/0014-language-python-uv.md`](../../context/decisions/0014-language-python-uv.md); the toolchain is `uv` — no exceptions, no alternatives. The hard constraints below are now in force.**

Pinned: Python 3.14 (committed `.python-version`), `pyproject.toml` + `uv.lock` committed, all commands run via `uv run …`.

## Hard constraints

- No `pip install`. No `requirements.txt`. Dependencies are uv-managed via `pyproject.toml` + `uv.lock`.
- No `poetry`, no `pipenv`, no `rye`, no `conda`, no `pdm`, no plain `python -m venv`.
- All Python commands run via `uv run …` (e.g. `uv run pytest`, `uv run python script.py`).
- Environment setup is `uv sync`.
- Adding a dependency is `uv add <pkg>` (use `--dev` for dev-only).
- Removing a dependency is `uv remove <pkg>`.
- The Python version is pinned via `uv python pin <version>`, producing a `.python-version` file that is committed.

## Why

The owner of this repo has standardised on `uv` across projects. Mixing Python toolchains across repos creates support load, surprises on cold-start, and lockfile churn. `uv` is fast enough and stable enough that there is no live debate to reopen here.

## Interaction with other rules

- This rule does **not** override `no-premature-tech-choices.md`. You still cannot write a `pyproject.toml` or any `.py` file until a decision in `context/decisions/` says Python is in use.
- Once that decision exists, *how* Python is set up is already settled — bootstrap with `uv init`, `uv python pin`, and `uv add` for the agreed initial dependencies.
