"""Finished product „hotový výrobek" — third product kind (per 0095).

Unlimited like Voda (never deducted/seeded/blocks) but visible + sellable on
výdej; excluded from příjem + inventura; sold by the piece („ks").
"""

from decimal import Decimal

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from inventory.forms import MovementLineForm
from inventory.models import DodaciList, Movement, Product, Stock
from inventory.tests._support import _VIEW_TEST_OVERRIDES
from inventory.views.catalogue import catalogue_stock_groups

# --- 1. Model properties ---------------------------------------------------


@pytest.mark.django_db
def test_is_unlimited_and_unit(pepper, voda, hotovy_vyrobek) -> None:
    mixture = Product.objects.create(name_cs="Směs A", kind=Product.Kind.MIXTURE)
    assert hotovy_vyrobek.is_unlimited is True
    assert voda.is_unlimited is True  # untracked
    assert pepper.is_unlimited is False
    assert mixture.is_unlimited is False
    assert hotovy_vyrobek.unit == "ks"
    assert pepper.unit == "kg"
    assert mixture.unit == "kg"
    assert voda.unit == "kg"


# --- 2. catalogue_stock_groups helper -------------------------------------


@pytest.mark.django_db
def test_groups_finished_only_in_unlimited(tyn, sez, pepper, hotovy_vyrobek) -> None:
    """A finished product lands only in unlimited_rows — never empty/low/ok;
    a raw_spice at 0 stock still lands in empty_rows (guards §5↔§6)."""
    groups = catalogue_stock_groups([pepper, hotovy_vyrobek], [tyn, sez])
    unlimited_pks = {r["product"].pk for r in groups["unlimited_rows"]}
    assert hotovy_vyrobek.pk in unlimited_pks
    for key in ("empty_rows", "low_rows", "ok_rows"):
        assert hotovy_vyrobek.pk not in {r["product"].pk for r in groups[key]}
    # pepper (raw_spice, no stock → effective 0) still classes as empty.
    assert pepper.pk in {r["product"].pk for r in groups["empty_rows"]}
    assert groups["kpi_unlimited"] == 1


# --- 3. Katalog render -----------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_katalog_shows_finished_group(user_vlastnik, pepper, hotovy_vyrobek) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/").content.decode("utf-8")
    assert "Hotové výrobky — neomezeno" in body
    assert hotovy_vyrobek.name_cs in body
    assert "neomezeno" in body
    # The finished product is NOT in the Prázdné group (it's unlimited).
    assert 'id="cat-group-unlimited"' in body
    # KPI products counts both pepper (empty) + the finished product.
    assert 'data-kpi-live="products">2</span>' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_katalog_kind_filter_finished(user_vlastnik, pepper, hotovy_vyrobek) -> None:
    """?kind=hotovy_vyrobek shows the group, not „Nic neodpovídá"."""
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(
        "/sklad/katalog/?kind=hotovy_vyrobek"
    ).content.decode("utf-8")
    assert hotovy_vyrobek.name_cs in body
    assert "Hotové výrobky — neomezeno" in body
    assert pepper.name_cs not in body
    # The group renders (not the „Nic neodpovídá" fall-through branch, which
    # would omit the group section entirely).
    assert 'id="cat-group-unlimited"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_katalog_state_filter_hides_finished(user_vlastnik, hotovy_vyrobek) -> None:
    """A stock-state filter suppresses the unlimited group."""
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(
        "/sklad/katalog/?state=empty"
    ).content.decode("utf-8")
    assert 'id="cat-group-unlimited"' not in body


# --- 4. Výdej --------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_finished_saves_no_stock(
    user_tyn, tyn, ricany, hotovy_vyrobek
) -> None:
    """A finished výdej line saves, touches no Stock row, never overdraws."""
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": hotovy_vyrobek.pk,
            "lines-0-quantity_kg": "5",
        },
    )
    assert response.status_code == 302, response.content[:500]
    mv = Movement.objects.get()
    assert mv.lines.count() == 1
    assert not Stock.objects.filter(product=hotovy_vyrobek).exists()


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_mixed_kg_and_pieces(
    user_tyn, tyn, ricany, pepper, hotovy_vyrobek
) -> None:
    """A mixed kg + ks výdej: kg line deducts, finished line doesn't; the
    dodák detail renders both units."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "2.5",
            "lines-1-product": hotovy_vyrobek.pk,
            "lines-1-quantity_kg": "3",
        },
    )
    assert response.status_code == 302, response.content[:500]
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("7.500")
    dl = DodaciList.objects.get()
    body = client.get(
        reverse("inventory:dodaci_list_detail", args=[dl.cislo])
    ).content.decode("utf-8")
    assert "3 ks" in body
    assert "2,5 kg" in body
    assert "Množství" in body


# --- 6. Dropdown scope -----------------------------------------------------


@pytest.mark.django_db
def test_dropdown_scope(pepper, voda, hotovy_vyrobek) -> None:
    """Finished in výdej queryset, not in příjem; Voda in neither."""
    vydej = MovementLineForm()  # výdej: finished included
    prijem = MovementLineForm(exclude_finished=True)
    vydej_pks = set(vydej.fields["product"].queryset.values_list("pk", flat=True))
    prijem_pks = set(prijem.fields["product"].queryset.values_list("pk", flat=True))
    assert hotovy_vyrobek.pk in vydej_pks
    assert hotovy_vyrobek.pk not in prijem_pks
    assert pepper.pk in vydej_pks and pepper.pk in prijem_pks
    assert voda.pk not in vydej_pks and voda.pk not in prijem_pks


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_dropdown_excludes_finished(
    user_tyn, tyn, pepper, hotovy_vyrobek
) -> None:
    client = Client()
    client.force_login(user_tyn)
    body = client.get("/sklad/prijem/novy/").content.decode("utf-8")
    assert pepper.name_cs in body
    assert hotovy_vyrobek.name_cs not in body


# --- 7. line_row_partial parity -------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_partial_scope(user_tyn, pepper, hotovy_vyrobek) -> None:
    client = Client()
    client.force_login(user_tyn)
    # výdej add-row (?warn=1) includes finished.
    vydej = client.get(
        "/sklad/_partials/line-row/?index=1&warn=1"
    ).content.decode("utf-8")
    assert hotovy_vyrobek.name_cs in vydej
    # příjem add-row (no param) excludes finished.
    prijem = client.get(
        "/sklad/_partials/line-row/?index=1"
    ).content.decode("utf-8")
    assert hotovy_vyrobek.name_cs not in prijem
    # výdej-edit add-row (?finished=1) includes finished.
    fin = client.get(
        "/sklad/_partials/line-row/?index=1&finished=1"
    ).content.decode("utf-8")
    assert hotovy_vyrobek.name_cs in fin


# --- 8. Inventura ----------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_excludes_finished(
    user_vlastnik, tyn, pepper, hotovy_vyrobek
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    per_branch = client.get(
        "/sklad/katalog/inventura/TYN/"
    ).content.decode("utf-8")
    assert pepper.name_cs in per_branch
    assert hotovy_vyrobek.name_cs not in per_branch
    vse = client.get(
        "/sklad/katalog/inventura/vse/"
    ).content.decode("utf-8")
    assert hotovy_vyrobek.name_cs not in vse


# --- 10. Product detail ----------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_finished_unlimited(user_vlastnik, hotovy_vyrobek) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(
        reverse("inventory:product_detail", args=[hotovy_vyrobek.pk])
    ).content.decode("utf-8")
    assert "Neomezené množství" in body
    # No per-branch stock table header, no stock-adjust action.
    assert "Upravit stav skladu" not in body
