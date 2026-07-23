"""Movement history (screen 10) + the post-create confirmation page."""

from __future__ import annotations

from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils.http import urlencode
from django.views.decorators.http import require_GET

from ...models import (
    Branch,
    DodaciList,
    Movement,
)


@require_GET
def movement_saved(request, pk: int):
    """Confirmation page after a successful create."""
    movement = get_object_or_404(
        Movement.objects.select_related("branch", "odberatel", "dodavatel"),
        pk=pk,
    )
    dodaci_list = DodaciList.objects.filter(movement=movement).first()
    return render(
        request,
        "inventory/movement_saved.html",
        {"movement": movement, "dodaci_list": dodaci_list},
    )


@require_GET
def movement_history(request):
    """Chronological filterable record of every movement.

    Layout (per Pass 5g redesign):
    - **Tab chips** at top: Vše / Příjmy / Výdeje / Inventura / Editováno.
      `?tab=<name>` is the shorthand the chips use; counts per tab
      are computed against the same branch-scoped + date/q-filtered
      base qs so the chip badges always tell the truth for the
      current view.
    - **Filter card** below tabs: branch (vlastník only — obsluha is
      auto-scoped), date from/to, free-text q.
    - **Table** at the bottom — same as before, capped at 200.

    Legacy `?kind=` and `?edited=` URL params still work for
    bookmarked links; new `?tab=` is the operator-facing shorthand.
    """
    from datetime import date as _date

    base_qs = (
        Movement.objects.select_related(
            "branch", "odberatel", "dodavatel", "created_by"
        )
        .prefetch_related("lines__product", "audit_entries")
    )

    # Branch scoping — obsluha forced to own branch.
    if request.user.is_obsluha and request.user.branch_id:
        base_qs = base_qs.filter(branch_id=request.user.branch_id)
        branch_locked = request.user.branch
    else:
        branch_locked = None
        branch_filter = request.GET.get("branch") or ""
        if branch_filter:
            base_qs = base_qs.filter(branch_id=branch_filter)

    date_from = request.GET.get("date_from") or ""
    date_to = request.GET.get("date_to") or ""

    def _parse(s: str):
        try:
            return _date.fromisoformat(s)
        except ValueError:
            return None

    df, dt = _parse(date_from), _parse(date_to)

    # Per 0063: text search (`q`) is filtered client-side in the browser
    # (diacritic-insensitive, typo-tolerant, as-you-type) over the rendered
    # rows. The server only echoes the term back into the input. Date, branch,
    # and tab stay server-side and pre-narrow the (200-capped) set as before;
    # the "Nalezeno" / tab counts therefore reflect server totals, not the
    # client-typed text.
    search = (request.GET.get("q") or "").strip()

    # Per 0059: PLANNED príjmy (objednávky) are NOT history — they live only
    # in the "Plánované" tab. The other tabs are DONE-only (what happened).
    # The date range filters `date_issued` on the history tabs, but the
    # promised `expected_on` on Plánované (date_issued there is just "today").
    def _apply_date(qs, field):
        if df is not None:
            qs = qs.filter(**{f"{field}__gte": df})
        if dt is not None:
            qs = qs.filter(**{f"{field}__lte": dt})
        return qs

    done_base = _apply_date(
        base_qs.filter(status=Movement.Status.DONE), "date_issued"
    )
    planned_base = _apply_date(
        base_qs.filter(
            status=Movement.Status.PLANNED, kind=Movement.Kind.PRIJEM
        ),
        "expected_on",
    )

    inventura_filter = Q(note__startswith="[STAV] ")
    planned_count = planned_base.count()
    tab_counts = {
        # "Vše" now unions DONE + PLANNED (per 0066) — planned surfaces here too.
        "all": done_base.count() + planned_count,
        "prijem": done_base.filter(kind=Movement.Kind.PRIJEM).count(),
        "vydej": done_base.filter(kind=Movement.Kind.VYDEJ).count(),
        "inventura": done_base.filter(inventura_filter).count(),
        "edited": done_base.filter(audit_entries__isnull=False).distinct().count(),
        "planned": planned_count,
    }

    # Resolve the active tab. Legacy `?kind=` / `?edited=1` map onto
    # the new tab system so bookmarked links keep their behaviour.
    tab = request.GET.get("tab") or ""
    legacy_kind = request.GET.get("kind") or ""
    legacy_edited = request.GET.get("edited") == "1"
    if not tab:
        if legacy_kind in (Movement.Kind.PRIJEM, Movement.Kind.VYDEJ):
            tab = legacy_kind
        elif legacy_edited:
            tab = "edited"
        else:
            tab = "all"

    if tab == "planned":
        # Worklist ordering: soonest arrival first.
        items = list(planned_base.order_by("expected_on", "id"))
    elif tab == "all":
        # Per 0066: upcoming planned first (soonest arrival), then done history.
        items = list(planned_base.order_by("expected_on", "id")) + list(
            done_base.order_by("-date_issued", "-id")
        )
    else:
        qs = done_base
        if tab == Movement.Kind.PRIJEM:
            qs = qs.filter(kind=Movement.Kind.PRIJEM)
        elif tab == Movement.Kind.VYDEJ:
            qs = qs.filter(kind=Movement.Kind.VYDEJ)
        elif tab == "inventura":
            qs = qs.filter(inventura_filter)
        elif tab == "edited":
            qs = qs.filter(audit_entries__isnull=False).distinct()
        items = list(qs.order_by("-date_issued", "-id"))

    # Paginate at 50 rows/page (per 0066), replacing the old 200 cap.
    paginator = Paginator(items, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    movements = list(page_obj.object_list)

    # Per-movement total kg for the "Množství" column. Lines are already
    # prefetched, so this sums in Python without extra queries.
    for mv in movements:
        # Per 0095: finished-product („ks") lines are unlimited and not kg —
        # exclude them so a piece count is never folded into the mass total.
        mv.total_kg = sum(
            (
                line.quantity_kg
                for line in mv.lines.all()
                if not line.product.is_unlimited
            ),
            Decimal("0.000"),
        )

    # Query string (minus page) so pagination links keep the current filters.
    page_params = {"tab": tab}
    if request.GET.get("branch"):
        page_params["branch"] = request.GET.get("branch")
    if date_from:
        page_params["date_from"] = date_from
    if date_to:
        page_params["date_to"] = date_to
    if search:
        page_params["q"] = search
    page_querystring = urlencode(page_params)

    branches = list(Branch.objects.filter(is_active=True).order_by("code"))

    tabs = [
        ("all", "Vše", tab_counts["all"]),
        (Movement.Kind.PRIJEM, "Příjmy", tab_counts["prijem"]),
        (Movement.Kind.VYDEJ, "Výdeje", tab_counts["vydej"]),
        ("inventura", "Inventura / úprava stavu", tab_counts["inventura"]),
        ("edited", "Editováno", tab_counts["edited"]),
        ("planned", "Plánované", tab_counts["planned"]),
    ]

    return render(
        request,
        "inventory/movement_history.html",
        {
            "movements": movements,
            "count": paginator.count,
            "page_obj": page_obj,
            "page_querystring": page_querystring,
            "branches": branches,
            "branch_locked": branch_locked,
            "filter_branch": request.GET.get("branch") or "",
            "filter_kind": legacy_kind,  # back-compat for any external link
            "filter_date_from": date_from,
            "filter_date_to": date_to,
            "filter_edited": legacy_edited,
            "filter_q": search,
            "active_tab": tab,
            "tabs": tabs,
        },
    )
