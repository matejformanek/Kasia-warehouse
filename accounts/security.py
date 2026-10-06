"""Login brute-force helpers (decision 0104).

- ``client_ip`` — the real client address behind the Caddy proxy. Used as
  ``AXES_CLIENT_IP_CALLABLE`` (so django-axes keys lockouts per username + IP,
  not per the Caddy container) and by the password-reset throttle.
- ``ThrottledPasswordResetView`` — Django's ``PasswordResetView`` with a small
  cache-based per-IP limit on POST, so the public reset form can't be used to
  spam inboxes / the SMTP account.
"""

from __future__ import annotations

from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.shortcuts import render

# Per-IP password-reset POSTs allowed per window. The cache is the default
# per-process LocMem (no CACHES configured), so with N gunicorn workers the
# effective ceiling is up to N x this — still a hard bound, no new infra.
PASSWORD_RESET_LIMIT = 5
PASSWORD_RESET_WINDOW_SECONDS = 60 * 60


def client_ip(request) -> str | None:
    """Client IP as seen by Caddy.

    Caddy (no ``trusted_proxies`` configured) *replaces* any client-sent
    ``X-Forwarded-For`` with the real peer address, and ``web:8000`` is not
    published outside the compose network — so the header is trustworthy.
    The RIGHTMOST entry is used: it is the one the nearest proxy (Caddy)
    wrote, so even if Caddy ever switched to appending, a spoofed leftmost
    value could not pick the lockout key. Falls back to ``REMOTE_ADDR``
    (tests, direct access).
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.META.get("REMOTE_ADDR")


class ThrottledPasswordResetView(auth_views.PasswordResetView):
    """``PasswordResetView`` that refuses more than ``PASSWORD_RESET_LIMIT``
    POSTs per client IP per hour (429 + the Czech lockout page)."""

    def post(self, request, *args, **kwargs):
        key = f"pwreset-ip:{client_ip(request) or 'unknown'}"
        # add() is a no-op if the key exists, so the window starts at the
        # first attempt and is not extended by later ones.
        cache.add(key, 0, PASSWORD_RESET_WINDOW_SECONDS)
        try:
            attempts = cache.incr(key)
        except ValueError:  # expired between add() and incr()
            cache.set(key, 1, PASSWORD_RESET_WINDOW_SECONDS)
            attempts = 1
        if attempts > PASSWORD_RESET_LIMIT:
            return render(request, "registration/locked_out.html", status=429)
        return super().post(request, *args, **kwargs)
