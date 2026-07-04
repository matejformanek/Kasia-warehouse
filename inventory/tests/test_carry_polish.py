import re
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    Branch,
    Movement,
    MovementLine,
    Product,
    Stock,
    Supplier,
)
from inventory.services import (
    apply_movement,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
    _mk_mixture_with_recipe,
)

# Decision 0053 — Stock row existence IS the "branch carries product" flag.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_low_stock_summary_skips_branch_without_stock_row(
    tyn, sez, pepper
) -> None:
    """Per 0053: a branch without a Stock row does not enter the
    low-stock report, even when its 'effective = 0' would otherwise
    register as below threshold."""
    from inventory.services import low_stock_rows

    pepper.reorder_threshold_kg = Decimal("10.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("5.000"))
    # TYN intentionally has no Stock row for pepper.

    rows = low_stock_rows()
    pairs = {(r.product.pk, r.branch.code) for r in rows}
    assert (pepper.pk, "SEZ") in pairs
    assert (pepper.pk, "TYN") not in pairs


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_chip_omits_branch_without_stock_row(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """Catalogue per-branch chip does not appear for a branch that
    doesn't carry the product (no Stock row)."""
    pepper.reorder_threshold_kg = Decimal("10.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("5.000"))
    # No Stock row at TYN.

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    pepper_row_idx = body.index("Pepř")
    snippet = body[pepper_row_idx : pepper_row_idx + 2000]

    chips = re.findall(
        r"<span class=\"(?:low|empty)-branch\"[^>]*>([A-Z]{3})</span>", snippet
    )
    assert "SEZ" in chips
    assert "TYN" not in chips


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_seeds_stock_rows_for_all_active_branches(
    user_vlastnik, tyn, sez
) -> None:
    """Per 0053: creating a product seeds a 0-kg Stock row on every
    active branch, preserving today's 'visible everywhere' default."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/novy/",
        {
            "name_cs": "Kmín",
            "kind": Product.Kind.RAW_SPICE,
            "notes": "",
            "reorder_threshold_kg": "",
        },
    )
    assert response.status_code in (200, 302)
    product = Product.objects.get(name_cs="Kmín")
    branch_ids = set(
        Stock.objects.filter(product=product).values_list(
            "branch_id", flat=True
        )
    )
    active_branch_ids = set(
        Branch.objects.filter(is_active=True).values_list("id", flat=True)
    )
    assert branch_ids == active_branch_ids
    assert all(
        s.quantity == Decimal("0.000")
        for s in Stock.objects.filter(product=product)
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_branch_add_creates_zero_stock_row(
    user_vlastnik, tyn, pepper
) -> None:
    """Vlastník POST adds carry-state (0-kg Stock row). Second POST is a
    no-op (idempotent)."""
    client = Client()
    client.force_login(user_vlastnik)
    url = f"/sklad/katalog/{pepper.pk}/pobocky/{tyn.pk}/pridat/"
    r1 = client.post(url)
    assert r1.status_code in (200, 302)
    assert Stock.objects.filter(product=pepper, branch=tyn).exists()
    stock = Stock.objects.get(product=pepper, branch=tyn)
    assert stock.quantity == Decimal("0.000")
    # Second POST stays idempotent.
    r2 = client.post(url)
    assert r2.status_code in (200, 302)
    assert Stock.objects.filter(product=pepper, branch=tyn).count() == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_branch_remove_deletes_row_even_with_stock(
    user_vlastnik, tyn, pepper
) -> None:
    """Per 0053 + Matej's allow-but-warn pick: the server has no
    precondition — removal succeeds even with quantity > 0. UI warns."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.500"))
    client = Client()
    client.force_login(user_vlastnik)
    url = f"/sklad/katalog/{pepper.pk}/pobocky/{tyn.pk}/odebrat/"
    response = client.post(url)
    assert response.status_code in (200, 302)
    assert not Stock.objects.filter(product=pepper, branch=tyn).exists()


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_branch_add_forbidden_for_obsluha(
    user_obsluha_tyn, tyn, pepper
) -> None:
    """Carry-state mutation is vlastník-only; obsluha gets 403."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    url = f"/sklad/katalog/{pepper.pk}/pobocky/{tyn.pk}/pridat/"
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_edit_renders_pobocky_section_with_drzi_state(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """Product edit page shows the Pobočky section with the correct
    drží/nedrží state per branch and the matching action button."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("2.000"))
    # SEZ has no Stock row → nedrží.

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Pobočky držící tento produkt" in body
    assert "Drží" in body
    assert "Nedrží" in body
    # The TYN row has the Odebrat action; the SEZ row has Přidat.
    assert (
        f"/sklad/katalog/{pepper.pk}/pobocky/{tyn.pk}/odebrat/" in body
    )
    assert (
        f"/sklad/katalog/{pepper.pk}/pobocky/{sez.pk}/pridat/" in body
    )


# ---------------------------------------------------------------------------
# Polish round 2 — row-click, auto-append line, catalog state filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_job_index_rows_are_row_link(user_vlastnik, tyn, pepper) -> None:
    """Mixing index rows must use the shared `tr.row-link` pattern so the
    whole row navigates to the job detail."""
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("2.000"),
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/michani/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'class="row-link"' in body
    assert f'data-href="/sklad/michani/{job.pk}/"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_form_lines_has_add_line_btn_id(user_vlastnik) -> None:
    """The auto-append <script> in _movement_form_lines.html keys off
    `#add-line-btn` — guarantee the marker keeps shipping."""
    client = Client()
    client.force_login(user_vlastnik)
    for path in ("/sklad/prijem/novy/", "/sklad/vydej/novy/"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        assert 'id="add-line-btn"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_partial_still_returns_blank_row(user_tyn) -> None:
    """Sanity: line_row_partial keeps returning a blank row with the
    expected name attrs — the auto-append JS depends on it."""
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/_partials/line-row/?index=5")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="lines-5-product"' in body
    assert 'name="lines-5-quantity_kg"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_filter_state_low_keeps_only_low_rows(
    user_vlastnik, tyn, sez, pepper, paprika
) -> None:
    """?state=low keeps rows where is_low but not effective<=0 with threshold."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    # Pepper: low (1 kg < 5 kg threshold, still positive).
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("1.000"))
    # Paprika: above threshold on both branches.
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("20.000"))
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("20.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?state=low")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs not in body
    assert "Nalezeno: 1" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_form_shows_recent_movements_panel(
    user_vlastnik, tyn, supplier, pepper
) -> None:
    """The příjem create form renders the last N příjmy underneath
    with a link to the pre-filtered history page."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 28),
            dodavatel=supplier,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/prijem/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Poslední příjmy" in body
    assert "/sklad/pohyby/?tab=prijem" in body
    assert supplier.name in body
    # The vydej-only tab link must NOT appear in the příjem panel.
    assert "?tab=vydej" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_form_shows_recent_movements_panel(
    user_vlastnik, tyn, ricany, pepper
) -> None:
    """The výdej create form renders the last N výdeje underneath
    with a link to the pre-filtered history page."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 28),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/vydej/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Poslední výdeje" in body
    assert "/sklad/pohyby/?tab=vydej" in body
    assert ricany.name in body
    assert "?tab=prijem" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recent_movements_panel_scopes_obsluha_to_own_branch(
    user_obsluha_tyn, user_vlastnik, tyn, sez, supplier, pepper
) -> None:
    """Obsluha sees only own-branch movements in the recent panel."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("0.000"))
    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 28),
            dodavatel=supplier,
            note="TYN-PANEL-TEST",
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    sez_supplier = Supplier.objects.create(name="SEZ Dodavatel")
    apply_movement(
        movement=Movement(
            branch=sez,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 28),
            dodavatel=sez_supplier,
            note="SEZ-PANEL-TEST",
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/prijem/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Both suppliers appear in the dodavatel <select> dropdown. The
    # panel scoping assertion runs on the "Poslední příjmy" snippet
    # only — that snippet must not include the SEZ supplier name.
    panel_start = body.index("Poslední příjmy")
    panel = body[panel_start:]
    assert supplier.name in panel
    assert sez_supplier.name not in panel


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recent_movements_panel_hidden_when_empty(user_vlastnik) -> None:
    """No movements yet → no panel rendered (silent on empty)."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/prijem/novy/")
    body = response.content.decode("utf-8")
    assert "Poslední příjmy" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_filter_state_empty_keeps_only_empty_rows(
    user_vlastnik, tyn, sez, pepper, paprika
) -> None:
    """?state=empty keeps rows where effective<=0 and threshold is set."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    # Pepper: effective = 0 on both branches → empty.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("0.000"))
    # Paprika: low but not empty.
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("1.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?state=empty")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs not in body
    assert "Nalezeno: 1" in body




# ---------------------------------------------------------------------------
