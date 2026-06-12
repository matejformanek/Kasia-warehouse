# Multi-stage build per context/decisions/0022-container-image.md.
# Builder installs Python deps via uv into a project-local .venv;
# runtime carries only the Pango stack + DejaVu fonts + the .venv.

ARG PYTHON_VERSION=3.14
ARG UV_VERSION=0.5

# --- uv binary ----------------------------------------------------------------
# Newer buildx refuses variable expansion in COPY --from=…; the workaround is
# to pull the uv image into a named stage so subsequent COPY --from=uv_stage
# is a plain reference. (Error seen on main pre-fix:
# "variable expansion is not supported for --from".)
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_stage

# --- builder ----------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS builder

COPY --from=uv_stage /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# --- runtime ----------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS runtime

# WeasyPrint runtime: Pango + HarfBuzz + a font with full Czech diacritics.
# Cairo is intentionally omitted (no longer a runtime dep of WeasyPrint).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        fonts-dejavu-core \
        tini \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app . /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=kasia.settings.base

RUN mkdir -p /app/staticfiles && chown -R app:app /app/staticfiles
RUN DJANGO_SECRET_KEY=build-only DJANGO_ALLOWED_HOSTS=* \
        python manage.py collectstatic --noinput

USER app
EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "kasia.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
