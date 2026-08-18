from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, override_settings

from inventory.models import (
    Customer,
    DodaciList,
    DodaciListNumberSequence,
    MixingJob,
    MixingJobLine,
    Movement,
    MovementAudit,
    MovementLine,
    Product,
    Settings,
    Stock,
    Supplier,
)
from inventory.services import (
    apply_movement,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
    _mk_mixture_with_recipe,
    _recipient_formset_keepall,
)

# Pass 4 — mixing job (screen 15, per decision 0039)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_micharna_seed_rows_exist() -> None:
    """Seed migration 0007 inserts the internal Míchárna pair."""

    assert Customer.objects.filter(name="Míchárna", is_internal=True).exists()
    assert Supplier.objects.filter(name="Míchárna", is_internal=True).exists()


@pytest.mark.django_db
def test_is_internal_customer_skips_dodaci_list(
    tyn, user_tyn, pepper
) -> None:
    """A vydej to an internal odběratel must NOT create a DodaciList +
    must NOT require active SettingsRecipient rows."""
    from inventory.models import SettingsRecipient

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    micharna = Customer.objects.get(name="Míchárna", is_internal=True)
    # Clear all recipients to prove the guard is real (per 0052).
    SettingsRecipient.objects.all().delete()

    mv = apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=micharna,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    assert not DodaciList.objects.filter(movement=mv).exists()


@pytest.mark.django_db
def test_start_mixing_job_writes_consume_and_snapshot(
    tyn, user_tyn, pepper, paprika
) -> None:
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe(
        "Test směs",
        [(pepper, "0.7"), (paprika, "0.3")],
    )

    job = start_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("5.000"),
        user=user_tyn,
    )
    assert job.state == MixingJob.State.RUNNING
    assert job.consume_movement is not None
    # Stock decremented by derived qty (5 * 0.7 = 3.5 and 5 * 0.3 = 1.5).
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("6.500")
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("8.500")
    lines = {jl.component_product_id: jl for jl in job.lines.all()}
    assert lines[pepper.pk].ratio_at_start == Decimal("0.700000")
    assert lines[pepper.pk].derived_qty == Decimal("3.500")
    assert lines[paprika.pk].derived_qty == Decimal("1.500")


@pytest.mark.django_db
def test_start_mixing_job_rejects_overdraw(tyn, user_tyn, pepper) -> None:
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    with pytest.raises(ValidationError):
        start_mixing_job(
            branch=tyn,
            mixture=mixture,
            target_qty=Decimal("5.000"),
            user=user_tyn,
        )
    # Job and Movement rolled back.
    assert MixingJob.objects.count() == 0
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("1.000")


@pytest.mark.django_db
def test_start_mixing_job_rejects_non_mixture(tyn, user_tyn, pepper) -> None:
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    with pytest.raises(ValidationError):
        start_mixing_job(
            branch=tyn,
            mixture=pepper,
            target_qty=Decimal("1.000"),
            user=user_tyn,
        )


@pytest.mark.django_db
def test_start_mixing_job_rejects_mixture_without_recipe(
    tyn, user_tyn
) -> None:
    from inventory.services import start_mixing_job

    mixture = Product.objects.create(name_cs="Empty", kind=Product.Kind.MIXTURE)
    with pytest.raises(ValidationError):
        start_mixing_job(
            branch=tyn,
            mixture=mixture,
            target_qty=Decimal("1.000"),
            user=user_tyn,
        )


@pytest.mark.django_db
def test_finish_mixing_job_writes_produce_and_marks_done(
    tyn, user_tyn, pepper, paprika
) -> None:
    from inventory.services import finish_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("5.000"), user=user_tyn
    )
    finish_mixing_job(
        mixing_job=job,
        actual_produced_qty=Decimal("4.900"),
        line_actuals=None,
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.state == MixingJob.State.DONE
    assert job.actual_produced_qty == Decimal("4.900")
    assert job.produce_movement is not None
    assert (
        Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("4.900")
    )
    assert job.yield_delta == Decimal("-0.100")


@pytest.mark.django_db
def test_finish_mixing_job_with_line_actuals_corrects_consume(
    tyn, user_tyn, pepper, paprika
) -> None:
    from inventory.services import finish_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("5.000"), user=user_tyn
    )
    pepper_line = job.lines.get(component_product=pepper)
    finish_mixing_job(
        mixing_job=job,
        actual_produced_qty=Decimal("5.000"),
        line_actuals={pepper_line.pk: Decimal("3.600")},
        user=user_tyn,
    )
    pepper_line.refresh_from_db()
    assert pepper_line.actual_qty == Decimal("3.600")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal(
        "6.400"
    )

    assert MovementAudit.objects.filter(
        movement=job.consume_movement, field="quantity_kg"
    ).exists()


