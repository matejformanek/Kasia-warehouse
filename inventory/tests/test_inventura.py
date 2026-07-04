from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    Customer,
    Movement,
    Stock,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
)

# Pass 5d — Manual stock adjustment (per decision 0041)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_requires_login(pepper) -> None:
    response = Client().get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 302
    assert "/sklad/prihlaseni/" in response["Location"]


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_forbidden_for_obsluha(user_obsluha_tyn, pepper) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_renders_for_vlastnik(user_vlastnik, pepper, tyn) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 200
    assert b"\xc3\x9aprava stavu" in response.content  # "Úprava stavu"
    assert b'value="10.0"' in response.content


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_prefills_1dp_and_subunit_save_is_noop(
    user_vlastnik, pepper, tyn, sez
) -> None:
    """A sub-0.1 stored value (9.997) prefills as 10.0; saving it unchanged
    writes no movement and demands no reason. A genuine edit still writes one."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("9.997"))
    client = Client()
    client.force_login(user_vlastnik)

    # GET prefills the 1dp rounded value, not the raw 3dp residue.
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 200
    assert b'value="10.0"' in response.content
    assert b"9.997" not in response.content

    # POSTing that prefilled value unchanged → no-op, no reason required.
    before = Movement.objects.count()
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "10.0",
            f"qty_{sez.pk}": "0.000",
            "reason": "",
        },
    )
    assert response.status_code == 302
    assert Movement.objects.count() == before  # no phantom correction
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("9.997")

    # A genuine edit still writes exactly one [STAV] movement + rewrites to 1dp.
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "12",
            f"qty_{sez.pk}": "0.000",
            "reason": "inventura",
        },
    )
    assert response.status_code == 302
    assert Movement.objects.count() == before + 1
    mv = Movement.objects.order_by("-id").first()
    assert mv.note.startswith("[STAV] ")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("12.0")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_positive_delta_writes_prijem(
    user_vlastnik, pepper, tyn, sez
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "12.500",
            f"qty_{sez.pk}": "0.000",
            "reason": "inventura — naval o 2,5 kg víc",
        },
    )
    assert response.status_code == 302
    s = Stock.objects.get(product=pepper, branch=tyn)
    assert s.quantity == Decimal("12.500")
    mv = Movement.objects.filter(
        branch=tyn, kind=Movement.Kind.PRIJEM
    ).order_by("-id").first()
    assert mv is not None
    assert mv.note.startswith("[STAV] ")
    assert "naval" in mv.note
    assert mv.dodavatel.is_internal is True
    assert mv.dodavatel.name == "Inventura / ruční úprava"


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_negative_delta_writes_vydej(
    user_vlastnik, pepper, tyn, sez
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "7.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "inventura — chybí 3 kg",
        },
    )
    assert response.status_code == 302
    s = Stock.objects.get(product=pepper, branch=tyn)
    assert s.quantity == Decimal("7.000")
    mv = Movement.objects.filter(
        branch=tyn, kind=Movement.Kind.VYDEJ
    ).order_by("-id").first()
    assert mv is not None
    assert mv.note.startswith("[STAV] ")
    assert mv.odberatel.is_internal is True
    assert mv.odberatel.name == "Inventura / ruční úprava"


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_zero_delta_noop(user_vlastnik, pepper, tyn, sez) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "10.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "",
        },
    )
    assert response.status_code == 302
    after = Movement.objects.count()
    assert after == before  # no movement written


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_requires_reason(user_vlastnik, pepper, tyn, sez) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "12.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "",
        },
    )
    assert response.status_code == 200  # form re-rendered with error
    s = Stock.objects.get(product=pepper, branch=tyn)
    assert s.quantity == Decimal("10.000")  # unchanged


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_creates_stock_row_when_missing(
    user_vlastnik, paprika, tyn, sez
) -> None:
    """Adjusting from 0 (no Stock row yet) creates the Stock row implicitly."""
    assert not Stock.objects.filter(product=paprika, branch=tyn).exists()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{paprika.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "5.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "počáteční stav",
        },
    )
    assert response.status_code == 302
    s = Stock.objects.get(product=paprika, branch=tyn)
    assert s.quantity == Decimal("5.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_movement_appears_in_history_with_stav_prefix(
    user_vlastnik, pepper, tyn, sez
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "11.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "úprava",
        },
    )
    response = client.get("/sklad/pohyby/")
    assert response.status_code == 200
    # Counterparty appears in the history Protistrana column.
    # The [STAV] note prefix is in the DB (Movement.note) — future
    # work surfaces it as a Historie filter; for now we only assert
    # the synthetic movement made it into Historie.
    assert b"Inventura" in response.content
    mv = Movement.objects.filter(branch=tyn).order_by("-id").first()
    assert mv.note.startswith("[STAV] ")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_per_product_bulk_writes_one_movement_per_changed_branch(
    user_vlastnik, pepper, tyn, sez
) -> None:
    """Per-product inventura: rows for both branches change in one POST → two
    Movements, one per branch; the shared reason lands on both."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("4.000"))
    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "12.500",
            f"qty_{sez.pk}": "3.500",
            "reason": "inventura k 29. 06.",
        },
    )
    assert response.status_code == 302
    assert Movement.objects.count() == before + 2
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("12.500")
    assert Stock.objects.get(product=pepper, branch=sez).quantity == Decimal("3.500")
    for mv in Movement.objects.order_by("-id")[:2]:
        assert mv.note.startswith("[STAV] ")
        assert "inventura k 29. 06." in mv.note


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_renders_all_active_branches_as_rows(
    user_vlastnik, pepper, tyn, sez
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    # SEZ has no Stock row → still expected as a "Nedrží" row.
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 200
    body = response.content
    assert f'name="qty_{tyn.pk}"'.encode() in body
    assert f'name="qty_{sez.pk}"'.encode() in body
    assert b"Dr\xc5\xbe\xc3\xad" in body  # "Drží"
    assert b"Nedr\xc5\xbe\xc3\xad" in body  # "Nedrží"


# ---------------------------------------------------------------------------
# Pass 5e — Bulk inventura editor (per decision 0041)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_requires_login() -> None:
    response = Client().get("/sklad/katalog/inventura/TYN/")
    assert response.status_code == 302


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_obsluha_own_branch_ok(user_obsluha_tyn, tyn, pepper) -> None:
    # Per 0073: obsluha may run inventura for their OWN branch.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("4.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/inventura/TYN/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Inventura — TYN" in body
    assert pepper.name_cs in body
    # No cross-branch switcher for obsluha (would 403).
    assert "/katalog/inventura/vse/" not in body
    assert "/katalog/inventura/dochazi/" not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_obsluha_other_branch_forbidden(user_obsluha_tyn, sez) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    assert client.get("/sklad/katalog/inventura/SEZ/").status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_obsluha_cross_branch_forbidden(user_obsluha_tyn) -> None:
    # The cross-branch roll-ups ("Vše" / "Dochází zboží") stay owner-only.
    client = Client()
    client.force_login(user_obsluha_tyn)
    assert client.get("/sklad/katalog/inventura/vse/").status_code == 403
    assert client.get("/sklad/katalog/inventura/dochazi/").status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_obsluha_can_correct_own_branch_stock(
    user_obsluha_tyn, tyn, pepper
) -> None:
    # Per 0073: obsluha's own-branch inventura writes [STAV] corrections.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("4.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {f"qty_{pepper.pk}": "9.0", "reason": "inventura obsluhy"},
    )
    assert response.status_code == 302
    pepper.refresh_from_db()
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("9.000")
    from inventory.models import Movement
    assert Movement.objects.filter(
        branch=tyn, status=Movement.Status.DONE
    ).exists()


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_renders_for_vlastnik(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/inventura/TYN/")
    assert response.status_code == 200
    body = response.content
    assert b"Inventura \xe2\x80\x94 TYN" in body  # "Inventura — TYN"
    assert pepper.name_cs.encode() in body
    # Rows carry the current stock as a clean 1-dp dot value (data-current +
    # prefill), per the Part A phantom-edit fix — no longer the raw 3dp residue.
    assert b'data-current="10.0"' in body
    assert b'data-current="5.5"' in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_low_toggle_single_branch(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    # Single-branch inventura carries the "Dochází" checkbox, and each row is
    # marked below/above its reorder threshold (data-low). pepper sits above
    # its threshold, paprika below → one data-low="1" and one data-low="0".
    from inventory.models import StockThresholdOverride

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.500"))
    StockThresholdOverride.objects.create(
        product=pepper, branch=tyn, threshold_kg=Decimal("5.000")
    )
    StockThresholdOverride.objects.create(
        product=paprika, branch=tyn, threshold_kg=Decimal("20.000")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/inventura/TYN/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'id="inventura-low-only"' in body
    assert "Dochází" in body
    assert 'data-low="1"' in body
    assert 'data-low="0"' in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_low_toggle_hidden_cross_branch(
    user_vlastnik, tyn, pepper
) -> None:
    # The "Dochází" toggle is single-branch only — never on the cross-branch
    # "Vše" or "Dochází zboží" views.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    for code in ("vse", "dochazi"):
        response = client.get(f"/sklad/katalog/inventura/{code}/")
        assert response.status_code == 200
        assert b'id="inventura-low-only"' not in response.content


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_data_current_uses_dot_decimal(
    user_vlastnik, tyn, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/inventura/TYN/")
    # data-current is the clean 1-dp value (dot), matching the floatformat:1
    # display + the server compare (per 0061 / Part A phantom-edit fix).
    assert b'data-current="1.5"' in response.content
    assert b'data-current="1,5"' not in response.content


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_x5_value_no_phantom_edit(user_vlastnik, tyn, pepper) -> None:
    """A `.x5` stock (45.450) rounds HALF_UP to 45.5 for display, prefill AND
    data-current — so the row loads un-edited and re-submitting it is a no-op
    (no movement, no reason required). Regression for the phantom-edit bug where
    display used HALF_UP (45,5) but the prefill used HALF_EVEN (45,4)."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("45.450"))
    client = Client()
    client.force_login(user_vlastnik)

    response = client.get("/sklad/katalog/inventura/TYN/")
    assert response.status_code == 200
    assert b'value="45.5"' in response.content       # prefill HALF_UP
    assert b'data-current="45.5"' in response.content  # JS-truth HALF_UP
    assert b'value="45.4"' not in response.content

    before = Movement.objects.count()
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {f"qty_{pepper.pk}": "45.5", "reason": ""},
    )
    assert response.status_code == 302
    assert Movement.objects.count() == before  # no phantom correction
    assert (
        Stock.objects.get(product=pepper, branch=tyn).quantity
        == Decimal("45.450")
    )


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_per_branch_save_redirects_to_catalogue(
    user_vlastnik, tyn, sez, pepper
) -> None:
    # Regression: the per-branch save must land on the /sklad/-prefixed
    # catalogue (was a bare /katalog/?branch=… → 404). Checked for both
    # branches. An empty POST is a no-op that still redirects.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_vlastnik)
    for code in ("TYN", "SEZ"):
        response = client.post(f"/sklad/katalog/inventura/{code}/", {})
        assert response.status_code == 302
        assert response.headers["Location"].startswith(
            f"/sklad/katalog/?branch={code}"
        )


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_products_filter_restricts_rows(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    # Per 0060: ?products=<pk,…> narrows the per-branch inventura to those
    # products (a blend's inputs). Other products drop out.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/inventura/TYN/?products={pepper.pk}")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_per_branch_honours_next_round_trip(
    user_vlastnik, tyn, pepper
) -> None:
    # Per 0060: a `next=` (e.g. back to the míchání form) is honoured on a
    # per-branch save via _safe_next.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {"next": "/sklad/michani/novy/?branch=1"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/michani/novy/?branch=1"


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_writes_movements_for_changed_rows_only(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.500"))

    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {
            "reason": "inventura 2026-06-12",
            f"qty_{pepper.pk}": "10.000",   # unchanged → skip
            f"qty_{paprika.pk}": "6.000",  # +0.500 → write
        },
    )
    assert response.status_code == 302
    after = Movement.objects.count()
    assert after == before + 1  # only paprika changed
    paprika_stock = Stock.objects.get(product=paprika, branch=tyn)
    assert paprika_stock.quantity == Decimal("6.000")
    pepper_stock = Stock.objects.get(product=pepper, branch=tyn)
    assert pepper_stock.quantity == Decimal("10.000")
    # The synthetic Movement carries the batch reason in note (with [STAV] prefix).
    mv = Movement.objects.order_by("-id").first()
    assert mv.note.startswith("[STAV] ")
    assert "inventura 2026-06-12" in mv.note


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_subunit_prefill_save_is_noop(
    user_vlastnik, tyn, pepper
) -> None:
    """Posting the 1dp prefill (10.0) for a sub-0.1 stored row (9.997) writes
    no movement and requires no reason — the compare happens at 1 dp."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("9.997"))
    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {"reason": "", f"qty_{pepper.pk}": "10.0"},
    )
    assert response.status_code == 302  # redirect, no reason demanded
    assert Movement.objects.count() == before  # no phantom change
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("9.997")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_requires_reason(
    user_vlastnik, tyn, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {"reason": "", f"qty_{pepper.pk}": "12.000"},
    )
    # Form re-renders with error; no movements written.
    assert response.status_code == 200
    assert Movement.objects.count() == before


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_handles_multiple_changes_atomically(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {
            "reason": "inventura — víc změn najednou",
            f"qty_{pepper.pk}": "11.500",   # +1.500
            f"qty_{paprika.pk}": "4.000",  # -1.500
        },
    )
    assert response.status_code == 302
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("11.500")
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("4.000")
    # Two movements: one prijem (pepper +) and one vydej (paprika -).
    new_movements = list(Movement.objects.order_by("-id")[:2])
    kinds = {mv.kind for mv in new_movements}
    assert kinds == {Movement.Kind.PRIJEM, Movement.Kind.VYDEJ}


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_button_appears_when_branch_selected(
    user_vlastnik, tyn
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    # Without ?branch — no inventura button.
    response_no = client.get("/sklad/katalog/")
    assert response_no.status_code == 200
    assert b"Inventura TYN" not in response_no.content
    # With ?branch=TYN — button present.
    response_yes = client.get("/sklad/katalog/?branch=TYN")
    assert response_yes.status_code == 200
    assert b"Inventura TYN" in response_yes.content


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_katalog_inventura_cta_hidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    # The Katalog's own inventura CTA stays vlastník-only. Per 0073 obsluha
    # reaches inventura via the nav + the Přehled button instead, so the nav
    # link IS present — but the page-level cta-inventura button is not.
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    assert b"cta-inventura" not in response.content
    # Nav entry point exists for obsluha now (own-branch inventura).
    assert b"/katalog/inventura/TYN/" in response.content


# ---------------------------------------------------------------------------
# Pass 5f — Guided overdraw correction (per decision 0042)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_warning_card_shows_with_correction_button_for_vlastnik(
    user_vlastnik, tyn, pepper
) -> None:
    """Vlastník submitting an overdraw výdej sees the structured
    warning card with an "Upravit stav skladu" button per row."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": str(tyn.pk),
            "odberatel": str(
                Customer.objects.get(is_default_recipient=True).pk
            ),
            "date_issued": date.today().isoformat(),
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "12.000",  # 7 kg shortfall
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 200
    body = response.content
    assert b"Nedostatek na skladu" in body or b"Nedostatek na sklad" in body
    assert b"12,0" in body  # 1 dp, Czech comma (per 0061)
    assert b"5,0" in body
    assert b"7,0" in body  # shortfall
    assert b"Upravit stav skladu" in body
    # Movement should NOT have been created.
    assert not Movement.objects.filter(
        kind=Movement.Kind.VYDEJ, branch=tyn
    ).exists()


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_warning_card_hides_button_for_obsluha(
    user_obsluha_tyn, tyn, pepper
) -> None:
    """Obsluha sees the structured warning but no correction button
    (stock direct edit is vlastník-only per 0040)."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": str(tyn.pk),
            "odberatel": str(
                Customer.objects.get(is_default_recipient=True).pk
            ),
            "date_issued": date.today().isoformat(),
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "10.000",
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 200
    body = response.content
    assert b"jen vlastn\xc3\xadk" in body  # "jen vlastník"
    assert b"Upravit stav skladu" not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_warning_lists_all_insufficient_lines(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    """Multi-line overdraw shows ALL the short items, not just the first."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": str(tyn.pk),
            "odberatel": str(
                Customer.objects.get(is_default_recipient=True).pk
            ),
            "date_issued": date.today().isoformat(),
            "note": "",
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "8.000",  # 3 short
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
            "lines-1-product": str(paprika.pk),
            "lines-1-quantity_kg": "10.000",  # 7 short
            "lines-1-sarze": "",
            "lines-1-expiry": "",
            "lines-1-note": "",
        },
    )
    assert response.status_code == 200
    body = response.content
    assert pepper.name_cs.encode() in body
    assert paprika.name_cs.encode() in body
    # Both shortfalls appear (1 dp, Czech comma per 0061).
    assert b"3,0" in body
    assert b"7,0" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_aggregates_multiple_lines_of_same_product(
    user_vlastnik, tyn, pepper
) -> None:
    """Two formset rows for the same product (different šarže) sum up
    against stock for the overdraw check."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": str(tyn.pk),
            "odberatel": str(
                Customer.objects.get(is_default_recipient=True).pk
            ),
            "date_issued": date.today().isoformat(),
            "note": "",
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "6.000",
            "lines-0-sarze": "A",
            "lines-0-expiry": "",
            "lines-0-note": "",
            "lines-1-product": str(pepper.pk),
            "lines-1-quantity_kg": "6.000",  # combined 12 > 10
            "lines-1-sarze": "B",
            "lines-1-expiry": "",
            "lines-1-note": "",
        },
    )
    assert response.status_code == 200
    assert b"Nedostatek na sklad" in response.content
    assert b"12,0" in response.content  # combined requested (1 dp, comma)
    assert b"2,0" in response.content  # shortfall


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_clears_after_stock_correction(
    user_vlastnik, tyn, pepper
) -> None:
    """After vlastník bumps Stock via apply_stock_adjustment the same
    výdej submit goes through."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    ricany_pk = Customer.objects.get(is_default_recipient=True).pk
    client = Client()
    client.force_login(user_vlastnik)
    payload = {
        "branch": str(tyn.pk),
        "odberatel": str(ricany_pk),
        "date_issued": date.today().isoformat(),
        "note": "",
        "lines-TOTAL_FORMS": "1",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "1",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-product": str(pepper.pk),
        "lines-0-quantity_kg": "8.000",
        "lines-0-sarze": "",
        "lines-0-expiry": "",
        "lines-0-note": "",
    }
    # 1st attempt — overdraw, form re-rendered.
    r1 = client.post("/sklad/vydej/novy/", payload)
    assert r1.status_code == 200
    assert not Movement.objects.filter(
        kind=Movement.Kind.VYDEJ, branch=tyn
    ).exists()
    # Operator corrects stock via the helper service.
    from inventory.services import apply_stock_adjustment

    apply_stock_adjustment(
        product=pepper,
        branch=tyn,
        new_quantity=Decimal("10.000"),
        reason="inventura — opraveno",
        user=user_vlastnik,
    )
    # 2nd attempt — same payload, now goes through.
    r2 = client.post("/sklad/vydej/novy/", payload)
    assert r2.status_code == 302
    assert Movement.objects.filter(
        kind=Movement.Kind.VYDEJ, branch=tyn
    ).exists()


# ---------------------------------------------------------------------------
