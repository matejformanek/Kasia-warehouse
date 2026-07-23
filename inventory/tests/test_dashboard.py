from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    EmailLog,
    Movement,
    MovementLine,
    Product,
    Stock,
)
from inventory.services import (
    edit_movement,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
    _make_planned_prijem,
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


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_owner_dashboard_counts_empty_at_default_threshold(
    user_vlastnik, tyn, pepper
) -> None:
    """Regression for Problem 1 (0093): a pair empty at the default threshold 0
    (`0 < 0 == False`) is now counted in the owner Přehled „Vyprodáno" KPI +
    breakdown + branch panel empty_rows — it was silently dropped before."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200

    assert response.context["kpi_empty"] >= 1
    assert "TYN" in response.context["kpi_empty_breakdown"]
    tyn_panel = next(
        p for p in response.context["branch_panels"] if p["branch"].code == "TYN"
    )
    empty_pks = {r.product.pk for r in tyn_panel["empty_rows"]}
    assert pepper.pk in empty_pks


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_owner_dashboard_empty_with_open_order_counts_as_ordered(
    user_vlastnik, tyn, pepper, supplier
) -> None:
    """Objednáno split preserved (0093): an empty pair with an open PLANNED
    příjem lands in kpi_ordered, not kpi_empty."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    _make_planned_prijem(
        branch=tyn,
        product=pepper,
        qty=Decimal("10.000"),
        eta=date.today(),
        user=user_vlastnik,
        supplier=supplier,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200

    assert response.context["kpi_ordered"] >= 1
    tyn_panel = next(
        p for p in response.context["branch_panels"] if p["branch"].code == "TYN"
    )
    ordered_pks = {r.product.pk for r in tyn_panel["ordered_rows"]}
    empty_pks = {r.product.pk for r in tyn_panel["empty_rows"]}
    assert pepper.pk in ordered_pks
    assert pepper.pk not in empty_pks


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
    from inventory.services import send_first_dodaci

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    # Per 0096: a dodák is "editovaný" only after it was sent (edits before
    # send stay v1). Send first so the edit auto-reissues to v2.
    send_first_dodaci(dl, sent_by=user_tyn)
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
    """A SENT dodák whose latest [OPRAVA] send at current_version FAILED appears
    in the 'Nedoručené e-maily' bucket; once re-sent successfully, it drops out.
    Per 0096 the failed bucket only applies to already-sent dodáky — a
    WAITING+failed-first-send dodák lives in "Čeká na odeslání" instead
    (see test_dashboard_waiting_failed_first_send_not_in_failed)."""
    from inventory import services
    from inventory.services import send_first_dodaci

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    # Send the first e-mail OK → SENT at v1.
    send_first_dodaci(dl, sent_by=user_tyn)

    # An edit now auto-reissues [OPRAVA]; make that send fail → FAILED at v2.
    def _fail(self, *args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(services.email.EmailMessage, "send", _fail)
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
    dl.refresh_from_db()
    assert EmailLog.objects.filter(
        dodaci_list=dl, status=EmailLog.Status.FAILED, dodaci_version=2
    ).exists()

    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    assert "Nedoručený" in body  # K vyřešení task badge
    assert dl.cislo in body
    # to_resolve_count should be ≥ 1
    assert "K vyřešení" in body

    # Now restore normal send and re-send → the latest log at v2 is SENT,
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


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_lists_waiting_dodaky(user_vlastnik, user_tyn, tyn, ricany, pepper) -> None:
    """Per 0096: the owner Přehled shows an all-branch 'Čeká na odeslání'
    section for dodáky created but not yet sent."""
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/").content.decode("utf-8")
    assert "Čeká na odeslání" in body
    assert dl.cislo in body
    # The waiting Odeslat button posts to the send route.
    assert f"/sklad/dodaky/{dl.cislo}/odeslat/" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_waiting_drops_after_send(user_vlastnik, user_tyn, tyn, ricany, pepper) -> None:
    from inventory.services import send_first_dodaci

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    send_first_dodaci(dl, sent_by=user_tyn)
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/").content.decode("utf-8")
    # The waiting Odeslat button for this dodák is gone once it's sent.
    assert f"/sklad/dodaky/{dl.cislo}/odeslat/" not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_waiting_failed_first_send_not_in_failed(
    user_vlastnik, user_tyn, tyn, ricany, pepper, monkeypatch
) -> None:
    """Per 0096: a WAITING dodák whose first send FAILED shows only in 'Čeká na
    odeslání', never in the 'Nedoručený e-mail' bucket."""
    from inventory import services
    from inventory.services import send_first_dodaci

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)

    def _fail(self, *args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(services.email.EmailMessage, "send", _fail)
    send_first_dodaci(dl, sent_by=user_tyn)
    dl.refresh_from_db()
    assert dl.send_state == dl.SendState.WAITING
    assert EmailLog.objects.filter(dodaci_list=dl, status=EmailLog.Status.FAILED).exists()

    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/").content.decode("utf-8")
    assert "Čeká na odeslání" in body
    assert f"/sklad/dodaky/{dl.cislo}/odeslat/" in body
    assert "Nedoručený" not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_lists_waiting_dodaky(
    user_obsluha_tyn, user_tyn, tyn, ricany, pepper
) -> None:
    """Per 0096: the branch dashboard shows its own-branch waiting dodáky."""
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/pobocka/TYN/").content.decode("utf-8")
    assert "Čeká na odeslání" in body
    assert dl.cislo in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_waiting_scoped_to_own_branch(
    user_obsluha_sez, user_tyn, tyn, sez, ricany, pepper
) -> None:
    """An obsluha viewing another branch's dashboard 403s; on their own branch
    they must not see the other branch's waiting dodák."""
    mv, dl_tyn = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_obsluha_sez)
    # Own branch (SEZ) — no waiting dodák there, and TYN's must not leak.
    body = client.get("/sklad/pobocka/SEZ/").content.decode("utf-8")
    assert dl_tyn.cislo not in body
    # Other branch's dashboard is forbidden entirely.
    assert client.get("/sklad/pobocka/TYN/").status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_index_waiting_section_obsluha_scoped(
    user_obsluha_sez, user_tyn, tyn, sez, ricany, pepper, paprika
) -> None:
    """The dodák index 'Čeká na odeslání' section is branch-scoped for obsluha."""
    mv_tyn, dl_tyn = _seed_vydej(user_tyn, tyn, ricany, pepper)
    # A SEZ waiting dodák the obsluha SHOULD see.
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("9.000"))
    from inventory.services import apply_movement

    mv_sez = apply_movement(
        movement=Movement(
            branch=sez,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=paprika, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    from inventory.models import DodaciList

    dl_sez = DodaciList.objects.get(movement=mv_sez)

    client = Client()
    client.force_login(user_obsluha_sez)
    body = client.get("/sklad/dodaky/").content.decode("utf-8")
    assert "Čeká na odeslání" in body
    assert dl_sez.cislo in body
    assert dl_tyn.cislo not in body


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


def _group_html(body: str, group_id: str) -> str:
    """Return the inner HTML of the grouped <section id="cat-group-..."> or ""
    if that group is absent (helper for grouped-branch-dashboard assertions)."""
    marker = f'id="{group_id}"'
    start = body.find(marker)
    if start == -1:
        return ""
    end = body.find("</section>", start)
    return body[start:end]


def _kpi_block(body: str, label: str) -> str:
    """Return the HTML of the KPI card whose `.lbl` is `label` (up to the next
    </div>) — the k-val lives inside it."""
    marker = f">{label}</span>"
    start = body.find(marker)
    if start == -1:
        return ""
    return body[start:body.find("</div>", start)]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_lists_stock_for_branch(
    user_obsluha_tyn, tyn, sez, pepper, paprika
) -> None:
    # Per 0094 only CRITICAL products render on the branch Přehled, so both TYN
    # products are given a threshold that puts them in "Dochází".
    pepper.reorder_threshold_kg = Decimal("10.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
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
    # Both are below their threshold → "Dochází" group. V pořádku is dropped
    # from the branch Přehled entirely (0094).
    assert 'class="cat-body"' in body
    low_html = _group_html(body, "cat-group-low")
    assert pepper.name_cs in low_html
    assert paprika.name_cs in low_html
    assert _group_html(body, "cat-group-ok") == ""


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_groups_by_stock_state(user_obsluha_tyn, tyn) -> None:
    """A low + empty product each lands in its critical group; the ok product is
    NOT rendered (0094 — V pořádku is Katalog-only). The header KPI Dochází /
    Prázdné counts equal the group sizes (0064)."""
    ok = Product.objects.create(
        name_cs="OK zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    low = Product.objects.create(
        name_cs="Dochazi zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    empty = Product.objects.create(
        name_cs="Prazdne zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    Stock.objects.create(product=ok, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=low, branch=tyn, quantity=Decimal("3.000"))
    Stock.objects.create(product=empty, branch=tyn, quantity=Decimal("0.000"))

    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/pobocka/TYN/").content.decode("utf-8")

    assert low.name_cs in _group_html(body, "cat-group-low")
    assert empty.name_cs in _group_html(body, "cat-group-empty")
    # Per 0094 V pořádku is dropped from the branch Přehled: the ok product does
    # not render here at all (it stays reachable via Katalog + Inventura).
    assert _group_html(body, "cat-group-ok") == ""
    assert ok.name_cs not in body
    assert 'data-filter-bucket="ok"' not in body
    # Header KPI counts match the group sub-heads exactly (1 low, 1 empty).
    assert 'data-kpi-live="low">1</span>' in _kpi_block(body, "Dochází")
    assert 'data-kpi-live="empty">1</span>' in _kpi_block(body, "Prázdné")
    # Critical buckets still recompute live from visible rows (0084).
    assert 'data-filter-bucket="empty"' in body
    assert 'data-filter-bucket="low"' in body
    # Per 0094 these two KPIs are now STATIC (no data-kpi-live) — a live
    # recompute would under-count without V pořádku rendered; empty/low stay live.
    assert 'data-kpi-live="products-stocked"' not in body
    assert 'data-kpi-live="total-kg"' not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_all_healthy_shows_positive_empty_state(
    user_obsluha_tyn, tyn
) -> None:
    """Per 0094: when nothing is critical, the branch Přehled shows a positive
    empty-state (not the healthy tail), and the ok product is absent from the
    Stav-skladu card."""
    ok = Product.objects.create(
        name_cs="OK zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    Stock.objects.create(product=ok, branch=tyn, quantity=Decimal("10.000"))

    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/pobocka/TYN/").content.decode("utf-8")

    assert "nic nedochází" in body
    assert ok.name_cs not in body
    assert _group_html(body, "cat-group-empty") == ""
    assert _group_html(body, "cat-group-low") == ""
    assert _group_html(body, "cat-group-ok") == ""


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_has_inventura_button(user_obsluha_tyn, tyn) -> None:
    # Per 0073: the Přehled links obsluha to their own-branch inventura.
    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/pobocka/TYN/").content.decode("utf-8")
    assert "/katalog/inventura/TYN/" in body
    assert ">Inventura<" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_unstocked_product_is_empty(
    user_obsluha_tyn, tyn, pepper
) -> None:
    """An active product with NO Stock row at the branch surfaces in the
    "Prázdné" group (the intended behavioral shift — all active products show)."""
    # pepper exists but has no Stock row at TYN.
    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/pobocka/TYN/").content.decode("utf-8")
    assert pepper.name_cs in _group_html(body, "cat-group-empty")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_excludes_untracked_product(
    user_obsluha_tyn, tyn, pepper, voda
) -> None:
    """Per 0088: an untracked product never shows in the obsluha Přehled
    "Stav skladu" card (not even as Prázdné)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/pobocka/TYN/").content.decode("utf-8")
    assert pepper.name_cs in body
    assert voda.name_cs not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_search_filters_stock(
    user_obsluha_tyn, tyn, pepper, paprika
) -> None:
    # Per 0063 the `q` text filter moved client-side: the server renders ALL
    # (critical) stock rows regardless of `q`, each carrying the data-filter-text
    # the JS folds/matches. (Folding/typo matching itself is verified in-browser.)
    # Per 0094 only critical rows render, so both products are given a threshold
    # that puts them in "Dochází".
    pepper.reorder_threshold_kg = Decimal("10.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
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
