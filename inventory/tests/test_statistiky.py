"""Statistiky — vlastník analytics screen + the analytics service (0107)."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from inventory.models import Movement, MovementLine, Stock
from inventory.services import analytics, counterparties
from inventory.services.mixing import record_completed_mixing_job
from inventory.tests._support import _VIEW_TEST_OVERRIDES, _mk_mixture_with_recipe

URL = "inventory:statistiky_index"
D = Decimal


def _mv(
    branch,
    user,
    kind,
    day,
    qty,
    product,
    *,
    odberatel=None,
    dodavatel=None,
    status=Movement.Status.DONE,
):
    mv = Movement.objects.create(
        branch=branch,
        kind=kind,
        status=status,
        date_issued=day,
        odberatel=odberatel,
        dodavatel=dodavatel,
        created_by=user,
    )
    MovementLine.objects.create(movement=mv, product=product, quantity_kg=D(qty))
    return mv


def _flt(start, end, **kw):
    return analytics.Filters(start, end, kw.pop("granularity", "mesic"), **kw)


JUN = _flt(date(2026, 6, 1), date(2026, 6, 30))


def _total(qs):
    return sum((line.quantity_kg for line in qs), D("0"))


# --- access --------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_obsluha_forbidden(user_obsluha_tyn):
    c = Client()
    c.force_login(user_obsluha_tyn)
    assert c.get(reverse(URL)).status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_anonymous_redirected_to_login():
    resp = Client().get(reverse(URL))
    assert resp.status_code == 302
    assert "prihlaseni" in resp["Location"]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
@pytest.mark.parametrize("section", [s for s, _ in analytics.SECTIONS])
def test_vlastnik_sees_every_section(user_vlastnik, tyn, ricany, pepper, section):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 3), "4", pepper, odberatel=ricany)
    c = Client()
    c.force_login(user_vlastnik)
    resp = c.get(
        reverse(URL),
        {"sekce": section, "rozsah": "vlastni", "od": "2026-06-01", "do": "2026-06-30"},
    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "{#" not in body and "#}" not in body and "{%" not in body
    assert "Statistiky" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_empty_state_and_nav_link(user_vlastnik):
    c = Client()
    c.force_login(user_vlastnik)
    body = c.get(reverse(URL), {"sekce": "vydeje"}).content.decode()
    assert "Za zvolené období nejsou data." in body
    assert reverse(URL) in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_garbage_params_fall_back(user_vlastnik):
    c = Client()
    c.force_login(user_vlastnik)
    resp = c.get(
        reverse(URL),
        {
            "sekce": "x",
            "rozsah": "y",
            "gran": "z",
            "od": "bad",
            "pobocka": "999",
            "produkt": ["abc", "999"],
        },
    )
    assert resp.status_code == 200


# --- flow definitions ----------------------------------------------------


@pytest.mark.django_db
def test_micharna_vs_sales_split(tyn, user_vlastnik, ricany, pepper):
    micharna = counterparties.customer("micharna")
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 5), "10", pepper, odberatel=micharna)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 6), "3", pepper, odberatel=ricany)
    _mv(
        tyn,
        user_vlastnik,
        "vydej",
        date(2026, 6, 7),
        "99",
        pepper,
        odberatel=counterparties.customer("adjustment"),
    )
    _mv(
        tyn,
        user_vlastnik,
        "vydej",
        date(2026, 6, 8),
        "98",
        pepper,
        odberatel=counterparties.customer("transfer"),
    )
    assert _total(analytics.consumption_lines(JUN)) == D("10")
    assert _total(analytics.sales_lines(JUN)) == D("3")


@pytest.mark.django_db
def test_receipts_exclude_internal_legs(tyn, user_vlastnik, pepper, supplier):
    _mv(tyn, user_vlastnik, "prijem", date(2026, 6, 5), "7", pepper, dodavatel=supplier)
    _mv(
        tyn,
        user_vlastnik,
        "prijem",
        date(2026, 6, 5),
        "2",
        pepper,
        dodavatel=counterparties.supplier("unknown_supplier"),
    )
    _mv(
        tyn,
        user_vlastnik,
        "prijem",
        date(2026, 6, 5),
        "50",
        pepper,
        dodavatel=counterparties.supplier("micharna"),
    )
    _mv(
        tyn,
        user_vlastnik,
        "prijem",
        date(2026, 6, 5),
        "51",
        pepper,
        dodavatel=counterparties.supplier("adjustment"),
    )
    _mv(
        tyn,
        user_vlastnik,
        "prijem",
        date(2026, 6, 5),
        "52",
        pepper,
        dodavatel=counterparties.supplier("transfer"),
    )
    assert _total(analytics.receipt_lines(JUN)) == D("9")


@pytest.mark.django_db
def test_planned_movements_excluded(tyn, user_vlastnik, pepper, supplier):
    _mv(
        tyn,
        user_vlastnik,
        "prijem",
        date(2026, 6, 5),
        "7",
        pepper,
        dodavatel=supplier,
        status=Movement.Status.PLANNED,
    )
    assert _total(analytics.receipt_lines(JUN)) == D("0")


@pytest.mark.django_db
def test_unlimited_products_excluded(tyn, user_vlastnik, ricany, pepper, voda, hotovy_vyrobek):
    for p in (pepper, voda, hotovy_vyrobek):
        _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 6), "5", p, odberatel=ricany)
    assert _total(analytics.sales_lines(JUN)) == D("5")


@pytest.mark.django_db
def test_out_of_range_dates_excluded(tyn, user_vlastnik, ricany, pepper):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 5, 31), "5", pepper, odberatel=ricany)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 30), "1", pepper, odberatel=ricany)
    assert _total(analytics.sales_lines(JUN)) == D("1")


# --- mixing jobs ---------------------------------------------------------


def _done_job(tyn, user, pepper, produced="4", on=date(2026, 6, 10)):
    Stock.objects.update_or_create(product=pepper, branch=tyn, defaults={"quantity": D("100")})
    mixture = _mk_mixture_with_recipe("Směs", [(pepper, "1.0")])
    return record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=D(produced),
        actual_produced_qty=D(produced),
        user=user,
        as_of=on,
    )


@pytest.mark.django_db
def test_done_job_counts_and_cancelled_does_not(tyn, user_vlastnik, pepper):
    from inventory.services import cancel_mixing_job, start_mixing_job

    job = _done_job(tyn, user_vlastnik, pepper, "4")
    assert _total(analytics.consumption_lines(JUN)) == D("4")
    assert analytics.done_jobs(JUN).count() == 1
    assert sum(j.actual_produced_qty for j in analytics.done_jobs(JUN)) == D("4")
    # produced směs is a prijem from the internal míchárna, not a příjem
    assert _total(analytics.receipt_lines(JUN)) == D("0")

    running = start_mixing_job(
        branch=tyn,
        mixture=job.mixture,
        target_qty=D("2"),
        user=user_vlastnik,
        as_of=date(2026, 6, 11),
    )
    cancel_mixing_job(mixing_job=running, reason="chyba", user=user_vlastnik)
    assert analytics.done_jobs(JUN).count() == 1
    assert _total(analytics.consumption_lines(JUN)) == D("4")


@pytest.mark.django_db
def test_deleted_job_not_counted(tyn, user_vlastnik, pepper):
    from inventory.services import delete_completed_mixing_job

    job = _done_job(tyn, user_vlastnik, pepper, "4")
    delete_completed_mixing_job(mixing_job=job, user=user_vlastnik)
    assert analytics.done_jobs(JUN).count() == 0
    assert _total(analytics.consumption_lines(JUN)) == D("0")


# --- bucketing / filters -------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("gran", "labels", "values"),
    [
        ("mesic", ["05/2026", "06/2026", "07/2026"], [1.0, 5.0, 0.0]),
        ("rok", ["2026"], [6.0]),
    ],
)
def test_bucketing_month_year(tyn, user_vlastnik, ricany, pepper, gran, labels, values):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 5, 20), "1", pepper, odberatel=ricany)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), "2", pepper, odberatel=ricany)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 28), "3", pepper, odberatel=ricany)
    f = _flt(date(2026, 5, 1), date(2026, 7, 31), granularity=gran)
    res = analytics.sales_trend(f)
    assert res["labels"] == labels
    assert res["datasets"][0]["data"] == values


@pytest.mark.django_db
def test_bucketing_day_fills_gaps(tyn, user_vlastnik, ricany, pepper):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), "2", pepper, odberatel=ricany)
    f = _flt(date(2026, 6, 1), date(2026, 6, 3), granularity="den")
    assert analytics.sales_trend(f)["datasets"][0]["data"] == [0.0, 2.0, 0.0]


def test_granularity_coarsens_when_too_many_buckets():
    f = _flt(date(2020, 1, 1), date(2026, 1, 1), granularity="den")
    assert analytics.effective_granularity(f) != "den"


@pytest.mark.django_db
def test_branch_and_product_filters(tyn, sez, user_vlastnik, ricany, pepper, paprika):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), "2", pepper, odberatel=ricany)
    _mv(sez, user_vlastnik, "vydej", date(2026, 6, 2), "4", pepper, odberatel=ricany)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), "8", paprika, odberatel=ricany)
    lo, hi = JUN.date_from, JUN.date_to
    by_branch = _flt(lo, hi, branch_id=tyn.pk)
    by_product = _flt(lo, hi, product_ids=(pepper.pk,))
    assert _total(analytics.sales_lines(by_branch)) == D("10")
    assert _total(analytics.sales_lines(by_product)) == D("6")
    both = _flt(JUN.date_from, JUN.date_to, branch_id=sez.pk, product_ids=(pepper.pk,))
    assert _total(analytics.sales_lines(both)) == D("4")


# --- delta / kpis --------------------------------------------------------


def test_delta_helper():
    assert analytics.delta(D("15"), D("10"))["pct"] == 50.0
    assert analytics.delta(D("5"), D("10"))["dir"] == "down"
    assert analytics.delta(D("5"), D("0"))["pct"] is None
    assert analytics.delta(D("0"), D("0"))["dir"] == "flat"


def test_previous_period_is_same_length_and_adjacent():
    prev = _flt(date(2026, 6, 1), date(2026, 6, 30)).previous()
    assert (prev.date_from, prev.date_to) == (date(2026, 5, 2), date(2026, 5, 31))


@pytest.mark.django_db
def test_kpis_include_delta_vs_previous(tyn, user_vlastnik, ricany, pepper):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 5, 15), "10", pepper, odberatel=ricany)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 15), "15", pepper, odberatel=ricany)
    sold = next(k for k in analytics.kpis(JUN) if k["key"] == "sold")
    assert sold["value"] == D("15")
    assert sold["delta"]["pct"] == 50.0


def test_resolve_range_presets():
    today = date(2026, 6, 15)
    assert analytics.resolve_range("mesic", today) == (date(2026, 6, 1), today)
    assert analytics.resolve_range("minuly", today) == (date(2026, 5, 1), date(2026, 5, 31))
    assert analytics.resolve_range("12m", today)[0] == date(2025, 7, 1)
    assert analytics.resolve_range("rok", today)[0] == date(2026, 1, 1)
    assert analytics.resolve_range("vlastni", today, date(2026, 3, 9), date(2026, 3, 1)) == (
        date(2026, 3, 1),
        date(2026, 3, 9),
    )


# --- csv -----------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_csv_download(user_vlastnik, tyn, ricany, pepper):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 3), "4.25", pepper, odberatel=ricany)
    c = Client()
    c.force_login(user_vlastnik)
    resp = c.get(
        reverse(URL),
        {
            "format": "csv",
            "panel": "sales_by_product",
            "rozsah": "vlastni",
            "od": "2026-06-01",
            "do": "2026-06-30",
        },
    )
    assert resp.status_code == 200
    text = resp.content.decode("utf-8")
    assert text.startswith("﻿")
    lines = text.lstrip("﻿").splitlines()
    assert lines[0] == "Název;kg"
    assert lines[1] == "Pepř černý;4,3"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_csv_unknown_panel_404(user_vlastnik):
    c = Client()
    c.force_login(user_vlastnik)
    assert c.get(reverse(URL), {"format": "csv", "panel": "nope"}).status_code == 404


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_csv_obsluha_forbidden(user_obsluha_tyn):
    c = Client()
    c.force_login(user_obsluha_tyn)
    assert c.get(reverse(URL), {"format": "csv", "panel": "mix_trend"}).status_code == 403


# --- registry ------------------------------------------------------------


@pytest.mark.django_db
def test_registry_sanity(tyn, user_vlastnik, ricany, pepper):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 3), "4", pepper, odberatel=ricany)
    keys = [p.key for p in analytics.PANELS]
    assert len(keys) == len(set(keys))
    sections = {s for s, _ in analytics.SECTIONS}
    for panel in analytics.PANELS:
        assert panel.section in sections
        assert panel.chart in {"bar", "line", "hbar", "doughnut", "explorer"}
        res = panel.query(JUN)
        assert {"labels", "datasets", "table", "drill", "has_data"} <= set(res)
        assert analytics.panel_csv(panel, JUN).startswith("﻿")
    assert {p.section for p in analytics.PANELS} == sections


@pytest.mark.django_db
def test_csv_neutralises_formula_text(tyn, user_vlastnik, pepper):
    from inventory.models import Customer

    evil = Customer.objects.create(name='=HYPERLINK("http://x","y")')
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 3), "4", pepper, odberatel=evil)
    panel = analytics.PANELS_BY_KEY["sales_by_customer"]
    row = analytics.panel_csv(panel, JUN).lstrip("\ufeff").splitlines()[1]
    assert "'=HYPERLINK(" in row
    assert not row.startswith("=") and not row.startswith('"=')
    assert row.endswith(";4,0")


@pytest.mark.django_db
def test_batch_panels_have_data_when_kg_is_zero(tyn, user_vlastnik, pepper):
    job = _done_job(tyn, user_vlastnik, pepper, "4")
    job.actual_produced_qty = None
    job.save()
    for key in ("batches_trend", "batches_by_mixture", "batches_by_user", "batches_by_branch"):
        assert analytics.PANELS_BY_KEY[key].query(JUN)["has_data"], key


@pytest.mark.django_db
def test_bucket_drill_disabled_at_day_granularity(tyn, user_vlastnik, ricany, pepper):
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), "2", pepper, odberatel=ricany)
    day = _flt(date(2026, 6, 1), date(2026, 6, 3), granularity="den")
    assert analytics.sales_trend(day)["drill"] is None
    assert analytics.sales_trend(JUN)["drill"]["param"] == "bucket"


@pytest.mark.django_db
def test_products_over_time_all_products_and_sums(tyn, user_vlastnik, ricany, supplier):
    from inventory.models import Product

    micharna = counterparties.customer("micharna")
    prods = [
        Product.objects.create(name_cs=f"Koření {i:02d}", kind=Product.Kind.RAW_SPICE)
        for i in range(12)
    ]
    for i, p in enumerate(prods):
        _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), str(i + 1), p, odberatel=micharna)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 20), "3", prods[0], odberatel=micharna)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 4), "5", prods[0], odberatel=ricany)
    _mv(tyn, user_vlastnik, "prijem", date(2026, 6, 4), "6", prods[1], dodavatel=supplier)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 5, 10), "2", prods[0], odberatel=micharna)

    res = analytics.products_over_time(_flt(date(2026, 5, 1), date(2026, 6, 30)))
    ex = res["explorer"]
    assert len(ex["products"]) == 12
    first = next(p for p in ex["products"] if p["name"] == "Koření 00")
    assert first["series"]["mix"] == [2.0, 4.0]
    assert first["series"]["sales"] == [0.0, 5.0]
    assert first["kg"]["mix"] == 6.0
    for key in ("mix", "sales", "receipts"):
        by_bucket = [
            round(sum(p["series"][key][i] for p in ex["products"]), 1)
            for i in range(len(res["labels"]))
        ]
        assert by_bucket == ex["totals"][key]
        assert round(sum(by_bucket), 1) == ex["grand"][key]
    assert ex["grand"]["receipts"] == 6.0


@pytest.mark.django_db
def test_products_over_time_exclusions_and_previous(
    tyn, user_vlastnik, ricany, pepper, voda, hotovy_vyrobek, supplier
):
    micharna = counterparties.customer("micharna")
    for p in (voda, hotovy_vyrobek):
        _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), "9", p, odberatel=micharna)
    _mv(
        tyn,
        user_vlastnik,
        "prijem",
        date(2026, 6, 2),
        "8",
        pepper,
        dodavatel=supplier,
        status=Movement.Status.PLANNED,
    )
    _mv(
        tyn,
        user_vlastnik,
        "prijem",
        date(2026, 6, 2),
        "7",
        pepper,
        dodavatel=counterparties.supplier("micharna"),
    )
    _mv(
        tyn,
        user_vlastnik,
        "vydej",
        date(2026, 6, 2),
        "6",
        pepper,
        odberatel=counterparties.customer("adjustment"),
    )
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 3), "10", pepper, odberatel=micharna)
    _mv(tyn, user_vlastnik, "vydej", date(2026, 5, 15), "5", pepper, odberatel=micharna)

    ex = analytics.products_over_time(JUN)["explorer"]
    assert [p["name"] for p in ex["products"]] == ["Pepř černý"]
    row = ex["products"][0]
    assert row["kg"] == {"mix": 10.0, "sales": 0.0, "receipts": 0.0}
    assert row["prev"]["mix"] == 5.0
    assert ex["grand_prev"]["mix"] == 5.0


@pytest.mark.django_db
def test_products_over_time_respects_product_filter(tyn, user_vlastnik, ricany, pepper, paprika):
    for p in (pepper, paprika):
        _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), "3", p, odberatel=ricany)
    f = _flt(JUN.date_from, JUN.date_to, product_ids=(paprika.pk,))
    names = [p["name"] for p in analytics.products_over_time(f)["explorer"]["products"]]
    assert names == ["Paprika sladká"]


@pytest.mark.django_db
def test_products_over_time_empty_and_csv(tyn, user_vlastnik, ricany, pepper):
    assert analytics.products_over_time(JUN)["has_data"] is False
    _mv(tyn, user_vlastnik, "vydej", date(2026, 6, 2), "3", pepper, odberatel=ricany)
    text = analytics.panel_csv(analytics.PANELS_BY_KEY["products_over_time"], JUN)
    lines = text.lstrip("﻿").splitlines()
    assert lines[0].startswith("Produkt;Spotřeba v míchání (kg);Prodej (kg);Příjem (kg)")
    assert lines[1].startswith("Pepř černý;0,0;3,0;0,0")
    assert lines[-1].startswith("Celkem;0,0;3,0;0,0")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overview_renders_explorer(user_vlastnik, user_obsluha_tyn, tyn, ricany, pepper):
    _mv(tyn, user_vlastnik, "vydej", date.today(), "3", pepper, odberatel=ricany)
    c = Client()
    c.force_login(user_vlastnik)
    body = c.get(reverse(URL), {"sekce": "prehled"}).content.decode()
    assert "data-explorer-for" in body and "Top 10 produktů" in body
    resp = c.get(reverse(URL), {"format": "csv", "panel": "products_over_time"})
    assert resp.status_code == 200
    o = Client()
    o.force_login(user_obsluha_tyn)
    assert o.get(reverse(URL), {"sekce": "prehled"}).status_code == 403
