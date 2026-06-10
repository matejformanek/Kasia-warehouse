import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction

from inventory.models import Branch

User = get_user_model()


@pytest.mark.django_db
def test_create_user_with_email() -> None:
    user = User.objects.create_user(email="petr@example.cz", password="x" * 12)
    assert user.email == "petr@example.cz"
    assert user.username is None
    assert user.check_password("x" * 12)


@pytest.mark.django_db
def test_email_unique() -> None:
    User.objects.create_user(email="karolina@example.cz", password="x" * 12)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create_user(email="karolina@example.cz", password="y" * 12)


@pytest.mark.django_db
def test_create_superuser() -> None:
    admin = User.objects.create_superuser(email="admin@example.cz", password="x" * 12)
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.is_active is True


@pytest.mark.django_db
def test_user_branch_nullable_for_vlastnik() -> None:
    user = User.objects.create_user(email="vlastnik@example.cz", password="x" * 12)
    assert user.branch is None


@pytest.mark.django_db
def test_user_branch_assigned_for_obsluha() -> None:
    tyn = Branch.objects.get(code="TYN")
    user = User.objects.create_user(
        email="obsluha-tyn@example.cz",
        password="x" * 12,
        branch=tyn,
    )
    assert user.branch == tyn


@pytest.mark.django_db
def test_seed_migration_creates_groups() -> None:
    assert Group.objects.filter(name="vlastnik").exists()
    assert Group.objects.filter(name="obsluha").exists()
