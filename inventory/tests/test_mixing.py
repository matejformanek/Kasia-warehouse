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
def test_mixing_create_post_actual_produced_override(user_vlastnik, tyn, pepper) -> None:
    # The optional "skutečně vyrobeno" override records a produced qty that
    # differs from the target (per 0060).
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
            "actual_produced_qty": "1.900",
        },
    )
    assert response.status_code == 302
    job = MixingJob.objects.get()
    assert job.state == MixingJob.State.DONE
    assert job.actual_produced_qty == Decimal("1.900")


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
            "actual_produced_qty": "4.800",
            "note": "poznámka k dávce",
        },
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "pod nulu" in body or "Skladová" in body
    assert MixingJob.objects.count() == 0
    # Per 0060 (3b): every POSTed value is echoed back so nothing is lost.
    assert 'value="5.000"' in body  # target_qty
    assert 'value="4.800"' in body  # actual_produced_qty
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
