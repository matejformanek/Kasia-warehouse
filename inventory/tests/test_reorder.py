from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.test import Client, override_settings

from inventory.models import (
    DodaciList,
    MixingJob,
    Movement,
    MovementLine,
    Product,
    RecipeComponent,
    Stock,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
)

# Pass 6 — Reorder threshold + reservations (per decisions 0043 + 0044 + 0045)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_threshold_for_returns_override_when_present(tyn, sez, pepper) -> None:
    """threshold_for() returns the branch-specific override over the
    product default, per decision 0043."""
    from inventory.models import StockThresholdOverride
    from inventory.services import threshold_for

    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    StockThresholdOverride.objects.create(
        product=pepper, branch=tyn, threshold_kg=Decimal("10.000")
    )
    assert threshold_for(pepper, tyn) == Decimal("10.000")
    # No override for SEZ → falls back to product default.
    assert threshold_for(pepper, sez) == Decimal("5.000")


@pytest.mark.django_db(transaction=True)
def test_migration_0018_backfills_null_threshold() -> None:
    """Per 0072: migration 0018 backfills existing NULL thresholds to 0 before
    the column becomes NOT NULL. Roll inventory back to 0017 (nullable), insert a
    NULL, migrate forward, assert it landed on 0."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    app = "inventory"
    before = "0017_migrate_open_planned_orders"
    after = "0018_reorder_threshold_not_null"
    try:
        # Back to the nullable-column state.
        executor = MigrationExecutor(connection)
        executor.migrate([(app, before)])
        OldProduct = executor.loader.project_state(
            [(app, before)]
        ).apps.get_model(app, "Product")
        p = OldProduct.objects.create(
            name_cs="Historicky bez prahu",
            kind="raw_spice",
            reorder_threshold_kg=None,
        )
        assert p.reorder_threshold_kg is None

        # Forward through 0018 → backfill NULL → 0.
        executor = MigrationExecutor(connection)
        executor.migrate([(app, after)])
        NewProduct = executor.loader.project_state(
            [(app, after)]
        ).apps.get_model(app, "Product")
        assert NewProduct.objects.get(pk=p.pk).reorder_threshold_kg == Decimal(
            "0.000"
        )
    finally:
        # Leave the DB migrated to the CURRENT leaf migration for the rest of
        # the suite — not the hardcoded `after`, which goes stale the moment a
        # newer migration lands (e.g. 0019). A stale schema breaks the next
        # transactional test's teardown flush (TRUNCATE can't drop a table the
        # live model set no longer knows about).
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes(app))


@pytest.mark.django_db
def test_threshold_for_defaults_to_zero(tyn, pepper) -> None:
    """Per 0072 the threshold is not-null, default 0 — with no override and no
    per-product value set, threshold_for() returns 0 (not None)."""
    from inventory.services import threshold_for

    assert pepper.reorder_threshold_kg == Decimal("0.000")
    assert threshold_for(pepper, tyn) == Decimal("0.000")


@pytest.mark.django_db
def test_reserved_kg_planned_mixing_counts(
    tyn, pepper, paprika, user_vlastnik
) -> None:
    """A PLANNED MixingJob's component lines feed reserved_kg() at the
    job's branch — but RUNNING and CANCELLED do not."""
    from inventory.services import plan_mixing_job, reserved_kg

    mix = Product.objects.create(name_cs="Test směs", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=pepper, ratio=Decimal("0.500")
    )
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=paprika, ratio=Decimal("0.500")
    )
    # PLANNED job 10 kg → 5 kg pepper + 5 kg paprika reserved.
    plan_mixing_job(
        branch=tyn,
        mixture=mix,
        target_qty=Decimal("10.000"),
        user=user_vlastnik,
    )
    assert reserved_kg(pepper, tyn) == Decimal("5.000")
    assert reserved_kg(paprika, tyn) == Decimal("5.000")


@pytest.mark.django_db
def test_reserved_kg_running_job_does_not_count(
    tyn, pepper, user_vlastnik
) -> None:
    """A RUNNING MixingJob has already decremented stock; it should NOT
    additionally count as reserved."""
    from inventory.services import (
        plan_mixing_job,
        reserved_kg,
        start_mixing_job,
    )

    mix = Product.objects.create(name_cs="Mix2", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=pepper, ratio=Decimal("1.000")
    )
    # Add enough stock so start can consume.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("20.000"))
    job = plan_mixing_job(
        branch=tyn, mixture=mix, target_qty=Decimal("5.000"), user=user_vlastnik
    )
    assert reserved_kg(pepper, tyn) == Decimal("5.000")
    start_mixing_job(job=job, user=user_vlastnik)
    assert reserved_kg(pepper, tyn) == Decimal("0.000")


