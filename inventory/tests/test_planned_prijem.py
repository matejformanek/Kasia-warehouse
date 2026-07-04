from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.test import Client, override_settings

from inventory.models import (
    Movement,
    MovementLine,
    Stock,
)
from inventory.services import (
    apply_movement,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
    _make_planned_prijem,
)

# Planned príjem (objednávka merged into příjem) — per decision 0059
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_no_date_receives_immediately(user_tyn, tyn, supplier, pepper) -> None:
    """Empty/past arrival date → an ordinary DONE příjem that hits stock now."""
    client = Client()
    client.force_login(user_tyn)
    resp = client.post(
        "/sklad/prijem/novy/",
        {
            "branch": tyn.pk,
            "dodavatel": supplier.pk,
            "date_issued": "2026-06-12",
            "expected_on": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "4.000",
        },
    )
    assert resp.status_code == 302, resp.content[:500]
    mv = Movement.objects.get()
    assert mv.status == Movement.Status.DONE
    assert mv.expected_on is None
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("4.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_future_date_is_planned_no_stock(user_tyn, tyn, pepper) -> None:
    """A future arrival date → a PLANNED príjem: stock unchanged, no supplier
    required, and the date_issued future-guard is NOT tripped by expected_on."""
    client = Client()
    client.force_login(user_tyn)
    resp = client.post(
        "/sklad/prijem/novy/",
        {
            "branch": tyn.pk,
            "dodavatel": "",  # optional on a planned příjem
            "date_issued": "2026-06-12",
            "expected_on": "2026-12-31",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "9.000",
        },
    )
    assert resp.status_code == 302, resp.content[:500]
    mv = Movement.objects.get()
    assert mv.status == Movement.Status.PLANNED
    assert mv.expected_on == date(2026, 12, 31)
    assert mv.dodavatel_id is None
    # No Stock row created — planned inbound never touches stock.
    assert not Stock.objects.filter(product=pepper, branch=tyn, quantity__gt=0).exists()


@pytest.mark.django_db
def test_confirm_planned_receipt_applies_adjusted_qty_and_drops_zero(
    tyn, pepper, paprika, supplier, user_vlastnik
) -> None:
    """confirm_planned_receipt adjusts per-line quantities, drops a 0 line,
    flips the whole receipt to DONE, and applies the result to stock."""
    from inventory.services import confirm_planned_receipt

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))
    movement = Movement(
        branch=tyn,
        kind=Movement.Kind.PRIJEM,
        status=Movement.Status.PLANNED,
        date_issued=date.today(),
        expected_on=date(2026, 12, 31),
    )
    lines = [
        MovementLine(product=pepper, quantity_kg=Decimal("10.000")),
        MovementLine(product=paprika, quantity_kg=Decimal("5.000")),
    ]
    apply_movement(movement=movement, lines=lines, user=user_vlastnik)
    # PLANNED — stock untouched.
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("3.000")

    pepper_line = movement.lines.get(product=pepper)
    paprika_line = movement.lines.get(product=paprika)
    confirm_planned_receipt(
        movement=movement,
        line_qty_by_id={
            pepper_line.pk: Decimal("8.000"),   # arrived less than ordered
            paprika_line.pk: Decimal("0.000"),  # didn't arrive → dropped
        },
        supplier=supplier,
        user=user_vlastnik,
    )
    movement.refresh_from_db()
    assert movement.status == Movement.Status.DONE
    assert movement.expected_on is None
    assert movement.dodavatel == supplier
    assert movement.date_issued == date.today()
    # Only the pepper line survives; stock rose by the adjusted amount.
    assert movement.lines.count() == 1
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("11.000")
    assert not Stock.objects.filter(product=paprika, branch=tyn, quantity__gt=0).exists()


@pytest.mark.django_db
def test_confirm_without_supplier_uses_internal_objednavka(
    tyn, pepper, user_vlastnik
) -> None:
    """No supplier on the movement or at confirm → internal 'Objednávka'."""
    from inventory.services import confirm_planned_receipt

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("5.000"),
        eta=date(2026, 12, 31), user=user_vlastnik,
    )
    line = movement.lines.get()
    confirm_planned_receipt(
        movement=movement,
        line_qty_by_id={line.pk: Decimal("5.000")},
        user=user_vlastnik,
    )
    movement.refresh_from_db()
    assert movement.dodavatel.name == "Objednávka"
    assert movement.dodavatel.is_internal is True
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("5.000")


