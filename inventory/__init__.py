"""Inventory app — the warehouse core (stock, movements, catalogue, dodáky).

Split from the former monolith modules into re-exporting packages per decision
0068 (and 0070 for the recursive ``views/movements/`` sub-package). Each package
exposes a stable import surface through its ``__init__.py`` — external code keeps
importing ``inventory.models.X`` / ``inventory.services.x`` /
``from inventory.views import …`` unchanged regardless of which submodule a name
actually lives in:

- ``models/``    — Branch, Product, Recipe, Movement, MovementLine, Stock, …
- ``services/``  — the business logic (apply/edit movement, dodák, mixing, …)
- ``views/``     — thin controllers (``movements/`` is a nested sub-package)
- ``forms/`` · ``admin/`` · ``tests/``

See ``context/architecture.md`` for the full package map and the recipe for
adding a screen / číselník / movement type.
"""
