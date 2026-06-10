from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client

from inventory.models import Branch, Customer, Product, RecipeComponent, Stock


def test_healthz_returns_200() -> None:
    response = Client().get("/healthz")
    assert response.status_code == 200
    assert response.content == b"ok"


@pytest.mark.django_db
def test_branch_creation_and_code_unique() -> None:
    # TYN + SEZ already exist via seed migration.
    assert Branch.objects.filter(code="TYN").exists()
    assert Branch.objects.filter(code="SEZ").exists()
    with pytest.raises(IntegrityError):
        Branch.objects.create(code="TYN", name="duplicate")


@pytest.mark.django_db
def test_product_active_name_unique() -> None:
    Product.objects.create(name_cs="Pepř černý", kind=Product.Kind.RAW_SPICE)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Product.objects.create(name_cs="Pepř černý", kind=Product.Kind.RAW_SPICE)
    # Archived row with the same name is allowed per screens/04.
    first = Product.objects.get(name_cs="Pepř černý")
    first.is_active = False
    first.save()
    Product.objects.create(name_cs="Pepř černý", kind=Product.Kind.RAW_SPICE)


@pytest.mark.django_db
def test_stock_unique_per_product_branch() -> None:
    tyn = Branch.objects.get(code="TYN")
    product = Product.objects.create(name_cs="Kmín", kind=Product.Kind.RAW_SPICE)
    Stock.objects.create(product=product, branch=tyn, quantity=Decimal("1.000"))
    with pytest.raises(IntegrityError):
        Stock.objects.create(product=product, branch=tyn, quantity=Decimal("2.000"))


@pytest.mark.django_db
def test_stock_non_negative_check() -> None:
    tyn = Branch.objects.get(code="TYN")
    product = Product.objects.create(name_cs="Bobkový list", kind=Product.Kind.RAW_SPICE)
    with pytest.raises(IntegrityError):
        Stock.objects.create(product=product, branch=tyn, quantity=Decimal("-0.001"))


@pytest.mark.django_db
def test_stock_decimal_precision() -> None:
    tyn = Branch.objects.get(code="TYN")
    product = Product.objects.create(name_cs="Skořice", kind=Product.Kind.RAW_SPICE)
    Stock.objects.create(product=product, branch=tyn, quantity=Decimal("1.234"))
    fetched = Stock.objects.get(product=product, branch=tyn)
    assert fetched.quantity == Decimal("1.234")


@pytest.mark.django_db
def test_recipe_component_ratio_bounds() -> None:
    mixture = Product.objects.create(name_cs="Gulášové koření", kind=Product.Kind.MIXTURE)
    component = Product.objects.create(name_cs="Paprika sladká", kind=Product.Kind.RAW_SPICE)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RecipeComponent.objects.create(
                mixture_product=mixture,
                component_product=component,
                ratio=Decimal("0"),
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RecipeComponent.objects.create(
                mixture_product=mixture,
                component_product=component,
                ratio=Decimal("1.000001"),
            )


@pytest.mark.django_db
def test_recipe_component_requires_mixture_kind() -> None:
    not_a_mixture = Product.objects.create(name_cs="Sůl", kind=Product.Kind.RAW_SPICE)
    component = Product.objects.create(name_cs="Pepř bílý", kind=Product.Kind.RAW_SPICE)
    rc = RecipeComponent(
        mixture_product=not_a_mixture,
        component_product=component,
        ratio=Decimal("0.5"),
    )
    with pytest.raises(ValidationError):
        rc.clean()


@pytest.mark.django_db
def test_recipe_component_no_self_cycle() -> None:
    mixture = Product.objects.create(name_cs="Cyklická směs", kind=Product.Kind.MIXTURE)
    rc = RecipeComponent(
        mixture_product=mixture,
        component_product=mixture,
        ratio=Decimal("0.5"),
    )
    with pytest.raises(ValidationError):
        rc.clean()


@pytest.mark.django_db
def test_seed_migration_creates_branches_and_ricany() -> None:
    assert Branch.objects.filter(code="TYN").exists()
    assert Branch.objects.filter(code="SEZ").exists()
    defaults = Customer.objects.filter(is_default_recipient=True)
    assert defaults.count() == 1
    assert defaults.first().name == "Říčany"


@pytest.mark.django_db
def test_default_customer_partial_unique() -> None:
    other = Customer.objects.create(name="Jiný odběratel")
    other.is_default_recipient = True
    with pytest.raises(IntegrityError):
        other.save()
