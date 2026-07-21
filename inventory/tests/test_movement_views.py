import json
import re
from decimal import Decimal

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from inventory.models import (
    DodaciList,
    EmailLog,
    Movement,
    MovementAudit,
    Stock,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
    _seed_vydej,
)

# Pass 3a — HTMX views (auth, příjem, výdej, partials)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_anonymous_home_redirects_to_login() -> None:
    response = Client().get("/sklad/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_healthz_is_public() -> None:
    # Healthz is decorated with @login_not_required.
    response = Client().get("/healthz")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_login_renders_czech() -> None:
    response = Client().get("/sklad/prihlaseni/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Přihlášení" in body
    assert "E-mail" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_login_success_redirects_home(user_tyn) -> None:
    user_tyn.set_password("zkouska123")
    user_tyn.save()
    client = Client()
    response = client.post(
        "/sklad/prihlaseni/",
        {"username": user_tyn.email, "password": "zkouska123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_loads_for_authenticated_user(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Nový příjem" in body
    assert "Nový výdej" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_get_renders(user_tyn, supplier) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/prijem/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Nový příjem" in body
    assert supplier.name in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_post_creates_movement_and_redirects(
    user_tyn, tyn, supplier, pepper
) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/prijem/novy/",
        {
            "branch": tyn.pk,
            "dodavatel": supplier.pk,
            "date_issued": "2026-06-12",
            "note": "test",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "3.250",
        },
    )
    assert response.status_code == 302, response.content[:500]
    assert response.headers["Location"].startswith("/sklad/pohyby/")
    mv = Movement.objects.get()
    assert mv.kind == Movement.Kind.PRIJEM
    assert mv.lines.count() == 1
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("3.250")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_post_empty_lines_shows_error(user_tyn, tyn, supplier) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/prijem/novy/",
        {
            "branch": tyn.pk,
            "dodavatel": supplier.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 200
    assert Movement.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_post_creates_dodaci_list_and_redirects(
    user_tyn, tyn, ricany, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "2.000",
        },
    )
    assert response.status_code == 302, response.content[:500]
    mv = Movement.objects.get()
    assert mv.kind == Movement.Kind.VYDEJ
    dl = DodaciList.objects.get(movement=mv)
    assert dl.cislo == "TYN-2026-0001"
    saved = client.get(f"/sklad/pohyby/{mv.pk}/")
    assert saved.status_code == 200
    assert b"TYN-2026-0001" in saved.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_post_overdraw_keeps_form(user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "5.000",
        },
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Per decision 0042 — overdraw surfaces as the structured warning
    # card, not the old "pod nulu" service error.
    assert "Nedostatek na sklad" in body
    assert Movement.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_partial(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/_partials/line-row/?index=2")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="lines-2-product"' in body
    assert 'name="lines-2-quantity_kg"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_qty_min_matches_step(user_tyn) -> None:
    # Round numbers (10000) must be accepted — min must align with step="0.1",
    # not the stale min="0.001" which made every round number a stepMismatch.
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/vydej/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'min="0.1"' in body
    assert 'min="0.001"' not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_post_accepts_round_number(user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("20000.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "10000",
        },
    )
    assert response.status_code == 302, response.content[:500]
    assert Movement.objects.count() == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_form_embeds_stock_map_and_no_htmx(user_tyn, tyn, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/vydej/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # The JSON stock map is embedded and carries the seeded on-hand.
    match = re.search(
        r'<script id="vydej-stock-map" type="application/json">(.*?)</script>',
        body,
        re.DOTALL,
    )
    assert match, "vydej-stock-map json_script block not found"
    data = json.loads(match.group(1))
    assert data[str(tyn.pk)][str(pepper.pk)] == "3.000"
    # The JS render target is present.
    assert 'id="stock-warn-cell-0"' in body
    # No htmx live-check machinery remains (the add-line button still uses
    # htmx to append rows — only the stock-warn round-trip is gone).
    assert "stock_warn_partial" not in body
    assert "/_partials/stock-warn/" not in body
    assert 'hx-target="#stock-warn-cell' not in body
    assert "stockWarnVals" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_form_inventura_jump_for_vlastnik(user_tyn, tyn) -> None:
    # user_tyn has no role group → is_vlastnik. The over-stock block offers a
    # jump to inventura pre-filtered to the flagged products (per 0060).
    client = Client()
    client.force_login(user_tyn)
    body = client.get("/sklad/vydej/novy/").content.decode("utf-8")
    match = re.search(
        r'<script id="vydej-inventura-urls" type="application/json">(.*?)</script>',
        body,
        re.DOTALL,
    )
    assert match, "vydej-inventura-urls json_script block not found"
    urls = json.loads(match.group(1))
    assert urls[str(tyn.pk)] == reverse("inventory:inventura_edit", args=[tyn.code])
    assert 'id="stock-block-inventura"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_form_inventura_jump_absent_for_obsluha(user_obsluha_tyn) -> None:
    # Obsluha may not open inventura — no jump blob, no link.
    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/vydej/novy/").content.decode("utf-8")
    assert 'id="vydej-inventura-urls"' not in body
    assert 'id="stock-block-inventura"' not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_partial_warn_flag_wires_stock_warn(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    warned = client.get("/sklad/_partials/line-row/?index=1&warn=1")
    assert warned.status_code == 200
    body = warned.content.decode("utf-8")
    # ?warn=1 → the JS render-target cell, no htmx.
    assert "stock-warn-cell" in body
    assert 'id="stock-warn-cell-1"' in body
    assert "hx-get" not in body
    assert "/_partials/stock-warn/" not in body
    # Without ?warn=1 (e.g. příjem add-row), no stock-warn hooks at all.
    plain = client.get("/sklad/_partials/line-row/?index=1")
    assert plain.status_code == 200
    plain_body = plain.content.decode("utf-8")
    assert "stock-warn-cell" not in plain_body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_partial_routes_require_login() -> None:
    response = Client().get("/sklad/_partials/line-row/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


# ---------------------------------------------------------------------------
# Pass 3b — dodák list/detail/PDF/resend + movement edit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_index_empty(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/dodaky/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Dodací listy" in body
    assert "Nalezeno: 0" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_index_lists_dodak(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/dodaky/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert dl.cislo in body
    assert "Nalezeno: 1" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_index_branch_filter(
    user_tyn, tyn, sez, ricany, pepper
) -> None:
    mv, _dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    # Hit the filter via querystring (SEZ has no dodáky → list should be empty).
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/?branch={sez.pk}")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Nalezeno: 0" in body
    # Filtering for TYN keeps the row.
    response = client.get(f"/sklad/dodaky/?branch={tyn.pk}")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_detail_renders(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/{dl.cislo}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert dl.cislo in body
    assert "Stáhnout PDF" in body
    assert "Znovu odeslat" in body
    assert "Otevřít výdej" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_pdf_download(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/{dl.cislo}/pdf/")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert f'filename="{dl.cislo}.pdf"' in response.headers["Content-Disposition"]
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 1000


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_resend_writes_log(user_tyn, tyn, ricany, pepper) -> None:
    from django.core import mail

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    outbox_before = len(mail.outbox)
    logs_before = EmailLog.objects.filter(dodaci_list=dl).count()

    client = Client()
    client.force_login(user_tyn)
    response = client.post(f"/sklad/dodaky/{dl.cislo}/znovu-odeslat/")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/sklad/dodaky/{dl.cislo}/"

    assert len(mail.outbox) == outbox_before + 1
    log = (
        EmailLog.objects.filter(dodaci_list=dl)
        .order_by("-created_at", "-id")
        .first()
    )
    assert log is not None
    assert log.trigger_reason == "ruční opětovné odeslání"
    assert (
        EmailLog.objects.filter(dodaci_list=dl).count() == logs_before + 1
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_routes_require_login() -> None:
    for path in (
        "/sklad/dodaky/",
        "/sklad/dodaky/anything/",
        "/sklad/dodaky/anything/pdf/",
    ):
        response = Client().get(path)
        assert response.status_code == 302
        assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_detail_404_for_unknown_cislo(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/dodaky/TYN-2099-9999/")
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_get_renders(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/pohyby/{mv.pk}/upravit/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Úprava" in body
    assert "Důvod úpravy" in body
    # Linked dodák warning visible.
    assert dl.cislo in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_post_bumps_version_and_audits(
    user_tyn, tyn, ricany, pepper
) -> None:
    from django.core import mail

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    line = mv.lines.get()
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        f"/sklad/pohyby/{mv.pk}/upravit/",
        {
            "reason": "oprava hmotnosti",
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-11",
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "1",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-line_id": str(line.pk),
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "3.000",
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 302, response.content[:500]

    dl.refresh_from_db()
    assert dl.current_version == 2
    # An OPRAVA send + log row landed via the edit hook.
    assert any("[OPRAVA]" in m.subject for m in mail.outbox)
    log = EmailLog.objects.filter(dodaci_list=dl, dodaci_version=2).get()
    assert log.trigger_reason == "oprava: oprava hmotnosti"
    # And the audit row exists.
    assert MovementAudit.objects.filter(movement=mv).count() >= 1


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_no_changes_is_noop(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    line = mv.lines.get()
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        f"/sklad/pohyby/{mv.pk}/upravit/",
        {
            "reason": "kontrola",
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-11",
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "1",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-line_id": str(line.pk),
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": str(line.quantity_kg),
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 302
    dl.refresh_from_db()
    assert dl.current_version == 1
    assert MovementAudit.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_overdraw_keeps_form(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper, qty="2.000", stock="5.000")
    line = mv.lines.get()
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        f"/sklad/pohyby/{mv.pk}/upravit/",
        {
            "reason": "pokus o předčerpání",
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-11",
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "1",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-line_id": str(line.pk),
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "99.000",
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 200, response.content[:300]
    dl.refresh_from_db()
    assert dl.current_version == 1
    assert MovementAudit.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_404_for_unknown_pk(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/pohyby/99999/upravit/")
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_post_now_redirects_to_dodaci_list_detail(
    user_tyn, tyn, ricany, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "1.500",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/dodaky/TYN-2026-0001/"


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Editing a DONE movement can add a new product line (template gap fix): the
# formset already accepts a POSTed row with a blank line_id as an "add" op.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_can_add_new_line(
    user_tyn, tyn, supplier, pepper, paprika
) -> None:
    from datetime import date

    from inventory.models import MovementLine
    from inventory.services import apply_movement

    mv = apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 11),
            dodavatel=supplier,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("4.000"))],
        user=user_tyn,
    )
    existing = mv.lines.get()
    client = Client()
    client.force_login(user_tyn)
    resp = client.post(
        f"/sklad/pohyby/{mv.pk}/upravit/",
        {
            "reason": "přidání položky",
            "branch": tyn.pk,
            "dodavatel": supplier.pk,
            "date_issued": "2026-06-11",
            "note": "",
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "1",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-line_id": str(existing.pk),
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "4.000",
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
            # New line — blank line_id → _line_changes emits an "add" op.
            "lines-1-line_id": "",
            "lines-1-product": str(paprika.pk),
            "lines-1-quantity_kg": "2.000",
            "lines-1-sarze": "",
            "lines-1-expiry": "",
            "lines-1-note": "",
        },
    )
    assert resp.status_code == 302, resp.content[:500]
    assert mv.lines.count() == 2
    assert mv.lines.filter(
        product=paprika, quantity_kg=Decimal("2.000")
    ).exists()
    assert MovementAudit.objects.filter(
        movement=mv, event=MovementAudit.Event.LINE_ADDED
    ).exists()
