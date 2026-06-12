# Vendored static assets

Per [`context/decisions/0018-frontend-htmx.md`](../../../context/decisions/0018-frontend-htmx.md)
htmx is shipped as a single vendored static asset (no JS bundler, no
Node).

| File | Source | Pinned version | Licence |
|---|---|---|---|
| `htmx.min.js` | https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js | 2.0.4 | BSD-2-Clause / Zero |

To upgrade: fetch the new version into this directory, run the test
suite, run `uv run python manage.py collectstatic --noinput` (WhiteNoise
re-hashes the file on next deploy), bump the version in this table.
