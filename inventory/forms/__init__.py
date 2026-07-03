"""Inventory forms package.

Split from the former monolithic ``forms.py`` (decision 0068), grouped by
subsystem. Re-exported here so ``from inventory.forms import X`` keeps working.
No cross-module form inheritance — every base/subclass chain lives within its
own submodule.
"""

from .ciselniky import (
    BranchForm,
    CustomerForm,
    ProductForm,
    RecipeComponentForm,
    RecipeComponentFormSet,
    SupplierForm,
    ThresholdOverrideForm,
    ThresholdOverrideFormSet,
)
from .feedback import FeedbackForm
from .movement import (
    MovementEditLineFormSet,
    MovementLineForm,
    MovementLineFormSet,
    PrijemEditForm,
    PrijemForm,
    VydejEditForm,
    VydejForm,
    assert_no_future_date,
    kind_label,
)
from .planning import MixingPlanForm, PlannedTransferForm
from .recipe_import import (
    XLSImportReviewHeaderForm,
    XLSImportReviewLineForm,
    XLSImportReviewLineFormSet,
    XLSImportUploadForm,
)
from .settings import (
    SettingsForm,
    SettingsRecipientForm,
    SettingsRecipientFormSet,
    SmtpTestForm,
)

__all__ = [
    "PrijemForm",
    "VydejForm",
    "MovementLineForm",
    "MovementLineFormSet",
    "MovementEditLineFormSet",
    "PrijemEditForm",
    "VydejEditForm",
    "assert_no_future_date",
    "kind_label",
    "SettingsForm",
    "SettingsRecipientForm",
    "SettingsRecipientFormSet",
    "SmtpTestForm",
    "SupplierForm",
    "CustomerForm",
    "ProductForm",
    "RecipeComponentForm",
    "RecipeComponentFormSet",
    "BranchForm",
    "ThresholdOverrideForm",
    "ThresholdOverrideFormSet",
    "PlannedTransferForm",
    "MixingPlanForm",
    "FeedbackForm",
    "XLSImportUploadForm",
    "XLSImportReviewHeaderForm",
    "XLSImportReviewLineForm",
    "XLSImportReviewLineFormSet",
]
