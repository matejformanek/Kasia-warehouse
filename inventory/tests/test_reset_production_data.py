"""Tests for the go-live production wipe command (decision 0087).

The autouse conftest fixtures (`_ensure_micharna_seed`, `settings_with_recipients`)
seed the reference data that must survive: the five internal counterparties,
Říčany, the Settings singleton + two recipients. These tests build a rich
operational graph on top (movements, dodák, mixing job, executed transfer,
feedback, screen visits) and assert `reset_production_data` deletes everything
outside the keep-set in a PROTECT-safe order.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from inventory.models import (
    Customer,
    DodaciList,
    DodaciListNumberSequence,
    EmailLog,
    Feedback,
    MixingJob,
    Movement,
    MovementLine,
    PlannedTransfer,
    Product,
    RecipeComponent,
    ScreenVisit,
    Stock,
    StockThresholdOverride,
    Supplier,
)
from inventory.services import (
    apply_movement,
    execute_planned_transfer,
    start_mixing_job,
)
from inventory.tests._support import _LOCMEM_EMAIL

User = get_user_model()

KEEP_EMAILS = (
    "admin@kasia.cz",
    "petr@kasia.cz",
    "karolina@kasia.cz",
    "matej.formanek@kasia.cz",
)


@pytest.fixture
def kept_users(db):
    """The four keep-set users; admin is the superuser."""
    admin = User.objects.create_superuser(
        email="admin@kasia.cz", password="x" * 12
    )
    petr = User.objects.create_user(email="petr@kasia.cz", password="x" * 12)
    karolina = User.objects.create_user(
        email="karolina@kasia.cz", password="x" * 12
    )
    matej = User.objects.create_user(
        email="matej.formanek@kasia.cz", password="x" * 12
    )
    return {"admin": admin, "petr": petr, "karolina": karolina, "matej": matej}


@pytest.fixture
def populated(db, kept_users, tyn, sez, ricany, pepper, paprika, supplier):
    """Build a full operational graph that exercises every PROTECT FK.

    supplier fixture = "Dodavatel A" (non-internal → must be deleted).
    Also creates a non-kept obsluha user.
    """
    creator = kept_users["karolina"]

    # A non-kept user (test / shadow-run staff account).
    nonkept = User.objects.create_user(
        email="tyn@kasia.local", password="x" * 12, branch=tyn
    )

    # Initial stocking at TYN (příjem Movement + Stock).
    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 7, 1),
            dodavatel=supplier,
        ),
        lines=[
            MovementLine(product=pepper, quantity_kg=Decimal("25.000")),
            MovementLine(product=paprika, quantity_kg=Decimal("20.000")),
        ],
        user=creator,
    )

    # Mixture + recipe, then a running mixing job (consume Movement +
    # MixingJobLine snapshot).
    mixture = Product.objects.create(
        name_cs="Testovací směs", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture,
        component_product=paprika,
        ratio=Decimal("0.600000"),
    )
    RecipeComponent.objects.create(
        mixture_product=mixture,
        component_product=pepper,
        ratio=Decimal("0.400000"),
    )
    start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("3.000"), user=creator
    )

    # Výdej to Říčany → DodaciList + EmailLog + number sequence.
    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 7, 2),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=creator,
    )

    # An executed inter-branch transfer → paired Movements with transfer FK
    # (exercises Movement.transfer → PlannedTransfer PROTECT ordering).
    pt = PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("2.000"),
        scheduled_for=date(2026, 7, 3),
        created_by=creator,
    )
    execute_planned_transfer(pt, executed_by=creator)

    # A test customer (non-internal → deleted).
    Customer.objects.create(name="Hospůdka U Lípy", address="Hradec Králové")

    # Threshold override, feedback, screen visits.
    StockThresholdOverride.objects.create(
        product=pepper, branch=tyn, threshold_kg=Decimal("5.000")
    )
    Feedback.objects.create(created_by=nonkept, description="test hlášení")
    ScreenVisit.objects.create(
        user=nonkept, url_name="home", path="/sklad/"
    )
    return {"nonkept": nonkept, "creator": creator, "mixture": mixture}


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_dry_run_mutates_nothing(populated) -> None:
    before = {
        "users": User.objects.count(),
        "products": Product.objects.count(),
        "movements": Movement.objects.count(),
        "stock": Stock.objects.count(),
        "dodaci": DodaciList.objects.count(),
        "mixing": MixingJob.objects.count(),
        "customers": Customer.objects.count(),
        "suppliers": Supplier.objects.count(),
    }
    assert before["movements"] > 0  # sanity: graph really was built

    call_command("reset_production_data")  # no --commit

    assert User.objects.count() == before["users"]
    assert Product.objects.count() == before["products"]
    assert Movement.objects.count() == before["movements"]
    assert Stock.objects.count() == before["stock"]
    assert DodaciList.objects.count() == before["dodaci"]
    assert MixingJob.objects.count() == before["mixing"]
    assert Customer.objects.count() == before["customers"]
    assert Supplier.objects.count() == before["suppliers"]


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_commit_wipes_operational_and_catalogue(populated) -> None:
    call_command("reset_production_data", "--commit")

    # Everything operational + entered-catalogue gone.
    assert Movement.objects.count() == 0
    assert MovementLine.objects.count() == 0
    assert DodaciList.objects.count() == 0
    assert DodaciListNumberSequence.objects.count() == 0
    assert EmailLog.objects.count() == 0
    assert MixingJob.objects.count() == 0
    assert PlannedTransfer.objects.count() == 0
    assert Stock.objects.count() == 0
    assert StockThresholdOverride.objects.count() == 0
    assert Product.objects.count() == 0
    assert RecipeComponent.objects.count() == 0
    assert Feedback.objects.count() == 0
    assert ScreenVisit.objects.count() == 0

    # Keep-set survives.
    assert set(User.objects.values_list("email", flat=True)) == set(KEEP_EMAILS)
    assert Customer.objects.filter(is_default_recipient=True).exists()  # Říčany
    # Test customer/supplier gone; internal counterparties kept.
    assert not Customer.objects.filter(name="Hospůdka U Lípy").exists()
    assert not Supplier.objects.filter(name="Dodavatel A").exists()
    assert Customer.objects.filter(name="Míchárna", is_internal=True).exists()
    assert Supplier.objects.filter(name="Neuveden", is_internal=True).exists()
    assert Supplier.objects.filter(name="Objednávka", is_internal=True).exists()


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_kept_superuser_survives(populated, kept_users) -> None:
    call_command("reset_production_data", "--commit")
    admin = User.objects.get(email="admin@kasia.cz")
    assert admin.is_superuser
    # Password untouched — still authenticates.
    assert admin.check_password("x" * 12)


@pytest.mark.django_db(transaction=True)
def test_guard_aborts_without_superuser_in_keep_set(db, tyn) -> None:
    # Kept users exist but none is a superuser.
    for email in KEEP_EMAILS:
        User.objects.create_user(email=email, password="x" * 12)
    # A stray row that would be deleted — proves the abort is before mutation.
    Product.objects.create(name_cs="Nesmí zmizet", kind=Product.Kind.RAW_SPICE)

    with pytest.raises(CommandError, match="superuser"):
        call_command("reset_production_data", "--commit")

    assert Product.objects.filter(name_cs="Nesmí zmizet").exists()


@pytest.mark.django_db(transaction=True)
def test_guard_aborts_when_kept_user_missing(db) -> None:
    # Only three of the four keep-set users exist (+ a superuser so the
    # superuser check isn't what trips first).
    User.objects.create_superuser(email="admin@kasia.cz", password="x" * 12)
    User.objects.create_user(email="petr@kasia.cz", password="x" * 12)
    User.objects.create_user(email="karolina@kasia.cz", password="x" * 12)
    # matej.formanek@kasia.cz deliberately absent.

    with pytest.raises(CommandError, match="missing"):
        call_command("reset_production_data", "--commit")


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_number_sequence_reset_lets_next_dodak_start_at_0001(
    populated, tyn, ricany, pepper, kept_users
) -> None:
    # Sequence advanced during the populated graph.
    assert DodaciListNumberSequence.objects.exists()

    call_command("reset_production_data", "--commit")
    assert not DodaciListNumberSequence.objects.exists()

    # Re-enter a product + stock + výdej; the first real dodák is 0001.
    salt = Product.objects.create(name_cs="Sůl", kind=Product.Kind.RAW_SPICE)
    Stock.objects.create(product=salt, branch=tyn, quantity=Decimal("10.000"))
    mv = apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date.today(),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=salt, quantity_kg=Decimal("1.000"))],
        user=kept_users["karolina"],
    )
    dl = DodaciList.objects.get(movement=mv)
    assert dl.cislo.endswith("-0001")
