"""Reorder thresholds, reservations, low-stock summary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.mail import EmailMessage

from ..models import (
    Branch,
    MixingJob,
    MixingJobLine,
    Movement,
    MovementLine,
    PlannedTransfer,
    Product,
    Settings,
    Stock,
    StockThresholdOverride,
)
from .email import _active_low_stock_recipients, _smtp_connection_from_settings


@dataclass
class LowStockRow:
    """One (product, branch) row below threshold for the dashboard panel
    and the daily summary e-mail."""

    product: Product
    branch: Branch
    on_hand: Decimal
    reserved: Decimal
    effective: Decimal
    threshold: Decimal
    deficit: Decimal
    # Per 0057: informational PLANNED-order overlay. None when the pair has
    # no open objednávka. These do NOT affect effective/deficit/membership
    # or the deficit-DESC sort — purely a badge + presentation hint.
    ordered_kg: Decimal | None = None
    ordered_eta: date | None = None


def threshold_for(product: Product, branch: Branch) -> Decimal | None:
    """Return the per-(product, branch) reorder threshold per 0043.

    Lookup order: branch-specific override row, then the product
    default, then None (no alert).
    """
    override = StockThresholdOverride.objects.filter(
        product=product, branch=branch
    ).first()
    if override is not None:
        return override.threshold_kg
    return product.reorder_threshold_kg


def reserved_kg(product: Product, branch: Branch) -> Decimal:
    """Sum outgoing reservations at one branch for one product per 0044.

    Two sources:
    - PLANNED MixingJobLine.derived_qty where the job runs at `branch`
      AND the line's component_product == `product`.
    - PLANNED PlannedTransfer.quantity_kg where source_branch == `branch`
      AND product == `product`.

    Does NOT subtract incoming planned transfers — reservations are
    outgoing-only in MVP. Returns Decimal("0.000") when nothing matches.
    """
    from django.db.models import Sum

    mixing_total = (
        MixingJobLine.objects.filter(
            mixing_job__state=MixingJob.State.PLANNED,
            mixing_job__branch=branch,
            component_product=product,
        ).aggregate(s=Sum("derived_qty"))["s"]
        or Decimal("0.000")
    )
    transfer_total = (
        PlannedTransfer.objects.filter(
            state=PlannedTransfer.State.PLANNED,
            source_branch=branch,
            product=product,
        ).aggregate(s=Sum("quantity_kg"))["s"]
        or Decimal("0.000")
    )
    return (mixing_total + transfer_total).quantize(Decimal("0.001"))


def effective_kg(product: Product, branch: Branch) -> Decimal:
    """Stock.quantity − reserved_kg(product, branch) per 0043.

    Returns Decimal("0.000") when no Stock row exists.
    """
    stock = Stock.objects.filter(product=product, branch=branch).first()
    on_hand = stock.quantity if stock else Decimal("0.000")
    return (on_hand - reserved_kg(product, branch)).quantize(Decimal("0.001"))


def low_stock_rows() -> list[LowStockRow]:
    """Every carried (product, branch) pair where a threshold is set and
    effective < threshold. Sorted by deficit DESC.

    Used by the owner dashboard panel, branch dashboard, product
    detail page, AND the daily summary e-mail. One source of truth.

    Per 0053, a branch *carries* a product iff a Stock row exists for
    that pair — branches without a row do not enter this report.
    """
    rows: list[LowStockRow] = []
    stocks = list(
        Stock.objects.select_related("product", "branch")
        .filter(branch__is_active=True, product__is_active=True)
        .order_by("product__name_cs", "branch__code")
    )
    if not stocks:
        return rows

    overrides_by_pair = {
        (o.product_id, o.branch_id): o.threshold_kg
        for o in StockThresholdOverride.objects.filter(
            product__in={s.product_id for s in stocks},
            branch__in={s.branch_id for s in stocks},
        )
    }

    # Per 0059: overlay open (PLANNED) príjem lines per (product, branch) so a
    # low row can show an "Objednáno" badge. Informational only — does NOT
    # change effective/deficit/membership or the sort below. Re-sourced from
    # PLANNED príjem Movement lines (was PlannedOrder under 0057).
    from django.db.models import Min, Sum

    orders_by_pair: dict[tuple[int, int], tuple[Decimal, date]] = {}
    for row in (
        MovementLine.objects.filter(
            movement__status=Movement.Status.PLANNED,
            movement__kind=Movement.Kind.PRIJEM,
            product__in={s.product_id for s in stocks},
            movement__branch__in={s.branch_id for s in stocks},
        )
        .values("product_id", "movement__branch_id")
        .annotate(total=Sum("quantity_kg"), eta=Min("movement__expected_on"))
    ):
        orders_by_pair[(row["product_id"], row["movement__branch_id"])] = (
            row["total"],
            row["eta"],
        )

    for stock in stocks:
        product = stock.product
        branch = stock.branch
        threshold = overrides_by_pair.get((product.pk, branch.pk))
        if threshold is None:
            threshold = product.reorder_threshold_kg
        if threshold is None:
            continue
        on_hand = stock.quantity
        reserved = reserved_kg(product, branch)
        effective = (on_hand - reserved).quantize(Decimal("0.001"))
        if effective < threshold:
            ordered = orders_by_pair.get((product.pk, branch.pk))
            rows.append(
                LowStockRow(
                    product=product,
                    branch=branch,
                    on_hand=on_hand,
                    reserved=reserved,
                    effective=effective,
                    threshold=threshold,
                    deficit=(threshold - effective).quantize(Decimal("0.001")),
                    ordered_kg=(ordered[0] if ordered else None),
                    ordered_eta=(ordered[1] if ordered else None),
                )
            )
    rows.sort(key=lambda r: r.deficit, reverse=True)
    return rows


def seed_branch_carriage_for_product(product: Product) -> None:
    """Create a 0-kg Stock row for every active Branch that does not
    already carry `product`. Per 0053, row existence IS the carry-flag.

    Idempotent: skips branches that already have a Stock row.
    """
    existing_branch_ids = set(
        Stock.objects.filter(product=product).values_list("branch_id", flat=True)
    )
    for branch in Branch.objects.filter(is_active=True):
        if branch.pk in existing_branch_ids:
            continue
        Stock.objects.create(
            product=product, branch=branch, quantity=Decimal("0.000")
        )


# ---------------------------------------------------------------------------
# PlannedTransfer execution + cancellation (per 0044)
# ---------------------------------------------------------------------------



def planned_prijem_lines_for(product: Product, branch: Branch):
    """Open (PLANNED) príjem lines for one (product, branch) pair, soonest
    arrival first. Replaces `planned_orders_for` (0057) for the inventura
    inline display."""
    return (
        MovementLine.objects.filter(
            movement__status=Movement.Status.PLANNED,
            movement__kind=Movement.Kind.PRIJEM,
            product=product,
            movement__branch=branch,
        )
        .select_related("movement", "movement__branch", "product")
        .order_by("movement__expected_on", "movement_id", "id")
    )


# ---------------------------------------------------------------------------
# Daily low-stock summary e-mail (per 0045)
# ---------------------------------------------------------------------------


def _format_low_stock_list(rows: list[LowStockRow]) -> str:
    """Render the multi-line `<seznam>` placeholder body."""
    lines = []
    for r in rows:
        lines.append(
            f"- {r.product.name_cs} @ {r.branch.code}: "
            f"efektivně {r.effective} kg / práh {r.threshold} kg"
        )
    return "\n".join(lines)


def send_low_stock_summary() -> int | None:
    """Build the low-stock list, render templates, send to subscribed
    recipients per 0045 + 0052.

    Returns the number of rows on success; None if nothing to send.
    Recipients are all active SettingsRecipient rows with
    `is_low_stock_recipient=True`. If none match, no e-mail is sent and
    None is returned (matches `_assert_recipients_set`'s no-raise posture
    for the daily cron path).
    """
    rows = low_stock_rows()
    if not rows:
        return None

    s = Settings.load()
    recipients = _active_low_stock_recipients()
    if not recipients:
        return None

    today = date.today().strftime("%d. %m. %Y")
    seznam = _format_low_stock_list(rows)
    subject = (
        s.template_low_stock_subject
        .replace("<datum>", today)
        .replace("<seznam>", seznam)
    )
    body = (
        s.template_low_stock_body
        .replace("<datum>", today)
        .replace("<seznam>", seznam)
    )

    from_email = (
        f"{s.email_from_name} <{s.email_from_address}>"
        if s.email_from_name and s.email_from_address
        else (s.email_from_address or None)
    )

    connection = _smtp_connection_from_settings(s)
    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=from_email,
        to=recipients,
        connection=connection,
    )
    msg.send(fail_silently=False)
    return len(rows)


# ---------------------------------------------------------------------------
# XLS recipe importer — per decision 0048
# ---------------------------------------------------------------------------