@pytest.mark.django_db
def test_confirm_all_zero_lines_raises(tyn, pepper, user_vlastnik) -> None:
    """Confirming with every line set to 0 leaves no items → ValidationError."""

    from inventory.services import confirm_planned_receipt

    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("5.000"),
        eta=date(2026, 12, 31), user=user_vlastnik,
    )
    line = movement.lines.get()
    with pytest.raises(ValidationError):
        confirm_planned_receipt(
            movement=movement,
            line_qty_by_id={line.pk: Decimal("0.000")},
            user=user_vlastnik,
        )


@pytest.mark.django_db
def test_confirm_guard_rejects_non_planned(tyn, pepper, supplier, user_vlastnik) -> None:
    """confirm_planned_receipt refuses a DONE movement."""

    from inventory.services import apply_movement, confirm_planned_receipt

    movement = Movement(
        branch=tyn, kind=Movement.Kind.PRIJEM, date_issued=date(2026, 6, 1),
        dodavatel=supplier,
    )
    apply_movement(
        movement=movement,
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_vlastnik,
    )
    with pytest.raises(ValidationError):
        confirm_planned_receipt(
            movement=movement, line_qty_by_id={}, user=user_vlastnik
        )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_confirm_view_applies_stock(tyn, pepper, user_obsluha_tyn) -> None:
    """POST to the confirm endpoint with an adjusted amount raises Stock and
    flips the movement to DONE. All logged-in users."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("10.000"),
        eta=date(2026, 12, 31), user=user_obsluha_tyn,
    )
    line = movement.lines.get()
    client = Client()
    client.force_login(user_obsluha_tyn)
    resp = client.post(
        f"/sklad/prijem/{movement.pk}/potvrdit/",
        {f"qty_{line.pk}": "7.500", "as_of": date.today().isoformat(), "supplier": ""},
    )
    assert resp.status_code == 302
    movement.refresh_from_db()
    assert movement.status == Movement.Status.DONE
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("8.500")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_plan_cancel_deletes_and_touches_no_stock(
    tyn, pepper, user_vlastnik
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("2.000"))
    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("5.000"),
        eta=date(2026, 12, 31), user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(f"/sklad/prijem/{movement.pk}/zrusit/")
    assert resp.status_code == 302
    assert not Movement.objects.filter(pk=movement.pk).exists()
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("2.000")


@pytest.mark.django_db
def test_low_stock_row_carries_order_overlay_without_changing_deficit(
    tyn, pepper, user_vlastnik
) -> None:
    """A PLANNED príjem populates ordered_kg/ordered_eta but leaves the row
    listed with unchanged effective/deficit (0059 informational invariant)."""
    from inventory.services import low_stock_rows

    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))

    before = low_stock_rows()
    assert len(before) == 1
    assert before[0].ordered_kg is None
    assert before[0].deficit == Decimal("4.000")

    _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"),
        eta=date(2026, 7, 15), user=user_vlastnik,
    )
    after = low_stock_rows()
    assert len(after) == 1
    row = after[0]
    assert row.effective == Decimal("1.000")
    assert row.deficit == Decimal("4.000")
    assert row.ordered_kg == Decimal("9.000")
    assert row.ordered_eta == date(2026, 7, 15)


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_low_stock_panel_shows_resolve_button_and_orders_badge(
    tyn, pepper, user_vlastnik
) -> None:
    """Owner home renders the Upravit button; an ordered row shows the badge."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))

    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/").content.decode("utf-8")
    # Per-branch Inventura button opens that branch's inventura.
    assert "Inventura TYN" in body
    assert "/sklad/katalog/inventura/TYN/" in body

    _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"),
        eta=date(2026, 7, 15), user=user_vlastnik,
    )
    body2 = client.get("/sklad/").content.decode("utf-8")
    assert "Objednáno" in body2


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dochazi_lists_cross_branch_low_rows(
    tyn, sez, pepper, paprika, user_vlastnik
) -> None:
    """The special 'dochazi' inventura lists only below-threshold rows,
    across all branches, with the pobočka column."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("2.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("9.000"))

    client = Client()
    client.force_login(user_vlastnik)
    resp = client.get("/sklad/katalog/inventura/dochazi/")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    assert "Dochází zboží" in body
    assert pepper.name_cs in body
    assert paprika.name_cs not in body
    assert f"qty_{pepper.pk}_{tyn.pk}" in body
    assert f"qty_{pepper.pk}_{sez.pk}" in body
    # Dochází now prefills the nový-stav cell with current stock (1 dp, dot in
    # the type=number value=), matching the per-branch / Vše views.
    assert 'value="1.0"' in body  # TYN pepper 1.000 → 1.0
    assert 'value="2.0"' in body  # SEZ pepper 2.000 → 2.0


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dochazi_adjust_and_order_in_one_post(
    tyn, sez, pepper, paprika, user_vlastnik
) -> None:
    """No date → immediate stock correction; date set → PLANNED príjem. One POST."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("2.000"))

    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        "/sklad/katalog/inventura/dochazi/",
        {
            f"qty_{pepper.pk}_{tyn.pk}": "12.000",
            f"eta_{pepper.pk}_{tyn.pk}": "",
            f"qty_{paprika.pk}_{tyn.pk}": "8.000",
            f"eta_{paprika.pk}_{tyn.pk}": "2026-07-20",
            "reason": "doplnění z panelu",
        },
    )
    assert resp.status_code == 302
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("12.000")
    # Paprika stock unchanged — the order is a PLANNED príjem, not received.
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("2.000")
    planned = Movement.objects.get(
        status=Movement.Status.PLANNED, branch=tyn, kind=Movement.Kind.PRIJEM
    )
    assert planned.expected_on == date(2026, 7, 20)
    pline = planned.lines.get()
    assert pline.product == paprika
    assert pline.quantity_kg == Decimal("8.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dated_rows_group_into_one_movement_per_branch_eta(
    tyn, pepper, paprika, user_vlastnik
) -> None:
    """Two dated rows on the same branch + ETA collapse into ONE PLANNED
    príjem Movement with two lines (per 0059 grouping)."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        "/sklad/katalog/inventura/TYN/",
        {
            f"qty_{pepper.pk}": "5.000",
            f"eta_{pepper.pk}": "2026-08-01",
            f"qty_{paprika.pk}": "6.000",
            f"eta_{paprika.pk}": "2026-08-01",
        },
    )
    assert resp.status_code == 302
    planned = Movement.objects.filter(
        status=Movement.Status.PLANNED, branch=tyn
    )
    assert planned.count() == 1
    mv = planned.get()
    assert mv.expected_on == date(2026, 8, 1)
    assert mv.lines.count() == 2


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dochazi_blocked_for_obsluha(
    tyn, pepper, user_obsluha_tyn
) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    resp = client.get("/sklad/katalog/inventura/dochazi/")
    assert resp.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_missing_reason_preserves_typed_values(
    tyn, sez, pepper, paprika, user_vlastnik
) -> None:
    """Regression: a missing reason must NOT wipe the operator's input."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("2.000"))

    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        "/sklad/katalog/inventura/dochazi/",
        {
            f"qty_{pepper.pk}_{tyn.pk}": "13.000",
            f"eta_{pepper.pk}_{tyn.pk}": "",
            f"qty_{paprika.pk}_{tyn.pk}": "7.000",
            f"eta_{paprika.pk}_{tyn.pk}": "2026-09-01",
            "reason": "",
        },
    )
    assert resp.status_code == 200
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("1.000")
    body = resp.content.decode("utf-8")
    assert 'value="13.000"' in body
    assert 'value="7.000"' in body
    assert 'value="2026-09-01"' in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_vse_lists_all_products_all_branches(
    tyn, sez, pepper, paprika, user_vlastnik
) -> None:
    """The 'vse' option shows every active product × every active branch."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.get("/sklad/katalog/inventura/vse/")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    assert "Inventura — vše" in body
    assert f"qty_{pepper.pk}_{tyn.pk}" in body
    assert f"qty_{pepper.pk}_{sez.pk}" in body
    assert f"qty_{paprika.pk}_{tyn.pk}" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_inventura_button_always_present(user_vlastnik, tyn) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    no_branch = client.get("/sklad/katalog/").content.decode("utf-8")
    assert "Inventura — vše" in no_branch
    assert "/sklad/katalog/inventura/vse/" in no_branch
    with_branch = client.get("/sklad/katalog/?branch=TYN").content.decode("utf-8")
    assert "Inventura TYN" in with_branch


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dochazi_shows_existing_order_with_year_and_controls(
    tyn, pepper, user_vlastnik
) -> None:
    """An open PLANNED príjem shows inline with year + confirm/cancel controls
    pointing at prijem_confirm / prijem_plan_cancel (0059)."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"),
        eta=date(2026, 7, 15), user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/inventura/dochazi/").content.decode("utf-8")
    assert "15. 07. 2026" in body
    assert f"/sklad/prijem/{movement.pk}/potvrdit/" in body
    assert f"plan-cancel-{movement.pk}" in body
    assert 'id="kasia-confirm"' in body
    assert 'class="js-confirm"' in body
    assert "return confirm(" not in body


