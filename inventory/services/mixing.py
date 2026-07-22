"""Mixing job lifecycle (plan/start/finish/cancel/record)."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    Customer,
    MixingJob,
    MixingJobLine,
    Movement,
    MovementLine,
    Product,
    RecipeComponent,
    Supplier,
)
from . import counterparties
from .movement import apply_movement, build_movement, edit_movement


def _micharna_customer() -> Customer:
    return counterparties.customer("micharna")


def _micharna_supplier() -> Supplier:
    return counterparties.supplier("micharna")


def plan_mixing_job(
    *,
    branch,
    mixture: Product,
    target_qty: Decimal,
    user,
    planned_for=None,
    note: str = "",
) -> MixingJob:
    """Create a PLANNED MixingJob without touching Stock.

    Per [0044](../context/decisions/0044-reservations-planned-states.md):
    PLANNED jobs reserve stock via `reserved_kg()` (their
    `MixingJobLine.derived_qty` rows feed the reservation total) but
    do not decrement `Stock.quantity`. The transition to RUNNING — via
    `start_mixing_job(job=<planned>)` — is the moment stock is
    actually consumed.

    Snapshots the recipe at the moment of planning so a future recipe
    edit doesn't retroactively change a planned job's reservation.
    """
    if mixture.kind != Product.Kind.MIXTURE:
        raise ValidationError({"mixture": "Vybraný produkt není směs."})
    if target_qty is None or target_qty <= 0:
        raise ValidationError(
            {"target_qty": "Cílové množství musí být větší než 0."}
        )

    recipe = list(
        RecipeComponent.objects.filter(mixture_product=mixture)
        .select_related("component_product")
        .order_by("component_product__name_cs")
    )
    if not recipe:
        raise ValidationError({"mixture": "Směs nemá vyplněnou recepturu."})

    with transaction.atomic():
        job = MixingJob.objects.create(
            branch=branch,
            mixture=mixture,
            target_qty=target_qty,
            state=MixingJob.State.PLANNED,
            planned_for=planned_for,
            created_by=user,
            note=note,
        )
        for rc in recipe:
            # Untracked components (per 0088, e.g. „Voda“) are unlimited — no
            # MixingJobLine, so they never feed reserved_kg() (which sums only
            # PLANNED MixingJobLine.derived_qty). Skipping here is what keeps a
            # planned water line from producing a phantom reservation.
            if not rc.component_product.is_stock_tracked:
                continue
            derived = (target_qty * rc.ratio).quantize(Decimal("0.001"))
            if derived <= 0:
                raise ValidationError(
                    {
                        "target_qty": (
                            f"Odvozené množství pro {rc.component_product} "
                            f"je 0; zvolte větší cíl."
                        )
                    }
                )
            MixingJobLine.objects.create(
                mixing_job=job,
                component_product=rc.component_product,
                ratio_at_start=rc.ratio,
                derived_qty=derived,
                actual_qty=derived,
            )
        return job


def start_mixing_job(
    *,
    branch=None,
    mixture: Product | None = None,
    target_qty: Decimal | None = None,
    user,
    as_of=None,
    note: str = "",
    sarze_by_component: dict | None = None,
    job: MixingJob | None = None,
) -> MixingJob:
    """Snapshot the recipe at the current ratios, write the consume
    Movement (kind=vydej, odberatel=Míchárna internal) atomically, and
    return a running MixingJob.

    Two entry shapes, per
    [0044](../context/decisions/0044-reservations-planned-states.md):

    - **Fresh start (one-shot):** caller passes branch, mixture,
      target_qty. We create the RUNNING MixingJob + consume Movement
      in one atomic block.
    - **From a PLANNED job:** caller passes `job=<planned MixingJob>`.
      We assert `job.state == PLANNED`, snapshot already exists on
      `MixingJobLine` rows, transition state PLANNED → RUNNING, write
      the consume Movement, link `consume_movement` to the job.

    Raises ValidationError on:
    - mixture without recipe (fresh-start);
    - target_qty <= 0 (fresh-start);
    - any component's stock would go negative at this branch.

    Per 0039: ratios snapshotted at start; future recipe edits don't
    touch in-flight jobs. Stock-overdraw refusal hits via the existing
    `_apply_line_to_stock` invariant.
    """
    from datetime import date as _date

    sarze_by_component = sarze_by_component or {}
    date_issued = as_of.date() if hasattr(as_of, "date") else (
        as_of if as_of is not None else _date.today()
    )

    if job is not None:
        # PLANNED → RUNNING path.
        if job.state != MixingJob.State.PLANNED:
            raise ValidationError(
                {"state": "Spustit lze pouze plánovanou dávku."}
            )
        branch = job.branch
        mixture = job.mixture
        target_qty = job.target_qty
        existing_lines = list(
            job.lines.select_related("component_product").order_by(
                "component_product__name_cs"
            )
        )
        if not existing_lines:
            raise ValidationError(
                {"mixture": "Plánovaná dávka nemá žádné položky."}
            )

        with transaction.atomic():
            consume_movement = build_movement(
                branch=branch,
                kind=Movement.Kind.VYDEJ,
                counterparty=_micharna_customer(),
                date_issued=date_issued,
                note=(
                    f"Míchání směsi {mixture.name_cs} ({target_qty} kg). "
                    f"{job.note or note}".strip()
                ),
            )
            # No untracked filter needed here: consume lines are built from the
            # existing MixingJobLine rows, and plan_mixing_job never creates a
            # line for an untracked component (per 0088). Correctness is derived
            # from that — don't add a redundant guard.
            consume_lines = [
                MovementLine(
                    product=jl.component_product,
                    quantity_kg=jl.derived_qty,
                    sarze=sarze_by_component.get(jl.component_product_id, jl.sarze or ""),
                )
                for jl in existing_lines
            ]
            apply_movement(
                movement=consume_movement, lines=consume_lines, user=user
            )
            # Mirror sarze input back onto the MixingJobLine rows.
            for jl in existing_lines:
                new_sarze = sarze_by_component.get(jl.component_product_id)
                if new_sarze and new_sarze != jl.sarze:
                    jl.sarze = new_sarze
                    jl.save(update_fields=["sarze"])
            job.state = MixingJob.State.RUNNING
            job.consume_movement = consume_movement
            job.save(update_fields=["state", "consume_movement"])
            return job

    # Fresh-start path.
    if mixture is None or branch is None:
        raise ValidationError(
            {"mixture": "Pobočka a směs jsou povinné."}
        )
    if mixture.kind != Product.Kind.MIXTURE:
        raise ValidationError(
            {"mixture": "Vybraný produkt není směs."}
        )
    if target_qty is None or target_qty <= 0:
        raise ValidationError(
            {"target_qty": "Cílové množství musí být větší než 0."}
        )

    recipe = list(
        RecipeComponent.objects.filter(mixture_product=mixture)
        .select_related("component_product")
        .order_by("component_product__name_cs")
    )
    if not recipe:
        raise ValidationError(
            {"mixture": "Směs nemá vyplněnou recepturu."}
        )

    with transaction.atomic():
        # Build the consume Movement (one vydej with N lines).
        consume_movement = build_movement(
            branch=branch,
            kind=Movement.Kind.VYDEJ,
            counterparty=_micharna_customer(),
            date_issued=date_issued,
            note=(
                f"Míchání směsi {mixture.name_cs} ({target_qty} kg). "
                f"{note}".strip()
            ),
        )

        consume_lines: list[MovementLine] = []
        snapshots: list[tuple[Product, Decimal, Decimal]] = []
        for rc in recipe:
            # Untracked components (per 0088, e.g. „Voda“) are unlimited — no
            # consume MovementLine, no MixingJobLine. A RUNNING mix therefore
            # never decrements water stock or records it as consumed.
            if not rc.component_product.is_stock_tracked:
                continue
            derived = (target_qty * rc.ratio).quantize(Decimal("0.001"))
            if derived <= 0:
                # Pathological: a positive ratio rounded to 0 at 3 dp.
                raise ValidationError(
                    {
                        "target_qty": (
                            f"Odvozené množství pro {rc.component_product} "
                            f"je 0; zvolte větší cíl."
                        )
                    }
                )
            consume_lines.append(
                MovementLine(
                    product=rc.component_product,
                    quantity_kg=derived,
                    sarze=sarze_by_component.get(rc.component_product_id, ""),
                )
            )
            snapshots.append((rc.component_product, rc.ratio, derived))

        apply_movement(
            movement=consume_movement, lines=consume_lines, user=user
        )

        new_job = MixingJob.objects.create(
            branch=branch,
            mixture=mixture,
            target_qty=target_qty,
            state=MixingJob.State.RUNNING,
            created_by=user,
            note=note,
            consume_movement=consume_movement,
        )
        MixingJobLine.objects.bulk_create(
            [
                MixingJobLine(
                    mixing_job=new_job,
                    component_product=component,
                    ratio_at_start=ratio,
                    derived_qty=derived,
                    actual_qty=derived,
                    sarze=sarze_by_component.get(component.pk, ""),
                )
                for component, ratio, derived in snapshots
            ]
        )
        return new_job


def finish_mixing_job(
    *,
    mixing_job: MixingJob,
    actual_produced_qty: Decimal,
    line_actuals: dict[int, Decimal] | None = None,
    user,
    as_of=None,
) -> MixingJob:
    """Write the produce Movement, persist any operator-edited actual
    consumption per component, and mark the job done.

    `line_actuals` is `{mixing_job_line_id: actual_qty}`. Missing
    entries keep the line's existing `actual_qty` (defaulted to
    `derived_qty` at start). If an actual differs from the derived,
    the consume Movement is corrected via `edit_movement` with a
    canned reason so the audit trail captures it.
    """
    from datetime import date as _date

    if mixing_job.state != MixingJob.State.RUNNING:
        raise ValidationError(
            {"state": "Lze ukončit pouze probíhající dávku."}
        )
    if actual_produced_qty is None or actual_produced_qty < 0:
        raise ValidationError(
            {
                "actual_produced_qty": (
                    "Skutečné vyrobené množství nemůže být záporné."
                )
            }
        )

    line_actuals = line_actuals or {}
    date_issued = as_of.date() if hasattr(as_of, "date") else (
        as_of if as_of is not None else _date.today()
    )

    with transaction.atomic():
        # Per-line actual edits — applied via edit_movement so the
        # stock delta + audit trail are computed by the existing service.
        line_changes = []
        consume_movement = mixing_job.consume_movement
        consume_lines_by_product = {
            ml.product_id: ml for ml in consume_movement.lines.all()
        }

        for jl_id, new_actual in line_actuals.items():
            jl = MixingJobLine.objects.get(pk=jl_id, mixing_job=mixing_job)
            new_actual = Decimal(new_actual).quantize(Decimal("0.001"))
            if new_actual <= 0:
                raise ValidationError(
                    {
                        "line_actuals": (
                            f"Spotřeba {jl.component_product} musí být > 0."
                        )
                    }
                )
            jl.actual_qty = new_actual
            jl.save(update_fields=["actual_qty"])

            consume_line = consume_lines_by_product.get(jl.component_product_id)
            if consume_line is not None and consume_line.quantity_kg != new_actual:
                line_changes.append(
                    {
                        "op": "update",
                        "line_id": consume_line.pk,
                        "fields": {"quantity_kg": new_actual},
                    }
                )

        if line_changes:
            edit_movement(
                movement=consume_movement,
                changes={},
                line_changes=line_changes,
                reason=f"míchání: skutečná spotřeba (dávka #{mixing_job.pk})",
                user=user,
            )

        # Produce Movement — single-line prijem from Míchárna supplier.
        produce_movement = build_movement(
            branch=mixing_job.branch,
            kind=Movement.Kind.PRIJEM,
            counterparty=_micharna_supplier(),
            date_issued=date_issued,
            note=(
                f"Míchání směsi {mixing_job.mixture.name_cs} — vyrobeno "
                f"{actual_produced_qty} kg (cíl {mixing_job.target_qty} kg)."
            ),
        )
        produce_line = MovementLine(
            product=mixing_job.mixture,
            quantity_kg=actual_produced_qty,
        )
        if actual_produced_qty > 0:
            apply_movement(
                movement=produce_movement,
                lines=[produce_line],
                user=user,
            )
            mixing_job.produce_movement = produce_movement

        mixing_job.actual_produced_qty = actual_produced_qty
        mixing_job.state = MixingJob.State.DONE
        from django.utils.timezone import now as _now
        mixing_job.finished_at = _now()
        mixing_job.save(
            update_fields=[
                "actual_produced_qty",
                "state",
                "finished_at",
                "produce_movement",
            ]
        )
        # Refresh consume_movement reference (in case edit_movement
        # changed the line set / quantities).
        _ = mixing_job.consume_movement
        return mixing_job


def cancel_mixing_job(
    *,
    mixing_job: MixingJob,
    reason: str,
    user,
) -> MixingJob:
    """Cancel a PLANNED or RUNNING job per
    [0044](../context/decisions/0044-reservations-planned-states.md):

    - PLANNED → CANCELLED: no consume_movement exists yet, nothing to
      reverse. Just mark the state and finished_at.
    - RUNNING → CANCELLED: zero each consume line via edit_movement
      (returns consumed stock to the branch).
    """
    if mixing_job.state not in {
        MixingJob.State.PLANNED,
        MixingJob.State.RUNNING,
    }:
        raise ValidationError(
            {"state": "Lze zrušit pouze plánovanou nebo probíhající dávku."}
        )
    if not reason or not reason.strip():
        raise ValidationError(
            {"reason": "Důvod zrušení je povinný."}
        )

    with transaction.atomic():
        if mixing_job.state == MixingJob.State.RUNNING:
            consume_movement = mixing_job.consume_movement
            # Remove every line of the consume Movement — edit_movement
            # reverses the stock delta atomically and writes a LINE_REMOVED
            # audit row per line.
            line_changes = [
                {"op": "remove", "line_id": ml.pk}
                for ml in consume_movement.lines.all()
            ]
            if line_changes:
                edit_movement(
                    movement=consume_movement,
                    changes={},
                    line_changes=line_changes,
                    reason=f"míchání zrušeno: {reason}",
                    user=user,
                )

        mixing_job.state = MixingJob.State.CANCELLED
        mixing_job.cancel_reason = reason
        from django.utils.timezone import now as _now
        mixing_job.finished_at = _now()
        mixing_job.save(
            update_fields=["state", "cancel_reason", "finished_at"]
        )
        return mixing_job


def record_completed_mixing_job(
    *,
    branch,
    mixture: Product,
    target_qty: Decimal,
    actual_produced_qty: Decimal,
    line_actuals_by_component_pk: dict[int, Decimal] | None = None,
    user,
    as_of=None,
    note: str = "",
    sarze_by_component: dict | None = None,
) -> MixingJob:
    """One-shot path per 0039: start + finish in a single transaction
    using a single `as_of` date for both Movements. The operator uses
    this when they forgot to open the screen at start and is recording
    a completed batch after the fact.
    """
    job = start_mixing_job(
        branch=branch,
        mixture=mixture,
        target_qty=target_qty,
        user=user,
        as_of=as_of,
        note=note,
        sarze_by_component=sarze_by_component,
    )
    line_actuals: dict[int, Decimal] = {}
    if line_actuals_by_component_pk:
        for jl in job.lines.all():
            if jl.component_product_id in line_actuals_by_component_pk:
                line_actuals[jl.pk] = line_actuals_by_component_pk[
                    jl.component_product_id
                ]
    return finish_mixing_job(
        mixing_job=job,
        actual_produced_qty=actual_produced_qty,
        line_actuals=line_actuals,
        user=user,
        as_of=as_of,
    )


# ---------------------------------------------------------------------------
# Manual stock adjustment (Pass 5d, per decision 0041)
# ---------------------------------------------------------------------------