@pytest.mark.django_db
def test_reserved_kg_planned_transfer_outgoing_only(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """A PLANNED PlannedTransfer counts at source_branch only — NOT at
    target_branch. Promised inbound is explicitly deferred per 0044."""
    from inventory.models import PlannedTransfer
    from inventory.services import reserved_kg

    PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("3.000"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    assert reserved_kg(pepper, tyn) == Decimal("3.000")
    assert reserved_kg(pepper, sez) == Decimal("0.000")


@pytest.mark.django_db
def test_effective_kg_subtracts_reserved(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """effective_kg = Stock.quantity − reserved_kg at that branch."""
    from inventory.models import PlannedTransfer
    from inventory.services import effective_kg

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("2.500"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    assert effective_kg(pepper, tyn) == Decimal("7.500")
    # Target branch effective is unchanged (no inbound counting).
    assert effective_kg(pepper, sez) == Decimal("0.000")


@pytest.mark.django_db
def test_low_stock_rows_sorted_by_deficit(
    tyn, sez, pepper, paprika
) -> None:
    """low_stock_rows() returns only below-threshold (product, branch)
    pairs that the branch *carries* (per 0053), sorted by deficit DESC.
    SEZ has no Stock row for either product, so it does not appear."""
    from inventory.services import low_stock_rows

    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("2.000")
    paprika.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1.500"))

    rows = low_stock_rows()
    deficits = [r.deficit for r in rows]
    assert deficits == sorted(deficits, reverse=True)
    pairs = {(r.product.pk, r.branch.code) for r in rows}
    # Only TYN rows appear — SEZ carries neither product (no Stock row).
    assert pairs == {(pepper.pk, "TYN"), (paprika.pk, "TYN")}


@pytest.mark.django_db
def test_low_stock_rows_skips_products_without_threshold(
    tyn, pepper
) -> None:
    """Without a threshold set, the row never appears (no alert)."""
    from inventory.services import low_stock_rows

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.001"))
    # No threshold on pepper → no row even though stock is essentially zero.
    rows = low_stock_rows()
    assert not any(r.product.pk == pepper.pk for r in rows)


@pytest.mark.django_db
def test_low_stock_rows_include_empty_flag(tyn, pepper) -> None:
    """An empty pair at the default threshold 0 (`0 < 0 == False`) is dropped by
    the default narrow rule but included with `include_empty=True` (the broader
    `_below_alert` union used by the owner Přehled, per 0093)."""
    from inventory.services import low_stock_rows

    # pepper keeps its default reorder_threshold_kg (0, per 0072); 0 kg on hand.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))

    # Narrow (default): effective 0 < threshold 0 is False → excluded.
    narrow = low_stock_rows()
    assert not any(r.product.pk == pepper.pk for r in narrow)

    # Broad: _below_alert(0, 0) → effective ≤ 0 → included, deficit 0.
    broad = low_stock_rows(include_empty=True)
    pepper_rows = [r for r in broad if r.product.pk == pepper.pk]
    assert len(pepper_rows) == 1
    assert pepper_rows[0].branch.code == "TYN"
    assert pepper_rows[0].effective == Decimal("0.000")
    assert pepper_rows[0].deficit == Decimal("0.000")


@pytest.mark.django_db
def test_low_stock_rows_excludes_untracked_product(tyn, voda) -> None:
    """An untracked product (per 0088) never appears in low_stock_rows,
    regardless of threshold or on-hand — the queryset filters it out."""
    from inventory.services import low_stock_rows

    # Force a would-be-critical situation: a Stock row + a high threshold.
    # (Untracked products normally have no Stock row, but even if one exists
    # via a legacy path, it must not surface.)
    voda.reorder_threshold_kg = Decimal("100.000")
    voda.save()
    Stock.objects.create(product=voda, branch=tyn, quantity=Decimal("0.000"))

    rows = low_stock_rows()
    assert not any(r.product.pk == voda.pk for r in rows)


@pytest.mark.django_db
def test_plan_mixing_job_does_not_touch_stock(
    tyn, pepper, user_vlastnik
) -> None:
    """plan_mixing_job creates the PLANNED job + MixingJobLine rows
    without consuming Stock."""
    from inventory.services import plan_mixing_job

    mix = Product.objects.create(name_cs="MixA", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=pepper, ratio=Decimal("1.000")
    )
    job = plan_mixing_job(
        branch=tyn, mixture=mix, target_qty=Decimal("2.000"), user=user_vlastnik
    )
    assert job.state == MixingJob.State.PLANNED
    assert job.lines.count() == 1
    # Stock row not created.
    assert not Stock.objects.filter(product=pepper, branch=tyn).exists()
    # No Movement either.
    assert not Movement.objects.filter(branch=tyn).exists()


@pytest.mark.django_db
def test_start_mixing_job_from_planned_consumes_stock(
    tyn, pepper, user_vlastnik
) -> None:
    """start_mixing_job(job=planned) transitions PLANNED→RUNNING and
    decrements stock."""
    from inventory.services import plan_mixing_job, start_mixing_job

    mix = Product.objects.create(name_cs="MixB", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=pepper, ratio=Decimal("1.000")
    )
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    job = plan_mixing_job(
        branch=tyn, mixture=mix, target_qty=Decimal("3.000"), user=user_vlastnik
    )
    start_mixing_job(job=job, user=user_vlastnik)
    job.refresh_from_db()
    assert job.state == MixingJob.State.RUNNING
    assert job.consume_movement is not None
    pepper_stock = Stock.objects.get(product=pepper, branch=tyn)
    assert pepper_stock.quantity == Decimal("7.000")


@pytest.mark.django_db
def test_execute_planned_transfer_creates_paired_movements(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """execute_planned_transfer creates výdej @ source + příjem @ target,
    both linked back via the transfer FK, source decreased + target
    increased, dodák auto-issued on the výdej leg."""
    from inventory.models import PlannedTransfer
    from inventory.services import execute_planned_transfer

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    transfer = PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("3.000"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    vydej, prijem = execute_planned_transfer(transfer, executed_by=user_vlastnik)
    transfer.refresh_from_db()
    assert transfer.state == PlannedTransfer.State.DONE
    assert vydej.kind == Movement.Kind.VYDEJ
    assert prijem.kind == Movement.Kind.PRIJEM
    assert vydej.transfer_id == transfer.pk
    assert prijem.transfer_id == transfer.pk
    src_stock = Stock.objects.get(product=pepper, branch=tyn)
    tgt_stock = Stock.objects.get(product=pepper, branch=sez)
    assert src_stock.quantity == Decimal("7.000")
    assert tgt_stock.quantity == Decimal("3.000")
    # Counterparty is `is_internal=False` so dodák auto-issue fires.
    assert DodaciList.objects.filter(movement=vydej).exists()


@pytest.mark.django_db
def test_execute_planned_transfer_refuses_when_not_planned(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """Cannot execute a transfer that has already been DONE or CANCELLED."""
    from inventory.models import PlannedTransfer
    from inventory.services import execute_planned_transfer

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    transfer = PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("1.000"),
        scheduled_for=date.today(),
        state=PlannedTransfer.State.DONE,
        created_by=user_vlastnik,
    )
    with pytest.raises(ValidationError):
        execute_planned_transfer(transfer, executed_by=user_vlastnik)


@pytest.mark.django_db
def test_cancel_planned_transfer_no_stock_change(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """cancel_planned_transfer flips state to CANCELLED, touches no stock."""
    from inventory.models import PlannedTransfer
    from inventory.services import cancel_planned_transfer

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    transfer = PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("2.000"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    cancel_planned_transfer(transfer, cancelled_by=user_vlastnik)
    transfer.refresh_from_db()
    assert transfer.state == PlannedTransfer.State.CANCELLED
    stock = Stock.objects.get(product=pepper, branch=tyn)
    assert stock.quantity == Decimal("5.000")


@pytest.mark.django_db
def test_overdraw_check_unchanged_by_planned_transfer(
    tyn, sez, pepper, user_vlastnik, ricany
) -> None:
    """Per 0044 § (4): a PLANNED transfer does NOT block a competing
    výdej from passing the overdraw pre-check on `Stock.quantity`. The
    race-loser hits the DB CHECK constraint only on actual apply.
    """
    from inventory.models import PlannedTransfer
    from inventory.views import _compute_overdraw

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    # 4 kg of pepper reserved by a planned transfer — but stock is 5 kg.
    PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("4.000"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    # Try a výdej of 4.5 kg — would be over-reserved (4 + 4.5 > 5),
    # but the overdraw check looks at raw Stock.quantity only.
    line = MovementLine(product=pepper, quantity_kg=Decimal("4.500"))
    warnings = _compute_overdraw(tyn, [line])
    # 4.5 < 5 raw, so no warning. Reservations are informational only.
    assert warnings == []


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_threshold_field_hidden_for_obsluha(
    user_obsluha_tyn, pepper
) -> None:
    """Obsluha sees the product edit page but the threshold field is
    not rendered (vlastník-only per 0043)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit/")
    assert response.status_code == 200
    # Czech header "Objednací bod" should not appear for obsluha.
    assert b"Objedna" not in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_threshold_field_shown_for_vlastnik(user_vlastnik, pepper) -> None:
    """Vlastník sees the threshold field on the product edit page."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit/")
    assert response.status_code == 200
    assert b"Objedna" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_planned_transfer_create_view_creates_row(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """POSTing to /prevody/novy/ creates a PLANNED PlannedTransfer."""
    from inventory.models import PlannedTransfer

    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/prevody/novy/",
        {
            "source_branch": str(tyn.pk),
            "target_branch": str(sez.pk),
            "product": str(pepper.pk),
            "quantity_kg": "1.500",
            "scheduled_for": date.today().isoformat(),
            "notes": "test transfer",
        },
    )
    assert response.status_code == 302
    pt = PlannedTransfer.objects.get(product=pepper)
    assert pt.state == PlannedTransfer.State.PLANNED
    assert pt.quantity_kg == Decimal("1.500")
    assert pt.created_by_id == user_vlastnik.pk


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_planned_transfer_index_renders(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/prevody/")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_low_stock_panel_appears_on_owner_dashboard(
    user_vlastnik, tyn, pepper
) -> None:
    """Owner dashboard renders the "Dochází zboží" panel when there
    are rows below threshold."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Pepper is below threshold → it shows in TYN's "Dochází" group.
    assert "Dochází" in body
    assert pepper.name_cs in body


# ---------------------------------------------------------------------------
