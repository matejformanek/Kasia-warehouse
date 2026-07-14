"""Inventory views package.

Split from the former monolithic ``views.py`` (decision 0068), grouped by
feature. Cross-feature helpers live in ``_shared`` (``_require_vlastnik``,
``_dl_failed_at_current_version``, ``_safe_next``). Re-exported here so
``inventory/urls.py`` (``from . import views``; ``views.<name>``) and the tests
keep working unchanged.
"""

from .activity import activity_index
from .catalogue import (
    catalogue_index,
    product_archive,
    product_branch_add,
    product_branch_remove,
    product_create,
    product_detail,
    product_edit,
    product_reactivate,
    xls_import_confirm,
    xls_import_upload,
)
from .ciselniky import (
    branch_archive,
    branch_create,
    branch_edit,
    branch_index,
    branch_reactivate,
    customer_archive,
    customer_create,
    customer_edit,
    customer_index,
    customer_reactivate,
    supplier_archive,
    supplier_create,
    supplier_edit,
    supplier_index,
    supplier_reactivate,
)
from .dashboard import branch_dashboard, home
from .dodaci import (
    dodaci_list_detail,
    dodaci_list_index,
    dodaci_list_pdf,
    dodaci_list_resend,
    recipe_pdf,
)
from .email_log import email_log_detail, email_log_index, email_log_resend
from .inventura import inventura_edit, stock_adjust_edit
from .mixing import (
    mixing_job_cancel,
    mixing_job_create,
    mixing_job_detail,
    mixing_job_finish,
    mixing_job_index,
    mixing_job_start,
    mixing_plan_create,
    mixing_preview_partial,
)
from .movements import (
    _compute_overdraw,
    line_row_partial,
    movement_edit,
    movement_history,
    movement_saved,
    prijem_confirm,
    prijem_create,
    prijem_plan_cancel,
    vydej_create,
)
from .settings import settings_edit, settings_test_smtp
from .support import feedback_toggle_view, support_view
from .transfers import (
    planned_transfer_cancel,
    planned_transfer_create,
    planned_transfer_detail,
    planned_transfer_execute,
    planned_transfer_index,
)

__all__ = [
    "home",
    "branch_dashboard",
    "movement_saved",
    "movement_history",
    "prijem_create",
    "prijem_confirm",
    "prijem_plan_cancel",
    "vydej_create",
    "line_row_partial",
    "movement_edit",
    "_compute_overdraw",
    "catalogue_index",
    "product_detail",
    "product_create",
    "product_edit",
    "product_archive",
    "product_reactivate",
    "product_branch_add",
    "product_branch_remove",
    "xls_import_upload",
    "xls_import_confirm",
    "dodaci_list_index",
    "dodaci_list_detail",
    "dodaci_list_pdf",
    "recipe_pdf",
    "dodaci_list_resend",
    "email_log_index",
    "email_log_detail",
    "email_log_resend",
    "activity_index",
    "mixing_job_index",
    "mixing_job_create",
    "mixing_preview_partial",
    "mixing_job_detail",
    "mixing_job_finish",
    "mixing_job_cancel",
    "mixing_plan_create",
    "mixing_job_start",
    "settings_edit",
    "settings_test_smtp",
    "supplier_index",
    "supplier_create",
    "supplier_edit",
    "supplier_archive",
    "supplier_reactivate",
    "customer_index",
    "customer_create",
    "customer_edit",
    "customer_archive",
    "customer_reactivate",
    "branch_index",
    "branch_create",
    "branch_edit",
    "branch_archive",
    "branch_reactivate",
    "stock_adjust_edit",
    "inventura_edit",
    "planned_transfer_index",
    "planned_transfer_create",
    "planned_transfer_detail",
    "planned_transfer_execute",
    "planned_transfer_cancel",
    "support_view",
    "feedback_toggle_view",
]
