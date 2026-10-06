"""Decision 0104 — own-branch guards for obsluha (IDOR) + stock visibility.

Every guarded view: an obsluha on SEZ reaching a TYN object gets 403, and the
own-branch path keeps working.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from inventory.models import Movement, Stock
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
    _make_planned_prijem,
    _mk_mixture_with_recipe,
    _seed_vydej,
)


def _client(user) -> Client:
    c = Client()
    c.force_login(user)
    return c


def _edit_payload(mv, branch, ricany, pepper, qty="3.000") -> dict:
    line = mv.lines.get()
    return {
        "reason": "oprava hmotnosti",
        "branch": branch.pk,
        "odberatel": ricany.pk,
        "note": "",
        "lines-TOTAL_FORMS": "1",
        "lines-INITIAL_FORMS": "1",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-line_id": str(line.pk),
        "lines-0-product": str(pepper.pk),
        "lines-0-quantity_kg": qty,
        "lines-0-sarze": "",
        "lines-0-expiry": "",
        "lines-0-note": "",
    }


def _planned(tyn, pepper, user):
    return _make_planned_prijem(
        branch=tyn,
        product=pepper,
        qty=Decimal("4.000"),
        eta=date.today() + timedelta(days=3),
        user=user,
    )


# --- movement_edit -----------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_other_branch_obsluha_403(
    user_vlastnik, user_obsluha_sez, tyn, ricany, pepper
) -> None:
    mv, _dl = _seed_vydej(user_vlastnik, tyn, ricany, pepper)
    c = _client(user_obsluha_sez)
    assert c.get(reverse("inventory:movement_edit", args=[mv.pk])).status_code == 403
    response = c.post(
        reverse("inventory:movement_edit", args=[mv.pk]),
        _edit_payload(mv, tyn, ricany, pepper),
    )
    assert response.status_code == 403
    assert mv.lines.get().quantity_kg == Decimal("2.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_own_branch_obsluha_post_succeeds_branch_locked(
    user_obsluha_tyn, tyn, sez, ricany, pepper
) -> None:
    """A5 pin: the disabled branch field keeps its value from ``initial`` —
    obsluha can still save an edit, and a posted foreign branch is ignored."""
    mv, _dl = _seed_vydej(user_obsluha_tyn, tyn, ricany, pepper)
    c = _client(user_obsluha_tyn)
    get = c.get(reverse("inventory:movement_edit", args=[mv.pk]))
    assert get.status_code == 200
    assert get.context["form"].fields["branch"].disabled is True
    response = c.post(
        reverse("inventory:movement_edit", args=[mv.pk]),
        _edit_payload(mv, sez, ricany, pepper),  # tries to move it to SEZ
    )
    assert response.status_code == 302, response.content[:500]
    mv.refresh_from_db()
    assert mv.branch_id == tyn.pk
    assert mv.lines.get().quantity_kg == Decimal("3.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_vlastnik_branch_field_editable(
    user_vlastnik, tyn, ricany, pepper
) -> None:
    mv, _dl = _seed_vydej(user_vlastnik, tyn, ricany, pepper)
    response = _client(user_vlastnik).get(
        reverse("inventory:movement_edit", args=[mv.pk])
    )
    assert response.status_code == 200
    assert response.context["form"].fields["branch"].disabled is False


# --- movement_saved ----------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_saved_other_branch_obsluha_403(
    user_vlastnik, user_obsluha_sez, user_obsluha_tyn, tyn, ricany, pepper
) -> None:
    mv, _dl = _seed_vydej(user_vlastnik, tyn, ricany, pepper)
    url = reverse("inventory:movement_saved", args=[mv.pk])
    assert _client(user_obsluha_sez).get(url).status_code == 403
    assert _client(user_obsluha_tyn).get(url).status_code == 200
    assert _client(user_vlastnik).get(url).status_code == 200


# --- prijem_confirm / prijem_plan_cancel --------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_confirm_other_branch_obsluha_403(
    user_vlastnik, user_obsluha_sez, tyn, pepper
) -> None:
    mv = _planned(tyn, pepper, user_vlastnik)
    c = _client(user_obsluha_sez)
    url = reverse("inventory:prijem_confirm", args=[mv.pk])
    assert c.get(url).status_code == 403
    line = mv.lines.get()
    response = c.post(url, {f"qty_{line.pk}": "4", "as_of": date.today().isoformat()})
    assert response.status_code == 403
    mv.refresh_from_db()
    assert mv.status == Movement.Status.PLANNED
    assert not Stock.objects.filter(branch=tyn, product=pepper, quantity__gt=0).exists()


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_confirm_own_branch_obsluha_ok(user_obsluha_tyn, tyn, pepper) -> None:
    mv = _planned(tyn, pepper, user_obsluha_tyn)
    response = _client(user_obsluha_tyn).get(
        reverse("inventory:prijem_confirm", args=[mv.pk])
    )
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_plan_cancel_other_branch_obsluha_403(
    user_vlastnik, user_obsluha_sez, user_obsluha_tyn, tyn, pepper
) -> None:
    mv = _planned(tyn, pepper, user_vlastnik)
    url = reverse("inventory:prijem_plan_cancel", args=[mv.pk])
    assert _client(user_obsluha_sez).post(url).status_code == 403
    assert Movement.objects.filter(pk=mv.pk).exists()
    # Own branch still cancels.
    assert _client(user_obsluha_tyn).post(url).status_code == 302
    assert not Movement.objects.filter(pk=mv.pk).exists()


# --- obsluha without a branch is denied everything branch-owned --------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branchless_obsluha_denied(user_vlastnik, tyn, ricany, pepper) -> None:
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    u = get_user_model().objects.create_user(email="nob@example.cz", password="x" * 12)
    u.groups.add(Group.objects.get_or_create(name="obsluha")[0])
    mv, _dl = _seed_vydej(user_vlastnik, tyn, ricany, pepper)
    c = _client(u)
    assert c.get(reverse("inventory:movement_edit", args=[mv.pk])).status_code == 403
    assert c.get(reverse("inventory:movement_saved", args=[mv.pk])).status_code == 403


# --- own-branch stock visibility ---------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_preview_other_branch_obsluha_403(
    user_obsluha_sez, user_obsluha_tyn, tyn, pepper
) -> None:
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    Stock.objects.update_or_create(
        product=pepper, branch=tyn, defaults={"quantity": Decimal("7.000")}
    )
    url = reverse("inventory:mixing_preview_partial")
    q = {"branch": tyn.pk, "mixture": mixture.pk, "target_qty": "5"}
    assert _client(user_obsluha_sez).get(url, q).status_code == 403
    assert _client(user_obsluha_tyn).get(url, q).status_code == 200


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_stock_map_scoped_for_obsluha(
    user_obsluha_tyn, user_vlastnik, tyn, sez, pepper
) -> None:
    Stock.objects.update_or_create(
        product=pepper, branch=tyn, defaults={"quantity": Decimal("3.000")}
    )
    Stock.objects.update_or_create(
        product=pepper, branch=sez, defaults={"quantity": Decimal("9.000")}
    )
    url = reverse("inventory:vydej_create")
    obsluha_map = _client(user_obsluha_tyn).get(url).context["stock_map"]
    assert set(obsluha_map) == {str(tyn.pk)}
    owner_map = _client(user_vlastnik).get(url).context["stock_map"]
    assert {str(tyn.pk), str(sez.pk)} <= set(owner_map)


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_edit_carry_rows_scoped_for_obsluha(
    user_obsluha_tyn, user_vlastnik, tyn, sez, pepper
) -> None:
    url = reverse("inventory:product_edit", args=[pepper.pk])
    rows = _client(user_obsluha_tyn).get(url).context["carry_rows"]
    assert [r["branch"].pk for r in rows] == [tyn.pk]
    owner_rows = _client(user_vlastnik).get(url).context["carry_rows"]
    assert {r["branch"].pk for r in owner_rows} >= {tyn.pk, sez.pk}


# --- planned-transfer detail doesn't link obsluha into a 403 -----------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_planned_transfer_detail_links_only_own_leg_for_obsluha(
    user_vlastnik, user_obsluha_sez, tyn, sez, pepper
) -> None:
    """Převody stay unscoped (0104), but the detail page must not link a SEZ
    obsluha into the TYN leg's movement_edit (which now 403s)."""
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
    url = reverse("inventory:planned_transfer_detail", args=[transfer.pk])
    html = _client(user_obsluha_sez).get(url).content.decode()
    assert reverse("inventory:movement_edit", args=[prijem.pk]) in html
    assert reverse("inventory:movement_edit", args=[vydej.pk]) not in html
    owner_html = _client(user_vlastnik).get(url).content.decode()
    assert reverse("inventory:movement_edit", args=[vydej.pk]) in owner_html


