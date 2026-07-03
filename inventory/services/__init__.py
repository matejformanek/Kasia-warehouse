"""Inventory services package — the business-logic layer.

Split from the former monolithic ``services.py`` (decision 0068), layered to be
acyclic: ``stock`` / ``email`` / ``recipe_import`` (no intra-service deps) →
``dodaci_list`` → ``movement`` → ``mixing`` / ``adjustment`` / ``transfer`` /
``receipt`` / ``reorder``. Re-exported here so callers keep using
``inventory.services.<name>`` and ``from inventory.services import <name>``
unchanged — including the private helpers that tests and management commands
import directly.
"""

from .adjustment import apply_stock_adjustment
from .dodaci_list import (
    _amounts_summing_to,
    _create_dodaci_list_for_movement,
    _reserve_dodak_number,
    render_dodaci_list_pdf,
    render_recipe_pdf,
    send_dodaci_list_email,
)
from .email import (
    _active_dodak_recipients,
    _active_low_stock_recipients,
    _assert_recipients_set,
    _smtp_connection_from_settings,
)
from .mixing import (
    cancel_mixing_job,
    finish_mixing_job,
    plan_mixing_job,
    record_completed_mixing_job,
    start_mixing_job,
)
from .movement import apply_movement, edit_movement
from .receipt import confirm_planned_receipt
from .recipe_import import (
    ParsedRecipe,
    ParsedRecipeLine,
    create_mixture_from_review,
    parse_recipe_xls,
)
from .reorder import (
    LowStockRow,
    effective_kg,
    low_stock_rows,
    planned_prijem_lines_for,
    reserved_kg,
    seed_branch_carriage_for_product,
    send_low_stock_summary,
    threshold_for,
)
from .stock import _apply_line_to_stock
from .transfer import cancel_planned_transfer, execute_planned_transfer

__all__ = [
    "apply_movement",
    "edit_movement",
    "_apply_line_to_stock",
    "_smtp_connection_from_settings",
    "_active_dodak_recipients",
    "_active_low_stock_recipients",
    "_assert_recipients_set",
    "_reserve_dodak_number",
    "_create_dodaci_list_for_movement",
    "_amounts_summing_to",
    "render_dodaci_list_pdf",
    "render_recipe_pdf",
    "send_dodaci_list_email",
    "plan_mixing_job",
    "start_mixing_job",
    "finish_mixing_job",
    "cancel_mixing_job",
    "record_completed_mixing_job",
    "apply_stock_adjustment",
    "LowStockRow",
    "threshold_for",
    "reserved_kg",
    "effective_kg",
    "low_stock_rows",
    "seed_branch_carriage_for_product",
    "planned_prijem_lines_for",
    "send_low_stock_summary",
    "execute_planned_transfer",
    "cancel_planned_transfer",
    "confirm_planned_receipt",
    "ParsedRecipe",
    "ParsedRecipeLine",
    "create_mixture_from_review",
    "parse_recipe_xls",
]
