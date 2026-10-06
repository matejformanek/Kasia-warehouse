"""Base settings for the Kasia warehouse project.

Per context/decisions/0015-framework-django.md and downstream tech
decisions. Env-driven; the same module is used for local docker
compose and for the production VPS — runtime differences come from
.env. See ``.env.example`` for all runtime-configurable variables.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


_DEV_SECRET_KEY = "insecure-dev-key-do-not-use-in-prod"
# The placeholder shipped in .env.example — a copied-but-unedited .env.
_EXAMPLE_SECRET_KEY = "change-me-to-a-long-random-string"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _DEV_SECRET_KEY)
DEBUG = _env_bool("DJANGO_DEBUG", default=False)

# Per 0104: refuse to run a non-DEBUG process on a missing/known key (forged
# sessions + password-reset tokens). On prod this fails the deploy's
# `migrate` step, so the old container keeps serving. Skipped under pytest
# (host `make test` runs with no env); the Docker build passes its own
# throwaway key for collectstatic, CI passes `ci-only-secret`.
if (
    not DEBUG
    and SECRET_KEY in {"", _DEV_SECRET_KEY, _EXAMPLE_SECRET_KEY}
    and "pytest" not in sys.modules
):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is missing or a known default; set a real key in "
        ".env (or DJANGO_DEBUG=1 for local development)."
    )
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# Behind the TLS-terminating Caddy proxy (per 0024 / 0056). Caddy sets
# X-Forwarded-Proto; this lets Django emit https:// links + treat the
# request as secure. Caddy preserves the original Host, so no
# USE_X_FORWARDED_HOST. No SECURE_SSL_REDIRECT — Caddy does the redirect.
# All env-gated so behaviour is unchanged until the on-box .env opts in.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SECURE_COOKIES", default=False)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_SECURE_COOKIES", default=False)
# Per 0104: a session lasts one working day (12 h), not Django's 2 weeks —
# a forgotten session on a shared warehouse PC expires overnight.
SESSION_COOKIE_AGE = 12 * 60 * 60
# HSTS is deliberately NOT set here (per 0104): Caddy adds it on the prod
# kasia.cz host only. A Django-side SECURE_HSTS_SECONDS would also fire on
# local `make up` (https://localhost via `tls internal`) and pin HSTS on
# localhost in the developer's browser. `check --deploy` W004 is accepted.

# Absolute base URL (scheme + host, no trailing slash) for links in outgoing
# e-mails. The send path runs off-request (on_commit / management commands), so
# there is no request to derive the host from — a link built from reverse()
# alone would be a bare path a user can't click. Per-deployment via env
# (documented in .env.example); defaults to local dev. On the box set
# SITE_BASE_URL=https://kasia.cz.
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://localhost").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    # Login brute-force lockout (per 0104).
    "axes",
    "accounts",
    "inventory",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise must be directly after SecurityMiddleware per
    # context/decisions/0018-frontend-htmx.md.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Every view requires login unless decorated with @login_not_required
    # (Django 5.1+). The warehouse app lives under /sklad/ and is fully gated;
    # the public marketing site at / (web app) opts out per-view with
    # @login_not_required. See decisions 0020, 0050. (The /navrhy/ gallery,
    # decision 0047, was retired per 0067.)
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # Last app middleware on purpose (per 0077; only AxesMiddleware follows):
    # the response-phase ScreenVisit write needs
    # request.user (AuthenticationMiddleware) and request.htmx (HtmxMiddleware),
    # both set by the outer middlewares before the inner chain runs.
    "inventory.middleware.ScreenVisitMiddleware",
    # django-axes (per 0104) — the axes docs want it last; it only turns an
    # AxesBackend lockout signal into the lockout response, so sitting after
    # ScreenVisitMiddleware changes nothing for 0077.
    "axes.middleware.AxesMiddleware",
]

# --- Auth flow (per 0020; paths moved under /sklad/ per 0050) ---------------
# Name-based, so they re-resolve to the new /sklad/ paths automatically.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inventory:home"
# After logout, land on the public marketing homepage rather than the login
# screen (per 0050 — the public site is now the natural front door).
LOGOUT_REDIRECT_URL = "web:home"

ROOT_URLCONF = "kasia.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "kasia" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Umami tracker vars, public paths only (decision 0076).
                "web.context_processors.umami",
                # site_url + canonical_url for the public SEO head (0106).
                "web.context_processors.seo",
            ],
        },
    },
]

WSGI_APPLICATION = "kasia.wsgi.application"
ASGI_APPLICATION = "kasia.asgi.application"

# --- Database ---------------------------------------------------------------
# Per context/decisions/0016-database-postgres.md. SQLite fallback is for
# `manage.py check` on a fresh checkout only; real work uses the docker
# compose `db` service.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    ),
}

# --- Auth (per 0020) --------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# AxesStandaloneBackend first (per 0104): it counts failures and blocks a
# locked-out (username, IP) pair before ModelBackend checks the password.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# --- Login brute-force lockout (django-axes, per 0104) ---------------------
# 5 failures lock that (username, client IP) pair for an hour — keyed on BOTH
# so one attacker can't lock a user out from everywhere and one IP can't lock
# everybody out. Covers /sklad/prihlaseni/ and /admin/ (both authenticate via
# `username=`). Break-glass unlock: infra/RUNBOOK.md (`axes_reset`).
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
# Django's AuthenticationForm posts the e-mail as `username` (axes >= 7.0.2
# would otherwise look for USERNAME_FIELD = "email" and key on None).
AXES_USERNAME_FORM_FIELD = "username"
# The real client IP behind Caddy (rightmost X-Forwarded-For), not the proxy's.
AXES_CLIENT_IP_CALLABLE = "accounts.security.client_ip"
AXES_LOCKOUT_TEMPLATE = "registration/locked_out.html"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Localisation (per .claude/rules/language-conventions.md) --------------
LANGUAGE_CODE = "cs"
TIME_ZONE = "Europe/Prague"
USE_I18N = True
USE_TZ = True

# HTML5 <input type="date"> requires ISO YYYY-MM-DD to display a pre-filled
# value. Keep Czech formats as fallback parsers so a user can still type
# "28.06.2026" by hand.
DATE_INPUT_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d. %m. %Y"]

# --- Static files (WhiteNoise compressed manifest, per 0018) ---------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []
if (BASE_DIR / "kasia" / "static").exists():
    STATICFILES_DIRS.append(BASE_DIR / "kasia" / "static")
# The design-option mockups (top-level `design-options/`) were served under
# /static/navrhy/ for review (decision 0047). Retired per 0067: the files stay
# in the repo (in case we revisit a direction) but are no longer served, so the
# gallery is unavailable on both surfaces. Do NOT re-add this without a decision.

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- Media (operator-uploaded files — Settings.logo per 0037) --------------
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- E-mail (per 0019) ------------------------------------------------------
# Env-overridable so local dev can catch mail without a real SMTP server
# (e.g. django.core.mail.backends.console.EmailBackend prints to the web log).
# Default is the real SMTP backend, so prod is unchanged when the var is unset.
# The app builds its own SMTP connection from Settings (0049) via
# get_connection(), which honours this backend class — a console/filebased
# backend simply ignores the host/port/TLS kwargs, so overriding here catches
# every send path (app e-mails AND Django's password-reset mail).
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.cz")
# Fixed admin address notified on every new Podpora report (per 0079). Not a
# SettingsRecipient — this is the app operator, not the dodák-list recipients.
FEEDBACK_NOTIFY_EMAIL = os.environ.get(
    "FEEDBACK_NOTIFY_EMAIL", "matej.formanek@kasia.cz"
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
