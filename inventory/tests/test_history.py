from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    Movement,
    MovementLine,
    Stock,
)
from inventory.services import (
    edit_movement,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
)

# Pass 3e — movement history (screen 10)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_requires_login() -> None:
    response = Client().get("/sklad/pohyby/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_empty(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Historie pohybů" in body
    assert "Zatím žádné pohyby" in body
    assert "Nalezeno: 0" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_lists_movement(user_vlastnik, user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body
    assert pepper.name_cs in body
    assert "Říčany" in body
    assert "TYN-2026-0001" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_obsluha_scoped_to_own_branch(
    user_obsluha_tyn, user_tyn, tyn, sez, ricany, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    _apply(
        movement=Movement(
            branch=sez,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=paprika, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pohyby/")
    body = response.content.decode("utf-8")
    # obsluha-tyn sees only TYN row
    assert "Nalezeno: 1" in body
    assert pepper.name_cs in body
    assert paprika.name_cs not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_kind_filter(user_vlastnik, user_tyn, tyn, ricany, supplier, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 12),
            dodavatel=supplier,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?kind=vydej")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_branch_filter_for_vlastnik(
    user_vlastnik, user_tyn, tyn, sez, ricany, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    for branch, product, qty in (
        (tyn, pepper, "1.000"),
        (sez, paprika, "2.000"),
    ):
        _apply(
            movement=Movement(
                branch=branch,
                kind=Movement.Kind.VYDEJ,
                date_issued=date(2026, 6, 12),
                odberatel=ricany,
            ),
            lines=[MovementLine(product=product, quantity_kg=Decimal(qty))],
            user=user_tyn,
        )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/pohyby/?branch={tyn.pk}")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body
    assert pepper.name_cs in body
    assert paprika.name_cs not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_date_range_filter(user_vlastnik, user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    from inventory.services import apply_movement as _apply

    for d in (date(2026, 6, 5), date(2026, 6, 10), date(2026, 6, 15)):
        _apply(
            movement=Movement(
                branch=tyn,
                kind=Movement.Kind.VYDEJ,
                date_issued=d,
                odberatel=ricany,
            ),
            lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
            user=user_tyn,
        )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?date_from=2026-06-08&date_to=2026-06-12")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_edited_only_filter(
    user_vlastnik, user_tyn, tyn, ricany, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    mv_kept = _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    mv_edited = _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=paprika, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    line = mv_edited.lines.get()
    edit_movement(
        movement=mv_edited,
        changes={},
        line_changes=[
            {"op": "update", "line_id": line.pk, "fields": {"quantity_kg": Decimal("2.000")}}
        ],
        reason="oprava hmotnosti",
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?edited=1")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body
    # The edited movement appears.
    assert paprika.name_cs in body
    # The unedited movement does not.
    assert pepper.name_cs not in body
    assert mv_kept.pk != mv_edited.pk


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_search_filter(user_vlastnik, user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
            note="ahoj poznámka",
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_vlastnik)
    # Per 0063 `q` is filtered client-side now: the server renders the row
    # regardless of `q` (so it no longer zeroes out on a non-matching term),
    # carrying data-filter-text with product + counterparty + note for the
    # browser to fold/match. (Folding/typo matching is verified in-browser.)
    response = client.get("/sklad/pohyby/?q=neco-co-tam-neni")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 0" not in body
    assert "neodpovídají filtrům" not in body
    # The movement row carries the searchable text (product + counterparty + note).
    assert (
        f'data-filter-text="{pepper.name_cs} {ricany.name} ahoj poznámka"' in body
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_obsluha_branch_filter_param_ignored(
    user_obsluha_tyn, sez
) -> None:
    """obsluha passing ?branch=SEZ should still see only their own
    branch (param silently ignored when scope is forced)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/pohyby/?branch={sez.pk}")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # obsluha gets a "pobočka TYN" badge in the header
    # and the branch filter dropdown is NOT rendered.
    assert "pobočka TYN" in body
    assert 'id="id_filter_branch"' not in body


# ---------------------------------------------------------------------------
