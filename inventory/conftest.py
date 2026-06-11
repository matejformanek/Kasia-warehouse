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

from inventory.models import Branch, Customer, Product, Settings


@pytest.fixture
def tyn(db) -> Branch:
    # get_or_create — seed migrations populate the row on first setup, but
    # tests marked `django_db(transaction=True)` flush + don't re-serialize
    # by default, so a later transactional test would otherwise crash.
    branch, _ = Branch.objects.get_or_create(
        code="TYN", defaults={"name": "Týniště nad Orlicí"}
    )
    return branch


@pytest.fixture
def sez(db) -> Branch:
    branch, _ = Branch.objects.get_or_create(
        code="SEZ", defaults={"name": "Sezimovo Ústí"}
    )
    return branch


@pytest.fixture
def ricany(db) -> Customer:
    customer, _ = Customer.objects.get_or_create(
        is_default_recipient=True,
        defaults={"name": "Říčany", "address": "Říčany u Prahy"},
    )
    return customer


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


@pytest.fixture(autouse=True)
def settings_with_recipients(db) -> Settings:
    """Populate Settings.recipient_petr / recipient_karolina for all tests.

    The seed migration leaves recipients blank intentionally (operator
    fills them on first run). Pass 2's vydej hook refuses to apply a
    výdej while either recipient is empty; auto-applying this fixture
    keeps Pass 1 tests passing without each one repeating the boilerplate.

    Tests that need to verify the empty-recipient guard override these
    fields directly and re-save.
    """
    # Settings.load() will get_or_create — survives a flushed Settings
    # table across transaction=True tests.
    s = Settings.load()
    s.recipient_petr = "petr@example.cz"
    s.recipient_karolina = "karolina@example.cz"
    s.email_from_address = "no-reply@example.cz"
    s.email_from_name = "Kasia vera"
    s.save()
    return s
