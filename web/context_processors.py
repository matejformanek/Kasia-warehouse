"""Context processors for the public marketing site.

First custom context processor in the project — `company` / `nav` stay
per-view (``web/views.py::_public_context``) because the login page gets them
via a static ``extra_context`` dict on ``LoginView``, which cannot compute the
request-path gate this processor exists for.
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
