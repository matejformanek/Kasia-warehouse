"""Statistiky — read-only aggregation behind the vlastník analytics screen (0107).

Everything is derived from existing rows: ``Movement`` (``status=done``, bucketed
by ``date_issued``) + ``MovementLine`` for the kg flows, ``MixingJob`` (done) for
production. The flows are told apart by counterparty:

- spotřeba v míchání = výdej to the internal ``micharna`` customer
- prodej             = výdej to a non-internal customer (převod mezi pobočkami excluded)
- příjem             = příjem from a real supplier or "Neuveden" (the míchárna,
                       inventura and převod legs are excluded)

``Product.is_unlimited`` products (Voda, hotový výrobek — ks) never enter a kg sum.

Adding a panel = one query function + one ``Panel`` entry in ``PANELS``.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncYear

from ..models import Branch, MixingJob, Movement, MovementLine, Product
from . import counterparties

ZERO = Decimal("0")
_ONE_DP = Decimal("0.1")
MAX_BUCKETS = 400
TOP_N = 10
STACK_N = 8

GRANULARITIES = {"den": "Den", "mesic": "Měsíc", "rok": "Rok"}
_TRUNC = {"den": TruncDay, "mesic": TruncMonth, "rok": TruncYear}

SECTIONS = [
    ("prehled", "Přehled"),
    ("michani", "Spotřeba v míchání"),
    ("vydeje", "Výdeje"),
    ("prijem", "Příjem"),
    ("davky", "Dávky a lidé"),
]

RANGES = [
    ("30d", "Posledních 30 dní"),
    ("mesic", "Tento měsíc"),
    ("minuly", "Minulý měsíc"),
    ("12m", "Posledních 12 měsíců"),
    ("rok", "Tento rok"),
    ("vlastni", "Vlastní od–do"),
]


@dataclass(frozen=True)
class Filters:
    date_from: date
    date_to: date
    granularity: str = "mesic"
    branch_id: int | None = None
    product_ids: tuple[int, ...] = ()

    def previous(self) -> Filters:
        days = (self.date_to - self.date_from).days + 1
        prev_to = self.date_from - timedelta(days=1)
        return Filters(
            prev_to - timedelta(days=days - 1),
            prev_to,
            self.granularity,
            self.branch_id,
            self.product_ids,
        )


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, n: int) -> date:
    idx = d.year * 12 + d.month - 1 + n
    return date(idx // 12, idx % 12 + 1, 1)


def resolve_range(preset: str, today: date, raw_from=None, raw_to=None):
    """Return (date_from, date_to) for a preset; ``vlastni`` uses the raw values."""
    if preset == "mesic":
        return _month_start(today), today
    if preset == "minuly":
        first = _add_months(_month_start(today), -1)
        return first, _month_start(today) - timedelta(days=1)
    if preset == "12m":
        return _add_months(_month_start(today), -11), today
    if preset == "rok":
        return date(today.year, 1, 1), today
    if preset == "vlastni" and raw_from and raw_to:
        lo, hi = sorted((raw_from, raw_to))
        return lo, hi
    return today - timedelta(days=29), today


def effective_granularity(f: Filters) -> str:
    """Coarsen the requested granularity when it would draw too many buckets."""
    g = f.granularity if f.granularity in GRANULARITIES else "mesic"
    days = (f.date_to - f.date_from).days + 1
    if g == "den" and days > MAX_BUCKETS:
        g = "mesic"
    if g == "mesic" and days > MAX_BUCKETS * 30:
        g = "rok"
    return g


def _bucket_start(d: date, g: str) -> date:
    if g == "rok":
        return date(d.year, 1, 1)
    if g == "mesic":
        return _month_start(d)
    return d


def _next_bucket(d: date, g: str) -> date:
    if g == "rok":
        return date(d.year + 1, 1, 1)
    if g == "mesic":
        return _add_months(d, 1)
    return d + timedelta(days=1)


def bucket_starts(f: Filters) -> list[date]:
    g = effective_granularity(f)
    out, cur = [], _bucket_start(f.date_from, g)
    while cur <= f.date_to:
        out.append(cur)
        cur = _next_bucket(cur, g)
    return out


def _bucket_label(d: date, g: str) -> str:
    if g == "rok":
        return f"{d.year}"
    if g == "mesic":
        return f"{d.month:02d}/{d.year}"
    return f"{d.day}. {d.month}. {d.year}"


def kg1(value) -> float:
    return float(Decimal(value or 0).quantize(_ONE_DP, rounding=ROUND_HALF_UP))


# --- base querysets ------------------------------------------------------


def _lines(f: Filters):
    qs = MovementLine.objects.filter(
        movement__status=Movement.Status.DONE,
        movement__date_issued__range=(f.date_from, f.date_to),
        product__is_stock_tracked=True,
    ).exclude(product__kind=Product.Kind.HOTOVY_VYROBEK)
    if f.branch_id:
        qs = qs.filter(movement__branch_id=f.branch_id)
    if f.product_ids:
        qs = qs.filter(product_id__in=f.product_ids)
    return qs


def consumption_lines(f: Filters):
    return _lines(f).filter(
        movement__kind=Movement.Kind.VYDEJ,
        movement__odberatel=counterparties.customer("micharna"),
    )


def sales_lines(f: Filters):
    return (
        _lines(f)
        .filter(
            movement__kind=Movement.Kind.VYDEJ,
            movement__odberatel__is_internal=False,
            movement__transfer__isnull=True,
        )
        .exclude(movement__odberatel=counterparties.customer("transfer"))
    )


def receipt_lines(f: Filters):
    return (
        _lines(f)
        .filter(
            Q(movement__dodavatel__isnull=True)
            | Q(movement__dodavatel__is_internal=False)
            | Q(movement__dodavatel=counterparties.supplier("unknown_supplier")),
            movement__kind=Movement.Kind.PRIJEM,
            movement__transfer__isnull=True,
        )
        .exclude(movement__dodavatel=counterparties.supplier("transfer"))
    )


def done_jobs(f: Filters):
    qs = (
        MixingJob.objects.filter(state=MixingJob.State.DONE)
        .annotate(day=Coalesce("produce_movement__date_issued", "consume_movement__date_issued"))
        .filter(day__range=(f.date_from, f.date_to))
    )
    if f.branch_id:
        qs = qs.filter(branch_id=f.branch_id)
    if f.product_ids:
        qs = qs.filter(mixture_id__in=f.product_ids)
    return qs


def _total(qs, field_name="quantity_kg") -> Decimal:
    return qs.aggregate(t=Sum(field_name))["t"] or ZERO


# --- result building -----------------------------------------------------


def _table(columns: list[tuple[str, str]], rows: list[list]) -> dict:
    """``columns`` = (label, kind) with kind text|kg|int; rows hold raw values."""
    return {
        "columns": [{"label": label, "kind": kind} for label, kind in columns],
        "rows": [[{"kind": columns[i][1], "v": v} for i, v in enumerate(row)] for row in rows],
        "raw_rows": rows,
    }


def _result(labels, datasets, table, drill=None, has_data=None) -> dict:
    return {
        "labels": labels,
        "datasets": [{"label": label, "data": [kg1(v) for v in data]} for label, data in datasets],
        "table": table,
        "drill": drill,
        "has_data": any(v for _, data in datasets for v in data) if has_data is None else has_data,
    }


def _series(qs, f: Filters, value="quantity_kg", date_field="movement__date_issued"):
    """kg per bucket for ``qs`` -> (labels, values, drill spans)."""
    g = effective_granularity(f)
    rows = qs.annotate(b=_TRUNC[g](date_field)).values("b").annotate(t=Sum(value)).order_by("b")
    by_bucket = {r["b"]: r["t"] or ZERO for r in rows}
    starts = bucket_starts(f)
    return (
        [_bucket_label(d, g) for d in starts],
        [by_bucket.get(d, ZERO) for d in starts],
        _bucket_drill(starts, g, f),
    )


def _bucket_drill(starts, g: str, f: Filters) -> dict | None:
    if g == "den":
        return None
    spans = []
    for d in starts:
        lo = max(d, f.date_from)
        hi = min(_next_bucket(d, g) - timedelta(days=1), f.date_to)
        spans.append([lo.isoformat(), hi.isoformat()])
    return {"param": "bucket", "values": spans, "finer": g}


def _trend_panel(qs, f: Filters, title: str) -> dict:
    labels, values, drill = _series(qs, f)
    table = _table(
        [("Období", "text"), ("kg", "kg")],
        [[label, v] for label, v in zip(labels, values, strict=True)]
        + [["Celkem", sum(values, ZERO)]],
    )
    return _result(labels, [(title, values)], table, drill)


def _group_panel(qs, id_field, label_field, title, drill_param=None, limit=None):
    rows = list(
        qs.values(id_field, label_field)
        .annotate(t=Sum("quantity_kg"))
        .order_by("-t", label_field)[:limit]
    )
    labels = [r[label_field] or "—" for r in rows]
    values = [r["t"] or ZERO for r in rows]
    table = _table(
        [("Název", "text"), ("kg", "kg")], [[lb, v] for lb, v in zip(labels, values, strict=True)]
    )
    drill = {"param": drill_param, "values": [r[id_field] for r in rows]} if drill_param else None
    return _result(labels, [(title, values)], table, drill)


def _stacked_by_product(qs, f: Filters) -> dict:
    g = effective_granularity(f)
    top = list(
        qs.values("product_id", "product__name_cs")
        .annotate(t=Sum("quantity_kg"))
        .order_by("-t", "product__name_cs")[:STACK_N]
    )
    top_ids = [r["product_id"] for r in top]
    starts = bucket_starts(f)
    cells: dict[tuple, Decimal] = defaultdict(lambda: ZERO)
    for r in (
        qs.annotate(b=_TRUNC[g]("movement__date_issued"))
        .values("b", "product_id")
        .annotate(t=Sum("quantity_kg"))
    ):
        key = r["product_id"] if r["product_id"] in top_ids else None
        cells[(r["b"], key)] += r["t"] or ZERO
    datasets = [(r["product__name_cs"], [cells[(d, r["product_id"])] for d in starts]) for r in top]
    if any(cells[(d, None)] for d in starts):
        datasets.append(("Ostatní", [cells[(d, None)] for d in starts]))
    labels = [_bucket_label(d, g) for d in starts]
    table = _table(
        [("Období", "text")] + [(name, "kg") for name, _ in datasets],
        [[label] + [data[i] for _, data in datasets] for i, label in enumerate(labels)],
    )
    res = _result(labels, datasets, table, _bucket_drill(starts, g, f))
    res["stacked"] = True
    return res


# --- panels --------------------------------------------------------------


def overview_trend(f: Filters) -> dict:
    g = effective_granularity(f)
    starts = bucket_starts(f)
    series = [
        ("Příjem", receipt_lines(f)),
        ("Spotřeba v míchání", consumption_lines(f)),
        ("Prodej", sales_lines(f)),
    ]
    datasets = [(name, _series(qs, f)[1]) for name, qs in series]
    labels = [_bucket_label(d, g) for d in starts]
    table = _table(
        [("Období", "text")] + [(name, "kg") for name, _ in datasets],
        [[label] + [data[i] for _, data in datasets] for i, label in enumerate(labels)],
    )
    return _result(labels, datasets, table, _bucket_drill(starts, g, f))


def overview_top_products(f: Filters) -> dict:
    out: dict[int, dict] = {}
    for key, qs in (("mix", consumption_lines(f)), ("sales", sales_lines(f))):
        for r in qs.values("product_id", "product__name_cs").annotate(t=Sum("quantity_kg")):
            row = out.setdefault(
                r["product_id"],
                {"name": r["product__name_cs"], "mix": ZERO, "sales": ZERO},
            )
            row[key] += r["t"] or ZERO
    top = sorted(out.items(), key=lambda kv: (-(kv[1]["mix"] + kv[1]["sales"]), kv[1]["name"]))[
        :TOP_N
    ]
    labels = [v["name"] for _, v in top]
    datasets = [
        ("Spotřeba v míchání", [v["mix"] for _, v in top]),
        ("Prodej", [v["sales"] for _, v in top]),
    ]
    table = _table(
        [("Produkt", "text"), ("Míchání (kg)", "kg"), ("Prodej (kg)", "kg"), ("Celkem (kg)", "kg")],
        [[v["name"], v["mix"], v["sales"], v["mix"] + v["sales"]] for _, v in top],
    )
    res = _result(labels, datasets, table, {"param": "product", "values": [pk for pk, _ in top]})
    res["stacked"] = True
    return res


EXPLORER_METRICS = [
    ("mix", "Spotřeba v míchání", consumption_lines),
    ("sales", "Prodej", sales_lines),
    ("receipts", "Příjem", receipt_lines),
]


def products_over_time(f: Filters) -> dict:
    """Every active product x bucket x metric (GA4-style explorer, rendered client-side)."""
    g = effective_granularity(f)
    starts = bucket_starts(f)
    index = {d: i for i, d in enumerate(starts)}
    prev = f.previous()
    products: dict[int, dict] = {}
    totals = {key: [ZERO] * len(starts) for key, _, _ in EXPLORER_METRICS}
    grand = {key: ZERO for key, _, _ in EXPLORER_METRICS}
    grand_prev = {key: ZERO for key, _, _ in EXPLORER_METRICS}

    def entry(pid, name):
        return products.setdefault(
            pid,
            {
                "id": pid,
                "name": name,
                "kg": {k: ZERO for k, _, _ in EXPLORER_METRICS},
                "prev": {k: ZERO for k, _, _ in EXPLORER_METRICS},
                "series": {k: [ZERO] * len(starts) for k, _, _ in EXPLORER_METRICS},
            },
        )

    for key, _, lines in EXPLORER_METRICS:
        rows = (
            lines(f)
            .annotate(b=_TRUNC[g]("movement__date_issued"))
            .values("product_id", "product__name_cs", "b")
            .annotate(t=Sum("quantity_kg"))
        )
        for r in rows:
            t = r["t"] or ZERO
            p = entry(r["product_id"], r["product__name_cs"])
            p["kg"][key] += t
            p["series"][key][index[r["b"]]] += t
            totals[key][index[r["b"]]] += t
            grand[key] += t
        for r in (
            lines(prev).values("product_id", "product__name_cs").annotate(t=Sum("quantity_kg"))
        ):
            t = r["t"] or ZERO
            entry(r["product_id"], r["product__name_cs"])["prev"][key] += t
            grand_prev[key] += t

    # Products that only had previous-period activity stay out of the table.
    rows = sorted(
        (p for p in products.values() if any(p["kg"].values())),
        key=lambda p: (-p["kg"]["mix"], -p["kg"]["sales"], -p["kg"]["receipts"], p["name"]),
    )
    labels = [_bucket_label(d, g) for d in starts]

    columns = [("Produkt", "text")]
    columns += [(f"{label} (kg)", "kg") for _, label, _ in EXPLORER_METRICS]
    columns += [(f"{label} — předchozí období (kg)", "kg") for _, label, _ in EXPLORER_METRICS]
    table_rows = [
        [p["name"]]
        + [p["kg"][k] for k, _, _ in EXPLORER_METRICS]
        + [p["prev"][k] for k, _, _ in EXPLORER_METRICS]
        for p in rows
    ]
    table_rows.append(
        ["Celkem"]
        + [grand[k] for k, _, _ in EXPLORER_METRICS]
        + [grand_prev[k] for k, _, _ in EXPLORER_METRICS]
    )
    res = _result(
        labels,
        [(label, totals[key]) for key, label, _ in EXPLORER_METRICS],
        _table(columns, table_rows),
        None,
        has_data=bool(rows),
    )
    res["explorer"] = {
        "metrics": [{"key": k, "label": label} for k, label, _ in EXPLORER_METRICS],
        "products": [
            {
                "id": p["id"],
                "name": p["name"],
                "kg": {k: kg1(v) for k, v in p["kg"].items()},
                "prev": {k: kg1(v) for k, v in p["prev"].items()},
                "series": {k: [kg1(v) for v in vals] for k, vals in p["series"].items()},
            }
            for p in rows
        ],
        "totals": {k: [kg1(v) for v in vals] for k, vals in totals.items()},
        "grand": {k: kg1(v) for k, v in grand.items()},
        "grand_prev": {k: kg1(v) for k, v in grand_prev.items()},
    }
    return res


def mix_trend(f: Filters) -> dict:
    return _trend_panel(consumption_lines(f), f, "Spotřeba v míchání")


def mix_stacked(f: Filters) -> dict:
    return _stacked_by_product(consumption_lines(f), f)


def mix_by_product(f: Filters) -> dict:
    return _group_panel(
        consumption_lines(f), "product_id", "product__name_cs", "Spotřeba v míchání", "product"
    )


def mix_by_mixture(f: Filters) -> dict:
    qs = consumption_lines(f)
    return _group_panel(
        qs,
        "movement__mixing_job_as_consume__mixture_id",
        "movement__mixing_job_as_consume__mixture__name_cs",
        "Spotřeba v míchání",
    )


def sales_trend(f: Filters) -> dict:
    return _trend_panel(sales_lines(f), f, "Prodej")


def sales_by_customer(f: Filters) -> dict:
    return _group_panel(
        sales_lines(f), "movement__odberatel_id", "movement__odberatel__name", "Prodej"
    )


def sales_by_product(f: Filters) -> dict:
    return _group_panel(sales_lines(f), "product_id", "product__name_cs", "Prodej", "product")


def sales_by_branch(f: Filters) -> dict:
    return _group_panel(sales_lines(f), "movement__branch_id", "movement__branch__name", "Prodej")


def receipts_trend(f: Filters) -> dict:
    return _trend_panel(receipt_lines(f), f, "Příjem")


def receipts_by_supplier(f: Filters) -> dict:
    return _group_panel(
        receipt_lines(f), "movement__dodavatel_id", "movement__dodavatel__name", "Příjem"
    )


def receipts_by_product(f: Filters) -> dict:
    return _group_panel(receipt_lines(f), "product_id", "product__name_cs", "Příjem", "product")


def _job_panel(f: Filters, id_field: str, label_field: str, first: str, drill=None) -> dict:
    rows = list(
        done_jobs(f)
        .values(id_field, label_field)
        .annotate(n=Count("id"), kg=Sum("actual_produced_qty"))
        .order_by(F("kg").desc(nulls_last=True), label_field)
    )
    labels = [r[label_field] or "—" for r in rows]
    values = [r["kg"] or ZERO for r in rows]
    table = _table(
        [(first, "text"), ("Dávek", "int"), ("Vyrobeno (kg)", "kg")],
        [[lb, r["n"], v] for lb, r, v in zip(labels, rows, values, strict=True)],
    )
    return _result(
        labels,
        [("Vyrobeno", values)],
        table,
        {"param": drill, "values": [r[id_field] for r in rows]} if drill else None,
        has_data=any(r["n"] for r in rows),
    )


def batches_by_mixture(f: Filters) -> dict:
    return _job_panel(f, "mixture_id", "mixture__name_cs", "Směs", "product")


def batches_by_user(f: Filters) -> dict:
    return _job_panel(f, "created_by_id", "created_by__email", "Uživatel")


def batches_by_branch(f: Filters) -> dict:
    return _job_panel(f, "branch_id", "branch__name", "Pobočka")


def batches_trend(f: Filters) -> dict:
    g = effective_granularity(f)
    rows = (
        done_jobs(f)
        .annotate(b=_TRUNC[g]("day"))
        .values("b")
        .annotate(n=Count("id"), kg=Sum("actual_produced_qty"))
    )
    by_bucket = {r["b"]: r for r in rows}
    starts = bucket_starts(f)
    labels = [_bucket_label(d, g) for d in starts]
    values = [(by_bucket.get(d) or {}).get("kg") or ZERO for d in starts]
    counts = [(by_bucket.get(d) or {}).get("n") or 0 for d in starts]
    table = _table(
        [("Období", "text"), ("Dávek", "int"), ("Vyrobeno (kg)", "kg")],
        [[lb, n, v] for lb, n, v in zip(labels, counts, values, strict=True)],
    )
    return _result(
        labels,
        [("Vyrobeno", values)],
        table,
        _bucket_drill(starts, g, f),
        has_data=any(counts),
    )


@dataclass(frozen=True)
class Panel:
    key: str
    title: str
    section: str
    query: Callable[[Filters], dict]
    chart: str  # bar | line | hbar | doughnut
    wide: bool = field(default=False)


PANELS: list[Panel] = [
    Panel(
        "overview_trend", "Příjem, míchání a prodej v čase", "prehled", overview_trend, "line", True
    ),
    Panel(
        "products_over_time",
        "Všechny produkty v čase",
        "prehled",
        products_over_time,
        "explorer",
        True,
    ),
    Panel("overview_top_products", "Top 10 produktů", "prehled", overview_top_products, "hbar"),
    Panel("mix_trend", "Spotřeba v míchání v čase", "michani", mix_trend, "bar", True),
    Panel("mix_stacked", "Spotřeba podle surovin", "michani", mix_stacked, "bar", True),
    Panel("mix_by_product", "Spotřeba podle suroviny", "michani", mix_by_product, "hbar"),
    Panel("mix_by_mixture", "Spotřeba podle směsi", "michani", mix_by_mixture, "hbar"),
    Panel("sales_trend", "Prodej v čase", "vydeje", sales_trend, "bar", True),
    Panel("sales_by_customer", "Prodej podle odběratele", "vydeje", sales_by_customer, "hbar"),
    Panel("sales_by_product", "Prodej podle produktu", "vydeje", sales_by_product, "hbar"),
    Panel("sales_by_branch", "Prodej podle pobočky", "vydeje", sales_by_branch, "doughnut"),
    Panel("receipts_trend", "Příjem v čase", "prijem", receipts_trend, "bar", True),
    Panel(
        "receipts_by_supplier", "Příjem podle dodavatele", "prijem", receipts_by_supplier, "hbar"
    ),
    Panel("receipts_by_product", "Příjem podle produktu", "prijem", receipts_by_product, "hbar"),
    Panel("batches_trend", "Dávky v čase", "davky", batches_trend, "bar", True),
    Panel("batches_by_mixture", "Dávky podle směsi", "davky", batches_by_mixture, "hbar"),
    Panel("batches_by_user", "Dávky podle uživatele", "davky", batches_by_user, "hbar"),
    Panel("batches_by_branch", "Dávky podle pobočky", "davky", batches_by_branch, "doughnut"),
]

PANELS_BY_KEY = {p.key: p for p in PANELS}


# --- KPI strip + delta ---------------------------------------------------


def delta(current: Decimal, previous: Decimal) -> dict:
    """Change vs the previous period; ``pct`` is None when there is no baseline."""
    diff = current - previous
    pct = None
    if previous:
        pct = float((diff / previous * 100).quantize(_ONE_DP, rounding=ROUND_HALF_UP))
    return {
        "diff": diff,
        "pct": pct,
        "dir": "up" if diff > 0 else "down" if diff < 0 else "flat",
        "previous": previous,
    }


def _kpi_values(f: Filters) -> dict[str, Decimal]:
    jobs = done_jobs(f)
    return {
        "consumed": _total(consumption_lines(f)),
        "produced": _total(jobs, "actual_produced_qty"),
        "sold": _total(sales_lines(f)),
        "received": _total(receipt_lines(f)),
        "batches": Decimal(jobs.count()),
    }


KPI_DEFS = [
    ("consumed", "Spotřeba v míchání", "kg"),
    ("produced", "Vyrobeno", "kg"),
    ("sold", "Prodáno", "kg"),
    ("received", "Přijato", "kg"),
    ("batches", "Počet dávek", "dávek"),
]


def kpis(f: Filters) -> list[dict]:
    cur, prev = _kpi_values(f), _kpi_values(f.previous())
    return [
        {
            "key": key,
            "label": label,
            "unit": unit,
            "value": cur[key],
            "delta": delta(cur[key], prev[key]),
        }
        for key, label, unit in KPI_DEFS
    ]


# --- helpers for the view ------------------------------------------------


def branch_choices():
    return list(Branch.objects.filter(is_active=True).order_by("code"))


def product_choices():
    return list(
        Product.objects.filter(is_stock_tracked=True)
        .exclude(kind=Product.Kind.HOTOVY_VYROBEK)
        .order_by("name_cs")
    )


def _csv_safe(value):
    """Neutralise spreadsheet formulas in user-controlled text cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def panel_csv(panel: Panel, f: Filters) -> str:
    table = panel.query(f)["table"]
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow([c["label"] for c in table["columns"]])
    for row in table["raw_rows"]:
        writer.writerow(
            [
                str(Decimal(v).quantize(_ONE_DP, rounding=ROUND_HALF_UP)).replace(".", ",")
                if col["kind"] == "kg"
                else _csv_safe(v)
                for v, col in zip(row, table["columns"], strict=True)
            ]
        )
    return buf.getvalue()
