"""Shared pytest fixtures for inventory tests.

Seed-aware: fixtures fetch already-seeded rows (Branch TYN/SEZ, Říčany
Customer) via `.objects.get(...)` rather than creating them. The
`0002_seed_branches_and_ricany` migration already inserts those rows and
the partial-unique constraints on Branch.code / Customer.is_default_recipient
would refuse a duplicate.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from inventory.models import Branch, Customer, Product


@pytest.fixture
def tyn(db) -> Branch:
    return Branch.objects.get(code="TYN")


@pytest.fixture
def sez(db) -> Branch:
    return Branch.objects.get(code="SEZ")


@pytest.fixture
def ricany(db) -> Customer:
    return Customer.objects.get(is_default_recipient=True)


@pytest.fixture
def supplier(db):
    from inventory.models import Supplier
    return Supplier.objects.create(name="Dodavatel A")


@pytest.fixture
def pepper(db) -> Product:
    return Product.objects.create(name_cs="Pepř černý", kind=Product.Kind.RAW_SPICE)


@pytest.fixture
def paprika(db) -> Product:
    return Product.objects.create(name_cs="Paprika sladká", kind=Product.Kind.RAW_SPICE)


@pytest.fixture
def user_tyn(db, tyn):
    User = get_user_model()
    return User.objects.create_user(
        email="obsluha-tyn@example.cz",
        password="x" * 12,
        branch=tyn,
    )


@pytest.fixture
def user_vlastnik(db):
    User = get_user_model()
    return User.objects.create_user(
        email="vlastnik@example.cz",
        password="x" * 12,
    )
