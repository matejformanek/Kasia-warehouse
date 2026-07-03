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
    form = MovementLineForm(prefix=f"lines-{index}")
    show_stock_warn = request.GET.get("warn") == "1"
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