# ---------------------------------------------------------------------------
# Movement history — Plánované tab + DONE-only history (per 0059)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_planned_tab_lists_only_planned(
    tyn, pepper, supplier, user_vlastnik
) -> None:
    """The Plánované tab lists only PLANNED rows; the other tabs exclude them,
    and a PLANNED row is absent from the home recent-movement panel."""

    # One DONE příjem + one PLANNED príjem.
    done = Movement(
        branch=tyn, kind=Movement.Kind.PRIJEM, date_issued=date(2026, 6, 20),
        dodavatel=supplier,
    )
    apply_movement(
        movement=done,
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_vlastnik,
    )
    planned = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"),
        eta=date(2026, 12, 31), user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)

    # Per 0066: "Vše" now unions DONE + PLANNED (1 + 1 = 2), and the planned
    # confirm link appears there too. The other tabs still exclude planned.
    all_tab = client.get("/sklad/pohyby/?tab=all").content.decode("utf-8")
    assert "Nalezeno: 2" in all_tab
    assert f"/sklad/prijem/{planned.pk}/potvrdit/" in all_tab
    prijem_tab = client.get("/sklad/pohyby/?tab=prijem").content.decode("utf-8")
    assert "Nalezeno: 1" in prijem_tab
    assert f"/sklad/prijem/{planned.pk}/potvrdit/" not in prijem_tab

    planned_tab = client.get("/sklad/pohyby/?tab=planned")
    body = planned_tab.content.decode("utf-8")
    assert "Nalezeno: 1" in body
    assert "Plánováno" in body
    assert f"/sklad/prijem/{planned.pk}/potvrdit/" in body

    # A FUTURE planned (Dec 31) is not yet due → absent from the home K-vyřešení.
    home = client.get("/sklad/").content.decode("utf-8")
    assert f"/sklad/prijem/{planned.pk}/potvrdit/" not in home


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_surfaces_due_planned_prijem(
    tyn, pepper, user_vlastnik
) -> None:
    """Per 0066: a PLANNED příjem whose expected_on <= today is a K-vyřešení
    task on the Přehled (Přijmout link); a future one is not."""
    today = date.today()
    due = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"), eta=today,
        user=user_vlastnik,
    )
    future = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("5.000"),
        eta=date(today.year + 1, 1, 15), user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/").content.decode("utf-8")
    assert "Očekávaný" in body  # due-planned task badge
    assert f"/sklad/prijem/{due.pk}/potvrdit/" in body
    assert f"/sklad/prijem/{future.pk}/potvrdit/" not in body


@pytest.mark.django_db
def test_migration_0017_migrates_open_planned_orders(
    tyn, pepper, supplier, user_vlastnik
) -> None:
    """The 0017 data migration turns an open PlannedOrder into a PLANNED
    Movement (+ line) and cancels the source order."""
    import importlib

    from django.apps import apps as global_apps

    from inventory.models import PlannedOrder

    order = PlannedOrder.objects.create(
        product=pepper,
        branch=tyn,
        supplier=supplier,
        quantity_kg=Decimal("12.000"),
        expected_on=date(2026, 12, 31),
        state=PlannedOrder.State.PLANNED,
        created_by=user_vlastnik,
    )
    mig = importlib.import_module(
        "inventory.migrations.0017_migrate_open_planned_orders"
    )
    mig.forwards(global_apps, None)

    order.refresh_from_db()
    assert order.state == PlannedOrder.State.CANCELLED
    mv = Movement.objects.get(status=Movement.Status.PLANNED, branch=tyn)
    assert mv.kind == Movement.Kind.PRIJEM
    assert mv.expected_on == date(2026, 12, 31)
    assert mv.dodavatel == supplier
    line = mv.lines.get()
    assert line.product == pepper
    assert line.quantity_kg == Decimal("12.000")