@pytest.mark.django_db
def test_finish_mixing_job_zero_produce_skips_movement(
    tyn, user_tyn, pepper
) -> None:
    from inventory.services import finish_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("1.000"), user=user_tyn
    )
    finish_mixing_job(
        mixing_job=job,
        actual_produced_qty=Decimal("0.000"),
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.state == MixingJob.State.DONE
    assert job.produce_movement is None


@pytest.mark.django_db
def test_finish_mixing_job_rejects_non_running(tyn, user_tyn, pepper) -> None:
    from inventory.services import (
        cancel_mixing_job,
        finish_mixing_job,
        start_mixing_job,
    )

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("1.000"), user=user_tyn
    )
    cancel_mixing_job(mixing_job=job, reason="testing", user=user_tyn)
    job.refresh_from_db()
    with pytest.raises(ValidationError):
        finish_mixing_job(
            mixing_job=job,
            actual_produced_qty=Decimal("0.500"),
            user=user_tyn,
        )


@pytest.mark.django_db
def test_cancel_mixing_job_restores_stock(tyn, user_tyn, pepper) -> None:
    from inventory.services import cancel_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("2.000"), user=user_tyn
    )
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal(
        "3.000"
    )
    cancel_mixing_job(mixing_job=job, reason="error v poměru", user=user_tyn)
    job.refresh_from_db()
    assert job.state == MixingJob.State.CANCELLED
    assert job.cancel_reason == "error v poměru"
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal(
        "5.000"
    )


@pytest.mark.django_db
def test_cancel_mixing_job_requires_reason(tyn, user_tyn, pepper) -> None:
    from inventory.services import cancel_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("1.000"), user=user_tyn
    )
    with pytest.raises(ValidationError):
        cancel_mixing_job(mixing_job=job, reason="   ", user=user_tyn)


@pytest.mark.django_db
def test_record_completed_mixing_job_one_shot(
    tyn, user_tyn, pepper, paprika
) -> None:
    from inventory.services import record_completed_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("5.000"),
        actual_produced_qty=Decimal("4.800"),
        line_actuals_by_component_pk={pepper.pk: Decimal("3.600")},
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.state == MixingJob.State.DONE
    assert job.actual_produced_qty == Decimal("4.800")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal(
        "6.400"
    )
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal(
        "8.500"
    )
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal(
        "4.800"
    )


# edit_completed_mixing_job (per 0100) ------------------------------------


def _seed_empty_movement_done_job(branch, mixture, user, components):
    """Hand-build a DONE MixingJob whose consume/produce movements exist but
    carry ZERO MovementLines — the job-12 shape the repair must rebuild.

    ``components`` is a list of ``(product, ratio, derived)``.
    """
    from inventory.services.movement import build_movement

    micharna_c = Customer.objects.get(name="Míchárna", is_internal=True)
    micharna_s = Supplier.objects.get(name="Míchárna", is_internal=True)
    consume = build_movement(
        branch=branch,
        kind=Movement.Kind.VYDEJ,
        counterparty=micharna_c,
        date_issued=date(2026, 8, 14),
        created_by=user,
    )
    consume.save()
    produce = build_movement(
        branch=branch,
        kind=Movement.Kind.PRIJEM,
        counterparty=micharna_s,
        date_issued=date(2026, 8, 14),
        created_by=user,
    )
    produce.save()
    job = MixingJob.objects.create(
        branch=branch,
        mixture=mixture,
        target_qty=Decimal("1.000"),
        actual_produced_qty=Decimal("1.000"),
        state=MixingJob.State.DONE,
        created_by=user,
        consume_movement=consume,
        produce_movement=produce,
    )
    for prod, ratio, derived in components:
        MixingJobLine.objects.create(
            mixing_job=job,
            component_product=prod,
            ratio_at_start=Decimal(ratio),
            derived_qty=Decimal(derived),
            actual_qty=Decimal(derived),
        )
    return job