# --- XLS importer caps ---------------------------------------------------------


def test_xlsx_zip_bomb_rejected() -> None:
    import io
    import zipfile

    from inventory.services.recipe_import import (
        _XLSX_MAX_UNCOMPRESSED_BYTES,
        _parse_xls_rows,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/bomb.xml", b"\0" * (_XLSX_MAX_UNCOMPRESSED_BYTES + 1))
    assert len(buf.getvalue()) < 2_500_000  # passes the upload-size cap
    buf.seek(0)
    with pytest.raises(ValueError, match="příliš velký"):
        _parse_xls_rows(buf, "bomb.xlsx")


def test_xlsx_not_a_zip_rejected_cleanly() -> None:
    import io

    from inventory.services.recipe_import import _parse_xls_rows

    with pytest.raises(ValueError):
        _parse_xls_rows(io.BytesIO(b"not a zip"), "x.xlsx")


def test_xlsx_rows_and_cols_capped() -> None:
    import io

    from openpyxl import Workbook

    from inventory.services.recipe_import import _MAX_COLS, _MAX_ROWS, _parse_xls_rows

    wb = Workbook()
    ws = wb.active
    for r in range(_MAX_ROWS + 50):
        ws.append([f"r{r}"] * (_MAX_COLS + 10))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    rows = _parse_xls_rows(buf, "big.xlsx")
    assert len(rows) == _MAX_ROWS
    assert max(len(r) for r in rows) == _MAX_COLS
