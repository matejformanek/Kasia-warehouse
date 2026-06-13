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
    """Generic logged-in user with branch=TYN. No role group — falls
    back to vlastník per accounts.User.is_vlastnik default. Pass 3a/b/c
    tests use this fixture and rely on the owner-dashboard routing
    that "unassigned → vlastník" produces."""
    User = get_user_model()
    return User.objects.create_user(
        email="user-tyn@example.cz",
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


@pytest.fixture
def user_obsluha_tyn(db, tyn):
    """Branch-staff user explicitly in the `obsluha` group + scoped to
    TYN. Routes to /pobocka/TYN/ on /."""
    from django.contrib.auth.models import Group

    User = get_user_model()
    u = User.objects.create_user(
        email="obsluha-tyn@example.cz",
        password="x" * 12,
        branch=tyn,
    )
    obsluha, _ = Group.objects.get_or_create(name="obsluha")
    u.groups.add(obsluha)
    return u


@pytest.fixture
def user_obsluha_sez(db, sez):
    from django.contrib.auth.models import Group

    User = get_user_model()
    u = User.objects.create_user(
        email="obsluha-sez@example.cz",
        password="x" * 12,
        branch=sez,
    )
    obsluha, _ = Group.objects.get_or_create(name="obsluha")
    u.groups.add(obsluha)
    return u


@pytest.fixture(autouse=True)
def _ensure_micharna_seed(db) -> None:
    """Re-seed the internal Míchárna Customer + Supplier rows.

    Migration 0007 inserts them, but `transaction=True` tests flush
    the DB without re-serializing the data; later transactional tests
    would otherwise crash when start_mixing_job fetches them.
    get_or_create is idempotent for the non-flushed case.
    """
    from inventory.models import Customer, Supplier

    # Re-seed Říčany (system-managed default odběratel per 0030) so
    # transaction=True tests that look it up by is_default_recipient
    # find it. Migration 0002 sets it but transactional flush wipes
    # data without serialize_rollback.
    Customer.objects.get_or_create(
        is_default_recipient=True,
        defaults={"name": "Říčany", "address": "Říčany u Prahy"},
    )
    Customer.objects.get_or_create(
        name="Míchárna",
        is_internal=True,
        defaults={"address": "interní výroba směsí"},
    )
    Supplier.objects.get_or_create(
        name="Míchárna",
        is_internal=True,
        defaults={"address": "interní výroba směsí"},
    )
    # Per 0041 — also re-seed the manual-stock-adjustment internal pair
    # (migration 0008) so apply_stock_adjustment can look them up
    # after a transactional flush.
    Customer.objects.get_or_create(
        name="Inventura / ruční úprava",
        is_internal=True,
        defaults={"address": "interní úprava stavu"},
    )
    Supplier.objects.get_or_create(
        name="Inventura / ruční úprava",
        is_internal=True,
        defaults={"address": "interní úprava stavu"},
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
