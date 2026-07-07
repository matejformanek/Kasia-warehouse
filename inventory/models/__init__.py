"""Inventory models package.

Split from the former monolithic ``models.py`` (decision 0068). Import order
matters: ``catalogue`` has no intra-app deps; ``movement`` depends on it;
``dodaci``/``mixing``/``planning`` depend on both. Re-exported here so external
code keeps importing ``from inventory.models import X`` unchanged. Migrations are
unaffected — they key on ``app_label`` + model name, not module path. Nested
``TextChoices`` (e.g. ``Movement.Kind``) ride along with their model class.
"""

from .catalogue import (
    Branch,
    Customer,
    Product,
    RecipeComponent,
    Stock,
    StockThresholdOverride,
    Supplier,
)
from .config import Settings, SettingsRecipient
from .dodaci import DodaciList, DodaciListNumberSequence
from .email_log import EmailLog
from .feedback import Feedback
from .mixing import MixingJob, MixingJobLine
from .movement import Movement, MovementAudit, MovementLine
from .planning import PlannedOrder, PlannedTransfer

__all__ = [
    "Branch",
    "Customer",
    "Supplier",
    "Product",
    "RecipeComponent",
    "Stock",
    "StockThresholdOverride",
    "Movement",
    "MovementLine",
    "MovementAudit",
    "DodaciListNumberSequence",
    "DodaciList",
    "EmailLog",
    "MixingJob",
    "MixingJobLine",
    "PlannedTransfer",
    "PlannedOrder",
    "Settings",
    "SettingsRecipient",
    "Feedback",
]