@pytest.mark.django_db
def test_edit_completed_recompute_scales_all_lines(
    tyn, user_tyn, pepper, paprika
) -> None:
    """recompute=True scales every consume line + the produce line to the new
    produced amount, and overwrites target_qty."""
    from inventory.services import (
        edit_completed_mixing_job,
        record_completed_mixing_job,
    )

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1000.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1000.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("100.000"),
        actual_produced_qty=Decimal("100.000"),
        user=user_tyn,
    )
    # Baseline after seed: consume 70/30, produce 100.
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("930.000")
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("100.000")

    edit_completed_mixing_job(
        mixing_job=job,
        produced_qty=Decimal("200.000"),
        recompute_consumption=True,
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.target_qty == Decimal("200.000")
    assert job.actual_produced_qty == Decimal("200.000")
    # Consume scaled to 140 / 60; produce to 200.
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("860.000")
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("940.000")
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("200.000")
    lines = {jl.component_product_id: jl for jl in job.lines.all()}
    assert lines[pepper.pk].actual_qty == Decimal("140.000")
    assert lines[pepper.pk].derived_qty == Decimal("140.000")
    assert lines[paprika.pk].actual_qty == Decimal("60.000")


@pytest.mark.django_db
def test_edit_completed_manual_override_touches_only_supplied_lines(
    tyn, user_tyn, pepper, paprika
) -> None:
    """recompute=False overrides only the supplied consume lines (+ produce);
    an unsupplied line keeps its actual, and derived_qty is never touched."""
    from inventory.services import (
        edit_completed_mixing_job,
        record_completed_mixing_job,
    )

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1000.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1000.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("100.000"),
        actual_produced_qty=Decimal("100.000"),
        user=user_tyn,
    )
    pepper_line = job.lines.get(component_product=pepper)
    paprika_line = job.lines.get(component_product=paprika)

    edit_completed_mixing_job(
        mixing_job=job,
        produced_qty=Decimal("100.000"),
        recompute_consumption=False,
        line_actuals={pepper_line.pk: Decimal("65.000")},
        user=user_tyn,
    )
    pepper_line.refresh_from_db()
    paprika_line.refresh_from_db()
    # pepper overridden 70 → 65 (5 kg returned to stock); derived untouched.
    assert pepper_line.actual_qty == Decimal("65.000")
    assert pepper_line.derived_qty == Decimal("70.000")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("935.000")
    # paprika untouched.
    assert paprika_line.actual_qty == Decimal("30.000")
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("970.000")
    # produce unchanged.
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("100.000")


