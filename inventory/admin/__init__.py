"""Inventory admin package.

Split from the former monolithic ``admin.py`` (decision 0068). Importing each
submodule here runs its ``@admin.register`` decorators, so Django's admin
autodiscover registers every ModelAdmin exactly as before.
"""

from . import (  # noqa: F401
    catalogue,
    config,
    dodaci,
    feedback,
    mixing,
    movement,
    planning,
)
