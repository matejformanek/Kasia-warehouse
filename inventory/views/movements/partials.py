"""HTMX partials for the movement create forms."""

from __future__ import annotations

from django.shortcuts import render
from django.views.decorators.http import require_GET

from ...forms import MovementLineForm


@require_GET
def line_row_partial(request):
    """Render one empty MovementLineForm row. The caller passes the
    new index via ?index=N so the prefix matches the formset."""
    try:
        index = int(request.GET.get("index", 0))
    except ValueError:
        index = 0
    show_stock_warn = request.GET.get("warn") == "1"
    # Per 0095: finished products („hotový výrobek“) are included on any výdej
    # add-row and excluded on příjem. On CREATE, warn=1 already marks the výdej
    # form (it also drives the over-stock layout + JS), so it implies finished.
    # výdej-EDIT has no over-stock layout but must still include finished, so it
    # sends an explicit ?finished=1 (plain Šarže layout, no empty Sklad cell).
    include_finished = show_stock_warn or request.GET.get("finished") == "1"
    form = MovementLineForm(
        prefix=f"lines-{index}", exclude_finished=not include_finished
    )
    return render(
        request,
        "inventory/_line_row.html",
        {
            "line_form": form,
            "index": index,
            "is_partial": True,
            "show_stock_warn": show_stock_warn,
        },
    )
