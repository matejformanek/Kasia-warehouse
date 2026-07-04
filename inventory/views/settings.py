"""Settings edit + SMTP test."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..forms import (
    SettingsForm,
    SettingsRecipientFormSet,
    SmtpTestForm,
)
from ..models import (
    Branch,
    DodaciListNumberSequence,
    Settings,
)
from ..services import (
    _smtp_connection_from_settings,
)
from ._shared import _require_vlastnik


def _branch_counters_summary() -> list[dict]:
    """For the read-only 'Číslování' subsection. One entry per branch
    with the latest counter (or None) for the current year."""
    from datetime import date as _date

    year = _date.today().year
    rows = []
    for b in Branch.objects.filter(is_active=True).order_by("code"):
        seq = DodaciListNumberSequence.objects.filter(
            branch=b, year=year
        ).first()
        last = seq.last_counter if seq else 0
        rows.append(
            {
                "branch": b,
                "year": year,
                "last_counter": last,
                "preview": (
                    f"{b.code}-{year}-{last:04d}" if last else f"{b.code}-{year}-—"
                ),
            }
        )
    return rows


def settings_edit(request):
    _require_vlastnik(request)
    instance = Settings.load()
    from ..models import SettingsRecipient
    recipient_qs = SettingsRecipient.objects.all().order_by(
        "-is_active", "sort_order", "id"
    )
    if request.method == "POST":
        form = SettingsForm(request.POST, request.FILES, instance=instance)
        recipient_formset = SettingsRecipientFormSet(
            request.POST, queryset=recipient_qs, prefix="recipient"
        )
        if form.is_valid() and recipient_formset.is_valid():
            form.save()
            recipient_formset.save()
            messages.success(request, "Nastavení uloženo.")
            return redirect("inventory:settings_edit")
    else:
        form = SettingsForm(instance=instance)
        recipient_formset = SettingsRecipientFormSet(
            queryset=recipient_qs, prefix="recipient"
        )

    smtp_test_form = SmtpTestForm(initial={"to_email": request.user.email})

    return render(
        request,
        "inventory/settings_form.html",
        {
            "form": form,
            "recipient_formset": recipient_formset,
            "settings": instance,
            "smtp_test_form": smtp_test_form,
            "branch_counters": _branch_counters_summary(),
            "branches": Branch.objects.filter(is_active=True).order_by("code"),
        },
    )


@require_POST
def settings_test_smtp(request):
    _require_vlastnik(request)
    form = SmtpTestForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Neplatná e-mailová adresa.")
        return redirect("inventory:settings_edit")

    to_email = form.cleaned_data["to_email"]
    s = Settings.load()

    # Same code path as the real dodák send — per decision 0049 the
    # helper is the single SMTP-connection construction site.
    from django.core.mail import EmailMessage

    from_address = s.email_from_address or None
    from_name = s.email_from_name or "Kasia vera"
    sender = (
        f"{from_name} <{from_address}>" if from_address else None
    )

    try:
        connection = _smtp_connection_from_settings(s)
        msg = EmailMessage(
            subject="Test e-mailu — Kasia vera",
            body=(
                "Toto je testovací e-mail z aplikace Kasia vera — sklad. "
                "Pokud čtete tento text, SMTP nastavení funguje."
            ),
            from_email=sender,
            to=[to_email],
            connection=connection,
        )
        msg.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — surface any SMTP error to operator
        messages.error(
            request,
            f"Test e-mailu selhal: {exc}",
        )
        return redirect("inventory:settings_edit")

    messages.success(request, f"Testovací e-mail odeslán na {to_email}.")
    return redirect("inventory:settings_edit")


# ---------------------------------------------------------------------------
# Pass 5 — Supplier CRUD (per decision 0040)
#
# Tier: all authenticated users (vlastník + obsluha).
# Routes: /dodavatele/, /dodavatele/novy/, /dodavatele/<pk>/upravit/,
#         /dodavatele/<pk>/archivovat/, /dodavatele/<pk>/aktivovat/.
# ---------------------------------------------------------------------------


