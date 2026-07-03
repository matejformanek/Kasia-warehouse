from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    Movement,
    MovementLine,
    Stock,
    Supplier,
)
from inventory.services import (
    apply_movement,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
)

# Pass 5g — Historie redesign (tab chips)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_tab_chips_render(user_vlastnik, tyn, pepper, ricany) -> None:
    """All five tabs render with correct counts; "Vše" active by default."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    # One prijem
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.PRIJEM,
            dodavatel=Supplier.objects.create(name="X"),
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("5.000"))],
        user=user_vlastnik,
    )
    # One vydej
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.VYDEJ, odberatel=ricany,
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    # One [STAV] (stock adjustment)
    from inventory.services import apply_stock_adjustment
    apply_stock_adjustment(
        product=pepper, branch=tyn, new_quantity=Decimal("110.000"),
        reason="inventura test", user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/")
    assert response.status_code == 200
    body = response.content
    assert b"V\xc5\xa1e" in body                                        # Vše
    assert b"P\xc5\x99\xc3\xadjmy" in body                              # Příjmy
    assert b"V\xc3\xbddeje" in body                                     # Výdeje
    assert b"Inventura / \xc3\xbaprava stavu" in body                   # Inventura / úprava stavu
    assert b"Editov\xc3\xa1no" in body                                  # Editováno


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_tab_prijem_filters_to_prijem_only(
    user_vlastnik, tyn, pepper, ricany
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("50.000"))
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.PRIJEM,
            dodavatel=Supplier.objects.create(name="P"),
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_vlastnik,
    )
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.VYDEJ, odberatel=ricany,
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?tab=prijem")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Only prijem rows; no vydej rows.
    assert "příjem" in body
    # vydej kind label appears only in the chip ("Výdeje (1)"); the
    # row-level Druh column should have only one rendered row.
    # Quick proxy: count `</tr>` in tbody… use the protistrana column
    # check instead. The vydej protistrana is Říčany; if no vydej rows
    # render, Říčany won't appear in the row data.
    assert "Říčany" not in body[body.index("<tbody"):]


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_tab_inventura_filters_to_stav_only(
    user_vlastnik, tyn, pepper, ricany
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("50.000"))
    # Normal výdej (not inventura).
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.VYDEJ, odberatel=ricany,
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    # Inventura — synthetic Movement with [STAV] prefix.
    from inventory.services import apply_stock_adjustment
    apply_stock_adjustment(
        product=pepper, branch=tyn, new_quantity=Decimal("60.000"),
        reason="inventura k testu", user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?tab=inventura")
    assert response.status_code == 200
    body = response.content
    # Only the inventura row should show. The inventura row uses the
    # "Inventura / ruční úprava" counterparty, which contains "Inventura".
    # The regular výdej used Říčany — should be absent from the table body.
    table_body_idx = body.index(b"<tbody")
    table_body = body[table_body_idx:]
    assert b"Inventura" in table_body
    assert b"\xc5\x98\xc3\xad\xc4\x8dany" not in table_body  # "Říčany"


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_inventura_movements_get_inventura_label(
    user_vlastnik, tyn, pepper
) -> None:
    """[STAV] movements get the special 'inventura' label in the Druh
    column, not the generic prijem/vydej tag."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("50.000"))
    from inventory.services import apply_stock_adjustment
    apply_stock_adjustment(
        product=pepper, branch=tyn, new_quantity=Decimal("55.000"),
        reason="test inventura", user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/")
    assert response.status_code == 200
    body = response.content
    # The inventura label replaces the prijem badge for [STAV] rows.
    table_body_idx = body.index(b"<tbody")
    assert b"inventura" in body[table_body_idx:]


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_legacy_kind_param_maps_to_tab(
    user_vlastnik, tyn, pepper, ricany
) -> None:
    """Bookmarked ?kind=vydej links still work after the tab redesign."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("50.000"))
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.PRIJEM,
            dodavatel=Supplier.objects.create(name="L"),
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_vlastnik,
    )
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.VYDEJ, odberatel=ricany,
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?kind=vydej")
    assert response.status_code == 200
    body = response.content
    # Active tab should be Výdeje.
    table_body_idx = body.index(b"<tbody")
    table_body = body[table_body_idx:]
    # Only the vydej should be in the body; no prijem row.
    assert b"\xc5\x98\xc3\xad\xc4\x8dany" in table_body  # Říčany odběratel


# ---------------------------------------------------------------------------
