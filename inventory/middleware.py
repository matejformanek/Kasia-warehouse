"""Screen-visit tracking middleware (per 0077) — the project's first custom
middleware.

Persists one ``ScreenVisit`` row per authenticated, full-page, successful GET
under ``/sklad/`` (PDF opens included — real usage signal). Registered **last**
in ``MIDDLEWARE``: it needs ``request.user`` (AuthenticationMiddleware) and
``request.htmx`` (HtmxMiddleware), both set on the way in by outer middlewares.
"""

import logging

from .models import ScreenVisit

logger = logging.getLogger(__name__)

# GET htmx fragment endpoints — not screens, never logged. Any NEW GET partial
# endpoint must be added here or it pollutes the Aktivita log (see
# .claude/rules/frontend-and-templates.md). POST endpoints need no entry (the
# method check already skips them).
EXCLUDED_URL_NAMES = frozenset({"line_row_partial", "mixing_preview_partial"})


class ScreenVisitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if self._should_record(request, response):
            try:
                ScreenVisit.objects.create(
                    user=request.user,
                    url_name=request.resolver_match.url_name,
                    namespace=request.resolver_match.namespace or "",
                    path=request.path[:512],
                )
            except Exception:
                # A tracking failure must never break the operator's request.
                logger.exception("ScreenVisit write failed for %s", request.path)
        return response

    @staticmethod
    def _should_record(request, response) -> bool:
        # Cheapest checks first; every miss returns before touching the DB.
        if request.method != "GET":
            # Reads only — writes are MovementAudit's job (0021/0035).
            return False
        if not request.path.startswith("/sklad/"):
            # Warehouse surface only; the public site keeps Umami (0076).
            return False
        if response.status_code != 200:
            # Skips redirects (incl. anonymous → login) and 404s.
            return False
        if not request.user.is_authenticated:
            # Load-bearing, not belt-and-braces: the login and password-reset
            # pages are @login_not_required and serve 200 to anonymous
            # visitors under /sklad/.
            return False
        if getattr(request, "htmx", False):
            # Fragment swaps are not pageviews (no hx-boost in the codebase,
            # so a real page view is never an htmx request).
            return False
        match = request.resolver_match
        if match is None or not match.url_name:
            return False
        if match.url_name in EXCLUDED_URL_NAMES:
            return False
        return True
