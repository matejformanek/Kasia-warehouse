"""Movements views sub-package.

Split from the former ``inventory/views/movements.py`` module (decision 0070 —
recursive sub-packaging, same re-export contract as 0068). Grouped by flow:
``history`` (movement_saved + movement_history), ``prijem``, ``vydej``, ``edit``,
``partials``; movement-form shared helpers live in ``._shared`` (package-local,
distinct from the cross-view ``inventory/views/_shared``).

Re-exported here so ``from inventory.views.movements import X`` keeps working, and
so ``inventory/views/__init__.py`` (which re-exports from ``.movements``) resolves
unchanged. ``_compute_overdraw`` is private-looking but public — re-exported and
referenced by ``inventory/tests/test_reorder.py``.
"""

from .edit import movement_edit
from .history import movement_history, movement_saved
from .partials import line_row_partial
from .prijem import prijem_confirm, prijem_create, prijem_plan_cancel
from .vydej import _compute_overdraw, vydej_create

__all__ = [
    "movement_saved",
    "movement_history",
    "prijem_create",
    "prijem_confirm",
    "prijem_plan_cancel",
    "vydej_create",
    "line_row_partial",
    "movement_edit",
    "_compute_overdraw",
]
