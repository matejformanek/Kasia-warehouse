"""Reorder thresholds, reservations, event-driven low-stock alert."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..models import (
    Branch,
    EmailLog,
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
from .email import _active_low_stock_recipients, send_and_log


@dataclass
class LowStockRow:
    """One (product, branch) row below threshold for the dashboard panel
    and the low-stock alert e-mail."""

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

    Used by the owner dashboard panel, branch dashboard, and product
    detail page. One source of truth for the per-pair low-stock report.

    Per 0053, a branch *carries* a product iff a Stock row exists for
    that pair — branches without a row do not enter this report.
    """
    rows: list[LowStockRow] = []
    stocks = list(
        Stock.objects.select_related("product", "branch")
        .filter(
            branch__is_active=True,
            product__is_active=True,
            product__is_stock_tracked=True,
        )
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

    Untracked products (per 0088, e.g. „Voda“) never get a Stock row —
    they are unlimited and excluded from every stock report.
    """
    if not product.is_stock_tracked:
        return
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
# Event-driven low-stock alert e-mail (per 0074, supersedes 0045's daily cron)
# ---------------------------------------------------------------------------
#
# The old daily summary (send_low_stock_summary, decision 0045) was never
# scheduled. Instead we alert the moment a stock movement pushes a (product,
# branch) pair into the Katalog "Dochází"/"Prázdné" state when it wasn't there
# before. The two movement chokepoints (apply_movement / edit_movement) snapshot
# `below_alert` per affected pair before mutating, then re-check on commit and
# e-mail only the pairs that newly crossed. See 0074.


def _below_alert(effective: Decimal, threshold: Decimal | None) -> bool:
    """True iff a (product, branch) pair belongs in the alert set — the union
    of the Katalog "Prázdné" + "Dochází" groups (i.e. NOT "V pořádku", per 0072).

    Broader than `low_stock_rows`' bare `effective < threshold`: a pair at
    exactly 0 with a 0 threshold (the Prázdné case) also alerts.
    """
    if effective <= 0:
        return True
    return threshold is not None and effective < threshold


def capture_low_stock_state(
    pairs: Iterable[tuple[Product, Branch]],
) -> dict[tuple[int, int], bool]:
    """Snapshot `_below_alert` per (product, branch) pair against current stock.

    Call BEFORE mutating stock so the query sees the pre-mutation state; the
    result is the `before` argument to `send_low_stock_alert_for_crossings`.
    Keyed by (product_id, branch_id) so it survives the atomic block.
    """
    return {
        (product.pk, branch.pk): _below_alert(
            effective_kg(product, branch), threshold_for(product, branch)
        )
        for product, branch in pairs
    }


def send_low_stock_alert_for_crossings(
    pairs: Iterable[tuple[Product, Branch]],
    before: dict[tuple[int, int], bool],
) -> None:
    """Re-check each pair against current (post-commit) stock and e-mail the
    pairs that just crossed into the alert set (were False before, True now).

    Register this via `transaction.on_commit` so a rollback discards it and
    the query reads the final committed state. A pair that was already low
    does not re-alert (transition check = idempotency, per 0074).
    """
    rows: list[LowStockRow] = []
    for product, branch in pairs:
        key = (product.pk, branch.pk)
        if before.get(key):  # already below before → not a new crossing
            continue
        threshold = threshold_for(product, branch)
        reserved = reserved_kg(product, branch)
        stock = Stock.objects.filter(product=product, branch=branch).first()
        on_hand = stock.quantity if stock else Decimal("0.000")
        effective = (on_hand - reserved).quantize(Decimal("0.001"))
        if not _below_alert(effective, threshold):
            continue
        rows.append(
            LowStockRow(
                product=product,
                branch=branch,
                on_hand=on_hand,
                reserved=reserved,
                effective=effective,
                threshold=threshold,
                deficit=(
                    (threshold - effective).quantize(Decimal("0.001"))
                    if threshold is not None
                    else effective
                ),
            )
        )
    if rows:
        _send_low_stock_alert_email(rows)


def _format_low_stock_list(rows: list[LowStockRow]) -> str:
    """Render the multi-line `<seznam>` placeholder body."""
    lines = []
    for r in rows:
        lines.append(
            f"- {r.product.name_cs} @ {r.branch.code}: "
            f"efektivně {r.effective} kg / práh {r.threshold} kg"
        )
    return "\n".join(lines)


def _send_low_stock_alert_email(rows: list[LowStockRow]) -> None:
    """Send the "Dochází zboží" alert for the just-crossed rows, reusing the
    existing `Settings.template_low_stock_subject/body` (placeholders `<datum>`
    + `<seznam>`), then log it via `send_and_log` (per 0075).

    Runs post-commit inside an `on_commit` callback; `send_and_log` swallows any
    send error onto a FAILED `EmailLog` row and never re-raises. No
    `is_low_stock_recipient` subscribers → skip silently (no log row).
    """
    recipients = _active_low_stock_recipients()
    if not recipients:
        return
    s = Settings.load()
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
    send_and_log(
        category=EmailLog.Category.LOW_STOCK_ALERT,
        trigger_reason="pokles zásoby pod práh (pohyb)",
        subject=subject,
        body=body,
        recipients=recipients,
        from_email=from_email,
    )


# ---------------------------------------------------------------------------
# XLS recipe importer — per decision 0048
# ---------------------------------------------------------------------------

