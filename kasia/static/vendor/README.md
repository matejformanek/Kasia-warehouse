# Vendored static assets

Per [`context/decisions/0018-frontend-htmx.md`](../../../context/decisions/0018-frontend-htmx.md)
htmx (and, per [`0107`](../../../context/decisions/0107-analytics-dashboard-chartjs.md), Chart.js on the Statistiky page only) are shipped as single vendored static assets (no JS bundler, no
Node).

| File | Source | Pinned version | Licence |
|---|---|---|---|
| `htmx.min.js` | https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js | 2.0.4 | BSD-2-Clause / Zero |
| `chart.umd.min.js` | https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js (Statistiky, per 0107) | 4.4.7 | MIT (trailing `sourceMappingURL` comment removed: the manifest storage would 500 on the missing .map) |

To upgrade: fetch the new version into this directory, run the test
suite, run `uv run python manage.py collectstatic --noinput` (WhiteNoise
re-hashes the file on next deploy), bump the version in this table.