@pytest.mark.django_db
def test_edit_completed_rebuilds_empty_movements(
    tyn, user_tyn, pepper, paprika
) -> None:
    """The job-12 shape: both movements empty. The edit adds every consume
    line + the produce line, mutating stock for the first time."""
    from inventory.services import edit_completed_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("200.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("200.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = _seed_empty_movement_done_job(
        tyn,
        mixture,
        user_tyn,
        [(pepper, "0.7", "70.000"), (paprika, "0.3", "30.000")],
    )
    assert job.consume_movement.lines.count() == 0
    assert job.produce_movement.lines.count() == 0

    edit_completed_mixing_job(
        mixing_job=job,
        produced_qty=Decimal("100.000"),
        recompute_consumption=True,
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.consume_movement.lines.count() == 2
    assert job.produce_movement.lines.count() == 1
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("130.000")
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("170.000")
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("100.000")
    assert job.target_qty == Decimal("100.000")


@pytest.mark.django_db
def test_edit_completed_zero_produced_removes_produce_line(
    tyn, user_tyn, pepper
) -> None:
    """produced_qty=0 removes the produce line + nulls the FK, keeps consume
    + target_qty."""
    from inventory.services import (
        edit_completed_mixing_job,
        record_completed_mixing_job,
    )

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("10.000"),
        actual_produced_qty=Decimal("10.000"),
        user=user_tyn,
    )
    produce_mv = job.produce_movement
    edit_completed_mixing_job(
        mixing_job=job,
        produced_qty=Decimal("0"),
        recompute_consumption=True,
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.produce_movement is None
    assert job.actual_produced_qty == Decimal("0.000")
    assert job.target_qty == Decimal("10.000")  # kept (CHECK __gt=0)
    produce_mv.refresh_from_db()
    assert produce_mv.lines.count() == 0
    # Mixture stock reversed to 0; consume untouched.
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("0.000")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("90.000")


@pytest.mark.django_db
def test_edit_completed_idempotent_no_audit_rows(
    tyn, user_tyn, pepper, paprika
) -> None:
    """Re-running the same edit is a no-op — edit_movement skips no-op fields,
    so no new MovementAudit rows are written."""
    from inventory.services import (
        edit_completed_mixing_job,
        record_completed_mixing_job,
    )

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1000.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1000.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("100.000"),
        actual_produced_qty=Decimal("100.000"),
        user=user_tyn,
    )
    # First edit — changes nothing (produced already 100, recompute gives 70/30).
    edit_completed_mixing_job(
        mixing_job=job,
        produced_qty=Decimal("100.000"),
        recompute_consumption=True,
        user=user_tyn,
    )
    audit_before = MovementAudit.objects.count()
    # Re-run — must be a pure no-op.
    edit_completed_mixing_job(
        mixing_job=job,
        produced_qty=Decimal("100.000"),
        recompute_consumption=True,
        user=user_tyn,
    )
    assert MovementAudit.objects.count() == audit_before


# View tests --------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_routes_require_login() -> None:
    for path in ("/sklad/michani/", "/sklad/michani/novy/", "/sklad/michani/1/"):
        response = Client().get(path)
        assert response.status_code == 302
        assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_index_empty(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/michani/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Míchací dávky" in body
    assert "Nalezeno: 0" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_get_lists_only_mixtures_with_recipe(
    user_vlastnik, pepper
) -> None:
    with_recipe = _mk_mixture_with_recipe("S recepturou", [(pepper, "1.0")])
    Product.objects.create(name_cs="Bez receptury", kind=Product.Kind.MIXTURE)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/michani/novy/")
    body = response.content.decode("utf-8")
    assert with_recipe.name_cs in body
    assert "Bez receptury" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_get_prefills_target_from_default_batch(
    user_vlastnik, pepper
) -> None:
    """Per 0089: GET ?mixture=<id> for a mixture with default_batch_kg set
    prefills „Cílové množství" (1-dp dot) and emits the #mixture-defaults blob."""
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    Product.objects.filter(pk=mixture.pk).update(
        default_batch_kg=Decimal("337.000")
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/michani/novy/?mixture={mixture.pk}").content.decode("utf-8")
    assert 'id="id_target_qty"' in body
    assert 'value="337.0"' in body
    assert 'id="mixture-defaults"' in body
    assert "337.0" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_get_explicit_target_qty_wins(user_vlastnik, pepper) -> None:
    """Per 0089: an explicit ?target_qty= always overrides the default-batch
    prefill (the inventura round-trip / scaler mix-link contract)."""
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    Product.objects.filter(pk=mixture.pk).update(
        default_batch_kg=Decimal("337.000")
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(
        f"/sklad/michani/novy/?mixture={mixture.pk}&target_qty=99"
    ).content.decode("utf-8")
    assert 'value="99"' in body
    assert 'value="337.0"' not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_get_no_default_leaves_target_blank(
    user_vlastnik, pepper
) -> None:
    """Per 0089: a mixture with default_batch_kg=0 (unset) leaves the total
    field blank — today's behaviour, unchanged."""
    import re

    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/michani/novy/?mixture={mixture.pk}").content.decode("utf-8")
    # The target input renders with an empty value=""; the blob has no entry.
    assert re.search(r'id="id_target_qty"\s+value=""', body)
    assert 'id="mixture-defaults"' in body
    assert "337" not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_post_records_done_job(user_vlastnik, tyn, pepper) -> None:
    # Per 0060 there are no modes: a create is one immediate DONE míchání —
    # consume the recipe inputs + add the blend + immediate stock delta.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/michani/novy/",
        {
            "branch": tyn.pk,
            "mixture": mixture.pk,
            "target_qty": "2.000",
            "note": "",
        },
    )
    assert response.status_code == 302, response.content[:500]
    assert response.headers["Location"].startswith("/sklad/michani/")
    job = MixingJob.objects.get()
    assert job.state == MixingJob.State.DONE
    assert job.target_qty == Decimal("2.000")
    # Blank "skutečně vyrobeno" → defaults to the target.
    assert job.actual_produced_qty == Decimal("2.000")
    assert job.consume_movement is not None
    assert job.produce_movement is not None
    # Immediate stock delta: inputs drop, blend rises.
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("3.000")
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("2.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_post_produced_equals_namichano(user_vlastnik, tyn, pepper) -> None:
    # Per 0100: one field. „Namícháno" (posted as target_qty) sets both the
    # target and the produced amount — they are always equal.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/michani/novy/",
        {
            "branch": tyn.pk,
            "mixture": mixture.pk,
            "target_qty": "2.000",
        },
    )
    assert response.status_code == 302
    job = MixingJob.objects.get()
    assert job.state == MixingJob.State.DONE
    assert job.target_qty == Decimal("2.000")
    assert job.actual_produced_qty == Decimal("2.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_overdraw_keeps_form(
    user_vlastnik, tyn, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/michani/novy/",
        {
            "branch": tyn.pk,
            "mixture": mixture.pk,
            "target_qty": "5.000",
            "note": "poznámka k dávce",
        },
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "pod nulu" in body or "Skladová" in body
    assert MixingJob.objects.count() == 0
    # Per 0060 (3b): every POSTed value is echoed back so nothing is lost.
    assert 'value="5.000"' in body  # target_qty (Namícháno)
    assert "poznámka k dávce" in body  # note
    assert f'value="{tyn.pk}" selected' in body  # branch stays selected
    assert f'value="{mixture.pk}" selected' in body  # směs stays selected


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_finish_view(user_vlastnik, tyn, pepper) -> None:
    # LEGACY PATH (per 0060): the UI no longer creates RUNNING jobs, but the
    # finish view is retained to complete a legacy in-flight job. Build one
    # directly via start_mixing_job() rather than through the create screen.
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("2.000"), user=user_vlastnik
    )
    line = job.lines.get()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/michani/{job.pk}/dokoncit/",
        {
            "actual_produced_qty": "1.900",
            f"line-{line.pk}-actual_qty": "2.000",
        },
    )
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.state == MixingJob.State.DONE
    assert job.actual_produced_qty == Decimal("1.900")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_cancel_view_requires_reason(
    user_vlastnik, tyn, pepper
) -> None:
    # LEGACY PATH (per 0060): cancel is retained for a legacy in-flight job;
    # build a RUNNING job directly via start_mixing_job().
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("2.000"), user=user_vlastnik
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(f"/sklad/michani/{job.pk}/zrusit/", {"reason": "   "})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.state == MixingJob.State.RUNNING
    response = client.post(
        f"/sklad/michani/{job.pk}/zrusit/", {"reason": "vzal jsem špatnou recepturu"}
    )
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.state == MixingJob.State.CANCELLED


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_obsluha_forbidden_on_other_branch(
    user_obsluha_tyn, sez, pepper
) -> None:
    from inventory.services import start_mixing_job

    User = get_user_model()
    sez_runner = User.objects.create_user(
        email="sez-runner@example.cz", password="x" * 12, branch=sez
    )
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=sez, mixture=mixture, target_qty=Decimal("1.000"), user=sez_runner
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/michani/{job.pk}/")
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_detail_done_renders_edit_form(user_vlastnik, tyn, pepper) -> None:
    """The DONE detail page shows the unified edit form (per 0100)."""
    from inventory.services import record_completed_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("10.000"),
        actual_produced_qty=Decimal("10.000"),
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/michani/{job.pk}/").content.decode("utf-8")
    assert 'id="id_produced_qty"' in body
    assert 'name="recompute"' in body
    assert f"/sklad/michani/{job.pk}/upravit/" in body
    # No banker's-rounding prefill: value is a 1-dp dot.
    assert 'value="10.0"' in body
    # movement_edit links dropped from the status card.
    assert "Pohyb spotřeby" not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_detail_recompute_checkbox_reflects_state(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    """Per 0100 UX fix: the „Přepočítat" checkbox defaults to the job's actual
    state — checked for a recipe-proportional job, UNCHECKED (with real values
    shown) for a manually-overridden one, so a re-save never silently recomputes
    a manual override away."""
    import re

    from inventory.services import (
        edit_completed_mixing_job,
        record_completed_mixing_job,
    )

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1000.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1000.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("100.000"),
        actual_produced_qty=Decimal("100.000"),
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    # Recipe-proportional → checkbox checked.
    body = client.get(f"/sklad/michani/{job.pk}/").content.decode("utf-8")
    m = re.search(r'id="id_recompute"([^>]*)>', body)
    assert m and "checked" in m.group(1)

    # Manually override one line → no longer proportional.
    pepper_line = job.lines.get(component_product=pepper)
    edit_completed_mixing_job(
        mixing_job=job,
        produced_qty=Decimal("100.000"),
        recompute_consumption=False,
        line_actuals={pepper_line.pk: Decimal("65.000")},
        user=user_vlastnik,
    )
    body2 = client.get(f"/sklad/michani/{job.pk}/").content.decode("utf-8")
    m2 = re.search(r'id="id_recompute"([^>]*)>', body2)
    assert m2 and "checked" not in m2.group(1)
    # The real overridden value is shown (65.0), NOT the recomputed 70.0.
    assert 'value="65.0"' in body2


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_edit_view_recompute(user_vlastnik, tyn, pepper) -> None:
    from inventory.services import record_completed_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("10.000"),
        actual_produced_qty=Decimal("10.000"),
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/michani/{job.pk}/upravit/",
        {"produced_qty": "20.0", "recompute": "on"},
    )
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.actual_produced_qty == Decimal("20.000")
    assert job.target_qty == Decimal("20.000")
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("20.000")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("80.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_edit_view_manual_override(user_vlastnik, tyn, pepper, paprika) -> None:
    from inventory.services import record_completed_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1000.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1000.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("100.000"),
        actual_produced_qty=Decimal("100.000"),
        user=user_vlastnik,
    )
    pepper_line = job.lines.get(component_product=pepper)
    client = Client()
    client.force_login(user_vlastnik)
    # recompute checkbox absent ⇒ manual override of just pepper.
    response = client.post(
        f"/sklad/michani/{job.pk}/upravit/",
        {"produced_qty": "100.0", f"line-{pepper_line.pk}-actual_qty": "65.0"},
    )
    assert response.status_code == 302
    pepper_line.refresh_from_db()
    assert pepper_line.actual_qty == Decimal("65.000")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("935.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_edit_view_rejects_zero(user_vlastnik, tyn, pepper) -> None:
    from inventory.services import record_completed_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("10.000"),
        actual_produced_qty=Decimal("10.000"),
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/michani/{job.pk}/upravit/", {"produced_qty": "0"}
    )
    assert response.status_code == 302
    job.refresh_from_db()
    # Unchanged — a 0-kg edit is refused (pointed at Zrušit).
    assert job.actual_produced_qty == Decimal("10.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_edit_obsluha_forbidden_on_other_branch(
    user_obsluha_tyn, sez, pepper
) -> None:
    from inventory.services import record_completed_mixing_job

    User = get_user_model()
    sez_runner = User.objects.create_user(
        email="sez-edit@example.cz", password="x" * 12, branch=sez
    )
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("50.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = record_completed_mixing_job(
        branch=sez,
        mixture=mixture,
        target_qty=Decimal("5.000"),
        actual_produced_qty=Decimal("5.000"),
        user=sez_runner,
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        f"/sklad/michani/{job.pk}/upravit/",
        {"produced_qty": "6.0", "recompute": "on"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_preview_partial(user_vlastnik, tyn, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        f"/sklad/_partials/mixing-preview/?branch={tyn.pk}&mixture={mixture.pk}&target_qty=5.000"
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "nedostatek" in body
    # Quantities render at 1 dp with a Czech comma (per 0061).
    assert "5,0" in body
    assert "5,000" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_preview_builds_inventura_component_link(
    user_vlastnik, tyn, pepper
) -> None:
    # Per 0060 (3c): the preview offers a jump into the per-branch inventura
    # pre-filtered to the blend's components, with a `next=` back to míchání.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        f"/sklad/_partials/mixing-preview/?branch={tyn.pk}"
        f"&mixture={mixture.pk}&target_qty=5.000"
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert f"/sklad/katalog/inventura/{tyn.code}/?products=" in body
    assert f"products={pepper.pk}" in body
    # `next=` round-trip back to the míchání form (HTML-escaped &amp;).
    assert "next=" in body


# ---------------------------------------------------------------------------
# Untracked ingredients (per 0088)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_mixing_untracked_component_never_deducted_or_blocking(
    tyn, user_tyn, pepper, voda
) -> None:
    """A mixture with one tracked (pepper) + one untracked (voda) component
    mixes successfully; only the tracked component gets a consume MovementLine
    + a Stock delta, and voda never blocks the mix as a shortage."""
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe(
        "S vodou", [(pepper, "0.5"), (voda, "0.5")]
    )
    job = start_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("4.000"),
        user=user_tyn,
    )
    assert job.state == MixingJob.State.RUNNING
    # Only pepper consumed (4 * 0.5 = 2.0); voda produced no line.
    consume_products = {
        ln.product_id for ln in job.consume_movement.lines.all()
    }
    assert consume_products == {pepper.pk}
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("8.000")
    # No Stock row was ever created for the untracked component.
    assert not Stock.objects.filter(product=voda).exists()
    # No MixingJobLine for the untracked component either.
    assert {jl.component_product_id for jl in job.lines.all()} == {pepper.pk}


@pytest.mark.django_db
def test_mixing_untracked_component_does_not_block_when_zero_stock(
    tyn, user_tyn, pepper, voda
) -> None:
    """Even with 100% of a huge target routed through water, the mix isn't
    refused for want of water stock (voda is unlimited)."""
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    mixture = _mk_mixture_with_recipe(
        "Skoro voda", [(pepper, "0.01"), (voda, "0.99")]
    )
    job = start_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("50.000"),
        user=user_tyn,
    )
    assert job.state == MixingJob.State.RUNNING


@pytest.mark.django_db
def test_plan_mixing_job_skips_untracked_no_reservation(
    tyn, user_tyn, pepper, voda
) -> None:
    """A PLANNED job with an untracked component creates no MixingJobLine for
    it → reserved_kg stays 0 for the untracked product."""
    from inventory.services import plan_mixing_job, reserved_kg

    mixture = _mk_mixture_with_recipe(
        "Plán s vodou", [(pepper, "0.5"), (voda, "0.5")]
    )
    job = plan_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("6.000"),
        user=user_tyn,
    )
    assert {jl.component_product_id for jl in job.lines.all()} == {pepper.pk}
    assert reserved_kg(voda, tyn) == Decimal("0.000")
    # The tracked component IS reserved (6 * 0.5 = 3.0).
    assert reserved_kg(pepper, tyn) == Decimal("3.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_preview_untracked_shows_neomezeno(
    user_vlastnik, tyn, pepper, voda
) -> None:
    # Pepper needs 50 kg (0.5 × 100) — give it plenty so only the untracked
    # voda's "neomezeno" appears and nothing flags a shortage.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    mixture = _mk_mixture_with_recipe(
        "Náhled s vodou", [(pepper, "0.5"), (voda, "0.5")]
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        f"/sklad/_partials/mixing-preview/?branch={tyn.pk}"
        f"&mixture={mixture.pk}&target_qty=100.000"
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "neomezeno" in body
    # Water at 50 kg of a 100 kg target must NOT flag a shortage / overdraw card.
    assert "nedostatek" not in body
    # The untracked component id is excluded from the inventura jump.
    assert f"products={voda.pk}" not in body


# ---------------------------------------------------------------------------
# Screen 14 — Nastavení (operator-facing Settings UI)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_requires_login() -> None:
    response = Client().get("/sklad/nastaveni/")
    assert response.status_code == 302
    assert "/sklad/prihlaseni/" in response["Location"]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_forbidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/nastaveni/")
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_renders_for_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/nastaveni/")
    assert response.status_code == 200
    body = response.content
    assert b"<h1>Nastaven\xc3\xad</h1>" in body
    assert b"Spole\xc4\x8dnost" in body
    assert b"SMTP" in body
    assert b"P\xc5\x99\xc3\xadjemci dodac\xc3\xadho listu" in body
    assert b"\xc5\xa0ablony e-mail\xc5\xaf" in body
    assert b"Otestovat odesl\xc3\xa1n\xc3\xad" in body
    assert b"Pobo\xc4\x8dky" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_save_updates_company(user_vlastnik) -> None:

    client = Client()
    client.force_login(user_vlastnik)
    initial = Settings.load()
    data = {
        "company_name": "Kasia vera s.r.o.",
        "company_ico": "25756729",
        "company_dic": "CZ25756729",
        "company_address": "Říčany u Prahy",
        "company_phone": "+420 123 456 789",
        "company_email": "",
        "footer_text": initial.footer_text,
        "smtp_host": "smtp.example.cz",
        "smtp_port": "587",
        "smtp_use_tls": "on",
        "smtp_user": "kasia",
        "smtp_password": "",
        "email_from_address": "no-reply@example.cz",
        "email_from_name": "Kasia vera",
        "template_initial_subject": initial.template_initial_subject,
        "template_initial_body": initial.template_initial_body,
        "template_oprava_subject": initial.template_oprava_subject,
        "template_oprava_body": initial.template_oprava_body,
        "template_low_stock_subject": initial.template_low_stock_subject,
        "template_low_stock_body": initial.template_low_stock_body,
        **_recipient_formset_keepall(),
    }
    response = client.post("/sklad/nastaveni/", data)
    assert response.status_code == 302, response.content[:500]
    s = Settings.load()
    assert s.company_dic == "CZ25756729"
    assert s.smtp_host == "smtp.example.cz"
    # singleton stays singleton.
    assert Settings.objects.count() == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_empty_password_keeps_existing(user_vlastnik) -> None:

    s = Settings.load()
    s.smtp_password = "old-secret"
    s.save()

    client = Client()
    client.force_login(user_vlastnik)
    data = {
        "company_name": s.company_name,
        "company_ico": s.company_ico,
        "company_dic": s.company_dic,
        "company_address": s.company_address,
        "company_phone": s.company_phone,
        "company_email": s.company_email,
        "footer_text": s.footer_text,
        "smtp_host": s.smtp_host,
        "smtp_port": s.smtp_port,
        "smtp_use_tls": "on",
        "smtp_user": s.smtp_user,
        "smtp_password": "",  # blank → preserve
        "email_from_address": s.email_from_address,
        "email_from_name": s.email_from_name,
        "template_initial_subject": s.template_initial_subject,
        "template_initial_body": s.template_initial_body,
        "template_oprava_subject": s.template_oprava_subject,
        "template_oprava_body": s.template_oprava_body,
        "template_low_stock_subject": s.template_low_stock_subject,
        "template_low_stock_body": s.template_low_stock_body,
        **_recipient_formset_keepall(),
    }
    response = client.post("/sklad/nastaveni/", data)
    assert response.status_code == 302, response.content[:500]
    s2 = Settings.load()
    assert s2.smtp_password == "old-secret"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_test_smtp_sends_to_target(user_vlastnik) -> None:
    from django.core import mail

    client = Client()
    client.force_login(user_vlastnik)
    outbox_before = len(mail.outbox)
    response = client.post(
        "/sklad/nastaveni/test-smtp/",
        {"to_email": "petr@example.cz"},
    )
    assert response.status_code == 302
    assert len(mail.outbox) == outbox_before + 1
    msg = mail.outbox[-1]
    assert "petr@example.cz" in msg.to
    assert "Test" in msg.subject


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_test_smtp_forbidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/nastaveni/test-smtp/", {"to_email": "x@example.cz"}
    )
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_test_smtp_rejects_invalid_email(user_vlastnik) -> None:
    from django.core import mail

    client = Client()
    client.force_login(user_vlastnik)
    outbox_before = len(mail.outbox)
    response = client.post(
        "/sklad/nastaveni/test-smtp/", {"to_email": "not-an-email"}
    )
    assert response.status_code == 302
    assert len(mail.outbox) == outbox_before


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_branch_counters_render(user_vlastnik, tyn) -> None:
    from datetime import date


    DodaciListNumberSequence.objects.create(
        branch=tyn, year=date.today().year, last_counter=42
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/nastaveni/")
    assert response.status_code == 200
    expected_cislo = f"TYN-{date.today().year}-0042"
    assert expected_cislo.encode() in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_nastaveni_link_shown_for_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200
    assert b"Nastaven\xc3\xad" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_nastaveni_link_hidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    assert response.status_code == 200
    assert b"Nastaven\xc3\xad" not in response.content


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Recipe component mixing order (per 0092)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_preview_follows_position_order(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    """Per 0092: preview rows come in recipe position order, not
    alphabetically ('Paprika sladká' < 'Pepř černý', but pepper is first)."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    # _mk_mixture_with_recipe assigns position from tuple order (0092).
    mixture = _mk_mixture_with_recipe(
        "Směs pořadí", [(pepper, "0.6"), (paprika, "0.4")]
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(
        f"/sklad/_partials/mixing-preview/?branch={tyn.pk}"
        f"&mixture={mixture.pk}&target_qty=5.000"
    ).content.decode("utf-8")
    assert body.index(pepper.name_cs) < body.index(paprika.name_cs)


@pytest.mark.django_db
def test_mixing_job_lines_follow_position_order(tyn, user_vlastnik, pepper, paprika) -> None:
    """Per 0092: MixingJobLine rows are created in recipe position order, so
    their id order (the display order everywhere) matches the recipe."""
    from inventory.services.mixing import plan_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe(
        "Směs pořadí dávky", [(pepper, "0.6"), (paprika, "0.4")]
    )
    job = plan_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("5.000"),
        user=user_vlastnik,
    )
    names = [
        line.component_product.name_cs
        for line in job.lines.select_related("component_product").order_by("id")
    ]
    assert names == [pepper.name_cs, paprika.name_cs]
