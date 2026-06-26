"""Public marketing site views (decisions 0049 + 0050).

Every view is decorated ``@login_not_required`` — the global
LoginRequiredMiddleware (decision 0020) has no include-level opt-out, so each
public view must exempt itself, exactly like ``healthz`` and the ``/navrhy/``
redirect in ``kasia/urls.py``. The decorator covers BOTH the GET and POST
branch of the kontakt form; without it a POST would 302 to
``/sklad/prihlaseni/`` before the inquiry is ever saved.
"""

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse

from .content import COMPANY, NAV, PROVOZOVNY
from .forms import ContactInquiryForm
from .models import ContactInquiry

logger = logging.getLogger(__name__)

# Where kontakt-form notifications go. Public marketing address by default;
# overridable via env so it can be retargeted without code changes.
_CONTACT_RECIPIENTS = getattr(
    settings, "CONTACT_INQUIRY_RECIPIENTS", [COMPANY["email"]]
)


def _public_context(active: str, **extra) -> dict:
    """Shared context for every public page: company facts + nav state."""
    ctx = {"company": COMPANY, "nav": NAV, "active": active}
    ctx.update(extra)
    return ctx


@login_not_required
def home(request):
    return render(request, "web/home.html", _public_context("web:home"))


@login_not_required
def o_nas(request):
    return render(request, "web/o_nas.html", _public_context("web:o_nas"))


@login_not_required
def provozovny(request):
    return render(
        request,
        "web/provozovny.html",
        _public_context("web:provozovny", provozovny=PROVOZOVNY),
    )


@login_not_required
def kontakt(request):
    """GET renders the kontakt form; POST persists a ContactInquiry, then
    attempts an e-mail notification (failure never loses the saved row)."""
    if request.method == "POST":
        form = ContactInquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save()
            _notify_inquiry(inquiry)
            return redirect("web:kontakt_ok")
    else:
        form = ContactInquiryForm()
    return render(
        request, "web/kontakt.html", _public_context("web:kontakt", form=form)
    )


@login_not_required
def kontakt_ok(request):
    return render(request, "web/kontakt_ok.html", _public_context("web:kontakt"))


def _notify_inquiry(inquiry: ContactInquiry) -> None:
    """Best-effort e-mail notification of a new poptávka.

    Wrapped in try/except and never re-raised, mirroring
    inventory.services.send_dodaci_list_email (decision 0019). The inquiry is
    already committed; a missing/broken SMTP config must not surface to the
    public visitor or lose the row.
    """
    subject = f"Nová poptávka z webu — {inquiry.name}"
    body = (
        f"Jméno: {inquiry.name}\n"
        f"E-mail: {inquiry.email}\n"
        f"Telefon: {inquiry.phone or '—'}\n"
        f"Odesláno: {inquiry.created_at:%d. %m. %Y %H:%M}\n\n"
        f"Zpráva:\n{inquiry.message}\n"
    )
    try:
        EmailMessage(
            subject=subject,
            body=body,
            to=_CONTACT_RECIPIENTS,
            reply_to=[inquiry.email],
        ).send(fail_silently=False)
    except Exception:  # noqa: BLE001 — durability over uptime (0050)
        logger.warning(
            "Contact inquiry #%s saved but e-mail notification failed",
            inquiry.pk,
            exc_info=True,
        )


# --- robots.txt + sitemap.xml (hand-rolled; no django.contrib.sitemaps) -----
# Right-sized for four pages per decision 0050.
@login_not_required
def robots_txt(request):
    return TemplateResponse(
        request, "web/robots.txt", content_type="text/plain"
    )


@login_not_required
def sitemap_xml(request):
    pages = ["web:home", "web:o_nas", "web:provozovny", "web:kontakt"]
    urls = [request.build_absolute_uri(_reverse(name)) for name in pages]
    return TemplateResponse(
        request,
        "web/sitemap.xml",
        {"urls": urls},
        content_type="application/xml",
    )


def _reverse(name: str) -> str:
    from django.urls import reverse

    return reverse(name)
