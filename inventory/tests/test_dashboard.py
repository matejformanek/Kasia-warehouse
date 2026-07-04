from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    DodaciListEmailLog,
    Movement,
    MovementLine,
    Stock,
)
from inventory.services import (
    edit_movement,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
    _seed_vydej,
)

# Pass 3c — dashboard (screen 02)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_clean_morning(user_tyn) -> None:
    """First-ever state: branch panels exist with placeholders;
    K vyřešení says nothing to worry about today."""
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "TYN" in body and "SEZ" in body
    # Clean state: nothing below threshold, no activity yet.
    assert "Vše nad objednacím bodem" in body
    assert "Zatím žádné pohyby" in body
    assert "Zatím žádné dodací listy" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_shows_branch_stock(user_tyn, tyn, sez, pepper, paprika) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("3.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("1.500"))
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    # TYN total = 11.0 kg with 2 products; SEZ total = 1.5 kg with 1
    # product. Displayed at 1 dp with a Czech comma (per 0061). The Přehled
    # shows per-branch totals + product counts (the full stock list lives on
    # the branch dashboard, not here).
    assert "11,0" in body
    assert "1,5" in body
    assert "2 produktů" in body
    assert "1 produktů" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_lists_recent_dodaky(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    assert "Poslední dodací listy" in body
    assert dl.cislo in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_flags_edited_dodak(user_tyn, tyn, ricany, pepper) -> None:

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    line = mv.lines.get()
    edit_movement(
        movement=mv,
        changes={},
        line_changes=[
            {"op": "update", "line_id": line.pk, "fields": {"quantity_kg": Decimal("3.000")}}
        ],
        reason="oprava hmotnosti",
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    assert "Editovaný" in body  # K vyřešení task badge
    # The edited dodák appears with its v2 marker.
    assert dl.cislo in body
    assert "v2" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_flags_failed_send(user_tyn, tyn, ricany, pepper, monkeypatch) -> None:
    """A dodák whose latest send at current_version FAILED appears in
    the 'Nedoručené e-maily' bucket; once re-sent successfully, it
    drops out."""
    from inventory import services

    # First create the výdej WITH a failing SMTP so the initial send logs FAILED.
    def _fail(self, *args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(services.dodaci_list.EmailMessage, "send", _fail)
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    assert DodaciListEmailLog.objects.filter(
        dodaci_list=dl, status=DodaciListEmailLog.Status.FAILED
    ).exists()

    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    assert "Nedoručený" in body  # K vyřešení task badge
    assert dl.cislo in body
    # to_resolve_count should be ≥ 1
    assert "K vyřešení" in body

    # Now restore normal send and re-send → the latest log at v1 is SENT,
    # the failed bucket should empty.
    monkeypatch.undo()
    pdf = services.render_dodaci_list_pdf(dl)
    services.send_dodaci_list_email(
        dodaci_list=dl,
        trigger_reason="ruční opětovné odeslání",
        pdf_bytes=pdf,
    )
    response2 = client.get("/sklad/")
    body2 = response2.content.decode("utf-8")
    assert "Nedoručený" not in body2


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_requires_login() -> None:
    response = Client().get("/sklad/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


# ---------------------------------------------------------------------------
# Pass 3d — role gating + branch dashboard (screen 03)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_is_vlastnik_default_unassigned(user_tyn) -> None:
    # user_tyn has no group → default vlastník per accounts.User.is_vlastnik.
    assert user_tyn.is_vlastnik is True
    assert user_tyn.is_obsluha is False


@pytest.mark.django_db
def test_user_is_obsluha_when_in_group(user_obsluha_tyn) -> None:
    assert user_obsluha_tyn.is_obsluha is True
    assert user_obsluha_tyn.is_vlastnik is False


@pytest.mark.django_db
def test_user_superuser_is_vlastnik(admin_user) -> None:
    assert admin_user.is_vlastnik is True
    assert admin_user.is_obsluha is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_routes_obsluha_to_branch_dashboard(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/pobocka/TYN/"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_owner_lands_on_owner_dashboard(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Owner dashboard markers (KPI strip always renders).
    assert "Vyprodáno" in body
    assert "K vyřešení" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_renders_for_obsluha(user_obsluha_tyn, tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "TYN" in body and tyn.name in body
    assert "Stav skladu" in body
    assert "Nedávné pohyby" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_lists_stock_for_branch(
    user_obsluha_tyn, tyn, sez, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("3.000"))
    # SEZ stock that must NOT appear on TYN's dashboard.
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("99.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs in body
    # 99.000 from SEZ should NOT appear (TYN only has 8 and 3).
    assert "99,000" not in body and "99.000" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_search_filters_stock(
    user_obsluha_tyn, tyn, pepper, paprika
) -> None:
    # Per 0063 the `q` text filter moved client-side: the server renders ALL
    # stock rows regardless of `q`, each carrying the data-filter-text the JS
    # folds/matches. (Folding/typo matching itself is verified in-browser.)
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/pobocka/TYN/?q={pepper.name_cs[:4]}")
    body = response.content.decode("utf-8")
    # Both rows render server-side now — the browser narrows to the query.
    assert pepper.name_cs in body
    assert paprika.name_cs in body
    # Each row carries the searchable text the client filter consumes.
    assert f'data-filter-text="{pepper.name_cs}"' in body
    assert f'data-filter-text="{paprika.name_cs}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_obsluha_forbidden_on_other_branch(
    user_obsluha_tyn, sez
) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/SEZ/")
    assert response.status_code == 403
    assert "Nemáte oprávnění" in response.content.decode("utf-8")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_vlastnik_can_view_either_branch(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    for code in ("TYN", "SEZ"):
        response = client.get(f"/sklad/pobocka/{code}/")
        assert response.status_code == 200, code
        assert code in response.content.decode("utf-8")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_404_for_unknown_code(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pobocka/ZZZ/")
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_requires_login() -> None:
    response = Client().get("/sklad/pobocka/TYN/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_recent_movements(
    user_obsluha_tyn, tyn, ricany, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.500"))],
        user=user_obsluha_tyn,
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    body = response.content.decode("utf-8")
    assert "Říčany" in body
    assert "výdej" in body


# ---------------------------------------------------------------------------
