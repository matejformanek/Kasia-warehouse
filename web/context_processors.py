"""Context processors for the public marketing site.

`company` / `nav` stay per-view (``web/views.py::_public_context``) because
the login page gets them via a static ``extra_context`` dict on ``LoginView``,
which cannot compute anything request-derived — hence these processors.
"""

import os


def umami(request):
    """Umami tracker vars for the public base template (decision 0076).

    Read os.environ at request time, NOT at module import and NOT via a
    Django setting — the tests monkeypatch the env per request, and the
    settings-file convention (env read at import, e.g. EMAIL_HOST) would
    silently break them.
    """
    # Path-based privacy gate (decision 0076): never expose the tracker on
    # warehouse paths even though /sklad/prihlaseni/ extends web/base.html.
    if request.path.startswith("/sklad/") or request.path.startswith("/admin/"):
        return {"umami_website_id": "", "umami_src": ""}
    return {
        "umami_website_id": os.environ.get("UMAMI_WEBSITE_ID", ""),
        "umami_src": os.environ.get(
            "UMAMI_SCRIPT_URL", "https://analytics.kasia.cz/script.js"
        ),
    }


def public_base_url(request) -> str:
    """Scheme + host with no trailing slash, e.g. ``https://kasia.cz``.

    No configured base-URL setting on purpose (decision 0106): in prod Caddy
    is the only external path to Django and canonicalizes every host to
    ``https://kasia.cz`` (0056 — apex 301s for the IP and www), so ``request``
    already carries the canonical scheme + host. Locally and under tests the
    same code yields ``http://localhost`` / ``http://testserver``.

    Shared by the ``seo`` context processor and ``web.views.sitemap_xml`` so
    the head, robots.txt, and sitemap.xml can never disagree on the host.
    """
    return f"{request.scheme}://{request.get_host()}"


def seo(request) -> dict:
    """Expose ``site_url`` + ``canonical_url`` to every template render (0106)."""
    base = public_base_url(request)
    return {"site_url": base, "canonical_url": base + request.path}
