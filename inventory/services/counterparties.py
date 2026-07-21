"""Internal counterparty registry (decision 0068).

The system writes stock movements against seeded Customer/Supplier rows that
stand in for "the system itself". They were previously fetched by seven
near-identical ``objects.get(name=…, is_internal=…)`` helpers scattered across
the service modules; this centralizes the lookup, keyed by role.

Seed source of truth (migrations): ``micharna`` 0007, ``adjustment`` 0008,
``transfer`` 0010, ``order`` 0015, ``unknown_supplier`` 0024. ``transfer`` is
deliberately ``is_internal=False`` so the dodák auto-issue + e-mail hook fires
on its výdej leg (per 0044).
"""

from ..models import Customer, Supplier

# role -> (seeded name, is_internal)
_ROLES: dict[str, tuple[str, bool]] = {
    "micharna": ("Míchárna", True),
    "adjustment": ("Inventura / ruční úprava", True),
    "transfer": ("Převod mezi pobočkami", False),
    "order": ("Objednávka", True),
    # Per 0085: the default supplier on a DONE příjem when the operator picks
    # none („— Neuveden —" blank option). is_internal=True → hidden in the
    # picker, never triggers a dodák/e-mail.
    "unknown_supplier": ("Neuveden", True),
}


def customer(role: str) -> Customer:
    name, is_internal = _ROLES[role]
    return Customer.objects.get(name=name, is_internal=is_internal)


def supplier(role: str) -> Supplier:
    name, is_internal = _ROLES[role]
    return Supplier.objects.get(name=name, is_internal=is_internal)
