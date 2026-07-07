"""Dodaci list numbering, PDF render, e-mail send."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.template.loader import render_to_string

from ..models import (
    DodaciList,
    DodaciListNumberSequence,
    EmailLog,
    Movement,
    Product,
    RecipeComponent,
    Settings,
)
from .email import _active_dodak_recipients, send_and_log


def _reserve_dodak_number(*, branch, year: int) -> int:
    """Allocate the next per-(branch, year) counter under SELECT … FOR UPDATE.

    Must be called inside the caller's transaction.atomic() block — the
    row lock is released at commit.
    """
    seq, _ = (
        DodaciListNumberSequence.objects.select_for_update().get_or_create(
            branch=branch, year=year, defaults={"last_counter": 0}
        )
    )
    seq.last_counter += 1
    seq.save(update_fields=["last_counter"])
    return seq.last_counter


def _create_dodaci_list_for_movement(movement: Movement) -> DodaciList:
    """Insert one DodaciList row for a vydej Movement.

    Inside the caller's atomic block. Computes cislo from
    (branch.code, year, counter) per 0008.
    """
    year = movement.date_issued.year
    counter = _reserve_dodak_number(branch=movement.branch, year=year)
    cislo = f"{movement.branch.code}-{year}-{counter:04d}"
    return DodaciList.objects.create(
        movement=movement,
        branch=movement.branch,
        odberatel=movement.odberatel,
        date_issued=movement.date_issued,
        year_issued=year,
        counter=counter,
        cislo=cislo,
        current_version=1,
        created_by=movement.created_by,
    )


def render_dodaci_list_pdf(dodaci_list: DodaciList) -> bytes:
    """Render the dodák PDF via WeasyPrint per 0017.

    Template is templates/inventory/dodaci_list.html with embedded CSS
    Paged Media. Always re-renders against current Settings + current
    Customer (per 0007 / 0036).
    """
    # Imported lazily — keeps module import cheap for non-PDF callers
    # (admin pages, tests touching services without rendering).
    from pathlib import Path

    from django.conf import settings as django_settings
    from weasyprint import HTML

    lines = list(dodaci_list.movement.lines.all().order_by("id"))

    # WeasyPrint resolves images from disk. When Settings.logo is empty,
    # fall back to the bundled brand mark at
    # kasia/static/brand/kasia-logo.jpg. The template gets an absolute
    # file:// URL it can use directly.
    bundled_logo = Path(django_settings.BASE_DIR) / "kasia" / "static" / "brand" / "kasia-logo.jpg"
    default_logo_url = f"file://{bundled_logo}" if bundled_logo.exists() else ""

    html_string = render_to_string(
        "inventory/dodaci_list.html",
        {
            "dodaci_list": dodaci_list,
            "movement": dodaci_list.movement,
            "lines": lines,
            "show_sarze": any(line.sarze for line in lines),
            "show_note": any(line.note for line in lines),
            "settings": Settings.load(),
            "default_logo_url": default_logo_url,
        },
    )
    return HTML(string=html_string).write_pdf()


def _amounts_summing_to(
    ratios: list[Decimal], total: Decimal, places: int
) -> list[Decimal]:
    """Round each ``ratio * total`` to ``places`` decimals so the rounded
    parts sum **exactly** to ``total``.

    Ratios are assumed to sum to ~1.0 (the importer normalises them). Per-row
    half-up rounding can drift the column total by a few units in the last
    place (e.g. 33.33 × 3 = 99.99, or Knedlík's % summing to 100.01); we put
    the whole rounding difference on the largest line so both the rows and the
    total stay consistent.
    """
    q = Decimal(1).scaleb(-places)  # 0.01 for places=2, 0.001 for places=3
    amounts = [(r * total).quantize(q, rounding=ROUND_HALF_UP) for r in ratios]
    if not amounts:
        return amounts
    diff = total - sum(amounts, Decimal("0"))
    largest = max(range(len(amounts)), key=lambda i: amounts[i])
    amounts[largest] = (amounts[largest] + diff).quantize(q)
    return amounts


def render_recipe_pdf(product: Product, target_qty: Decimal | None = None) -> bytes:
    """Render a mixture's recipe sheet (ingredient amounts for ``target_qty``
    + the free-form mixing notes) to PDF via WeasyPrint, reusing the dodák PDF
    infra (0017).

    ``target_qty`` is the batch size chosen in the "Spočítat dávku" box
    (defaults to 100 kg). The notes are the free-form packing / mixing
    instructions captured from Petr's XLS on import (0048) and stored on
    ``Product.notes``.

    Percentages and per-batch kg are rounded to sum **exactly** to 100 % /
    ``target_qty`` (per 0055 — Knedlík rounded to 100.01 % otherwise).

    Raises ``ValueError`` (Czech) if the product is not a mixture or has no
    recipe rows.
    """
    from pathlib import Path

    from django.conf import settings as django_settings
    from weasyprint import HTML

    if product.kind != Product.Kind.MIXTURE:
        raise ValueError("Recepturu lze stáhnout jen pro směs.")

    components = list(
        RecipeComponent.objects.filter(mixture_product=product)
        .select_related("component_product")
        .order_by("component_product__name_cs")
    )
    if not components:
        raise ValueError("Tato směs nemá vyplněnou recepturu.")

    if target_qty is None or target_qty <= 0:
        target_qty = Decimal("100")
    target_qty = target_qty.quantize(Decimal("0.001"))

    ratios = [c.ratio for c in components]
    pcts = _amounts_summing_to(ratios, Decimal("100"), 2)
    kgs = _amounts_summing_to(ratios, target_qty, 3)
    rows = [
        {"name": c.component_product.name_cs, "pct": pct, "kg": kg}
        for c, pct, kg in zip(components, pcts, kgs, strict=True)
    ]

    bundled_logo = Path(django_settings.BASE_DIR) / "kasia" / "static" / "brand" / "kasia-logo.jpg"
    default_logo_url = f"file://{bundled_logo}" if bundled_logo.exists() else ""

    html_string = render_to_string(
        "inventory/recipe_pdf.html",
        {
            "product": product,
            "rows": rows,
            "target_qty": target_qty,
            "total_pct": sum(pcts, Decimal("0")),
            "notes": product.notes,
            "settings": Settings.load(),
            "default_logo_url": default_logo_url,
        },
    )
    return HTML(string=html_string).write_pdf()


def _substitute_template(text: str, dodaci_list: DodaciList) -> str:
    """Substitute the screen-14 placeholders. Reason placeholder is only
    used in the oprava body; the caller is expected to append the
    operator reason via trigger_reason for the e-mail log."""
    return (
        text
        .replace("<číslo>", dodaci_list.cislo)
        .replace("<datum>", dodaci_list.date_issued.strftime("%d. %m. %Y"))
    )


def send_dodaci_list_email(
    *,
    dodaci_list: DodaciList,
    trigger_reason: str,
    pdf_bytes: bytes,
    sent_by=None,
) -> EmailLog:
    """Send one dodák e-mail to every active SettingsRecipient row per 0052.

    Renders subject/body/from + attaches the PDF, then delegates the send +
    logging to `send_and_log` (per 0075) — which writes a SENT or FAILED
    `EmailLog` row and never re-raises. The výdej / oprava write that triggered
    the send is already committed. `sent_by` records the operator for a manual
    resend (None for the automatic on-commit send).
    """
    s = Settings.load()
    recipients = _active_dodak_recipients()
    is_oprava = trigger_reason.startswith("oprava")
    subject_template = (
        s.template_oprava_subject if is_oprava else s.template_initial_subject
    )
    body_template = s.template_oprava_body if is_oprava else s.template_initial_body
    subject = _substitute_template(subject_template, dodaci_list)
    body = _substitute_template(body_template, dodaci_list)
    if is_oprava:
        operator_reason = trigger_reason[len("oprava:") :].strip()
        body = body.replace("<text zdůvodnění od operátorky>", operator_reason)

    from_email = (
        f"{s.email_from_name} <{s.email_from_address}>"
        if s.email_from_name and s.email_from_address
        else (s.email_from_address or None)
    )

    # Category mirrors the migration 0019 derivation (resend checked first).
    if trigger_reason == "ruční opětovné odeslání":
        category = EmailLog.Category.DODACI_RESEND
    elif is_oprava:
        category = EmailLog.Category.DODACI_OPRAVA
    else:
        category = EmailLog.Category.DODACI_VYSTAVENI

    return send_and_log(
        category=category,
        trigger_reason=trigger_reason,
        subject=subject,
        body=body,
        recipients=recipients,
        from_email=from_email,
        attachments=[(f"{dodaci_list.cislo}.pdf", pdf_bytes, "application/pdf")],
        dodaci_list=dodaci_list,
        dodaci_version=dodaci_list.current_version,
        sent_by=sent_by,
    )


# ---------------------------------------------------------------------------
# Mixing job services (screen 15, per decision 0039)
# ---------------------------------------------------------------------------


