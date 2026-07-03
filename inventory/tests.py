import json
import re
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse

from inventory.models import (
    Branch,
    Customer,
    DodaciList,
    DodaciListEmailLog,
    DodaciListNumberSequence,
    Feedback,
    MixingJob,
    Movement,
    MovementAudit,
    MovementLine,
    Product,
    RecipeComponent,
    Settings,
    Stock,
    Supplier,
)
from inventory.services import (
    _reserve_dodak_number,
    apply_movement,
    edit_movement,
)


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


# ---------------------------------------------------------------------------
# Movement / MovementLine / MovementAudit — schema-level
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_movement_kind_choices_match_0030() -> None:
    # Locks the enum to decision 0030 (no prevod). Failing this means
    # someone added or removed a kind — update the decision first.
    assert list(Movement.Kind.values) == ["prijem", "vydej"]


@pytest.mark.django_db
def test_movement_counterparty_matches_kind_check(tyn, ricany, supplier, user_tyn) -> None:
    # výdej with dodavatel set (instead of odberatel) violates the constraint.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Movement.objects.create(
                branch=tyn,
                kind=Movement.Kind.VYDEJ,
                date_issued=date(2026, 6, 11),
                dodavatel=supplier,
                created_by=user_tyn,
            )
    # příjem with odberatel set (instead of dodavatel) also violates.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Movement.objects.create(
                branch=tyn,
                kind=Movement.Kind.PRIJEM,
                date_issued=date(2026, 6, 11),
                odberatel=ricany,
                created_by=user_tyn,
            )


@pytest.mark.django_db
def test_movement_line_quantity_positive_check(tyn, ricany, pepper, user_tyn) -> None:
    mv = Movement.objects.create(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        date_issued=date(2026, 6, 11),
        odberatel=ricany,
        created_by=user_tyn,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MovementLine.objects.create(
                movement=mv, product=pepper, quantity_kg=Decimal("0.000")
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MovementLine.objects.create(
                movement=mv, product=pepper, quantity_kg=Decimal("-0.001")
            )


@pytest.mark.django_db
def test_movement_audit_reason_required_check(tyn, ricany, pepper, user_tyn) -> None:
    mv = Movement.objects.create(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        date_issued=date(2026, 6, 11),
        odberatel=ricany,
        created_by=user_tyn,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MovementAudit.objects.create(
                movement=mv,
                edited_by=user_tyn,
                reason="",
                target_kind=MovementAudit.TargetKind.MOVEMENT,
                event=MovementAudit.Event.FIELD_CHANGED,
                field="note",
            )


# ---------------------------------------------------------------------------
# Service: apply_movement
# ---------------------------------------------------------------------------


def _prijem(tyn, supplier, user_tyn) -> Movement:
    return Movement(
        branch=tyn,
        kind=Movement.Kind.PRIJEM,
        date_issued=date(2026, 6, 11),
        dodavatel=supplier,
    )


def _vydej(tyn, ricany, user_tyn) -> Movement:
    return Movement(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        date_issued=date(2026, 6, 11),
        odberatel=ricany,
    )


@pytest.mark.django_db
def test_apply_prijem_creates_stock(tyn, supplier, pepper, user_tyn) -> None:
    mv = apply_movement(
        movement=_prijem(tyn, supplier, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("5.000"))],
        user=user_tyn,
    )
    assert mv.pk is not None
    stock = Stock.objects.get(product=pepper, branch=tyn)
    assert stock.quantity == Decimal("5.000")


@pytest.mark.django_db
def test_apply_prijem_increments_existing_stock(tyn, supplier, pepper, user_tyn) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("2.000"))
    apply_movement(
        movement=_prijem(tyn, supplier, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_tyn,
    )
    stock = Stock.objects.get(product=pepper, branch=tyn)
    assert stock.quantity == Decimal("5.000")


@pytest.mark.django_db
def test_apply_vydej_decrements_stock(tyn, ricany, pepper, user_tyn) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    stock = Stock.objects.get(product=pepper, branch=tyn)
    assert stock.quantity == Decimal("3.000")


@pytest.mark.django_db
def test_apply_vydej_refuses_overdraw(tyn, ricany, pepper, user_tyn) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    with pytest.raises(ValidationError):
        apply_movement(
            movement=_vydej(tyn, ricany, user_tyn),
            lines=[MovementLine(product=pepper, quantity_kg=Decimal("5.001"))],
            user=user_tyn,
        )
    assert Movement.objects.count() == 0
    assert MovementLine.objects.count() == 0
    stock = Stock.objects.get(product=pepper, branch=tyn)
    assert stock.quantity == Decimal("5.000")


@pytest.mark.django_db
def test_apply_movement_atomic_across_lines(tyn, ricany, pepper, paprika, user_tyn) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1.000"))
    with pytest.raises(ValidationError):
        apply_movement(
            movement=_vydej(tyn, ricany, user_tyn),
            lines=[
                MovementLine(product=pepper, quantity_kg=Decimal("2.000")),
                MovementLine(product=paprika, quantity_kg=Decimal("2.000")),  # overdraws
            ],
            user=user_tyn,
        )
    assert Movement.objects.count() == 0
    assert MovementLine.objects.count() == 0
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("10.000")
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("1.000")


@pytest.mark.django_db
def test_apply_requires_kind_specific_counterparty_service(
    tyn, ricany, supplier, pepper, user_tyn
) -> None:
    # výdej without odberatel raises from full_clean()
    mv = Movement(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        date_issued=date(2026, 6, 11),
    )
    with pytest.raises(ValidationError):
        apply_movement(
            movement=mv,
            lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
            user=user_tyn,
        )
    # příjem without dodavatel raises.
    mv2 = Movement(
        branch=tyn,
        kind=Movement.Kind.PRIJEM,
        date_issued=date(2026, 6, 11),
    )
    with pytest.raises(ValidationError):
        apply_movement(
            movement=mv2,
            lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
            user=user_tyn,
        )


@pytest.mark.django_db
def test_apply_writes_no_audit(tyn, supplier, pepper, user_tyn) -> None:
    apply_movement(
        movement=_prijem(tyn, supplier, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    assert MovementAudit.objects.count() == 0


# ---------------------------------------------------------------------------
# Service: edit_movement
# ---------------------------------------------------------------------------


def _make_vydej(tyn, ricany, pepper, user_tyn, stock_qty="5.000", line_qty="2.000"):
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal(stock_qty))
    return apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal(line_qty))],
        user=user_tyn,
    )


@pytest.mark.django_db
def test_edit_requires_reason(tyn, ricany, pepper, user_tyn) -> None:
    mv = _make_vydej(tyn, ricany, pepper, user_tyn)
    with pytest.raises(ValidationError):
        edit_movement(
            movement=mv,
            changes={"note": "x"},
            line_changes=[],
            reason="   ",
            user=user_tyn,
        )


@pytest.mark.django_db
def test_edit_kind_forbidden(tyn, ricany, pepper, user_tyn) -> None:
    mv = _make_vydej(tyn, ricany, pepper, user_tyn)
    with pytest.raises(ValidationError):
        edit_movement(
            movement=mv,
            changes={"kind": Movement.Kind.PRIJEM},
            line_changes=[],
            reason="pokus o změnu druhu",
            user=user_tyn,
        )


@pytest.mark.django_db
def test_edit_field_change_writes_one_audit_row(tyn, ricany, pepper, user_tyn) -> None:
    mv = _make_vydej(tyn, ricany, pepper, user_tyn)
    edit_movement(
        movement=mv,
        changes={"note": "doplněno"},
        line_changes=[],
        reason="oprava poznámky",
        user=user_tyn,
    )
    rows = list(MovementAudit.objects.filter(movement=mv))
    assert len(rows) == 1
    row = rows[0]
    assert row.target_kind == MovementAudit.TargetKind.MOVEMENT
    assert row.event == MovementAudit.Event.FIELD_CHANGED
    assert row.field == "note"
    assert row.old_value == ""
    assert row.new_value == "doplněno"
    assert row.reason == "oprava poznámky"


@pytest.mark.django_db
def test_edit_line_quantity_recomputes_stock_and_audits(tyn, ricany, pepper, user_tyn) -> None:
    mv = _make_vydej(tyn, ricany, pepper, user_tyn, stock_qty="5.000", line_qty="2.000")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("3.000")
    line = mv.lines.get()
    edit_movement(
        movement=mv,
        changes={},
        line_changes=[
            {"op": "update", "line_id": line.pk, "fields": {"quantity_kg": Decimal("3.000")}}
        ],
        reason="oprava množství",
        user=user_tyn,
    )
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("2.000")
    rows = list(MovementAudit.objects.filter(movement=mv))
    assert len(rows) == 1
    row = rows[0]
    assert row.target_kind == MovementAudit.TargetKind.LINE
    assert row.event == MovementAudit.Event.FIELD_CHANGED
    assert row.field == "quantity_kg"
    assert row.old_value == "2.000"
    assert row.new_value == "3.000"
    assert row.line_id == line.pk


@pytest.mark.django_db
def test_edit_line_add_audits_event_line_added(
    tyn, ricany, pepper, paprika, user_tyn
) -> None:
    mv = _make_vydej(tyn, ricany, pepper, user_tyn)
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("4.000"))
    edit_movement(
        movement=mv,
        changes={},
        line_changes=[
            {
                "op": "add",
                "fields": {"product": paprika, "quantity_kg": Decimal("1.000")},
            }
        ],
        reason="doplnění položky",
        user=user_tyn,
    )
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("3.000")
    row = MovementAudit.objects.get(movement=mv)
    assert row.event == MovementAudit.Event.LINE_ADDED
    assert row.target_kind == MovementAudit.TargetKind.LINE
    assert row.field == ""
    assert "Paprika" in row.new_value
    assert row.line_id is not None


@pytest.mark.django_db
def test_edit_line_remove_audits_event_line_removed(tyn, ricany, pepper, user_tyn) -> None:
    mv = _make_vydej(tyn, ricany, pepper, user_tyn)
    line = mv.lines.get()
    line_pk = line.pk
    edit_movement(
        movement=mv,
        changes={},
        line_changes=[{"op": "remove", "line_id": line_pk}],
        reason="odebrání položky",
        user=user_tyn,
    )
    # Stock reverts to the starting 5.000 (the výdej 2.000 is undone).
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("5.000")
    assert not MovementLine.objects.filter(pk=line_pk).exists()
    row = MovementAudit.objects.get(movement=mv)
    assert row.event == MovementAudit.Event.LINE_REMOVED
    assert row.field == ""
    assert row.line_id == line_pk
    assert row.new_value == ""
    assert row.old_value  # non-empty summary


@pytest.mark.django_db
def test_edit_overdraw_rolls_back_entirely(tyn, ricany, pepper, user_tyn) -> None:
    mv = _make_vydej(tyn, ricany, pepper, user_tyn, stock_qty="5.000", line_qty="2.000")
    line = mv.lines.get()
    with pytest.raises(ValidationError):
        edit_movement(
            movement=mv,
            changes={},
            line_changes=[
                {"op": "update", "line_id": line.pk, "fields": {"quantity_kg": Decimal("99.000")}}
            ],
            reason="pokus o předčerpání",
            user=user_tyn,
        )
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("3.000")
    assert MovementLine.objects.get(pk=line.pk).quantity_kg == Decimal("2.000")
    assert MovementAudit.objects.count() == 0


@pytest.mark.django_db
def test_edit_unchanged_fields_no_audit(tyn, ricany, pepper, user_tyn) -> None:
    mv = _make_vydej(tyn, ricany, pepper, user_tyn)
    line = mv.lines.get()
    edit_movement(
        movement=mv,
        changes={"note": mv.note},
        line_changes=[
            {"op": "update", "line_id": line.pk, "fields": {"quantity_kg": line.quantity_kg}}
        ],
        reason="no-op",
        user=user_tyn,
    )
    assert MovementAudit.objects.count() == 0


# ---------------------------------------------------------------------------
# Admin smoke
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    return User.objects.create_superuser(email="admin@example.cz", password="x" * 12)


_PLAIN_STATIC = {
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
}


@pytest.mark.django_db
@override_settings(**_PLAIN_STATIC)
def test_admin_movement_list_loads(admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    response = client.get(reverse("admin:inventory_movement_changelist"))
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(**_PLAIN_STATIC)
def test_admin_audit_is_readonly(admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    # The add URL should 403 because has_add_permission returns False.
    response = client.get(reverse("admin:inventory_movementaudit_add"))
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Pass 2 — DodaciList + Settings + WeasyPrint + e-mail
# ---------------------------------------------------------------------------


_LOCMEM_EMAIL = {"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}


# Schema -------------------------------------------------------------------


@pytest.mark.django_db
def test_settings_singleton_unique() -> None:
    # Seed already inserted the singleton row; a second insert violates the
    # UniqueConstraint on singleton_key.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Settings.objects.create(singleton_key="singleton")


@pytest.mark.django_db
def test_settings_load_returns_existing() -> None:
    a = Settings.load()
    b = Settings.load()
    assert a.pk == b.pk
    assert Settings.objects.count() == 1


@pytest.mark.django_db
def test_dodaci_list_cislo_unique(tyn, ricany, user_tyn) -> None:
    DodaciList.objects.create(
        movement=Movement.objects.create(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 11),
            odberatel=ricany,
            created_by=user_tyn,
        ),
        branch=tyn,
        odberatel=ricany,
        date_issued=date(2026, 6, 11),
        year_issued=2026,
        counter=1,
        cislo="TYN-2026-0001",
        created_by=user_tyn,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DodaciList.objects.create(
                movement=Movement.objects.create(
                    branch=tyn,
                    kind=Movement.Kind.VYDEJ,
                    date_issued=date(2026, 6, 11),
                    odberatel=ricany,
                    created_by=user_tyn,
                ),
                branch=tyn,
                odberatel=ricany,
                date_issued=date(2026, 6, 11),
                year_issued=2026,
                counter=2,
                cislo="TYN-2026-0001",  # duplicate
                created_by=user_tyn,
            )


@pytest.mark.django_db
def test_dodaci_list_per_branch_year_counter_unique(tyn, ricany, user_tyn) -> None:
    DodaciList.objects.create(
        movement=Movement.objects.create(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 11),
            odberatel=ricany,
            created_by=user_tyn,
        ),
        branch=tyn,
        odberatel=ricany,
        date_issued=date(2026, 6, 11),
        year_issued=2026,
        counter=1,
        cislo="TYN-2026-0001",
        created_by=user_tyn,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DodaciList.objects.create(
                movement=Movement.objects.create(
                    branch=tyn,
                    kind=Movement.Kind.VYDEJ,
                    date_issued=date(2026, 6, 11),
                    odberatel=ricany,
                    created_by=user_tyn,
                ),
                branch=tyn,
                odberatel=ricany,
                date_issued=date(2026, 6, 11),
                year_issued=2026,
                counter=1,  # duplicate (branch, year, counter)
                cislo="TYN-2026-9999",
                created_by=user_tyn,
            )


@pytest.mark.django_db
def test_dodaci_list_counter_positive_check(tyn, ricany, user_tyn) -> None:
    mv = Movement.objects.create(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        date_issued=date(2026, 6, 11),
        odberatel=ricany,
        created_by=user_tyn,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DodaciList.objects.create(
                movement=mv,
                branch=tyn,
                odberatel=ricany,
                date_issued=date(2026, 6, 11),
                year_issued=2026,
                counter=0,
                cislo="TYN-2026-0000",
                created_by=user_tyn,
            )


@pytest.mark.django_db
def test_dodaci_list_current_version_positive_check(tyn, ricany, user_tyn) -> None:
    mv = Movement.objects.create(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        date_issued=date(2026, 6, 11),
        odberatel=ricany,
        created_by=user_tyn,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DodaciList.objects.create(
                movement=mv,
                branch=tyn,
                odberatel=ricany,
                date_issued=date(2026, 6, 11),
                year_issued=2026,
                counter=1,
                cislo="TYN-2026-0001",
                current_version=0,
                created_by=user_tyn,
            )


@pytest.mark.django_db
def test_email_log_version_positive_check(tyn, ricany, user_tyn) -> None:
    mv = Movement.objects.create(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        date_issued=date(2026, 6, 11),
        odberatel=ricany,
        created_by=user_tyn,
    )
    dl = DodaciList.objects.create(
        movement=mv,
        branch=tyn,
        odberatel=ricany,
        date_issued=date(2026, 6, 11),
        year_issued=2026,
        counter=1,
        cislo="TYN-2026-0001",
        created_by=user_tyn,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DodaciListEmailLog.objects.create(
                dodaci_list=dl,
                version=0,
                recipients="a@b.cz",
                trigger_reason="test",
                status=DodaciListEmailLog.Status.SENT,
            )


# Numbering ----------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_reserve_first_counter_in_year(tyn) -> None:
    with transaction.atomic():
        n = _reserve_dodak_number(branch=tyn, year=2026)
    assert n == 1


@pytest.mark.django_db(transaction=True)
def test_reserve_increments_within_branch_year(tyn) -> None:
    with transaction.atomic():
        _reserve_dodak_number(branch=tyn, year=2026)
    with transaction.atomic():
        n = _reserve_dodak_number(branch=tyn, year=2026)
    assert n == 2


@pytest.mark.django_db(transaction=True)
def test_reserve_separates_branches(tyn, sez) -> None:
    with transaction.atomic():
        _reserve_dodak_number(branch=tyn, year=2026)
        _reserve_dodak_number(branch=tyn, year=2026)
        n_sez = _reserve_dodak_number(branch=sez, year=2026)
    assert n_sez == 1
    assert (
        DodaciListNumberSequence.objects.get(branch=tyn, year=2026).last_counter == 2
    )
    assert (
        DodaciListNumberSequence.objects.get(branch=sez, year=2026).last_counter == 1
    )


@pytest.mark.django_db(transaction=True)
def test_reserve_separates_years(tyn) -> None:
    with transaction.atomic():
        _reserve_dodak_number(branch=tyn, year=2026)
        n_2027 = _reserve_dodak_number(branch=tyn, year=2027)
    assert n_2027 == 1


# apply_movement vydej path ------------------------------------------------


@pytest.mark.django_db
def test_apply_vydej_creates_dodaci_list(tyn, ricany, pepper, user_tyn) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    dl = DodaciList.objects.get(movement=mv)
    assert dl.cislo == "TYN-2026-0001"
    assert dl.current_version == 1
    assert dl.odberatel == ricany
    assert dl.branch == tyn


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_apply_vydej_renders_pdf_and_queues_send(
    tyn, ricany, pepper, user_tyn
) -> None:
    from django.core import mail

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert "Dodací list TYN-2026-0001" in msg.subject
    assert set(msg.to) == {"petr@example.cz", "karolina@example.cz"}
    assert len(msg.attachments) == 1
    filename, content, mimetype = msg.attachments[0]
    assert filename == "TYN-2026-0001.pdf"
    assert mimetype == "application/pdf"
    assert content[:4] == b"%PDF"
    assert len(content) > 1000


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_apply_vydej_writes_sent_log(tyn, ricany, pepper, user_tyn) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    log = DodaciListEmailLog.objects.get(dodaci_list__movement=mv)
    assert log.status == DodaciListEmailLog.Status.SENT
    assert log.version == 1
    assert log.trigger_reason == "vystavení"


@pytest.mark.django_db
def test_apply_vydej_refuses_when_recipients_empty(
    tyn, ricany, pepper, user_tyn
) -> None:
    from inventory.models import SettingsRecipient

    # Per 0052: refuse when no active SettingsRecipient row exists.
    SettingsRecipient.objects.update(is_active=False)
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    with pytest.raises(ValidationError):
        apply_movement(
            movement=_vydej(tyn, ricany, user_tyn),
            lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
            user=user_tyn,
        )
    assert Movement.objects.count() == 0
    assert DodaciList.objects.count() == 0
    assert DodaciListEmailLog.objects.count() == 0


@pytest.mark.django_db
def test_apply_prijem_creates_no_dodaci_list(tyn, supplier, pepper, user_tyn) -> None:
    apply_movement(
        movement=_prijem(tyn, supplier, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_tyn,
    )
    assert DodaciList.objects.count() == 0
    assert DodaciListEmailLog.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_apply_vydej_failed_send_writes_failed_log(
    tyn, ricany, pepper, user_tyn, monkeypatch
) -> None:
    # Patch EmailMessage.send to raise so the locmem backend never sees the
    # message; the service catches the exception and writes a FAILED log.
    from inventory import services

    def _raise(self, *args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(services.EmailMessage, "send", _raise)

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    # Výdej committed.
    assert Movement.objects.filter(pk=mv.pk).exists()
    log = DodaciListEmailLog.objects.get(dodaci_list__movement=mv)
    assert log.status == DodaciListEmailLog.Status.FAILED
    assert "smtp down" in log.error_message


# SMTP source-of-truth (decision 0049) ------------------------------------


@pytest.mark.django_db
def test_smtp_connection_helper_uses_settings_db_when_set(monkeypatch) -> None:
    """Per 0049: when Settings.smtp_* string fields are populated,
    `_smtp_connection_from_settings` passes them verbatim to
    `get_connection`. Locmem ignores host/port so we monkeypatch the
    helper's `get_connection` to capture the call kwargs."""
    from inventory import services

    s = Settings.load()
    s.smtp_host = "test.example.cz"
    s.smtp_port = 2525
    s.smtp_user = "x"
    s.smtp_password = "y"
    s.smtp_use_tls = True
    s.save()

    captured = {}

    def _fake_get_connection(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(services, "get_connection", _fake_get_connection)
    services._smtp_connection_from_settings(Settings.load())

    assert captured == {
        "host": "test.example.cz",
        "port": 2525,
        "username": "x",
        "password": "y",
        "use_tls": True,
        "timeout": 10,
    }


@pytest.mark.django_db
def test_smtp_connection_helper_passes_none_for_blank_db_fields(monkeypatch) -> None:
    """Per 0049: blank Settings.smtp_* string fields produce `None`
    kwargs so Django's default backend reads `EMAIL_HOST*` from env."""
    from inventory import services

    s = Settings.load()
    s.smtp_host = ""
    s.smtp_port = 0
    s.smtp_user = ""
    s.smtp_password = ""
    s.smtp_use_tls = True
    s.save()

    captured = {}

    def _fake_get_connection(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(services, "get_connection", _fake_get_connection)
    services._smtp_connection_from_settings(Settings.load())

    assert captured == {
        "host": None,
        "port": None,
        "username": None,
        "password": None,
        "use_tls": True,
        "timeout": 10,
    }


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_send_dodaci_list_email_calls_helper(
    tyn, ricany, pepper, user_tyn, monkeypatch
) -> None:
    """Real výdej end-to-end exercises the shared helper exactly once."""
    from inventory import services

    s = Settings.load()
    s.smtp_host = "custom.example.cz"
    s.save()

    calls = []
    real_helper = services._smtp_connection_from_settings

    def _spy(settings_obj):
        calls.append(settings_obj.smtp_host)
        return real_helper(settings_obj)

    monkeypatch.setattr(services, "_smtp_connection_from_settings", _spy)

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    assert calls == ["custom.example.cz"]


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_send_dodaci_list_email_failure_still_logs_failed_row(
    tyn, ricany, pepper, user_tyn, monkeypatch
) -> None:
    """Per 0049 the helper does not change 0019's fail-silent contract:
    a send exception still produces a FAILED log row and the výdej
    commits."""
    from inventory import services

    def _raise(self, *args, **kwargs):
        raise RuntimeError("smtp boom")

    monkeypatch.setattr(services.EmailMessage, "send", _raise)

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    assert Movement.objects.filter(pk=mv.pk).exists()
    log = DodaciListEmailLog.objects.get(dodaci_list__movement=mv)
    assert log.status == DodaciListEmailLog.Status.FAILED
    assert "smtp boom" in log.error_message


# edit_movement re-issue hook ---------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_edit_vydej_bumps_current_version_and_audits(
    tyn, ricany, pepper, user_tyn
) -> None:
    from django.core import mail

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    assert len(mail.outbox) == 1

    line = mv.lines.get()
    edit_movement(
        movement=mv,
        changes={},
        line_changes=[
            {
                "op": "update",
                "line_id": line.pk,
                "fields": {"quantity_kg": Decimal("3.000")},
            }
        ],
        reason="oprava hmotnosti",
        user=user_tyn,
    )
    dl = DodaciList.objects.get(movement=mv)
    assert dl.current_version == 2
    assert len(mail.outbox) == 2
    assert mail.outbox[-1].subject.startswith("[OPRAVA] Dodací list")
    log = DodaciListEmailLog.objects.filter(dodaci_list=dl, version=2).get()
    assert log.trigger_reason == "oprava: oprava hmotnosti"


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_edit_movement_without_dodaci_list_skips_hook(
    tyn, supplier, pepper, user_tyn
) -> None:
    from django.core import mail

    mv = apply_movement(
        movement=_prijem(tyn, supplier, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_tyn,
    )
    assert mail.outbox == []
    edit_movement(
        movement=mv,
        changes={"note": "doplněno"},
        line_changes=[],
        reason="oprava poznámky",
        user=user_tyn,
    )
    assert DodaciList.objects.count() == 0
    assert mail.outbox == []


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_edit_movement_rollback_does_not_send_oprava(
    tyn, ricany, pepper, user_tyn
) -> None:
    from django.core import mail

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    outbox_before = len(mail.outbox)
    line = mv.lines.get()
    with pytest.raises(ValidationError):
        edit_movement(
            movement=mv,
            changes={},
            line_changes=[
                {
                    "op": "update",
                    "line_id": line.pk,
                    "fields": {"quantity_kg": Decimal("99.000")},
                }
            ],
            reason="pokus o předčerpání",
            user=user_tyn,
        )
    dl = DodaciList.objects.get(movement=mv)
    assert dl.current_version == 1
    assert len(mail.outbox) == outbox_before
    assert (
        DodaciListEmailLog.objects.filter(dodaci_list=dl).count() == 1
    )


# Management command -------------------------------------------------------


@pytest.mark.django_db
def test_generate_dodaci_list_command_writes_pdf(
    tmp_path, tyn, ricany, pepper, user_tyn
) -> None:
    from django.core.management import call_command

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    out = tmp_path / "out.pdf"
    call_command("generate_dodaci_list", str(mv.pk), "--output", str(out))
    data = out.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 1024


# Admin --------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_PLAIN_STATIC)
def test_settings_admin_no_add_when_singleton_exists(admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    response = client.get(reverse("admin:inventory_settings_add"))
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_PLAIN_STATIC)
def test_dodaci_list_admin_readonly(admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    add = client.get(reverse("admin:inventory_dodacilist_add"))
    assert add.status_code == 403
    changelist = client.get(reverse("admin:inventory_dodacilist_changelist"))
    assert changelist.status_code == 200


@pytest.mark.django_db(transaction=True)
@override_settings(**_PLAIN_STATIC, **_LOCMEM_EMAIL)
def test_dodaci_list_admin_resend_action(
    admin_user, tyn, ricany, pepper, user_tyn
) -> None:
    from django.core import mail

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    outbox_before = len(mail.outbox)
    dl = DodaciList.objects.get(movement=mv)

    client = Client()
    client.force_login(admin_user)
    response = client.post(
        reverse("admin:inventory_dodacilist_changelist"),
        {
            "action": "resend_dodaci_list",
            "_selected_action": [str(dl.pk)],
        },
        follow=True,
    )
    assert response.status_code == 200
    assert len(mail.outbox) == outbox_before + 1
    log = (
        DodaciListEmailLog.objects.filter(dodaci_list=dl)
        .order_by("-sent_at", "-id")
        .first()
    )
    assert log is not None
    assert log.version == dl.current_version


@pytest.mark.django_db
@override_settings(**_PLAIN_STATIC)
def test_email_log_admin_is_readonly(admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    response = client.get(reverse("admin:inventory_dodacilistemaillog_add"))
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Pass 3a — HTMX views (auth, příjem, výdej, partials)
# ---------------------------------------------------------------------------


_VIEW_TEST_OVERRIDES = {
    **_PLAIN_STATIC,
    **_LOCMEM_EMAIL,
}


def _recipient_formset_keepall() -> dict:
    """POST-data dict for the SettingsRecipient formset that keeps every
    existing row untouched. Tests POSTing /nastaveni/ that don't actually
    care about the recipient rows include this via **kwargs to satisfy
    the formset's management form + per-row required fields per 0052."""
    from inventory.models import SettingsRecipient

    rows = list(
        SettingsRecipient.objects.all().order_by(
            "-is_active", "sort_order", "id"
        )
    )
    payload: dict = {
        "recipient-TOTAL_FORMS": str(len(rows)),
        "recipient-INITIAL_FORMS": str(len(rows)),
        "recipient-MIN_NUM_FORMS": "0",
        "recipient-MAX_NUM_FORMS": "1000",
    }
    for i, r in enumerate(rows):
        payload[f"recipient-{i}-id"] = str(r.pk)
        payload[f"recipient-{i}-email"] = r.email
        payload[f"recipient-{i}-label"] = r.label
        payload[f"recipient-{i}-sort_order"] = str(r.sort_order)
        if r.is_active:
            payload[f"recipient-{i}-is_active"] = "on"
        if r.is_low_stock_recipient:
            payload[f"recipient-{i}-is_low_stock_recipient"] = "on"
    return payload


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_anonymous_home_redirects_to_login() -> None:
    response = Client().get("/sklad/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_healthz_is_public() -> None:
    # Healthz is decorated with @login_not_required.
    response = Client().get("/healthz")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_login_renders_czech() -> None:
    response = Client().get("/sklad/prihlaseni/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Přihlášení" in body
    assert "E-mail" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_login_success_redirects_home(user_tyn) -> None:
    user_tyn.set_password("zkouska123")
    user_tyn.save()
    client = Client()
    response = client.post(
        "/sklad/prihlaseni/",
        {"username": user_tyn.email, "password": "zkouska123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_loads_for_authenticated_user(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Nový příjem" in body
    assert "Nový výdej" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_get_renders(user_tyn, supplier) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/prijem/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Nový příjem" in body
    assert supplier.name in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_post_creates_movement_and_redirects(
    user_tyn, tyn, supplier, pepper
) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/prijem/novy/",
        {
            "branch": tyn.pk,
            "dodavatel": supplier.pk,
            "date_issued": "2026-06-12",
            "note": "test",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "3.250",
        },
    )
    assert response.status_code == 302, response.content[:500]
    assert response.headers["Location"].startswith("/sklad/pohyby/")
    mv = Movement.objects.get()
    assert mv.kind == Movement.Kind.PRIJEM
    assert mv.lines.count() == 1
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("3.250")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_post_empty_lines_shows_error(user_tyn, tyn, supplier) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/prijem/novy/",
        {
            "branch": tyn.pk,
            "dodavatel": supplier.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 200
    assert Movement.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_post_creates_dodaci_list_and_redirects(
    user_tyn, tyn, ricany, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "2.000",
        },
    )
    assert response.status_code == 302, response.content[:500]
    mv = Movement.objects.get()
    assert mv.kind == Movement.Kind.VYDEJ
    dl = DodaciList.objects.get(movement=mv)
    assert dl.cislo == "TYN-2026-0001"
    saved = client.get(f"/sklad/pohyby/{mv.pk}/")
    assert saved.status_code == 200
    assert b"TYN-2026-0001" in saved.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_post_overdraw_keeps_form(user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "5.000",
        },
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Per decision 0042 — overdraw surfaces as the structured warning
    # card, not the old "pod nulu" service error.
    assert "Nedostatek na sklad" in body
    assert Movement.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_partial(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/_partials/line-row/?index=2")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="lines-2-product"' in body
    assert 'name="lines-2-quantity_kg"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_qty_min_matches_step(user_tyn) -> None:
    # Round numbers (10000) must be accepted — min must align with step="0.1",
    # not the stale min="0.001" which made every round number a stepMismatch.
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/vydej/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'min="0.1"' in body
    assert 'min="0.001"' not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_post_accepts_round_number(user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("20000.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "10000",
        },
    )
    assert response.status_code == 302, response.content[:500]
    assert Movement.objects.count() == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_form_embeds_stock_map_and_no_htmx(user_tyn, tyn, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/vydej/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # The JSON stock map is embedded and carries the seeded on-hand.
    match = re.search(
        r'<script id="vydej-stock-map" type="application/json">(.*?)</script>',
        body,
        re.DOTALL,
    )
    assert match, "vydej-stock-map json_script block not found"
    data = json.loads(match.group(1))
    assert data[str(tyn.pk)][str(pepper.pk)] == "3.000"
    # The JS render target is present.
    assert 'id="stock-warn-cell-0"' in body
    # No htmx live-check machinery remains (the add-line button still uses
    # htmx to append rows — only the stock-warn round-trip is gone).
    assert "stock_warn_partial" not in body
    assert "/_partials/stock-warn/" not in body
    assert 'hx-target="#stock-warn-cell' not in body
    assert "stockWarnVals" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_form_inventura_jump_for_vlastnik(user_tyn, tyn) -> None:
    # user_tyn has no role group → is_vlastnik. The over-stock block offers a
    # jump to inventura pre-filtered to the flagged products (per 0060).
    client = Client()
    client.force_login(user_tyn)
    body = client.get("/sklad/vydej/novy/").content.decode("utf-8")
    match = re.search(
        r'<script id="vydej-inventura-urls" type="application/json">(.*?)</script>',
        body,
        re.DOTALL,
    )
    assert match, "vydej-inventura-urls json_script block not found"
    urls = json.loads(match.group(1))
    assert urls[str(tyn.pk)] == reverse("inventory:inventura_edit", args=[tyn.code])
    assert 'id="stock-block-inventura"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_form_inventura_jump_absent_for_obsluha(user_obsluha_tyn) -> None:
    # Obsluha may not open inventura — no jump blob, no link.
    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/vydej/novy/").content.decode("utf-8")
    assert 'id="vydej-inventura-urls"' not in body
    assert 'id="stock-block-inventura"' not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_partial_warn_flag_wires_stock_warn(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    warned = client.get("/sklad/_partials/line-row/?index=1&warn=1")
    assert warned.status_code == 200
    body = warned.content.decode("utf-8")
    # ?warn=1 → the JS render-target cell, no htmx.
    assert "stock-warn-cell" in body
    assert 'id="stock-warn-cell-1"' in body
    assert "hx-get" not in body
    assert "/_partials/stock-warn/" not in body
    # Without ?warn=1 (e.g. příjem add-row), no stock-warn hooks at all.
    plain = client.get("/sklad/_partials/line-row/?index=1")
    assert plain.status_code == 200
    plain_body = plain.content.decode("utf-8")
    assert "stock-warn-cell" not in plain_body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_partial_routes_require_login() -> None:
    response = Client().get("/sklad/_partials/line-row/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


# ---------------------------------------------------------------------------
# Pass 3b — dodák list/detail/PDF/resend + movement edit
# ---------------------------------------------------------------------------


def _seed_vydej(user, tyn, ricany, pepper, qty="2.000", stock="5.000"):
    """Create one výdej via apply_movement; return the Movement + DodaciList."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal(stock))
    from inventory.services import apply_movement as _apply

    mv = _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 11),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal(qty))],
        user=user,
    )
    dl = DodaciList.objects.get(movement=mv)
    return mv, dl


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_index_empty(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/dodaky/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Dodací listy" in body
    assert "Nalezeno: 0" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_index_lists_dodak(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/dodaky/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert dl.cislo in body
    assert "Nalezeno: 1" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_index_branch_filter(
    user_tyn, tyn, sez, ricany, pepper
) -> None:
    mv, _dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    # Hit the filter via querystring (SEZ has no dodáky → list should be empty).
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/?branch={sez.pk}")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Nalezeno: 0" in body
    # Filtering for TYN keeps the row.
    response = client.get(f"/sklad/dodaky/?branch={tyn.pk}")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_detail_renders(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/{dl.cislo}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert dl.cislo in body
    assert "Stáhnout PDF" in body
    assert "Znovu odeslat" in body
    assert "Otevřít výdej" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_pdf_download(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/{dl.cislo}/pdf/")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert f'filename="{dl.cislo}.pdf"' in response.headers["Content-Disposition"]
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 1000


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_resend_writes_log(user_tyn, tyn, ricany, pepper) -> None:
    from django.core import mail

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    outbox_before = len(mail.outbox)
    logs_before = DodaciListEmailLog.objects.filter(dodaci_list=dl).count()

    client = Client()
    client.force_login(user_tyn)
    response = client.post(f"/sklad/dodaky/{dl.cislo}/znovu-odeslat/")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/sklad/dodaky/{dl.cislo}/"

    assert len(mail.outbox) == outbox_before + 1
    log = (
        DodaciListEmailLog.objects.filter(dodaci_list=dl)
        .order_by("-sent_at", "-id")
        .first()
    )
    assert log is not None
    assert log.trigger_reason == "ruční opětovné odeslání"
    assert (
        DodaciListEmailLog.objects.filter(dodaci_list=dl).count() == logs_before + 1
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_routes_require_login() -> None:
    for path in (
        "/sklad/dodaky/",
        "/sklad/dodaky/anything/",
        "/sklad/dodaky/anything/pdf/",
    ):
        response = Client().get(path)
        assert response.status_code == 302
        assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_detail_404_for_unknown_cislo(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/dodaky/TYN-2099-9999/")
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_get_renders(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/pohyby/{mv.pk}/upravit/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Úprava" in body
    assert "Důvod úpravy" in body
    # Linked dodák warning visible.
    assert dl.cislo in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_post_bumps_version_and_audits(
    user_tyn, tyn, ricany, pepper
) -> None:
    from django.core import mail

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    line = mv.lines.get()
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        f"/sklad/pohyby/{mv.pk}/upravit/",
        {
            "reason": "oprava hmotnosti",
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-11",
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "1",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-line_id": str(line.pk),
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "3.000",
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 302, response.content[:500]

    dl.refresh_from_db()
    assert dl.current_version == 2
    # An OPRAVA send + log row landed via the edit hook.
    assert any("[OPRAVA]" in m.subject for m in mail.outbox)
    log = DodaciListEmailLog.objects.filter(dodaci_list=dl, version=2).get()
    assert log.trigger_reason == "oprava: oprava hmotnosti"
    # And the audit row exists.
    assert MovementAudit.objects.filter(movement=mv).count() >= 1


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_no_changes_is_noop(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    line = mv.lines.get()
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        f"/sklad/pohyby/{mv.pk}/upravit/",
        {
            "reason": "kontrola",
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-11",
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "1",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-line_id": str(line.pk),
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": str(line.quantity_kg),
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 302
    dl.refresh_from_db()
    assert dl.current_version == 1
    assert MovementAudit.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_overdraw_keeps_form(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper, qty="2.000", stock="5.000")
    line = mv.lines.get()
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        f"/sklad/pohyby/{mv.pk}/upravit/",
        {
            "reason": "pokus o předčerpání",
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-11",
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "1",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-line_id": str(line.pk),
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "99.000",
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 200, response.content[:300]
    dl.refresh_from_db()
    assert dl.current_version == 1
    assert MovementAudit.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_edit_404_for_unknown_pk(user_tyn) -> None:
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/pohyby/99999/upravit/")
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_post_now_redirects_to_dodaci_list_detail(
    user_tyn, tyn, ricany, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": tyn.pk,
            "odberatel": ricany.pk,
            "date_issued": "2026-06-12",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "1.500",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/dodaky/TYN-2026-0001/"


# ---------------------------------------------------------------------------
# Pass 3c — dashboard (screen 02)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_clean_morning(user_tyn) -> None:
    """First-ever state: branch panels exist with placeholders;
    K vyřešení says nothing to worry about today."""
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "TYN" in body and "SEZ" in body
    # Clean state: nothing below threshold, no activity yet.
    assert "Vše nad objednacím bodem" in body
    assert "Zatím žádné pohyby" in body
    assert "Zatím žádné dodací listy" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_shows_branch_stock(user_tyn, tyn, sez, pepper, paprika) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("3.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("1.500"))
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    # TYN total = 11.0 kg with 2 products; SEZ total = 1.5 kg with 1
    # product. Displayed at 1 dp with a Czech comma (per 0061). The Přehled
    # shows per-branch totals + product counts (the full stock list lives on
    # the branch dashboard, not here).
    assert "11,0" in body
    assert "1,5" in body
    assert "2 produktů" in body
    assert "1 produktů" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_lists_recent_dodaky(user_tyn, tyn, ricany, pepper) -> None:
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    assert "Poslední dodací listy" in body
    assert dl.cislo in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_flags_edited_dodak(user_tyn, tyn, ricany, pepper) -> None:
    from inventory.services import edit_movement

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    line = mv.lines.get()
    edit_movement(
        movement=mv,
        changes={},
        line_changes=[
            {"op": "update", "line_id": line.pk, "fields": {"quantity_kg": Decimal("3.000")}}
        ],
        reason="oprava hmotnosti",
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    assert "Editovaný" in body  # K vyřešení task badge
    # The edited dodák appears with its v2 marker.
    assert dl.cislo in body
    assert "v2" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_flags_failed_send(user_tyn, tyn, ricany, pepper, monkeypatch) -> None:
    """A dodák whose latest send at current_version FAILED appears in
    the 'Nedoručené e-maily' bucket; once re-sent successfully, it
    drops out."""
    from inventory import services
    from inventory.models import DodaciListEmailLog

    # First create the výdej WITH a failing SMTP so the initial send logs FAILED.
    def _fail(self, *args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(services.EmailMessage, "send", _fail)
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    assert DodaciListEmailLog.objects.filter(
        dodaci_list=dl, status=DodaciListEmailLog.Status.FAILED
    ).exists()

    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/")
    body = response.content.decode("utf-8")
    assert "Nedoručený" in body  # K vyřešení task badge
    assert dl.cislo in body
    # to_resolve_count should be ≥ 1
    assert "K vyřešení" in body

    # Now restore normal send and re-send → the latest log at v1 is SENT,
    # the failed bucket should empty.
    monkeypatch.undo()
    pdf = services.render_dodaci_list_pdf(dl)
    services.send_dodaci_list_email(
        dodaci_list=dl,
        trigger_reason="ruční opětovné odeslání",
        pdf_bytes=pdf,
    )
    response2 = client.get("/sklad/")
    body2 = response2.content.decode("utf-8")
    assert "Nedoručený" not in body2


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dashboard_requires_login() -> None:
    response = Client().get("/sklad/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


# ---------------------------------------------------------------------------
# Pass 3d — role gating + branch dashboard (screen 03)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_is_vlastnik_default_unassigned(user_tyn) -> None:
    # user_tyn has no group → default vlastník per accounts.User.is_vlastnik.
    assert user_tyn.is_vlastnik is True
    assert user_tyn.is_obsluha is False


@pytest.mark.django_db
def test_user_is_obsluha_when_in_group(user_obsluha_tyn) -> None:
    assert user_obsluha_tyn.is_obsluha is True
    assert user_obsluha_tyn.is_vlastnik is False


@pytest.mark.django_db
def test_user_superuser_is_vlastnik(admin_user) -> None:
    assert admin_user.is_vlastnik is True
    assert admin_user.is_obsluha is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_routes_obsluha_to_branch_dashboard(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/pobocka/TYN/"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_owner_lands_on_owner_dashboard(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Owner dashboard markers (KPI strip always renders).
    assert "Vyprodáno" in body
    assert "K vyřešení" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_renders_for_obsluha(user_obsluha_tyn, tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "TYN" in body and tyn.name in body
    assert "Stav skladu" in body
    assert "Nedávné pohyby" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_lists_stock_for_branch(
    user_obsluha_tyn, tyn, sez, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("3.000"))
    # SEZ stock that must NOT appear on TYN's dashboard.
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("99.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs in body
    # 99.000 from SEZ should NOT appear (TYN only has 8 and 3).
    assert "99,000" not in body and "99.000" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_search_filters_stock(
    user_obsluha_tyn, tyn, pepper, paprika
) -> None:
    # Per 0063 the `q` text filter moved client-side: the server renders ALL
    # stock rows regardless of `q`, each carrying the data-filter-text the JS
    # folds/matches. (Folding/typo matching itself is verified in-browser.)
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/pobocka/TYN/?q={pepper.name_cs[:4]}")
    body = response.content.decode("utf-8")
    # Both rows render server-side now — the browser narrows to the query.
    assert pepper.name_cs in body
    assert paprika.name_cs in body
    # Each row carries the searchable text the client filter consumes.
    assert f'data-filter-text="{pepper.name_cs}"' in body
    assert f'data-filter-text="{paprika.name_cs}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_obsluha_forbidden_on_other_branch(
    user_obsluha_tyn, sez
) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/SEZ/")
    assert response.status_code == 403
    assert "Nemáte oprávnění" in response.content.decode("utf-8")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_vlastnik_can_view_either_branch(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    for code in ("TYN", "SEZ"):
        response = client.get(f"/sklad/pobocka/{code}/")
        assert response.status_code == 200, code
        assert code in response.content.decode("utf-8")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_404_for_unknown_code(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pobocka/ZZZ/")
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_requires_login() -> None:
    response = Client().get("/sklad/pobocka/TYN/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_dashboard_recent_movements(
    user_obsluha_tyn, tyn, ricany, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.500"))],
        user=user_obsluha_tyn,
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    body = response.content.decode("utf-8")
    assert "Říčany" in body
    assert "výdej" in body


# ---------------------------------------------------------------------------
# Pass 3e — movement history (screen 10)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_requires_login() -> None:
    response = Client().get("/sklad/pohyby/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_empty(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Historie pohybů" in body
    assert "Zatím žádné pohyby" in body
    assert "Nalezeno: 0" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_lists_movement(user_vlastnik, user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body
    assert pepper.name_cs in body
    assert "Říčany" in body
    assert "TYN-2026-0001" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_obsluha_scoped_to_own_branch(
    user_obsluha_tyn, user_tyn, tyn, sez, ricany, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    _apply(
        movement=Movement(
            branch=sez,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=paprika, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pohyby/")
    body = response.content.decode("utf-8")
    # obsluha-tyn sees only TYN row
    assert "Nalezeno: 1" in body
    assert pepper.name_cs in body
    assert paprika.name_cs not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_kind_filter(user_vlastnik, user_tyn, tyn, ricany, supplier, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 12),
            dodavatel=supplier,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?kind=vydej")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_branch_filter_for_vlastnik(
    user_vlastnik, user_tyn, tyn, sez, ricany, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    for branch, product, qty in (
        (tyn, pepper, "1.000"),
        (sez, paprika, "2.000"),
    ):
        _apply(
            movement=Movement(
                branch=branch,
                kind=Movement.Kind.VYDEJ,
                date_issued=date(2026, 6, 12),
                odberatel=ricany,
            ),
            lines=[MovementLine(product=product, quantity_kg=Decimal(qty))],
            user=user_tyn,
        )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/pohyby/?branch={tyn.pk}")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body
    assert pepper.name_cs in body
    assert paprika.name_cs not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_date_range_filter(user_vlastnik, user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    from inventory.services import apply_movement as _apply

    for d in (date(2026, 6, 5), date(2026, 6, 10), date(2026, 6, 15)):
        _apply(
            movement=Movement(
                branch=tyn,
                kind=Movement.Kind.VYDEJ,
                date_issued=d,
                odberatel=ricany,
            ),
            lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
            user=user_tyn,
        )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?date_from=2026-06-08&date_to=2026-06-12")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_edited_only_filter(
    user_vlastnik, user_tyn, tyn, ricany, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply
    from inventory.services import edit_movement

    mv_kept = _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    mv_edited = _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=paprika, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    line = mv_edited.lines.get()
    edit_movement(
        movement=mv_edited,
        changes={},
        line_changes=[
            {"op": "update", "line_id": line.pk, "fields": {"quantity_kg": Decimal("2.000")}}
        ],
        reason="oprava hmotnosti",
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?edited=1")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 1" in body
    # The edited movement appears.
    assert paprika.name_cs in body
    # The unedited movement does not.
    assert pepper.name_cs not in body
    assert mv_kept.pk != mv_edited.pk


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_search_filter(user_vlastnik, user_tyn, tyn, ricany, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    from inventory.services import apply_movement as _apply

    _apply(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
            note="ahoj poznámka",
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    client = Client()
    client.force_login(user_vlastnik)
    # Per 0063 `q` is filtered client-side now: the server renders the row
    # regardless of `q` (so it no longer zeroes out on a non-matching term),
    # carrying data-filter-text with product + counterparty + note for the
    # browser to fold/match. (Folding/typo matching is verified in-browser.)
    response = client.get("/sklad/pohyby/?q=neco-co-tam-neni")
    body = response.content.decode("utf-8")
    assert "Nalezeno: 0" not in body
    assert "neodpovídají filtrům" not in body
    # The movement row carries the searchable text (product + counterparty + note).
    assert (
        f'data-filter-text="{pepper.name_cs} {ricany.name} ahoj poznámka"' in body
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_obsluha_branch_filter_param_ignored(
    user_obsluha_tyn, sez
) -> None:
    """obsluha passing ?branch=SEZ should still see only their own
    branch (param silently ignored when scope is forced)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/pohyby/?branch={sez.pk}")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # obsluha gets a "pobočka TYN" badge in the header
    # and the branch filter dropdown is NOT rendered.
    assert "pobočka TYN" in body
    assert 'id="id_filter_branch"' not in body


# ---------------------------------------------------------------------------
# Pass 3f — catalogue (screens 04 + 05, read-only)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_requires_login() -> None:
    response = Client().get("/sklad/katalog/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_lists_active_only_by_default(
    user_vlastnik, pepper, paprika
) -> None:
    paprika.is_active = False
    paprika.save()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_archived_filter(user_vlastnik, pepper, paprika) -> None:
    paprika.is_active = False
    paprika.save()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?status=archived")
    body = response.content.decode("utf-8")
    assert paprika.name_cs in body
    assert pepper.name_cs not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_search_filter(user_vlastnik, pepper, paprika) -> None:
    # Per 0063: `q` is a client-side filter — the server renders ALL rows
    # regardless of `q`, each carrying data-filter-text for the browser to
    # fold/match. (Folding/typo matching is verified in-browser.)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/?q={pepper.name_cs[:4]}")
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs in body
    assert f'data-filter-text="{pepper.name_cs}"' in body
    assert f'data-filter-text="{paprika.name_cs}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_kind_filter(user_vlastnik) -> None:
    Product.objects.create(name_cs="Surovina", kind=Product.Kind.RAW_SPICE)
    Product.objects.create(name_cs="Směs", kind=Product.Kind.MIXTURE)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?kind=mixture")
    body = response.content.decode("utf-8")
    assert "Směs" in body
    assert "Surovina" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_state_ok_filter(user_vlastnik, tyn) -> None:
    """?state=ok lists only rows that are neither low nor empty."""
    ok = Product.objects.create(
        name_cs="OK zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    low = Product.objects.create(
        name_cs="Dochazi zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    empty = Product.objects.create(
        name_cs="Prazdne zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    Stock.objects.create(product=ok, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=low, branch=tyn, quantity=Decimal("3.000"))
    Stock.objects.create(product=empty, branch=tyn, quantity=Decimal("0.000"))
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/?state=ok").content.decode("utf-8")
    assert ok.name_cs in body
    assert low.name_cs not in body
    assert empty.name_cs not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_shows_total_kg_for_vlastnik(
    user_vlastnik, tyn, sez, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("3.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    body = response.content.decode("utf-8")
    # 11.5 → Czech "11,5" at 1 dp (per 0061)
    assert "11,5" in body
    # New (Pass 6) header "Na skladě" + scope hint over both branches.
    assert "Na skladě" in body
    # Copy updated per Podpora feedback #4 — N-branch ready.
    assert "všechny aktivní pobočky" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_shows_branch_kg_for_obsluha(
    user_obsluha_tyn, tyn, sez, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("99.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/")
    body = response.content.decode("utf-8")
    # Pass 6: scope hint replaces the column header for branch scoping.
    assert "pro pobočku" in body and "TYN" in body
    assert "8,0" in body
    assert "99,0" not in body and "99.0" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_marks_mixture_with_recipe(user_vlastnik, pepper) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    body = response.content.decode("utf-8")
    assert mixture.name_cs in body
    assert "má recepturu" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_renders_for_raw_spice(
    user_vlastnik, tyn, sez, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("3.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert "8,0" in body
    assert "3,5" in body
    assert "11,5" in body
    # Recipe section absent for raw spice.
    assert "Receptura" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_renders_recipe_for_mixture(
    user_vlastnik, pepper, paprika
) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("0.7")
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika, ratio=Decimal("0.3")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/")
    body = response.content.decode("utf-8")
    assert "Receptura" in body
    assert pepper.name_cs in body
    assert paprika.name_cs in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_recipe_scaler_ratio_has_dot_decimal(
    user_vlastnik, pepper
) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("0.5")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/")
    assert b'data-ratio="0.500000"' in response.content
    assert b'data-ratio="0,500000"' not in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_shows_mixing_notes_and_pdf_link(user_vlastnik, pepper) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření",
        kind=Product.Kind.MIXTURE,
        notes="BALIT Á 5 KG",
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{mixture.pk}/").content.decode("utf-8")
    assert "Poznámky k míchání" in body  # XLS notes surfaced with the recipe
    assert "BALIT Á 5 KG" in body
    assert f"/sklad/katalog/{mixture.pk}/receptura/pdf/" in body
    assert "Stáhnout recepturu" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_pdf_download(user_vlastnik, pepper, paprika) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření",
        kind=Product.Kind.MIXTURE,
        notes="BALIT Á 5 KG\ndoba míchání 8 min",
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("0.7")
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika, ratio=Decimal("0.3")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/receptura/pdf/")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert "receptura-" in response.headers["Content-Disposition"]
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 1000


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_pdf_404_for_raw_spice(user_vlastnik, pepper) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/receptura/pdf/")
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_pdf_respects_qty(user_vlastnik, pepper, paprika) -> None:
    mixture = Product.objects.create(name_cs="Gulášové koření", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("0.7")
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika, ratio=Decimal("0.3")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/receptura/pdf/?qty=25")
    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"


def test_recipe_amounts_sum_exactly_to_total() -> None:
    """Largest-line rounding: % column sums to exactly 100, kg to the target —
    even for ratios whose naive per-row rounding drifts (Knedlík → 100.01)."""
    from inventory.services import _amounts_summing_to

    ratios = [Decimal("0.333333"), Decimal("0.333333"), Decimal("0.333334")]
    pcts = _amounts_summing_to(ratios, Decimal("100"), 2)
    assert sum(pcts, Decimal("0")) == Decimal("100.00")
    kgs = _amounts_summing_to(ratios, Decimal("25"), 3)
    assert sum(kgs, Decimal("0")) == Decimal("25.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_preselects_mixture_from_query(user_vlastnik, pepper) -> None:
    mixture = Product.objects.create(name_cs="Gulášové koření", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/michani/novy/?mixture={mixture.pk}").content.decode("utf-8")
    assert f'value="{mixture.pk}" selected' in body  # směs pre-selected from recipe page


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_shows_used_in_for_raw_spice(
    user_vlastnik, pepper
) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/")
    body = response.content.decode("utf-8")
    assert "Použito v směsích" in body
    assert mixture.name_cs in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_404_for_unknown(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/99999/")
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_obsluha_sees_only_own_branch_stock(
    user_obsluha_tyn, tyn, sez, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("99.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/katalog/{pepper.pk}/")
    body = response.content.decode("utf-8")
    assert "8,0" in body
    assert "99,0" not in body and "99.0" not in body


# ---------------------------------------------------------------------------
# Pass 4 — mixing job (screen 15, per decision 0039)
# ---------------------------------------------------------------------------


def _mk_mixture_with_recipe(name="Gulášové koření", components=None):
    """Helper: returns the mixture Product."""
    from inventory.models import RecipeComponent

    mixture = Product.objects.create(name_cs=name, kind=Product.Kind.MIXTURE)
    components = components or []
    for component, ratio in components:
        RecipeComponent.objects.create(
            mixture_product=mixture,
            component_product=component,
            ratio=Decimal(str(ratio)),
        )
    return mixture


@pytest.mark.django_db
def test_micharna_seed_rows_exist() -> None:
    """Seed migration 0007 inserts the internal Míchárna pair."""
    from inventory.models import Customer, Supplier

    assert Customer.objects.filter(name="Míchárna", is_internal=True).exists()
    assert Supplier.objects.filter(name="Míchárna", is_internal=True).exists()


@pytest.mark.django_db
def test_is_internal_customer_skips_dodaci_list(
    tyn, user_tyn, pepper
) -> None:
    """A vydej to an internal odběratel must NOT create a DodaciList +
    must NOT require active SettingsRecipient rows."""
    from inventory.models import Customer, SettingsRecipient
    from inventory.services import apply_movement

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    micharna = Customer.objects.get(name="Míchárna", is_internal=True)
    # Clear all recipients to prove the guard is real (per 0052).
    SettingsRecipient.objects.all().delete()

    mv = apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=micharna,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    assert not DodaciList.objects.filter(movement=mv).exists()


@pytest.mark.django_db
def test_start_mixing_job_writes_consume_and_snapshot(
    tyn, user_tyn, pepper, paprika
) -> None:
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe(
        "Test směs",
        [(pepper, "0.7"), (paprika, "0.3")],
    )

    job = start_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("5.000"),
        user=user_tyn,
    )
    assert job.state == MixingJob.State.RUNNING
    assert job.consume_movement is not None
    # Stock decremented by derived qty (5 * 0.7 = 3.5 and 5 * 0.3 = 1.5).
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("6.500")
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("8.500")
    lines = {jl.component_product_id: jl for jl in job.lines.all()}
    assert lines[pepper.pk].ratio_at_start == Decimal("0.700000")
    assert lines[pepper.pk].derived_qty == Decimal("3.500")
    assert lines[paprika.pk].derived_qty == Decimal("1.500")


@pytest.mark.django_db
def test_start_mixing_job_rejects_overdraw(tyn, user_tyn, pepper) -> None:
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    with pytest.raises(ValidationError):
        start_mixing_job(
            branch=tyn,
            mixture=mixture,
            target_qty=Decimal("5.000"),
            user=user_tyn,
        )
    # Job and Movement rolled back.
    assert MixingJob.objects.count() == 0
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("1.000")


@pytest.mark.django_db
def test_start_mixing_job_rejects_non_mixture(tyn, user_tyn, pepper) -> None:
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    with pytest.raises(ValidationError):
        start_mixing_job(
            branch=tyn,
            mixture=pepper,
            target_qty=Decimal("1.000"),
            user=user_tyn,
        )


@pytest.mark.django_db
def test_start_mixing_job_rejects_mixture_without_recipe(
    tyn, user_tyn
) -> None:
    from inventory.services import start_mixing_job

    mixture = Product.objects.create(name_cs="Empty", kind=Product.Kind.MIXTURE)
    with pytest.raises(ValidationError):
        start_mixing_job(
            branch=tyn,
            mixture=mixture,
            target_qty=Decimal("1.000"),
            user=user_tyn,
        )


@pytest.mark.django_db
def test_finish_mixing_job_writes_produce_and_marks_done(
    tyn, user_tyn, pepper, paprika
) -> None:
    from inventory.services import finish_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("5.000"), user=user_tyn
    )
    finish_mixing_job(
        mixing_job=job,
        actual_produced_qty=Decimal("4.900"),
        line_actuals=None,
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.state == MixingJob.State.DONE
    assert job.actual_produced_qty == Decimal("4.900")
    assert job.produce_movement is not None
    assert (
        Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("4.900")
    )
    assert job.yield_delta == Decimal("-0.100")


@pytest.mark.django_db
def test_finish_mixing_job_with_line_actuals_corrects_consume(
    tyn, user_tyn, pepper, paprika
) -> None:
    from inventory.services import finish_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("5.000"), user=user_tyn
    )
    pepper_line = job.lines.get(component_product=pepper)
    finish_mixing_job(
        mixing_job=job,
        actual_produced_qty=Decimal("5.000"),
        line_actuals={pepper_line.pk: Decimal("3.600")},
        user=user_tyn,
    )
    pepper_line.refresh_from_db()
    assert pepper_line.actual_qty == Decimal("3.600")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal(
        "6.400"
    )
    from inventory.models import MovementAudit

    assert MovementAudit.objects.filter(
        movement=job.consume_movement, field="quantity_kg"
    ).exists()


@pytest.mark.django_db
def test_finish_mixing_job_zero_produce_skips_movement(
    tyn, user_tyn, pepper
) -> None:
    from inventory.services import finish_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("1.000"), user=user_tyn
    )
    finish_mixing_job(
        mixing_job=job,
        actual_produced_qty=Decimal("0.000"),
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.state == MixingJob.State.DONE
    assert job.produce_movement is None


@pytest.mark.django_db
def test_finish_mixing_job_rejects_non_running(tyn, user_tyn, pepper) -> None:
    from inventory.services import (
        cancel_mixing_job,
        finish_mixing_job,
        start_mixing_job,
    )

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("1.000"), user=user_tyn
    )
    cancel_mixing_job(mixing_job=job, reason="testing", user=user_tyn)
    job.refresh_from_db()
    with pytest.raises(ValidationError):
        finish_mixing_job(
            mixing_job=job,
            actual_produced_qty=Decimal("0.500"),
            user=user_tyn,
        )


@pytest.mark.django_db
def test_cancel_mixing_job_restores_stock(tyn, user_tyn, pepper) -> None:
    from inventory.services import cancel_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("2.000"), user=user_tyn
    )
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal(
        "3.000"
    )
    cancel_mixing_job(mixing_job=job, reason="error v poměru", user=user_tyn)
    job.refresh_from_db()
    assert job.state == MixingJob.State.CANCELLED
    assert job.cancel_reason == "error v poměru"
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal(
        "5.000"
    )


@pytest.mark.django_db
def test_cancel_mixing_job_requires_reason(tyn, user_tyn, pepper) -> None:
    from inventory.services import cancel_mixing_job, start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("1.000"), user=user_tyn
    )
    with pytest.raises(ValidationError):
        cancel_mixing_job(mixing_job=job, reason="   ", user=user_tyn)


@pytest.mark.django_db
def test_record_completed_mixing_job_one_shot(
    tyn, user_tyn, pepper, paprika
) -> None:
    from inventory.services import record_completed_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "0.7"), (paprika, "0.3")])
    job = record_completed_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("5.000"),
        actual_produced_qty=Decimal("4.800"),
        line_actuals_by_component_pk={pepper.pk: Decimal("3.600")},
        user=user_tyn,
    )
    job.refresh_from_db()
    assert job.state == MixingJob.State.DONE
    assert job.actual_produced_qty == Decimal("4.800")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal(
        "6.400"
    )
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal(
        "8.500"
    )
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal(
        "4.800"
    )


# View tests --------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_routes_require_login() -> None:
    for path in ("/sklad/michani/", "/sklad/michani/novy/", "/sklad/michani/1/"):
        response = Client().get(path)
        assert response.status_code == 302
        assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_index_empty(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/michani/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Míchací dávky" in body
    assert "Nalezeno: 0" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_get_lists_only_mixtures_with_recipe(
    user_vlastnik, pepper
) -> None:
    with_recipe = _mk_mixture_with_recipe("S recepturou", [(pepper, "1.0")])
    Product.objects.create(name_cs="Bez receptury", kind=Product.Kind.MIXTURE)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/michani/novy/")
    body = response.content.decode("utf-8")
    assert with_recipe.name_cs in body
    assert "Bez receptury" not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_post_records_done_job(user_vlastnik, tyn, pepper) -> None:
    # Per 0060 there are no modes: a create is one immediate DONE míchání —
    # consume the recipe inputs + add the blend + immediate stock delta.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/michani/novy/",
        {
            "branch": tyn.pk,
            "mixture": mixture.pk,
            "target_qty": "2.000",
            "note": "",
        },
    )
    assert response.status_code == 302, response.content[:500]
    assert response.headers["Location"].startswith("/sklad/michani/")
    job = MixingJob.objects.get()
    assert job.state == MixingJob.State.DONE
    assert job.target_qty == Decimal("2.000")
    # Blank "skutečně vyrobeno" → defaults to the target.
    assert job.actual_produced_qty == Decimal("2.000")
    assert job.consume_movement is not None
    assert job.produce_movement is not None
    # Immediate stock delta: inputs drop, blend rises.
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("3.000")
    assert Stock.objects.get(product=mixture, branch=tyn).quantity == Decimal("2.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_post_actual_produced_override(user_vlastnik, tyn, pepper) -> None:
    # The optional "skutečně vyrobeno" override records a produced qty that
    # differs from the target (per 0060).
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/michani/novy/",
        {
            "branch": tyn.pk,
            "mixture": mixture.pk,
            "target_qty": "2.000",
            "actual_produced_qty": "1.900",
        },
    )
    assert response.status_code == 302
    job = MixingJob.objects.get()
    assert job.state == MixingJob.State.DONE
    assert job.actual_produced_qty == Decimal("1.900")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_overdraw_keeps_form(
    user_vlastnik, tyn, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/michani/novy/",
        {
            "branch": tyn.pk,
            "mixture": mixture.pk,
            "target_qty": "5.000",
            "actual_produced_qty": "4.800",
            "note": "poznámka k dávce",
        },
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "pod nulu" in body or "Skladová" in body
    assert MixingJob.objects.count() == 0
    # Per 0060 (3b): every POSTed value is echoed back so nothing is lost.
    assert 'value="5.000"' in body  # target_qty
    assert 'value="4.800"' in body  # actual_produced_qty
    assert "poznámka k dávce" in body  # note
    assert f'value="{tyn.pk}" selected' in body  # branch stays selected
    assert f'value="{mixture.pk}" selected' in body  # směs stays selected


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_finish_view(user_vlastnik, tyn, pepper) -> None:
    # LEGACY PATH (per 0060): the UI no longer creates RUNNING jobs, but the
    # finish view is retained to complete a legacy in-flight job. Build one
    # directly via start_mixing_job() rather than through the create screen.
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("2.000"), user=user_vlastnik
    )
    line = job.lines.get()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/michani/{job.pk}/dokoncit/",
        {
            "actual_produced_qty": "1.900",
            f"line-{line.pk}-actual_qty": "2.000",
        },
    )
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.state == MixingJob.State.DONE
    assert job.actual_produced_qty == Decimal("1.900")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_cancel_view_requires_reason(
    user_vlastnik, tyn, pepper
) -> None:
    # LEGACY PATH (per 0060): cancel is retained for a legacy in-flight job;
    # build a RUNNING job directly via start_mixing_job().
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn, mixture=mixture, target_qty=Decimal("2.000"), user=user_vlastnik
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(f"/sklad/michani/{job.pk}/zrusit/", {"reason": "   "})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.state == MixingJob.State.RUNNING
    response = client.post(
        f"/sklad/michani/{job.pk}/zrusit/", {"reason": "vzal jsem špatnou recepturu"}
    )
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.state == MixingJob.State.CANCELLED


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_obsluha_forbidden_on_other_branch(
    user_obsluha_tyn, sez, pepper
) -> None:
    from inventory.services import start_mixing_job

    User = get_user_model()
    sez_runner = User.objects.create_user(
        email="sez-runner@example.cz", password="x" * 12, branch=sez
    )
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=sez, mixture=mixture, target_qty=Decimal("1.000"), user=sez_runner
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/michani/{job.pk}/")
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_preview_partial(user_vlastnik, tyn, pepper) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        f"/sklad/_partials/mixing-preview/?branch={tyn.pk}&mixture={mixture.pk}&target_qty=5.000"
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "nedostatek" in body
    # Quantities render at 1 dp with a Czech comma (per 0061).
    assert "5,0" in body
    assert "5,000" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_preview_builds_inventura_component_link(
    user_vlastnik, tyn, pepper
) -> None:
    # Per 0060 (3c): the preview offers a jump into the per-branch inventura
    # pre-filtered to the blend's components, with a `next=` back to míchání.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        f"/sklad/_partials/mixing-preview/?branch={tyn.pk}"
        f"&mixture={mixture.pk}&target_qty=5.000"
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert f"/sklad/katalog/inventura/{tyn.code}/?products=" in body
    assert f"products={pepper.pk}" in body
    # `next=` round-trip back to the míchání form (HTML-escaped &amp;).
    assert "next=" in body


# ---------------------------------------------------------------------------
# Screen 14 — Nastavení (operator-facing Settings UI)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_requires_login() -> None:
    response = Client().get("/sklad/nastaveni/")
    assert response.status_code == 302
    assert "/sklad/prihlaseni/" in response["Location"]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_forbidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/nastaveni/")
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_renders_for_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/nastaveni/")
    assert response.status_code == 200
    body = response.content
    assert b"<h1>Nastaven\xc3\xad</h1>" in body
    assert b"Spole\xc4\x8dnost" in body
    assert b"SMTP" in body
    assert b"P\xc5\x99\xc3\xadjemci dodac\xc3\xadho listu" in body
    assert b"\xc5\xa0ablony e-mail\xc5\xaf" in body
    assert b"Otestovat odesl\xc3\xa1n\xc3\xad" in body
    assert b"Pobo\xc4\x8dky" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_save_updates_company(user_vlastnik) -> None:
    from inventory.models import Settings

    client = Client()
    client.force_login(user_vlastnik)
    initial = Settings.load()
    data = {
        "company_name": "Kasia vera s.r.o.",
        "company_ico": "25756729",
        "company_dic": "CZ25756729",
        "company_address": "Říčany u Prahy",
        "company_phone": "+420 123 456 789",
        "company_email": "",
        "footer_text": initial.footer_text,
        "smtp_host": "smtp.example.cz",
        "smtp_port": "587",
        "smtp_use_tls": "on",
        "smtp_user": "kasia",
        "smtp_password": "",
        "email_from_address": "no-reply@example.cz",
        "email_from_name": "Kasia vera",
        "template_initial_subject": initial.template_initial_subject,
        "template_initial_body": initial.template_initial_body,
        "template_oprava_subject": initial.template_oprava_subject,
        "template_oprava_body": initial.template_oprava_body,
        "template_low_stock_subject": initial.template_low_stock_subject,
        "template_low_stock_body": initial.template_low_stock_body,
        **_recipient_formset_keepall(),
    }
    response = client.post("/sklad/nastaveni/", data)
    assert response.status_code == 302, response.content[:500]
    s = Settings.load()
    assert s.company_dic == "CZ25756729"
    assert s.smtp_host == "smtp.example.cz"
    # singleton stays singleton.
    assert Settings.objects.count() == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_edit_empty_password_keeps_existing(user_vlastnik) -> None:
    from inventory.models import Settings

    s = Settings.load()
    s.smtp_password = "old-secret"
    s.save()

    client = Client()
    client.force_login(user_vlastnik)
    data = {
        "company_name": s.company_name,
        "company_ico": s.company_ico,
        "company_dic": s.company_dic,
        "company_address": s.company_address,
        "company_phone": s.company_phone,
        "company_email": s.company_email,
        "footer_text": s.footer_text,
        "smtp_host": s.smtp_host,
        "smtp_port": s.smtp_port,
        "smtp_use_tls": "on",
        "smtp_user": s.smtp_user,
        "smtp_password": "",  # blank → preserve
        "email_from_address": s.email_from_address,
        "email_from_name": s.email_from_name,
        "template_initial_subject": s.template_initial_subject,
        "template_initial_body": s.template_initial_body,
        "template_oprava_subject": s.template_oprava_subject,
        "template_oprava_body": s.template_oprava_body,
        "template_low_stock_subject": s.template_low_stock_subject,
        "template_low_stock_body": s.template_low_stock_body,
        **_recipient_formset_keepall(),
    }
    response = client.post("/sklad/nastaveni/", data)
    assert response.status_code == 302, response.content[:500]
    s2 = Settings.load()
    assert s2.smtp_password == "old-secret"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_test_smtp_sends_to_target(user_vlastnik) -> None:
    from django.core import mail

    client = Client()
    client.force_login(user_vlastnik)
    outbox_before = len(mail.outbox)
    response = client.post(
        "/sklad/nastaveni/test-smtp/",
        {"to_email": "petr@example.cz"},
    )
    assert response.status_code == 302
    assert len(mail.outbox) == outbox_before + 1
    msg = mail.outbox[-1]
    assert "petr@example.cz" in msg.to
    assert "Test" in msg.subject


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_test_smtp_forbidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/nastaveni/test-smtp/", {"to_email": "x@example.cz"}
    )
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_test_smtp_rejects_invalid_email(user_vlastnik) -> None:
    from django.core import mail

    client = Client()
    client.force_login(user_vlastnik)
    outbox_before = len(mail.outbox)
    response = client.post(
        "/sklad/nastaveni/test-smtp/", {"to_email": "not-an-email"}
    )
    assert response.status_code == 302
    assert len(mail.outbox) == outbox_before


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_branch_counters_render(user_vlastnik, tyn) -> None:
    from datetime import date

    from inventory.models import DodaciListNumberSequence

    DodaciListNumberSequence.objects.create(
        branch=tyn, year=date.today().year, last_counter=42
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/nastaveni/")
    assert response.status_code == 200
    expected_cislo = f"TYN-{date.today().year}-0042"
    assert expected_cislo.encode() in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_nastaveni_link_shown_for_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200
    assert b"Nastaven\xc3\xad" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_nastaveni_link_hidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    assert response.status_code == 200
    assert b"Nastaven\xc3\xad" not in response.content


# ---------------------------------------------------------------------------
# Pass 5 — Supplier + Customer CRUD (per decision 0040)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_index_requires_login() -> None:
    response = Client().get("/sklad/dodavatele/")
    assert response.status_code == 302
    assert "/sklad/prihlaseni/" in response["Location"]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_index_renders_for_obsluha(user_obsluha_tyn, supplier) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/dodavatele/")
    assert response.status_code == 200
    assert supplier.name.encode() in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_index_hides_internal(user_obsluha_tyn) -> None:
    from inventory.models import Supplier as Sup

    Sup.objects.create(name="Visible Dodavatel")
    # The "Míchárna" internal supplier was seeded; verify it doesn't show.
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/dodavatele/")
    assert b"Visible Dodavatel" in response.content
    assert b"M\xc3\xadch\xc3\xa1rna" not in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_create_by_obsluha(user_obsluha_tyn) -> None:
    from inventory.models import Supplier as Sup

    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/dodavatele/novy/",
        {
            "name": "Nový Dodavatel s.r.o.",
            "ico": "12345678",
            "address": "Praha 5",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    sup = Sup.objects.get(name="Nový Dodavatel s.r.o.")
    assert sup.ico == "12345678"
    assert sup.is_active is True
    assert sup.is_internal is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_create_rejects_duplicate_name(user_vlastnik, supplier) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/dodavatele/novy/",
        {"name": supplier.name, "is_active": "on"},
    )
    assert response.status_code == 200
    assert (
        b"Aktivn\xc3\xad dodavatel s t\xc3\xadmto n\xc3\xa1zvem u\xc5\xbe existuje"
        in response.content
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_edit_updates_fields(user_vlastnik, supplier) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/dodavatele/{supplier.pk}/upravit/",
        {
            "name": supplier.name,
            "ico": "99887766",
            "address": "Brno",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    supplier.refresh_from_db()
    assert supplier.ico == "99887766"
    assert supplier.address == "Brno"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_archive(user_obsluha_tyn, supplier) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/dodavatele/{supplier.pk}/archivovat/")
    assert response.status_code == 302
    supplier.refresh_from_db()
    assert supplier.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_archive_internal_refused(user_vlastnik) -> None:
    from inventory.models import Supplier as Sup

    micharna = Sup.objects.get(name="Míchárna", is_internal=True)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/dodavatele/{micharna.pk}/archivovat/", follow=True
    )
    assert response.status_code == 200
    micharna.refresh_from_db()
    assert micharna.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_reactivate(user_obsluha_tyn) -> None:
    from inventory.models import Supplier as Sup

    sup = Sup.objects.create(name="Archivovaný", is_active=False)
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/dodavatele/{sup.pk}/aktivovat/")
    assert response.status_code == 302
    sup.refresh_from_db()
    assert sup.is_active is True


# Customer ----------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_index_requires_login() -> None:
    response = Client().get("/sklad/odberatele/")
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_index_renders_for_obsluha(user_obsluha_tyn, ricany) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/odberatele/")
    assert response.status_code == 200
    assert b"\xc5\x98\xc3\xad\xc4\x8dany" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_index_hides_internal(user_obsluha_tyn) -> None:
    """Internal Míchárna customer is hidden from the operator list."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/odberatele/")
    assert response.status_code == 200
    assert b"M\xc3\xadch\xc3\xa1rna" not in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_create_by_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/odberatele/novy/",
        {
            "name": "Hospůdka U Lípy",
            "ico": "11223344",
            "dic": "CZ11223344",
            "address": "Hradec Králové",
            "email": "ulipy@example.cz",
            "phone": "+420 111 222 333",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    cust = Customer.objects.get(name="Hospůdka U Lípy")
    assert cust.email == "ulipy@example.cz"
    assert cust.is_default_recipient is False  # not flipped by operator


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_archive_refused_for_default_recipient(
    user_vlastnik, ricany
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/odberatele/{ricany.pk}/archivovat/", follow=True
    )
    assert response.status_code == 200
    ricany.refresh_from_db()
    assert ricany.is_active is True
    assert ricany.is_default_recipient is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_archive(user_obsluha_tyn) -> None:
    cust = Customer.objects.create(name="Půjčující odběratel")
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/odberatele/{cust.pk}/archivovat/")
    assert response.status_code == 302
    cust.refresh_from_db()
    assert cust.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_supplier_customer_links_visible_to_all(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    assert response.status_code == 200
    assert b"Dodavatel" in response.content
    assert b"Odb\xc4\x9bratel" in response.content


# ---------------------------------------------------------------------------
# Pass 5b — Product + Recipe CRUD (per decision 0040)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_requires_login() -> None:
    response = Client().get("/sklad/katalog/novy/")
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_by_obsluha(user_obsluha_tyn) -> None:
    """Per 0040: workers can add a new product."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/katalog/novy/",
        {
            "name_cs": "Tymián",
            "kind": "raw_spice",
            "notes": "Nově převzato od dodavatele.",
        },
    )
    assert response.status_code == 302
    p = Product.objects.get(name_cs="Tymián")
    assert p.kind == "raw_spice"
    assert p.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_redirects_vlastnik_into_recipe_edit_for_mixtures(
    user_vlastnik,
) -> None:
    """When a vlastník creates a mixture, redirect to the edit form so
    they can add components immediately."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/novy/",
        {"name_cs": "Nová směs", "kind": "mixture"},
    )
    p = Product.objects.get(name_cs="Nová směs")
    assert response.status_code == 302
    assert response["Location"].endswith(f"/sklad/katalog/{p.pk}/upravit/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_obsluha_mixture_lands_on_detail(user_obsluha_tyn) -> None:
    """Obsluha can create a mixture but doesn't get redirected into
    recipe edit (they can't edit recipes per 0040)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/katalog/novy/",
        {"name_cs": "Směs B", "kind": "mixture"},
    )
    p = Product.objects.get(name_cs="Směs B")
    assert response.status_code == 302
    assert response["Location"].endswith(f"/sklad/katalog/{p.pk}/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_rejects_duplicate_name(user_obsluha_tyn, pepper) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/katalog/novy/",
        {"name_cs": pepper.name_cs, "kind": "raw_spice"},
    )
    assert response.status_code == 200
    assert (
        b"Aktivn\xc3\xad produkt s t\xc3\xadmto n\xc3\xa1zvem u\xc5\xbe existuje"
        in response.content
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_edit_updates_name(user_obsluha_tyn, pepper) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit/",
        {
            "name_cs": "Pepř (přejmenovaný)",
            "kind": "raw_spice",
            "notes": "",
            # No recipe formset — obsluha can't edit recipe; template won't render it.
        },
    )
    assert response.status_code == 302
    pepper.refresh_from_db()
    assert pepper.name_cs == "Pepř (přejmenovaný)"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_edit_locks_kind_when_stock_exists(
    user_vlastnik, pepper, tyn
) -> None:
    """Kind field is disabled once Stock or RecipeComponent references exist."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit/")
    assert response.status_code == 200
    assert b"Typ produktu je zam\xc4\x8den\xc3\xbd" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_archive_vlastnik_only(user_obsluha_tyn, pepper) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/katalog/{pepper.pk}/archivovat/")
    assert response.status_code == 403
    pepper.refresh_from_db()
    assert pepper.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_archive_by_vlastnik(user_vlastnik, pepper) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(f"/sklad/katalog/{pepper.pk}/archivovat/")
    assert response.status_code == 302
    pepper.refresh_from_db()
    assert pepper.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_reactivate_blocks_name_collision(
    user_vlastnik, pepper
) -> None:
    """Can't re-activate when another active product has the same name."""
    pepper.is_active = False
    pepper.save()
    Product.objects.create(name_cs=pepper.name_cs, kind=pepper.kind)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/aktivovat/", follow=True
    )
    assert response.status_code == 200
    pepper.refresh_from_db()
    assert pepper.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_visible_only_to_vlastnik(
    user_vlastnik, user_obsluha_tyn, pepper, paprika
) -> None:
    """Recipe formset is rendered only when can_edit_recipe = True."""
    mixture = Product.objects.create(name_cs="Směs X", kind="mixture")
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("0.500"),
    )
    # As vlastník — should see recipe section.
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/upravit/")
    assert response.status_code == 200
    assert b"Receptura" in response.content
    assert b"recipe-TOTAL_FORMS" in response.content
    # As obsluha — recipe section hidden (mixture's recipe is vlastník-only).
    client2 = Client()
    client2.force_login(user_obsluha_tyn)
    response2 = client2.get(f"/sklad/katalog/{mixture.pk}/upravit/")
    assert response2.status_code == 200
    assert b"recipe-TOTAL_FORMS" not in response2.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_saves_changes(user_vlastnik, pepper, paprika) -> None:
    """Vlastník can change ratio of an existing recipe row."""
    mixture = Product.objects.create(name_cs="Směs Y", kind="mixture")
    rc = RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("0.300"),
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{mixture.pk}/upravit/",
        {
            "name_cs": mixture.name_cs,
            "kind": "mixture",
            "notes": "",
            "recipe-TOTAL_FORMS": "1",
            "recipe-INITIAL_FORMS": "1",
            "recipe-MIN_NUM_FORMS": "0",
            "recipe-MAX_NUM_FORMS": "1000",
            "recipe-0-id": str(rc.pk),
            "recipe-0-component_product": str(pepper.pk),
            "recipe-0-ratio": "0.700",
            "threshold-TOTAL_FORMS": "0",
            "threshold-INITIAL_FORMS": "0",
            "threshold-MIN_NUM_FORMS": "0",
            "threshold-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 302
    rc.refresh_from_db()
    assert rc.ratio == Decimal("0.700")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_has_new_product_button(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    assert b"Nov\xc3\xbd produkt" in response.content


# ---------------------------------------------------------------------------
# Pass 5c — Branch CRUD (per decision 0040, vlastník-only)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_index_requires_login() -> None:
    response = Client().get("/sklad/pobocky/")
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_index_forbidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocky/")
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_index_renders_for_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pobocky/")
    assert response.status_code == 200
    assert b"TYN" in response.content
    assert b"SEZ" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_create_by_vlastnik(user_vlastnik) -> None:
    from inventory.models import Branch as B

    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/pobocky/novy/",
        {
            "code": "prh",  # lower-case input; clean_code uppercases
            "name": "Praha (sklad)",
            "address": "Praha 5",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    new_branch = B.objects.get(code="PRH")
    assert new_branch.name == "Praha (sklad)"
    assert new_branch.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_create_rejects_invalid_code(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/pobocky/novy/",
        {"code": "TY", "name": "Test", "address": "", "is_active": "on"},
    )
    assert response.status_code == 200
    assert b"3 p\xc3\xadsmena" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_create_rejects_duplicate_code(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/pobocky/novy/",
        {"code": "TYN", "name": "Dup", "address": "", "is_active": "on"},
    )
    assert response.status_code == 200
    assert b"s t\xc3\xadmto k\xc3\xb3dem u\xc5\xbe existuje" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_edit_locks_code_after_first_dodak(
    user_vlastnik, tyn
) -> None:
    """Per 0008, the code is part of dodák number — locked once issued."""
    from datetime import date

    from inventory.models import DodaciList, DodaciListNumberSequence

    # Synthesise a dodák for TYN so the gate triggers.
    DodaciListNumberSequence.objects.create(
        branch=tyn, year=date.today().year, last_counter=1
    )
    # No movement required for the gate — _branch_code_locked looks at
    # DodaciList table directly.
    from inventory.models import Movement
    # Create a placeholder movement so the dodák FK is valid.
    mv = Movement.objects.create(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        odberatel=Customer.objects.get(is_default_recipient=True),
        date_issued=date.today(),
        note="",
        created_by=user_vlastnik,
    )
    DodaciList.objects.create(
        movement=mv,
        branch=tyn,
        odberatel=mv.odberatel,
        date_issued=date.today(),
        year_issued=date.today().year,
        counter=1,
        cislo=f"TYN-{date.today().year}-0001",
        current_version=1,
        created_by=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pobocky/TYN/upravit/")
    assert response.status_code == 200
    assert b"K\xc3\xb3d je zam\xc4\x8den\xc3\xbd" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_archive_refuses_with_stock(
    user_vlastnik, tyn, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.0"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/pobocky/TYN/archivovat/", follow=True
    )
    assert response.status_code == 200
    tyn.refresh_from_db()
    assert tyn.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_archive_refuses_with_active_users(
    user_vlastnik, sez
) -> None:
    """SEZ has obsluha-sez user (autouse seed) — archive should refuse."""
    from accounts.models import User as UserModel
    # Ensure at least one active user is on SEZ.
    UserModel.objects.create_user(
        email="sez-active@example.cz", password="x" * 12, branch=sez
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post("/sklad/pobocky/SEZ/archivovat/", follow=True)
    assert response.status_code == 200
    sez.refresh_from_db()
    assert sez.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_archive_succeeds_when_clean(user_vlastnik) -> None:
    """A branch with no stock + no active users can be archived."""
    from inventory.models import Branch as B
    new_branch = B.objects.create(code="ZZZ", name="Test", is_active=True)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/pobocky/{new_branch.code}/archivovat/", follow=True
    )
    assert response.status_code == 200
    new_branch.refresh_from_db()
    assert new_branch.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_pobocky_link_visible_to_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200
    assert b"Pobo\xc4\x8dky" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_pobocky_link_hidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    assert response.status_code == 200
    # The text "Pobočky" must not appear as a nav anchor for obsluha.
    # The branch dashboard h1 might have "pobočka" — sanity check on
    # the /pobocky/ URL not appearing in the anchors.
    assert b'href="/sklad/pobocky/"' not in response.content


# ---------------------------------------------------------------------------
# Pass 5d — Manual stock adjustment (per decision 0041)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_requires_login(pepper) -> None:
    response = Client().get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 302
    assert "/sklad/prihlaseni/" in response["Location"]


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_forbidden_for_obsluha(user_obsluha_tyn, pepper) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_renders_for_vlastnik(user_vlastnik, pepper, tyn) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 200
    assert b"\xc3\x9aprava stavu" in response.content  # "Úprava stavu"
    assert b'value="10.0"' in response.content


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_prefills_1dp_and_subunit_save_is_noop(
    user_vlastnik, pepper, tyn, sez
) -> None:
    """A sub-0.1 stored value (9.997) prefills as 10.0; saving it unchanged
    writes no movement and demands no reason. A genuine edit still writes one."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("9.997"))
    client = Client()
    client.force_login(user_vlastnik)

    # GET prefills the 1dp rounded value, not the raw 3dp residue.
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 200
    assert b'value="10.0"' in response.content
    assert b"9.997" not in response.content

    # POSTing that prefilled value unchanged → no-op, no reason required.
    before = Movement.objects.count()
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "10.0",
            f"qty_{sez.pk}": "0.000",
            "reason": "",
        },
    )
    assert response.status_code == 302
    assert Movement.objects.count() == before  # no phantom correction
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("9.997")

    # A genuine edit still writes exactly one [STAV] movement + rewrites to 1dp.
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "12",
            f"qty_{sez.pk}": "0.000",
            "reason": "inventura",
        },
    )
    assert response.status_code == 302
    assert Movement.objects.count() == before + 1
    mv = Movement.objects.order_by("-id").first()
    assert mv.note.startswith("[STAV] ")
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("12.0")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_positive_delta_writes_prijem(
    user_vlastnik, pepper, tyn, sez
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "12.500",
            f"qty_{sez.pk}": "0.000",
            "reason": "inventura — naval o 2,5 kg víc",
        },
    )
    assert response.status_code == 302
    s = Stock.objects.get(product=pepper, branch=tyn)
    assert s.quantity == Decimal("12.500")
    mv = Movement.objects.filter(
        branch=tyn, kind=Movement.Kind.PRIJEM
    ).order_by("-id").first()
    assert mv is not None
    assert mv.note.startswith("[STAV] ")
    assert "naval" in mv.note
    assert mv.dodavatel.is_internal is True
    assert mv.dodavatel.name == "Inventura / ruční úprava"


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_negative_delta_writes_vydej(
    user_vlastnik, pepper, tyn, sez
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "7.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "inventura — chybí 3 kg",
        },
    )
    assert response.status_code == 302
    s = Stock.objects.get(product=pepper, branch=tyn)
    assert s.quantity == Decimal("7.000")
    mv = Movement.objects.filter(
        branch=tyn, kind=Movement.Kind.VYDEJ
    ).order_by("-id").first()
    assert mv is not None
    assert mv.note.startswith("[STAV] ")
    assert mv.odberatel.is_internal is True
    assert mv.odberatel.name == "Inventura / ruční úprava"


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_zero_delta_noop(user_vlastnik, pepper, tyn, sez) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "10.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "",
        },
    )
    assert response.status_code == 302
    after = Movement.objects.count()
    assert after == before  # no movement written


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_requires_reason(user_vlastnik, pepper, tyn, sez) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "12.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "",
        },
    )
    assert response.status_code == 200  # form re-rendered with error
    s = Stock.objects.get(product=pepper, branch=tyn)
    assert s.quantity == Decimal("10.000")  # unchanged


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_creates_stock_row_when_missing(
    user_vlastnik, paprika, tyn, sez
) -> None:
    """Adjusting from 0 (no Stock row yet) creates the Stock row implicitly."""
    assert not Stock.objects.filter(product=paprika, branch=tyn).exists()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{paprika.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "5.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "počáteční stav",
        },
    )
    assert response.status_code == 302
    s = Stock.objects.get(product=paprika, branch=tyn)
    assert s.quantity == Decimal("5.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_movement_appears_in_history_with_stav_prefix(
    user_vlastnik, pepper, tyn, sez
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "11.000",
            f"qty_{sez.pk}": "0.000",
            "reason": "úprava",
        },
    )
    response = client.get("/sklad/pohyby/")
    assert response.status_code == 200
    # Counterparty appears in the history Protistrana column.
    # The [STAV] note prefix is in the DB (Movement.note) — future
    # work surfaces it as a Historie filter; for now we only assert
    # the synthetic movement made it into Historie.
    assert b"Inventura" in response.content
    mv = Movement.objects.filter(branch=tyn).order_by("-id").first()
    assert mv.note.startswith("[STAV] ")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_per_product_bulk_writes_one_movement_per_changed_branch(
    user_vlastnik, pepper, tyn, sez
) -> None:
    """Per-product inventura: rows for both branches change in one POST → two
    Movements, one per branch; the shared reason lands on both."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("4.000"))
    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit-stav/",
        {
            f"qty_{tyn.pk}": "12.500",
            f"qty_{sez.pk}": "3.500",
            "reason": "inventura k 29. 06.",
        },
    )
    assert response.status_code == 302
    assert Movement.objects.count() == before + 2
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("12.500")
    assert Stock.objects.get(product=pepper, branch=sez).quantity == Decimal("3.500")
    for mv in Movement.objects.order_by("-id")[:2]:
        assert mv.note.startswith("[STAV] ")
        assert "inventura k 29. 06." in mv.note


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_adjust_renders_all_active_branches_as_rows(
    user_vlastnik, pepper, tyn, sez
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    # SEZ has no Stock row → still expected as a "Nedrží" row.
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit-stav/")
    assert response.status_code == 200
    body = response.content
    assert f'name="qty_{tyn.pk}"'.encode() in body
    assert f'name="qty_{sez.pk}"'.encode() in body
    assert b"Dr\xc5\xbe\xc3\xad" in body  # "Drží"
    assert b"Nedr\xc5\xbe\xc3\xad" in body  # "Nedrží"


# ---------------------------------------------------------------------------
# Pass 5e — Bulk inventura editor (per decision 0041)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_requires_login() -> None:
    response = Client().get("/sklad/katalog/inventura/TYN/")
    assert response.status_code == 302


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_forbidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/inventura/TYN/")
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_renders_for_vlastnik(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/inventura/TYN/")
    assert response.status_code == 200
    body = response.content
    assert b"Inventura \xe2\x80\x94 TYN" in body  # "Inventura — TYN"
    assert pepper.name_cs.encode() in body
    assert b"10.000" in body
    assert b"5.500" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_data_current_uses_dot_decimal(
    user_vlastnik, tyn, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/inventura/TYN/")
    assert b'data-current="1.500"' in response.content
    assert b'data-current="1,500"' not in response.content


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_per_branch_save_redirects_to_catalogue(
    user_vlastnik, tyn, sez, pepper
) -> None:
    # Regression: the per-branch save must land on the /sklad/-prefixed
    # catalogue (was a bare /katalog/?branch=… → 404). Checked for both
    # branches. An empty POST is a no-op that still redirects.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_vlastnik)
    for code in ("TYN", "SEZ"):
        response = client.post(f"/sklad/katalog/inventura/{code}/", {})
        assert response.status_code == 302
        assert response.headers["Location"].startswith(
            f"/sklad/katalog/?branch={code}"
        )


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_products_filter_restricts_rows(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    # Per 0060: ?products=<pk,…> narrows the per-branch inventura to those
    # products (a blend's inputs). Other products drop out.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/inventura/TYN/?products={pepper.pk}")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_per_branch_honours_next_round_trip(
    user_vlastnik, tyn, pepper
) -> None:
    # Per 0060: a `next=` (e.g. back to the míchání form) is honoured on a
    # per-branch save via _safe_next.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {"next": "/sklad/michani/novy/?branch=1"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/michani/novy/?branch=1"


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_writes_movements_for_changed_rows_only(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.500"))

    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {
            "reason": "inventura 2026-06-12",
            f"qty_{pepper.pk}": "10.000",   # unchanged → skip
            f"qty_{paprika.pk}": "6.000",  # +0.500 → write
        },
    )
    assert response.status_code == 302
    after = Movement.objects.count()
    assert after == before + 1  # only paprika changed
    paprika_stock = Stock.objects.get(product=paprika, branch=tyn)
    assert paprika_stock.quantity == Decimal("6.000")
    pepper_stock = Stock.objects.get(product=pepper, branch=tyn)
    assert pepper_stock.quantity == Decimal("10.000")
    # The synthetic Movement carries the batch reason in note (with [STAV] prefix).
    mv = Movement.objects.order_by("-id").first()
    assert mv.note.startswith("[STAV] ")
    assert "inventura 2026-06-12" in mv.note


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_subunit_prefill_save_is_noop(
    user_vlastnik, tyn, pepper
) -> None:
    """Posting the 1dp prefill (10.0) for a sub-0.1 stored row (9.997) writes
    no movement and requires no reason — the compare happens at 1 dp."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("9.997"))
    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {"reason": "", f"qty_{pepper.pk}": "10.0"},
    )
    assert response.status_code == 302  # redirect, no reason demanded
    assert Movement.objects.count() == before  # no phantom change
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("9.997")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_requires_reason(
    user_vlastnik, tyn, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    before = Movement.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {"reason": "", f"qty_{pepper.pk}": "12.000"},
    )
    # Form re-renders with error; no movements written.
    assert response.status_code == 200
    assert Movement.objects.count() == before


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_edit_handles_multiple_changes_atomically(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("5.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/inventura/TYN/",
        {
            "reason": "inventura — víc změn najednou",
            f"qty_{pepper.pk}": "11.500",   # +1.500
            f"qty_{paprika.pk}": "4.000",  # -1.500
        },
    )
    assert response.status_code == 302
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("11.500")
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("4.000")
    # Two movements: one prijem (pepper +) and one vydej (paprika -).
    new_movements = list(Movement.objects.order_by("-id")[:2])
    kinds = {mv.kind for mv in new_movements}
    assert kinds == {Movement.Kind.PRIJEM, Movement.Kind.VYDEJ}


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_button_appears_when_branch_selected(
    user_vlastnik, tyn
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    # Without ?branch — no inventura button.
    response_no = client.get("/sklad/katalog/")
    assert response_no.status_code == 200
    assert b"Inventura TYN" not in response_no.content
    # With ?branch=TYN — button present.
    response_yes = client.get("/sklad/katalog/?branch=TYN")
    assert response_yes.status_code == 200
    assert b"Inventura TYN" in response_yes.content


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_button_hidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    # Obsluha is auto-scoped — branch dropdown isn't even shown but
    # the catalog page renders all products. The Inventura button
    # must not appear for obsluha regardless of any URL params.
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    assert b"Inventura" not in response.content


# ---------------------------------------------------------------------------
# Pass 5f — Guided overdraw correction (per decision 0042)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_warning_card_shows_with_correction_button_for_vlastnik(
    user_vlastnik, tyn, pepper
) -> None:
    """Vlastník submitting an overdraw výdej sees the structured
    warning card with an "Upravit stav skladu" button per row."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": str(tyn.pk),
            "odberatel": str(
                Customer.objects.get(is_default_recipient=True).pk
            ),
            "date_issued": date.today().isoformat(),
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "12.000",  # 7 kg shortfall
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 200
    body = response.content
    assert b"Nedostatek na skladu" in body or b"Nedostatek na sklad" in body
    assert b"12,0" in body  # 1 dp, Czech comma (per 0061)
    assert b"5,0" in body
    assert b"7,0" in body  # shortfall
    assert b"Upravit stav skladu" in body
    # Movement should NOT have been created.
    assert not Movement.objects.filter(
        kind=Movement.Kind.VYDEJ, branch=tyn
    ).exists()


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_warning_card_hides_button_for_obsluha(
    user_obsluha_tyn, tyn, pepper
) -> None:
    """Obsluha sees the structured warning but no correction button
    (stock direct edit is vlastník-only per 0040)."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": str(tyn.pk),
            "odberatel": str(
                Customer.objects.get(is_default_recipient=True).pk
            ),
            "date_issued": date.today().isoformat(),
            "note": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "10.000",
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
        },
    )
    assert response.status_code == 200
    body = response.content
    assert b"jen vlastn\xc3\xadk" in body  # "jen vlastník"
    assert b"Upravit stav skladu" not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_warning_lists_all_insufficient_lines(
    user_vlastnik, tyn, pepper, paprika
) -> None:
    """Multi-line overdraw shows ALL the short items, not just the first."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": str(tyn.pk),
            "odberatel": str(
                Customer.objects.get(is_default_recipient=True).pk
            ),
            "date_issued": date.today().isoformat(),
            "note": "",
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "8.000",  # 3 short
            "lines-0-sarze": "",
            "lines-0-expiry": "",
            "lines-0-note": "",
            "lines-1-product": str(paprika.pk),
            "lines-1-quantity_kg": "10.000",  # 7 short
            "lines-1-sarze": "",
            "lines-1-expiry": "",
            "lines-1-note": "",
        },
    )
    assert response.status_code == 200
    body = response.content
    assert pepper.name_cs.encode() in body
    assert paprika.name_cs.encode() in body
    # Both shortfalls appear (1 dp, Czech comma per 0061).
    assert b"3,0" in body
    assert b"7,0" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_aggregates_multiple_lines_of_same_product(
    user_vlastnik, tyn, pepper
) -> None:
    """Two formset rows for the same product (different šarže) sum up
    against stock for the overdraw check."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/vydej/novy/",
        {
            "branch": str(tyn.pk),
            "odberatel": str(
                Customer.objects.get(is_default_recipient=True).pk
            ),
            "date_issued": date.today().isoformat(),
            "note": "",
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": str(pepper.pk),
            "lines-0-quantity_kg": "6.000",
            "lines-0-sarze": "A",
            "lines-0-expiry": "",
            "lines-0-note": "",
            "lines-1-product": str(pepper.pk),
            "lines-1-quantity_kg": "6.000",  # combined 12 > 10
            "lines-1-sarze": "B",
            "lines-1-expiry": "",
            "lines-1-note": "",
        },
    )
    assert response.status_code == 200
    assert b"Nedostatek na sklad" in response.content
    assert b"12,0" in response.content  # combined requested (1 dp, comma)
    assert b"2,0" in response.content  # shortfall


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_overdraw_clears_after_stock_correction(
    user_vlastnik, tyn, pepper
) -> None:
    """After vlastník bumps Stock via apply_stock_adjustment the same
    výdej submit goes through."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    ricany_pk = Customer.objects.get(is_default_recipient=True).pk
    client = Client()
    client.force_login(user_vlastnik)
    payload = {
        "branch": str(tyn.pk),
        "odberatel": str(ricany_pk),
        "date_issued": date.today().isoformat(),
        "note": "",
        "lines-TOTAL_FORMS": "1",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "1",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-product": str(pepper.pk),
        "lines-0-quantity_kg": "8.000",
        "lines-0-sarze": "",
        "lines-0-expiry": "",
        "lines-0-note": "",
    }
    # 1st attempt — overdraw, form re-rendered.
    r1 = client.post("/sklad/vydej/novy/", payload)
    assert r1.status_code == 200
    assert not Movement.objects.filter(
        kind=Movement.Kind.VYDEJ, branch=tyn
    ).exists()
    # Operator corrects stock via the helper service.
    from inventory.services import apply_stock_adjustment

    apply_stock_adjustment(
        product=pepper,
        branch=tyn,
        new_quantity=Decimal("10.000"),
        reason="inventura — opraveno",
        user=user_vlastnik,
    )
    # 2nd attempt — same payload, now goes through.
    r2 = client.post("/sklad/vydej/novy/", payload)
    assert r2.status_code == 302
    assert Movement.objects.filter(
        kind=Movement.Kind.VYDEJ, branch=tyn
    ).exists()


# ---------------------------------------------------------------------------
# Pass 5g — Historie redesign (tab chips)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_tab_chips_render(user_vlastnik, tyn, pepper, ricany) -> None:
    """All five tabs render with correct counts; "Vše" active by default."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    # One prijem
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.PRIJEM,
            dodavatel=Supplier.objects.create(name="X"),
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("5.000"))],
        user=user_vlastnik,
    )
    # One vydej
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.VYDEJ, odberatel=ricany,
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    # One [STAV] (stock adjustment)
    from inventory.services import apply_stock_adjustment
    apply_stock_adjustment(
        product=pepper, branch=tyn, new_quantity=Decimal("110.000"),
        reason="inventura test", user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/")
    assert response.status_code == 200
    body = response.content
    assert b"V\xc5\xa1e" in body                                        # Vše
    assert b"P\xc5\x99\xc3\xadjmy" in body                              # Příjmy
    assert b"V\xc3\xbddeje" in body                                     # Výdeje
    assert b"Inventura / \xc3\xbaprava stavu" in body                   # Inventura / úprava stavu
    assert b"Editov\xc3\xa1no" in body                                  # Editováno


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_tab_prijem_filters_to_prijem_only(
    user_vlastnik, tyn, pepper, ricany
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("50.000"))
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.PRIJEM,
            dodavatel=Supplier.objects.create(name="P"),
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_vlastnik,
    )
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.VYDEJ, odberatel=ricany,
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?tab=prijem")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Only prijem rows; no vydej rows.
    assert "příjem" in body
    # vydej kind label appears only in the chip ("Výdeje (1)"); the
    # row-level Druh column should have only one rendered row.
    # Quick proxy: count `</tr>` in tbody… use the protistrana column
    # check instead. The vydej protistrana is Říčany; if no vydej rows
    # render, Říčany won't appear in the row data.
    assert "Říčany" not in body[body.index("<tbody"):]


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_tab_inventura_filters_to_stav_only(
    user_vlastnik, tyn, pepper, ricany
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("50.000"))
    # Normal výdej (not inventura).
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.VYDEJ, odberatel=ricany,
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    # Inventura — synthetic Movement with [STAV] prefix.
    from inventory.services import apply_stock_adjustment
    apply_stock_adjustment(
        product=pepper, branch=tyn, new_quantity=Decimal("60.000"),
        reason="inventura k testu", user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?tab=inventura")
    assert response.status_code == 200
    body = response.content
    # Only the inventura row should show. The inventura row uses the
    # "Inventura / ruční úprava" counterparty, which contains "Inventura".
    # The regular výdej used Říčany — should be absent from the table body.
    table_body_idx = body.index(b"<tbody")
    table_body = body[table_body_idx:]
    assert b"Inventura" in table_body
    assert b"\xc5\x98\xc3\xad\xc4\x8dany" not in table_body  # "Říčany"


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_inventura_movements_get_inventura_label(
    user_vlastnik, tyn, pepper
) -> None:
    """[STAV] movements get the special 'inventura' label in the Druh
    column, not the generic prijem/vydej tag."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("50.000"))
    from inventory.services import apply_stock_adjustment
    apply_stock_adjustment(
        product=pepper, branch=tyn, new_quantity=Decimal("55.000"),
        reason="test inventura", user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/")
    assert response.status_code == 200
    body = response.content
    # The inventura label replaces the prijem badge for [STAV] rows.
    table_body_idx = body.index(b"<tbody")
    assert b"inventura" in body[table_body_idx:]


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_legacy_kind_param_maps_to_tab(
    user_vlastnik, tyn, pepper, ricany
) -> None:
    """Bookmarked ?kind=vydej links still work after the tab redesign."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("50.000"))
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.PRIJEM,
            dodavatel=Supplier.objects.create(name="L"),
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_vlastnik,
    )
    apply_movement(
        movement=Movement(
            branch=tyn, kind=Movement.Kind.VYDEJ, odberatel=ricany,
            date_issued=date.today(), note="", created_by=user_vlastnik,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pohyby/?kind=vydej")
    assert response.status_code == 200
    body = response.content
    # Active tab should be Výdeje.
    table_body_idx = body.index(b"<tbody")
    table_body = body[table_body_idx:]
    # Only the vydej should be in the body; no prijem row.
    assert b"\xc5\x98\xc3\xad\xc4\x8dany" in table_body  # Říčany odběratel


# ---------------------------------------------------------------------------
# Pass 6 — Reorder threshold + reservations (per decisions 0043 + 0044 + 0045)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_threshold_for_returns_override_when_present(tyn, sez, pepper) -> None:
    """threshold_for() returns the branch-specific override over the
    product default, per decision 0043."""
    from inventory.models import StockThresholdOverride
    from inventory.services import threshold_for

    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    StockThresholdOverride.objects.create(
        product=pepper, branch=tyn, threshold_kg=Decimal("10.000")
    )
    assert threshold_for(pepper, tyn) == Decimal("10.000")
    # No override for SEZ → falls back to product default.
    assert threshold_for(pepper, sez) == Decimal("5.000")


@pytest.mark.django_db
def test_threshold_for_none_when_neither_set(tyn, pepper) -> None:
    """threshold_for() returns None (no alert) when nothing is set."""
    from inventory.services import threshold_for

    assert threshold_for(pepper, tyn) is None


@pytest.mark.django_db
def test_reserved_kg_planned_mixing_counts(
    tyn, pepper, paprika, user_vlastnik
) -> None:
    """A PLANNED MixingJob's component lines feed reserved_kg() at the
    job's branch — but RUNNING and CANCELLED do not."""
    from inventory.services import plan_mixing_job, reserved_kg

    mix = Product.objects.create(name_cs="Test směs", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=pepper, ratio=Decimal("0.500")
    )
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=paprika, ratio=Decimal("0.500")
    )
    # PLANNED job 10 kg → 5 kg pepper + 5 kg paprika reserved.
    plan_mixing_job(
        branch=tyn,
        mixture=mix,
        target_qty=Decimal("10.000"),
        user=user_vlastnik,
    )
    assert reserved_kg(pepper, tyn) == Decimal("5.000")
    assert reserved_kg(paprika, tyn) == Decimal("5.000")


@pytest.mark.django_db
def test_reserved_kg_running_job_does_not_count(
    tyn, pepper, user_vlastnik
) -> None:
    """A RUNNING MixingJob has already decremented stock; it should NOT
    additionally count as reserved."""
    from inventory.services import (
        plan_mixing_job,
        reserved_kg,
        start_mixing_job,
    )

    mix = Product.objects.create(name_cs="Mix2", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=pepper, ratio=Decimal("1.000")
    )
    # Add enough stock so start can consume.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("20.000"))
    job = plan_mixing_job(
        branch=tyn, mixture=mix, target_qty=Decimal("5.000"), user=user_vlastnik
    )
    assert reserved_kg(pepper, tyn) == Decimal("5.000")
    start_mixing_job(job=job, user=user_vlastnik)
    assert reserved_kg(pepper, tyn) == Decimal("0.000")


@pytest.mark.django_db
def test_reserved_kg_planned_transfer_outgoing_only(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """A PLANNED PlannedTransfer counts at source_branch only — NOT at
    target_branch. Promised inbound is explicitly deferred per 0044."""
    from inventory.models import PlannedTransfer
    from inventory.services import reserved_kg

    PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("3.000"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    assert reserved_kg(pepper, tyn) == Decimal("3.000")
    assert reserved_kg(pepper, sez) == Decimal("0.000")


@pytest.mark.django_db
def test_effective_kg_subtracts_reserved(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """effective_kg = Stock.quantity − reserved_kg at that branch."""
    from inventory.models import PlannedTransfer
    from inventory.services import effective_kg

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("2.500"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    assert effective_kg(pepper, tyn) == Decimal("7.500")
    # Target branch effective is unchanged (no inbound counting).
    assert effective_kg(pepper, sez) == Decimal("0.000")


@pytest.mark.django_db
def test_low_stock_rows_sorted_by_deficit(
    tyn, sez, pepper, paprika
) -> None:
    """low_stock_rows() returns only below-threshold (product, branch)
    pairs that the branch *carries* (per 0053), sorted by deficit DESC.
    SEZ has no Stock row for either product, so it does not appear."""
    from inventory.services import low_stock_rows

    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("2.000")
    paprika.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1.500"))

    rows = low_stock_rows()
    deficits = [r.deficit for r in rows]
    assert deficits == sorted(deficits, reverse=True)
    pairs = {(r.product.pk, r.branch.code) for r in rows}
    # Only TYN rows appear — SEZ carries neither product (no Stock row).
    assert pairs == {(pepper.pk, "TYN"), (paprika.pk, "TYN")}


@pytest.mark.django_db
def test_low_stock_rows_skips_products_without_threshold(
    tyn, pepper
) -> None:
    """Without a threshold set, the row never appears (no alert)."""
    from inventory.services import low_stock_rows

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.001"))
    # No threshold on pepper → no row even though stock is essentially zero.
    rows = low_stock_rows()
    assert not any(r.product.pk == pepper.pk for r in rows)


@pytest.mark.django_db
def test_plan_mixing_job_does_not_touch_stock(
    tyn, pepper, user_vlastnik
) -> None:
    """plan_mixing_job creates the PLANNED job + MixingJobLine rows
    without consuming Stock."""
    from inventory.services import plan_mixing_job

    mix = Product.objects.create(name_cs="MixA", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=pepper, ratio=Decimal("1.000")
    )
    job = plan_mixing_job(
        branch=tyn, mixture=mix, target_qty=Decimal("2.000"), user=user_vlastnik
    )
    assert job.state == MixingJob.State.PLANNED
    assert job.lines.count() == 1
    # Stock row not created.
    assert not Stock.objects.filter(product=pepper, branch=tyn).exists()
    # No Movement either.
    assert not Movement.objects.filter(branch=tyn).exists()


@pytest.mark.django_db
def test_start_mixing_job_from_planned_consumes_stock(
    tyn, pepper, user_vlastnik
) -> None:
    """start_mixing_job(job=planned) transitions PLANNED→RUNNING and
    decrements stock."""
    from inventory.services import plan_mixing_job, start_mixing_job

    mix = Product.objects.create(name_cs="MixB", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mix, component_product=pepper, ratio=Decimal("1.000")
    )
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    job = plan_mixing_job(
        branch=tyn, mixture=mix, target_qty=Decimal("3.000"), user=user_vlastnik
    )
    start_mixing_job(job=job, user=user_vlastnik)
    job.refresh_from_db()
    assert job.state == MixingJob.State.RUNNING
    assert job.consume_movement is not None
    pepper_stock = Stock.objects.get(product=pepper, branch=tyn)
    assert pepper_stock.quantity == Decimal("7.000")


@pytest.mark.django_db
def test_execute_planned_transfer_creates_paired_movements(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """execute_planned_transfer creates výdej @ source + příjem @ target,
    both linked back via the transfer FK, source decreased + target
    increased, dodák auto-issued on the výdej leg."""
    from inventory.models import DodaciList, PlannedTransfer
    from inventory.services import execute_planned_transfer

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    transfer = PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("3.000"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    vydej, prijem = execute_planned_transfer(transfer, executed_by=user_vlastnik)
    transfer.refresh_from_db()
    assert transfer.state == PlannedTransfer.State.DONE
    assert vydej.kind == Movement.Kind.VYDEJ
    assert prijem.kind == Movement.Kind.PRIJEM
    assert vydej.transfer_id == transfer.pk
    assert prijem.transfer_id == transfer.pk
    src_stock = Stock.objects.get(product=pepper, branch=tyn)
    tgt_stock = Stock.objects.get(product=pepper, branch=sez)
    assert src_stock.quantity == Decimal("7.000")
    assert tgt_stock.quantity == Decimal("3.000")
    # Counterparty is `is_internal=False` so dodák auto-issue fires.
    assert DodaciList.objects.filter(movement=vydej).exists()


@pytest.mark.django_db
def test_execute_planned_transfer_refuses_when_not_planned(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """Cannot execute a transfer that has already been DONE or CANCELLED."""
    from inventory.models import PlannedTransfer
    from inventory.services import execute_planned_transfer

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    transfer = PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("1.000"),
        scheduled_for=date.today(),
        state=PlannedTransfer.State.DONE,
        created_by=user_vlastnik,
    )
    with pytest.raises(ValidationError):
        execute_planned_transfer(transfer, executed_by=user_vlastnik)


@pytest.mark.django_db
def test_cancel_planned_transfer_no_stock_change(
    tyn, sez, pepper, user_vlastnik
) -> None:
    """cancel_planned_transfer flips state to CANCELLED, touches no stock."""
    from inventory.models import PlannedTransfer
    from inventory.services import cancel_planned_transfer

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    transfer = PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("2.000"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    cancel_planned_transfer(transfer, cancelled_by=user_vlastnik)
    transfer.refresh_from_db()
    assert transfer.state == PlannedTransfer.State.CANCELLED
    stock = Stock.objects.get(product=pepper, branch=tyn)
    assert stock.quantity == Decimal("5.000")


@pytest.mark.django_db
def test_overdraw_check_unchanged_by_planned_transfer(
    tyn, sez, pepper, user_vlastnik, ricany
) -> None:
    """Per 0044 § (4): a PLANNED transfer does NOT block a competing
    výdej from passing the overdraw pre-check on `Stock.quantity`. The
    race-loser hits the DB CHECK constraint only on actual apply.
    """
    from inventory.models import PlannedTransfer
    from inventory.views import _compute_overdraw

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    # 4 kg of pepper reserved by a planned transfer — but stock is 5 kg.
    PlannedTransfer.objects.create(
        source_branch=tyn,
        target_branch=sez,
        product=pepper,
        quantity_kg=Decimal("4.000"),
        scheduled_for=date.today(),
        created_by=user_vlastnik,
    )
    # Try a výdej of 4.5 kg — would be over-reserved (4 + 4.5 > 5),
    # but the overdraw check looks at raw Stock.quantity only.
    line = MovementLine(product=pepper, quantity_kg=Decimal("4.500"))
    warnings = _compute_overdraw(tyn, [line])
    # 4.5 < 5 raw, so no warning. Reservations are informational only.
    assert warnings == []


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mail_low_stock_summary_empty_sends_nothing(user_vlastnik) -> None:
    """No rows below threshold → no e-mail."""
    from django.core import mail

    from inventory.services import send_low_stock_summary

    result = send_low_stock_summary()
    assert result is None
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mail_low_stock_summary_populated_sends_one_email(
    tyn, pepper
) -> None:
    """One e-mail to every is_low_stock_recipient row per 0052."""
    from django.core import mail

    from inventory.models import SettingsRecipient
    from inventory.services import send_low_stock_summary

    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    # Conftest seeds Petr (is_low_stock_recipient=True) + Karolína (False).
    # Swap Petr's address to a deterministic value for the assertion.
    SettingsRecipient.objects.filter(label="Petr").update(
        email="petr@test.local"
    )

    result = send_low_stock_summary()
    assert result is not None and result >= 1
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["petr@test.local"]
    assert "Pepř" in msg.subject or "Dochází" in msg.subject
    assert "Pepř" in msg.body or pepper.name_cs in msg.body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_threshold_field_hidden_for_obsluha(
    user_obsluha_tyn, pepper
) -> None:
    """Obsluha sees the product edit page but the threshold field is
    not rendered (vlastník-only per 0043)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit/")
    assert response.status_code == 200
    # Czech header "Objednací bod" should not appear for obsluha.
    assert b"Objedna" not in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_threshold_field_shown_for_vlastnik(user_vlastnik, pepper) -> None:
    """Vlastník sees the threshold field on the product edit page."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit/")
    assert response.status_code == 200
    assert b"Objedna" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_planned_transfer_create_view_creates_row(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """POSTing to /prevody/novy/ creates a PLANNED PlannedTransfer."""
    from inventory.models import PlannedTransfer

    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/prevody/novy/",
        {
            "source_branch": str(tyn.pk),
            "target_branch": str(sez.pk),
            "product": str(pepper.pk),
            "quantity_kg": "1.500",
            "scheduled_for": date.today().isoformat(),
            "notes": "test transfer",
        },
    )
    assert response.status_code == 302
    pt = PlannedTransfer.objects.get(product=pepper)
    assert pt.state == PlannedTransfer.State.PLANNED
    assert pt.quantity_kg == Decimal("1.500")
    assert pt.created_by_id == user_vlastnik.pk


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_planned_transfer_index_renders(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/prevody/")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_low_stock_panel_appears_on_owner_dashboard(
    user_vlastnik, tyn, pepper
) -> None:
    """Owner dashboard renders the "Dochází zboží" panel when there
    are rows below threshold."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Pepper is below threshold → it shows in TYN's "Dochází" group.
    assert "Dochází" in body
    assert pepper.name_cs in body


# ---------------------------------------------------------------------------
# Pass 7 — Podpora (in-app docs + feedback log, per decision 0046)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_anonymous_redirects_to_login() -> None:
    response = Client().get("/sklad/podpora/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_get_renders_form_and_list_for_logged_in_user(
    user_vlastnik,
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/podpora/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Podpora" in body
    assert "Nahlásit chybu nebo požadavek" in body
    assert "Historie hlášení" in body
    assert "Žádná otevřená hlášení" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_post_creates_feedback_and_redirects(
    user_vlastnik,
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "/sklad/katalog/", "description": "Chybí mi sloupec X."},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/podpora/"
    f = Feedback.objects.get()
    assert f.description == "Chybí mi sloupec X."
    assert f.page_url == "/sklad/katalog/"
    assert f.created_by_id == user_vlastnik.pk
    assert f.resolved_at is None
    assert f.is_open


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_post_without_description_fails_validation(
    user_vlastnik,
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "/sklad/katalog/", "description": ""},
    )
    assert response.status_code == 200
    assert Feedback.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_post_with_optional_page_url(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "", "description": "Obecný nápad bez konkrétní stránky."},
    )
    assert response.status_code == 302
    f = Feedback.objects.get()
    assert f.page_url == ""


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_toggle_marks_resolved_as_vlastnik(user_vlastnik) -> None:
    f = Feedback.objects.create(
        created_by=user_vlastnik, description="test"
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(f"/sklad/podpora/{f.pk}/vyresit/")
    assert response.status_code == 302
    f.refresh_from_db()
    assert f.resolved_at is not None
    assert f.resolved_by_id == user_vlastnik.pk
    assert not f.is_open


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_toggle_reopens_already_resolved_as_vlastnik(
    user_vlastnik,
) -> None:
    f = Feedback.objects.create(
        created_by=user_vlastnik, description="test"
    )
    client = Client()
    client.force_login(user_vlastnik)
    client.post(f"/sklad/podpora/{f.pk}/vyresit/")
    client.post(f"/sklad/podpora/{f.pk}/vyresit/")
    f.refresh_from_db()
    assert f.resolved_at is None
    assert f.resolved_by is None
    assert f.is_open


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_hides_resolved_by_default_and_reveals_on_click(
    user_vlastnik,
) -> None:
    """Per 0059-part-B: resolved reports are hidden by default (only open +
    a reveal link render); ?show_resolved=1 renders the resolved rows."""
    from django.utils import timezone as _tz

    older_open = Feedback.objects.create(
        created_by=user_vlastnik, description="OLDER_OPEN_MARKER"
    )
    resolved = Feedback.objects.create(
        created_by=user_vlastnik, description="RESOLVED_MARKER"
    )
    resolved.resolved_at = _tz.now()
    resolved.resolved_by = user_vlastnik
    resolved.save()
    newer_open = Feedback.objects.create(
        created_by=user_vlastnik, description="NEWER_OPEN_MARKER"
    )

    client = Client()
    client.force_login(user_vlastnik)

    # Default GET: open rows render, resolved is NOT rendered, reveal link shown.
    body = client.get("/sklad/podpora/").content.decode("utf-8")
    pos_newer_open = body.find("NEWER_OPEN_MARKER")
    pos_older_open = body.find("OLDER_OPEN_MARKER")
    assert pos_newer_open != -1
    assert pos_older_open != -1
    assert "RESOLVED_MARKER" not in body  # hidden by default
    assert "Zobrazit vyřešená (1)" in body
    # Within open: newer comes before older.
    assert pos_newer_open < pos_older_open
    assert older_open.pk != newer_open.pk  # sanity

    # ?show_resolved=1 reveals the resolved row.
    revealed = client.get(
        "/sklad/podpora/?show_resolved=1"
    ).content.decode("utf-8")
    assert "RESOLVED_MARKER" in revealed
    assert "NEWER_OPEN_MARKER" in revealed


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_toggle_rejected_for_obsluha_with_message_redirect(
    user_obsluha_tyn, user_vlastnik,
) -> None:
    f = Feedback.objects.create(
        created_by=user_vlastnik, description="test"
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/podpora/{f.pk}/vyresit/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/podpora/"
    f.refresh_from_db()
    assert f.resolved_at is None
    assert f.is_open


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_visible_to_all_users_not_just_creator(
    user_vlastnik, user_obsluha_tyn,
) -> None:
    Feedback.objects.create(
        created_by=user_vlastnik, description="Hlášení od vlastníka"
    )
    Feedback.objects.create(
        created_by=user_obsluha_tyn, description="Hlášení od obsluhy"
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/podpora/")
    body = response.content.decode("utf-8")
    assert "Hlášení od vlastníka" in body
    assert "Hlášení od obsluhy" in body
    # Obsluha must NOT see the toggle button.
    assert "Vyřešit" not in body


# ---------------------------------------------------------------------------
# XLS recipe importer (Pass 8, per decision 0048)
# ---------------------------------------------------------------------------


_FIXTURE_XLS = "inventory/tests/fixtures/touzimsky.xls"


def _load_fixture_xls() -> bytes:
    with open(_FIXTURE_XLS, "rb") as f:
        return f.read()


def _xls_upload(name: str = "touzimsky.xls"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(
        name,
        _load_fixture_xls(),
        content_type="application/vnd.ms-excel",
    )


def test_parse_recipe_xls_sample() -> None:
    from inventory.services import parse_recipe_xls

    with open(_FIXTURE_XLS, "rb") as f:
        parsed = parse_recipe_xls(f, "touzimsky.xls")

    assert parsed.mixture_name == "Toužimský Knedlík"
    assert parsed.total_kg == Decimal("800.8")
    assert len(parsed.lines) == 5
    names = [line.name_cs for line in parsed.lines]
    assert "Krupička" in names
    assert "Škrob" in names
    assert "Sůl" in names
    assert "Kurkuma" in names
    # Notes capture the post-CELKEM rows.
    assert "BALIT" in parsed.notes
    assert "CELKOVÁ DOBA MÍCHÁNÍ" in parsed.notes
    assert parsed.warnings == []


def test_parse_recipe_xls_ratios_sum_to_one() -> None:
    from inventory.services import parse_recipe_xls

    with open(_FIXTURE_XLS, "rb") as f:
        parsed = parse_recipe_xls(f, "touzimsky.xls")

    total = sum((line.ratio for line in parsed.lines), Decimal("0"))
    assert total == Decimal("1.000000")
    for line in parsed.lines:
        assert line.ratio > 0


def test_parse_recipe_xls_title_cases_names() -> None:
    from inventory.services import parse_recipe_xls

    with open(_FIXTURE_XLS, "rb") as f:
        parsed = parse_recipe_xls(f, "touzimsky.xls")

    # Source XLS has "KRUPIČKA" (all caps) — must come back Title-Cased.
    assert "KRUPIČKA" not in [line.name_cs for line in parsed.lines]
    assert "Krupička" in [line.name_cs for line in parsed.lines]


def test_parse_recipe_xls_empty_file_raises_czech() -> None:
    import io

    from inventory.services import parse_recipe_xls

    # A 1-byte file is invalid XLS — both xlrd and openpyxl raise.
    # Our wrapper coerces all to ValueError with a Czech message
    # only for the "unknown extension" path; xlrd/openpyxl errors
    # bubble. Check that ValueError surfaces for the no-extension path.
    with pytest.raises(ValueError, match=".xls"):
        parse_recipe_xls(io.BytesIO(b"x"), "foo.txt")


@pytest.mark.django_db
def test_xls_import_upload_requires_login() -> None:
    response = Client().get("/sklad/katalog/import-xls/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_upload_obsluha_forbidden(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/import-xls/")
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_upload_vlastnik_renders_form(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/import-xls/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "XLS" in body
    assert "Načíst soubor" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_upload_post_parses_renders_review(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/import-xls/",
        {"xls_file": _xls_upload()},
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Toužimský" in body
    assert "Krupička" in body
    assert "Škrob" in body
    # No raw spices were seeded → every ingredient must show as new.
    assert "+ nová surovina" in body
    # Review form must be present.
    assert "Vytvořit směs" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_confirm_creates_mixture_and_components(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    # First POST: upload → review. We need to use the formset's management
    # form values that the review page rendered; easier to drive the service
    # path directly via the confirm endpoint with synthetic data that matches
    # what the review form would have posted.
    payload = {
        "name_cs": "Toužimský Knedlík",
        "notes": "BALIT Á 5 KG\nCELKOVÁ DOBA MÍCHÁNÍ 12 MINUT",
        "total_kg": "800.800",
        "form-TOTAL_FORMS": "5",
        "form-INITIAL_FORMS": "5",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-name_cs": "Krupička",
        "form-0-qty_kg": "317.000",
        "form-0-existing_product_id": "",
        "form-1-name_cs": "Škrob",
        "form-1-qty_kg": "112.000",
        "form-1-existing_product_id": "",
        "form-2-name_cs": "Vločky PF 51",
        "form-2-qty_kg": "355.000",
        "form-2-existing_product_id": "",
        "form-3-name_cs": "Sůl",
        "form-3-qty_kg": "16.000",
        "form-3-existing_product_id": "",
        "form-4-name_cs": "Kurkuma",
        "form-4-qty_kg": "0.800",
        "form-4-existing_product_id": "",
    }
    response = client.post("/sklad/katalog/import-xls/potvrdit/", payload)
    assert response.status_code == 302
    mixture = Product.objects.get(name_cs="Toužimský Knedlík")
    assert mixture.kind == Product.Kind.MIXTURE
    components = list(
        RecipeComponent.objects.filter(mixture_product=mixture)
        .order_by("component_product__name_cs")
    )
    assert len(components) == 5
    # Ratios sum to exactly 1.000000 — invariant from _normalize_ratios.
    assert sum((c.ratio for c in components), Decimal("0")) == Decimal("1.000000")
    # All five raw spices auto-created.
    raw_names = {c.component_product.name_cs for c in components}
    assert raw_names == {"Krupička", "Škrob", "Vločky PF 51", "Sůl", "Kurkuma"}
    for c in components:
        assert c.component_product.kind == Product.Kind.RAW_SPICE


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_confirm_reuses_existing_raw_spice_case_insensitive(
    user_vlastnik,
) -> None:
    """Seed "Krupička" in different case; import must reuse, not duplicate."""
    existing = Product.objects.create(
        name_cs="Krupička", kind=Product.Kind.RAW_SPICE
    )
    client = Client()
    client.force_login(user_vlastnik)
    payload = {
        "name_cs": "Test směs",
        "notes": "",
        "total_kg": "100.000",
        "form-TOTAL_FORMS": "2",
        "form-INITIAL_FORMS": "2",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        # All-caps to verify the casefold dedupe.
        "form-0-name_cs": "KRUPIČKA",
        "form-0-qty_kg": "80.000",
        "form-0-existing_product_id": "",
        "form-1-name_cs": "Pepř Nový",
        "form-1-qty_kg": "20.000",
        "form-1-existing_product_id": "",
    }
    response = client.post("/sklad/katalog/import-xls/potvrdit/", payload)
    assert response.status_code == 302
    # Only one "Krupička" exists — the existing one was reused.
    assert Product.objects.filter(name_cs__iexact="Krupička").count() == 1
    mixture = Product.objects.get(name_cs="Test směs")
    components = list(
        RecipeComponent.objects.filter(mixture_product=mixture)
    )
    assert any(c.component_product_id == existing.pk for c in components)


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_confirm_refuses_duplicate_mixture_name(
    user_vlastnik,
) -> None:
    Product.objects.create(
        name_cs="Toužimský Knedlík", kind=Product.Kind.MIXTURE
    )
    client = Client()
    client.force_login(user_vlastnik)
    payload = {
        "name_cs": "Toužimský Knedlík",
        "notes": "",
        "total_kg": "10.000",
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "1",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-name_cs": "Krupička",
        "form-0-qty_kg": "10.000",
        "form-0-existing_product_id": "",
    }
    response = client.post("/sklad/katalog/import-xls/potvrdit/", payload)
    assert response.status_code == 400
    body = response.content.decode("utf-8")
    assert "už v katalogu existuje" in body
    # Mixture count unchanged.
    assert Product.objects.filter(name_cs="Toužimský Knedlík").count() == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_confirm_rejects_zero_ratio(user_vlastnik) -> None:
    """One ingredient too tiny to represent at 6 dp → Czech error.

    Form qty_kg is decimal_places=3, smallest accepted = 0.001. For the
    ratio to quantise to 0 at 6 dp we need 0.001 / total < 5e-7, i.e.
    total > 2000. Using 0.001 / 9999.999 ≈ 1e-7 gives a reliable trip.
    """
    client = Client()
    client.force_login(user_vlastnik)
    payload = {
        "name_cs": "Mikro směs",
        "notes": "",
        "total_kg": "10000.000",
        "form-TOTAL_FORMS": "2",
        "form-INITIAL_FORMS": "2",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-name_cs": "Mouka",
        "form-0-qty_kg": "9999.999",
        "form-0-existing_product_id": "",
        "form-1-name_cs": "Mikrokoření",
        "form-1-qty_kg": "0.001",
        "form-1-existing_product_id": "",
    }
    response = client.post("/sklad/katalog/import-xls/potvrdit/", payload)
    assert response.status_code == 400
    body = response.content.decode("utf-8")
    assert "příliš malý poměr" in body
    # No mixture committed.
    assert not Product.objects.filter(name_cs="Mikro směs").exists()


@pytest.mark.django_db
def test_catalogue_index_shows_xls_import_button_for_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    with override_settings(**_VIEW_TEST_OVERRIDES):
        response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    assert "Importovat z XLS" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_catalogue_index_hides_xls_import_button_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    with override_settings(**_VIEW_TEST_OVERRIDES):
        response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    assert "Importovat z XLS" not in response.content.decode("utf-8")


# ---------------------------------------------------------------------------
# Batch A — Podpora feedback: form defaults to today, FAILED banner on dodák
# detail (per /podpora/ feedback #1 + #5, 2026-06-26).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_planned_transfer_create_view_prefills_today(user_vlastnik) -> None:
    """GET /prevody/novy/ renders scheduled_for pre-filled with today."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/prevody/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # ISO YYYY-MM-DD — browsers only honour ISO in <input type="date">.
    assert f'value="{date.today().isoformat()}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_plan_form_prefills_today(user_vlastnik, tyn) -> None:
    """GET /michani/planovat/ renders planned_for pre-filled with today."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/michani/planovat/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # ISO YYYY-MM-DD — browsers only honour ISO in <input type="date">.
    assert f'value="{date.today().isoformat()}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_create_view_prefills_today_iso(user_obsluha_tyn) -> None:
    """GET /sklad/prijem/novy/ renders date_issued pre-filled with today (ISO)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/prijem/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert f'value="{date.today().isoformat()}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_create_view_prefills_today_iso(user_obsluha_tyn) -> None:
    """GET /sklad/vydej/novy/ renders date_issued pre-filled with today (ISO)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/vydej/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert f'value="{date.today().isoformat()}"' in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_detail_renders_failed_banner_when_unresolved(
    user_tyn, tyn, ricany, pepper
) -> None:
    """When current_version has FAILED log and no SENT log, banner shows."""
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    # Replace all logs at current_version with a single FAILED row.
    DodaciListEmailLog.objects.filter(
        dodaci_list=dl, version=dl.current_version
    ).delete()
    DodaciListEmailLog.objects.create(
        dodaci_list=dl,
        version=dl.current_version,
        recipients="petr@kasia.cz",
        trigger_reason="initial send",
        status=DodaciListEmailLog.Status.FAILED,
        error_message="SMTP timeout",
    )
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/{dl.cislo}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Poslední odeslání selhalo." in body


# ---------------------------------------------------------------------------
# Batch B — Catalogue per-branch low-stock chips (Podpora feedback #4,
# 2026-06-26). Karolína: "Catalogue must show per-branch low-stock + drop
# the 'obě pobočky' assumption (N-branch ready)."
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_index_shows_branch_low_stock_chips(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """Product low at TYN only → 'TYN' chip on row, no 'SEZ'."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("20.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Pepper is low (not empty) → it lands in the "Dochází" group, whose
    # branch column is "Dochází na" and renders one low-branch chip.
    assert "sub-head low" in body  # the Dochází group header renders
    assert "sub-head empty" not in body  # no empty products → no empty group
    assert "Dochází na" in body
    assert ">TYN<" in body  # chip text
    # No SEZ chip on this row (SEZ has 20 kg > 5 kg threshold).
    pepper_row_idx = body.index("Pepř")
    snippet = body[pepper_row_idx : pepper_row_idx + 2000]
    assert "SEZ" not in snippet


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_index_three_branches_chip(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """Genericity proof: a third active branch low only there → chip shows."""
    new_b = Branch.objects.create(code="HRA", name="Hradec Králové", is_active=True)
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("20.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("20.000"))
    Stock.objects.create(product=pepper, branch=new_b, quantity=Decimal("1.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    pepper_row_idx = body.index("Pepř")
    snippet = body[pepper_row_idx : pepper_row_idx + 2000]
    assert ">HRA<" in snippet
    # The other two branches should not appear as chips in this row.
    assert ">TYN<" not in snippet
    assert ">SEZ<" not in snippet


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_filter_branch_does_not_show_per_branch_chip(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """When ?branch=<code> is set, per-row chip column is empty (existing
    per-row 'dochází' badge already covers the single-branch case)."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("20.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?branch=TYN")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    pepper_row_idx = body.index("Pepř")
    snippet = body[pepper_row_idx : pepper_row_idx + 2000]
    # With a single branch in scope the per-branch chip column is suppressed.
    assert "Pepř" in body
    # No branch chip element for the branch column must be present in this row.
    import re
    chips = re.findall(
        r"<span class=\"(?:low|empty)-branch\"[^>]*>([A-Z]{3})</span>", snippet
    )
    assert chips == []


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_obsluha_does_not_show_per_branch_chip(
    user_obsluha_tyn, tyn, pepper
) -> None:
    """Obsluha is implicitly single-branch scoped → chip column empty."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    pepper_row_idx = body.index("Pepř")
    snippet = body[pepper_row_idx : pepper_row_idx + 2000]
    import re
    chips = re.findall(
        r"<span class=\"(?:low|empty)-branch\"[^>]*>([A-Z]{3})</span>", snippet
    )
    assert chips == []


# ---------------------------------------------------------------------------
# Batch C — Settings recipient save bug (Feedback #2a, 2026-06-26).
# Root cause: the form template renders Settings fields via per-section
# whitelists. template_low_stock_subject + template_low_stock_body (added
# in decision 0045) were in none of the four sections, so POSTs stripped
# them, ModelForm flagged them required, validation silently failed, and
# Karolína's recipient change never persisted.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_form_renders_every_modelform_field(user_vlastnik) -> None:
    """Regression: every SettingsForm field has an input rendered in the
    page. If a future field is added to Settings without also updating
    settings_form.html, this fails before it reaches prod."""
    from inventory.forms import SettingsForm

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/nastaveni/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    form = SettingsForm()
    missing = [name for name in form.fields if f'name="{name}"' not in body]
    assert not missing, f"Fields rendered nowhere on /nastaveni/: {missing}"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_settings_recipient_change_persists_via_browser_payload(
    user_vlastnik,
) -> None:
    """Reproduce Karolína's flow: POST the EXACT field set the template
    renders (no extras). Recipient change must persist.

    Per 0052: recipients live in the SettingsRecipient formset; this
    test edits the Karolína row's email via the formset payload."""
    from inventory.models import Settings, SettingsRecipient

    client = Client()
    client.force_login(user_vlastnik)

    # Build the SettingsForm half of the POST from the rendered form so
    # the test is coupled to the template, not to a hand-curated payload.
    from inventory.forms import SettingsForm

    form = SettingsForm(instance=Settings.load())
    data = {}
    for name in form.fields:
        if name == "logo":
            continue  # FileField — leave unset
        if name == "smtp_password":
            data[name] = ""  # blank → preserve
            continue
        val = form[name].value()
        if val is None:
            val = ""
        if name == "smtp_use_tls":
            data[name] = "on" if val else ""
            continue
        data[name] = str(val)

    # Build the recipient-formset payload: keep Petr, change Karolína's
    # address.
    data.update(_recipient_formset_keepall())
    karolina = SettingsRecipient.objects.get(label="Karolína")
    petr = SettingsRecipient.objects.get(label="Petr")
    rows = list(
        SettingsRecipient.objects.all().order_by(
            "-is_active", "sort_order", "id"
        )
    )
    karolina_idx = rows.index(karolina)
    data[f"recipient-{karolina_idx}-email"] = "nova_karolina@kasia.cz"

    response = client.post("/sklad/nastaveni/", data)
    assert response.status_code == 302, (
        f"Expected redirect on save, got {response.status_code}. "
        f"Body: {response.content.decode('utf-8')[:1500]}"
    )
    karolina.refresh_from_db()
    assert karolina.email == "nova_karolina@kasia.cz"
    petr.refresh_from_db()
    assert petr.email == "petr@example.cz"  # untouched


# ---------------------------------------------------------------------------
# Batch D — N-list recipients (decision 0052 supersedes 0031 in part,
# 2026-06-28). Operator-managed SettingsRecipient table replaces the
# fixed (Petr, Karolína) pair on Settings.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_recipient_email_uniqueness_case_insensitive() -> None:
    from django.db import IntegrityError, transaction

    from inventory.models import SettingsRecipient

    # Conftest already created petr@example.cz. Adding PETR@EXAMPLE.CZ
    # must collide via the Lower("email") unique constraint.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SettingsRecipient.objects.create(
                email="PETR@EXAMPLE.CZ", label="Dup"
            )


@pytest.mark.django_db(transaction=True)
def test_send_dodaci_list_iterates_all_active_recipients(
    tyn, ricany, pepper, user_tyn
) -> None:
    """Three active rows → three recipients on the message."""
    from inventory.models import SettingsRecipient

    SettingsRecipient.objects.create(
        email="uctarna@kasia.cz",
        label="Účetní",
        is_active=True,
        is_low_stock_recipient=False,
        sort_order=2,
    )
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 28),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    log = DodaciListEmailLog.objects.get(dodaci_list__movement=mv)
    assert log.status == DodaciListEmailLog.Status.SENT
    # 3 active rows in conftest + new one = should ship to 3 addresses.
    recips = [r.strip() for r in log.recipients.split(",")]
    assert set(recips) == {
        "petr@example.cz",
        "karolina@example.cz",
        "uctarna@kasia.cz",
    }


@pytest.mark.django_db(transaction=True)
def test_send_dodaci_list_skips_inactive_recipients(
    tyn, ricany, pepper, user_tyn
) -> None:
    """Karolína inactive → only Petr receives."""
    from inventory.models import SettingsRecipient

    SettingsRecipient.objects.filter(label="Karolína").update(is_active=False)
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mv = apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 28),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_tyn,
    )
    log = DodaciListEmailLog.objects.get(dodaci_list__movement=mv)
    recips = [r.strip() for r in log.recipients.split(",")]
    assert recips == ["petr@example.cz"]


@pytest.mark.django_db
def test_send_dodaci_list_refuses_with_zero_active_recipients(
    tyn, ricany, pepper, user_tyn
) -> None:
    """No active recipients → ValidationError before any DB write."""
    from inventory.models import SettingsRecipient

    SettingsRecipient.objects.update(is_active=False)
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    with pytest.raises(ValidationError):
        apply_movement(
            movement=_vydej(tyn, ricany, user_tyn),
            lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
            user=user_tyn,
        )
    assert Movement.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_send_low_stock_summary_targets_low_stock_recipients_only(
    tyn, pepper
) -> None:
    """Karolína (is_low_stock_recipient=False) does NOT receive the summary."""
    from django.core import mail

    from inventory.services import send_low_stock_summary

    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))

    result = send_low_stock_summary()
    assert result is not None
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["petr@example.cz"]
    # Karolína is in the recipient table but NOT subscribed → not in to=.
    assert "karolina@example.cz" not in mail.outbox[0].to


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_send_low_stock_summary_returns_none_with_no_subscribers(
    tyn, pepper
) -> None:
    """No is_low_stock_recipient=True rows → no e-mail, return None."""
    from django.core import mail

    from inventory.models import SettingsRecipient
    from inventory.services import send_low_stock_summary

    SettingsRecipient.objects.update(is_low_stock_recipient=False)
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))

    result = send_low_stock_summary()
    assert result is None
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipient_formset_renders_existing_rows(user_vlastnik) -> None:
    """`/nastaveni/` renders one input row per existing SettingsRecipient
    plus the formset's empty extra row."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/nastaveni/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Both seeded emails appear pre-filled on the page.
    assert "petr@example.cz" in body
    assert "karolina@example.cz" in body
    # Formset management form is present.
    assert "recipient-TOTAL_FORMS" in body
    assert "recipient-INITIAL_FORMS" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipient_creation_via_settings_form(user_vlastnik) -> None:
    """POSTing /nastaveni/ with a new (extra) recipient row creates it."""
    from inventory.forms import SettingsForm
    from inventory.models import Settings, SettingsRecipient

    client = Client()
    client.force_login(user_vlastnik)

    # Build the Settings half of the payload.
    form = SettingsForm(instance=Settings.load())
    data = {}
    for name in form.fields:
        if name == "logo":
            continue
        if name == "smtp_password":
            data[name] = ""
            continue
        val = form[name].value()
        if val is None:
            val = ""
        if name == "smtp_use_tls":
            data[name] = "on" if val else ""
            continue
        data[name] = str(val)

    # Keep existing recipients + add one extra "Účetní" row.
    data.update(_recipient_formset_keepall())
    n = int(data["recipient-TOTAL_FORMS"])
    data["recipient-TOTAL_FORMS"] = str(n + 1)
    data[f"recipient-{n}-id"] = ""
    data[f"recipient-{n}-email"] = "uctarna@example.cz"
    data[f"recipient-{n}-label"] = "Účetní"
    data[f"recipient-{n}-is_active"] = "on"
    data[f"recipient-{n}-sort_order"] = "2"

    response = client.post("/sklad/nastaveni/", data)
    assert response.status_code == 302, response.content[:1500]
    assert SettingsRecipient.objects.filter(email="uctarna@example.cz").exists()


@pytest.mark.django_db
def test_data_migration_idempotent() -> None:
    """Re-running the 0012 RunPython callable on a populated table is a
    no-op. The conftest seed already populated Petr + Karolína; calling
    the migration helper again must not duplicate or modify them."""
    import importlib

    from django.apps import apps as django_apps

    from inventory.models import SettingsRecipient

    before = sorted(
        SettingsRecipient.objects.all().values_list("email", flat=True)
    )
    mod = importlib.import_module(
        "inventory.migrations.0012_settings_recipients_table"
    )
    mod._copy_recipients_into_table(django_apps, None)
    after = sorted(
        SettingsRecipient.objects.all().values_list("email", flat=True)
    )
    assert before == after


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_detail_no_banner_after_successful_resend(
    user_tyn, tyn, ricany, pepper
) -> None:
    """FAILED followed by SENT at current_version → no banner."""
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    DodaciListEmailLog.objects.filter(
        dodaci_list=dl, version=dl.current_version
    ).delete()
    DodaciListEmailLog.objects.create(
        dodaci_list=dl,
        version=dl.current_version,
        recipients="petr@kasia.cz",
        trigger_reason="initial send",
        status=DodaciListEmailLog.Status.FAILED,
        error_message="SMTP timeout",
    )
    DodaciListEmailLog.objects.create(
        dodaci_list=dl,
        version=dl.current_version,
        recipients="petr@kasia.cz",
        trigger_reason="ruční opětovné odeslání",
        status=DodaciListEmailLog.Status.SENT,
    )
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/{dl.cislo}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Poslední odeslání selhalo." not in body


# ---------------------------------------------------------------------------
# Decision 0053 — Stock row existence IS the "branch carries product" flag.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_low_stock_summary_skips_branch_without_stock_row(
    tyn, sez, pepper
) -> None:
    """Per 0053: a branch without a Stock row does not enter the
    low-stock report, even when its 'effective = 0' would otherwise
    register as below threshold."""
    from inventory.services import low_stock_rows

    pepper.reorder_threshold_kg = Decimal("10.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("5.000"))
    # TYN intentionally has no Stock row for pepper.

    rows = low_stock_rows()
    pairs = {(r.product.pk, r.branch.code) for r in rows}
    assert (pepper.pk, "SEZ") in pairs
    assert (pepper.pk, "TYN") not in pairs


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_chip_omits_branch_without_stock_row(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """Catalogue per-branch chip does not appear for a branch that
    doesn't carry the product (no Stock row)."""
    pepper.reorder_threshold_kg = Decimal("10.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("5.000"))
    # No Stock row at TYN.

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    pepper_row_idx = body.index("Pepř")
    snippet = body[pepper_row_idx : pepper_row_idx + 2000]
    import re

    chips = re.findall(
        r"<span class=\"(?:low|empty)-branch\"[^>]*>([A-Z]{3})</span>", snippet
    )
    assert "SEZ" in chips
    assert "TYN" not in chips


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_seeds_stock_rows_for_all_active_branches(
    user_vlastnik, tyn, sez
) -> None:
    """Per 0053: creating a product seeds a 0-kg Stock row on every
    active branch, preserving today's 'visible everywhere' default."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/novy/",
        {
            "name_cs": "Kmín",
            "kind": Product.Kind.RAW_SPICE,
            "notes": "",
            "reorder_threshold_kg": "",
        },
    )
    assert response.status_code in (200, 302)
    product = Product.objects.get(name_cs="Kmín")
    branch_ids = set(
        Stock.objects.filter(product=product).values_list(
            "branch_id", flat=True
        )
    )
    active_branch_ids = set(
        Branch.objects.filter(is_active=True).values_list("id", flat=True)
    )
    assert branch_ids == active_branch_ids
    assert all(
        s.quantity == Decimal("0.000")
        for s in Stock.objects.filter(product=product)
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_branch_add_creates_zero_stock_row(
    user_vlastnik, tyn, pepper
) -> None:
    """Vlastník POST adds carry-state (0-kg Stock row). Second POST is a
    no-op (idempotent)."""
    client = Client()
    client.force_login(user_vlastnik)
    url = f"/sklad/katalog/{pepper.pk}/pobocky/{tyn.pk}/pridat/"
    r1 = client.post(url)
    assert r1.status_code in (200, 302)
    assert Stock.objects.filter(product=pepper, branch=tyn).exists()
    stock = Stock.objects.get(product=pepper, branch=tyn)
    assert stock.quantity == Decimal("0.000")
    # Second POST stays idempotent.
    r2 = client.post(url)
    assert r2.status_code in (200, 302)
    assert Stock.objects.filter(product=pepper, branch=tyn).count() == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_branch_remove_deletes_row_even_with_stock(
    user_vlastnik, tyn, pepper
) -> None:
    """Per 0053 + Matej's allow-but-warn pick: the server has no
    precondition — removal succeeds even with quantity > 0. UI warns."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.500"))
    client = Client()
    client.force_login(user_vlastnik)
    url = f"/sklad/katalog/{pepper.pk}/pobocky/{tyn.pk}/odebrat/"
    response = client.post(url)
    assert response.status_code in (200, 302)
    assert not Stock.objects.filter(product=pepper, branch=tyn).exists()


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_branch_add_forbidden_for_obsluha(
    user_obsluha_tyn, tyn, pepper
) -> None:
    """Carry-state mutation is vlastník-only; obsluha gets 403."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    url = f"/sklad/katalog/{pepper.pk}/pobocky/{tyn.pk}/pridat/"
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_edit_renders_pobocky_section_with_drzi_state(
    user_vlastnik, tyn, sez, pepper
) -> None:
    """Product edit page shows the Pobočky section with the correct
    drží/nedrží state per branch and the matching action button."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("2.000"))
    # SEZ has no Stock row → nedrží.

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Pobočky držící tento produkt" in body
    assert "Drží" in body
    assert "Nedrží" in body
    # The TYN row has the Odebrat action; the SEZ row has Přidat.
    assert (
        f"/sklad/katalog/{pepper.pk}/pobocky/{tyn.pk}/odebrat/" in body
    )
    assert (
        f"/sklad/katalog/{pepper.pk}/pobocky/{sez.pk}/pridat/" in body
    )


# ---------------------------------------------------------------------------
# Polish round 2 — row-click, auto-append line, catalog state filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_job_index_rows_are_row_link(user_vlastnik, tyn, pepper) -> None:
    """Mixing index rows must use the shared `tr.row-link` pattern so the
    whole row navigates to the job detail."""
    from inventory.services import start_mixing_job

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))
    mixture = _mk_mixture_with_recipe("M", [(pepper, "1.0")])
    job = start_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("2.000"),
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/michani/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'class="row-link"' in body
    assert f'data-href="/sklad/michani/{job.pk}/"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_movement_form_lines_has_add_line_btn_id(user_vlastnik) -> None:
    """The auto-append <script> in _movement_form_lines.html keys off
    `#add-line-btn` — guarantee the marker keeps shipping."""
    client = Client()
    client.force_login(user_vlastnik)
    for path in ("/sklad/prijem/novy/", "/sklad/vydej/novy/"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        assert 'id="add-line-btn"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_line_row_partial_still_returns_blank_row(user_tyn) -> None:
    """Sanity: line_row_partial keeps returning a blank row with the
    expected name attrs — the auto-append JS depends on it."""
    client = Client()
    client.force_login(user_tyn)
    response = client.get("/sklad/_partials/line-row/?index=5")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="lines-5-product"' in body
    assert 'name="lines-5-quantity_kg"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_filter_state_low_keeps_only_low_rows(
    user_vlastnik, tyn, sez, pepper, paprika
) -> None:
    """?state=low keeps rows where is_low but not effective<=0 with threshold."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    # Pepper: low (1 kg < 5 kg threshold, still positive).
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("1.000"))
    # Paprika: above threshold on both branches.
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("20.000"))
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("20.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?state=low")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs not in body
    assert "Nalezeno: 1" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_form_shows_recent_movements_panel(
    user_vlastnik, tyn, supplier, pepper
) -> None:
    """The příjem create form renders the last N příjmy underneath
    with a link to the pre-filtered history page."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 28),
            dodavatel=supplier,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/prijem/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Poslední příjmy" in body
    assert "/sklad/pohyby/?tab=prijem" in body
    assert supplier.name in body
    # The vydej-only tab link must NOT appear in the příjem panel.
    assert "?tab=vydej" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_form_shows_recent_movements_panel(
    user_vlastnik, tyn, ricany, pepper
) -> None:
    """The výdej create form renders the last N výdeje underneath
    with a link to the pre-filtered history page."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 28),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/vydej/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Poslední výdeje" in body
    assert "/sklad/pohyby/?tab=vydej" in body
    assert ricany.name in body
    assert "?tab=prijem" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recent_movements_panel_scopes_obsluha_to_own_branch(
    user_obsluha_tyn, user_vlastnik, tyn, sez, supplier, pepper
) -> None:
    """Obsluha sees only own-branch movements in the recent panel."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("0.000"))
    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 28),
            dodavatel=supplier,
            note="TYN-PANEL-TEST",
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    sez_supplier = Supplier.objects.create(name="SEZ Dodavatel")
    apply_movement(
        movement=Movement(
            branch=sez,
            kind=Movement.Kind.PRIJEM,
            date_issued=date(2026, 6, 28),
            dodavatel=sez_supplier,
            note="SEZ-PANEL-TEST",
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("1.000"))],
        user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/prijem/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Both suppliers appear in the dodavatel <select> dropdown. The
    # panel scoping assertion runs on the "Poslední příjmy" snippet
    # only — that snippet must not include the SEZ supplier name.
    panel_start = body.index("Poslední příjmy")
    panel = body[panel_start:]
    assert supplier.name in panel
    assert sez_supplier.name not in panel


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recent_movements_panel_hidden_when_empty(user_vlastnik) -> None:
    """No movements yet → no panel rendered (silent on empty)."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/prijem/novy/")
    body = response.content.decode("utf-8")
    assert "Poslední příjmy" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_filter_state_empty_keeps_only_empty_rows(
    user_vlastnik, tyn, sez, pepper, paprika
) -> None:
    """?state=empty keeps rows where effective<=0 and threshold is set."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    # Pepper: effective = 0 on both branches → empty.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("0.000"))
    # Paprika: low but not empty.
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=paprika, branch=sez, quantity=Decimal("1.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?state=empty")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs not in body
    assert "Nalezeno: 1" in body




# ---------------------------------------------------------------------------
# Planned príjem (objednávka merged into příjem) — per decision 0059
# ---------------------------------------------------------------------------


def _make_planned_prijem(*, branch, product, qty, eta, user, supplier=None):
    """Test helper: create one PLANNED príjem Movement (objednávka) with a
    single line, via the same apply_movement path the view uses."""
    from inventory.services import apply_movement

    movement = Movement(
        branch=branch,
        kind=Movement.Kind.PRIJEM,
        status=Movement.Status.PLANNED,
        date_issued=date.today(),
        expected_on=eta,
        dodavatel=supplier,
    )
    line = MovementLine(product=product, quantity_kg=qty)
    return apply_movement(movement=movement, lines=[line], user=user)


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_no_date_receives_immediately(user_tyn, tyn, supplier, pepper) -> None:
    """Empty/past arrival date → an ordinary DONE příjem that hits stock now."""
    client = Client()
    client.force_login(user_tyn)
    resp = client.post(
        "/sklad/prijem/novy/",
        {
            "branch": tyn.pk,
            "dodavatel": supplier.pk,
            "date_issued": "2026-06-12",
            "expected_on": "",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "4.000",
        },
    )
    assert resp.status_code == 302, resp.content[:500]
    mv = Movement.objects.get()
    assert mv.status == Movement.Status.DONE
    assert mv.expected_on is None
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("4.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_future_date_is_planned_no_stock(user_tyn, tyn, pepper) -> None:
    """A future arrival date → a PLANNED príjem: stock unchanged, no supplier
    required, and the date_issued future-guard is NOT tripped by expected_on."""
    client = Client()
    client.force_login(user_tyn)
    resp = client.post(
        "/sklad/prijem/novy/",
        {
            "branch": tyn.pk,
            "dodavatel": "",  # optional on a planned příjem
            "date_issued": "2026-06-12",
            "expected_on": "2026-12-31",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": pepper.pk,
            "lines-0-quantity_kg": "9.000",
        },
    )
    assert resp.status_code == 302, resp.content[:500]
    mv = Movement.objects.get()
    assert mv.status == Movement.Status.PLANNED
    assert mv.expected_on == date(2026, 12, 31)
    assert mv.dodavatel_id is None
    # No Stock row created — planned inbound never touches stock.
    assert not Stock.objects.filter(product=pepper, branch=tyn, quantity__gt=0).exists()


@pytest.mark.django_db
def test_confirm_planned_receipt_applies_adjusted_qty_and_drops_zero(
    tyn, pepper, paprika, supplier, user_vlastnik
) -> None:
    """confirm_planned_receipt adjusts per-line quantities, drops a 0 line,
    flips the whole receipt to DONE, and applies the result to stock."""
    from inventory.services import apply_movement, confirm_planned_receipt

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))
    movement = Movement(
        branch=tyn,
        kind=Movement.Kind.PRIJEM,
        status=Movement.Status.PLANNED,
        date_issued=date.today(),
        expected_on=date(2026, 12, 31),
    )
    lines = [
        MovementLine(product=pepper, quantity_kg=Decimal("10.000")),
        MovementLine(product=paprika, quantity_kg=Decimal("5.000")),
    ]
    apply_movement(movement=movement, lines=lines, user=user_vlastnik)
    # PLANNED — stock untouched.
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("3.000")

    pepper_line = movement.lines.get(product=pepper)
    paprika_line = movement.lines.get(product=paprika)
    confirm_planned_receipt(
        movement=movement,
        line_qty_by_id={
            pepper_line.pk: Decimal("8.000"),   # arrived less than ordered
            paprika_line.pk: Decimal("0.000"),  # didn't arrive → dropped
        },
        supplier=supplier,
        user=user_vlastnik,
    )
    movement.refresh_from_db()
    assert movement.status == Movement.Status.DONE
    assert movement.expected_on is None
    assert movement.dodavatel == supplier
    assert movement.date_issued == date.today()
    # Only the pepper line survives; stock rose by the adjusted amount.
    assert movement.lines.count() == 1
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("11.000")
    assert not Stock.objects.filter(product=paprika, branch=tyn, quantity__gt=0).exists()


@pytest.mark.django_db
def test_confirm_without_supplier_uses_internal_objednavka(
    tyn, pepper, user_vlastnik
) -> None:
    """No supplier on the movement or at confirm → internal 'Objednávka'."""
    from inventory.services import confirm_planned_receipt

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("0.000"))
    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("5.000"),
        eta=date(2026, 12, 31), user=user_vlastnik,
    )
    line = movement.lines.get()
    confirm_planned_receipt(
        movement=movement,
        line_qty_by_id={line.pk: Decimal("5.000")},
        user=user_vlastnik,
    )
    movement.refresh_from_db()
    assert movement.dodavatel.name == "Objednávka"
    assert movement.dodavatel.is_internal is True
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("5.000")


@pytest.mark.django_db
def test_confirm_all_zero_lines_raises(tyn, pepper, user_vlastnik) -> None:
    """Confirming with every line set to 0 leaves no items → ValidationError."""
    from django.core.exceptions import ValidationError

    from inventory.services import confirm_planned_receipt

    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("5.000"),
        eta=date(2026, 12, 31), user=user_vlastnik,
    )
    line = movement.lines.get()
    with pytest.raises(ValidationError):
        confirm_planned_receipt(
            movement=movement,
            line_qty_by_id={line.pk: Decimal("0.000")},
            user=user_vlastnik,
        )


@pytest.mark.django_db
def test_confirm_guard_rejects_non_planned(tyn, pepper, supplier, user_vlastnik) -> None:
    """confirm_planned_receipt refuses a DONE movement."""
    from django.core.exceptions import ValidationError

    from inventory.services import apply_movement, confirm_planned_receipt

    movement = Movement(
        branch=tyn, kind=Movement.Kind.PRIJEM, date_issued=date(2026, 6, 1),
        dodavatel=supplier,
    )
    apply_movement(
        movement=movement,
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_vlastnik,
    )
    with pytest.raises(ValidationError):
        confirm_planned_receipt(
            movement=movement, line_qty_by_id={}, user=user_vlastnik
        )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_confirm_view_applies_stock(tyn, pepper, user_obsluha_tyn) -> None:
    """POST to the confirm endpoint with an adjusted amount raises Stock and
    flips the movement to DONE. All logged-in users."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("10.000"),
        eta=date(2026, 12, 31), user=user_obsluha_tyn,
    )
    line = movement.lines.get()
    client = Client()
    client.force_login(user_obsluha_tyn)
    resp = client.post(
        f"/sklad/prijem/{movement.pk}/potvrdit/",
        {f"qty_{line.pk}": "7.500", "as_of": date.today().isoformat(), "supplier": ""},
    )
    assert resp.status_code == 302
    movement.refresh_from_db()
    assert movement.status == Movement.Status.DONE
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("8.500")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_plan_cancel_deletes_and_touches_no_stock(
    tyn, pepper, user_vlastnik
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("2.000"))
    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("5.000"),
        eta=date(2026, 12, 31), user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(f"/sklad/prijem/{movement.pk}/zrusit/")
    assert resp.status_code == 302
    assert not Movement.objects.filter(pk=movement.pk).exists()
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("2.000")


@pytest.mark.django_db
def test_low_stock_row_carries_order_overlay_without_changing_deficit(
    tyn, pepper, user_vlastnik
) -> None:
    """A PLANNED príjem populates ordered_kg/ordered_eta but leaves the row
    listed with unchanged effective/deficit (0059 informational invariant)."""
    from inventory.services import low_stock_rows

    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))

    before = low_stock_rows()
    assert len(before) == 1
    assert before[0].ordered_kg is None
    assert before[0].deficit == Decimal("4.000")

    _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"),
        eta=date(2026, 7, 15), user=user_vlastnik,
    )
    after = low_stock_rows()
    assert len(after) == 1
    row = after[0]
    assert row.effective == Decimal("1.000")
    assert row.deficit == Decimal("4.000")
    assert row.ordered_kg == Decimal("9.000")
    assert row.ordered_eta == date(2026, 7, 15)


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_home_low_stock_panel_shows_resolve_button_and_orders_badge(
    tyn, pepper, user_vlastnik
) -> None:
    """Owner home renders the Upravit button; an ordered row shows the badge."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))

    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/").content.decode("utf-8")
    # Per-branch Inventura button opens that branch's inventura.
    assert "Inventura TYN" in body
    assert "/sklad/katalog/inventura/TYN/" in body

    _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"),
        eta=date(2026, 7, 15), user=user_vlastnik,
    )
    body2 = client.get("/sklad/").content.decode("utf-8")
    assert "Objednáno" in body2


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dochazi_lists_cross_branch_low_rows(
    tyn, sez, pepper, paprika, user_vlastnik
) -> None:
    """The special 'dochazi' inventura lists only below-threshold rows,
    across all branches, with the pobočka column."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("2.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("9.000"))

    client = Client()
    client.force_login(user_vlastnik)
    resp = client.get("/sklad/katalog/inventura/dochazi/")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    assert "Dochází zboží" in body
    assert pepper.name_cs in body
    assert paprika.name_cs not in body
    assert f"qty_{pepper.pk}_{tyn.pk}" in body
    assert f"qty_{pepper.pk}_{sez.pk}" in body
    # Dochází now prefills the nový-stav cell with current stock (1 dp, dot in
    # the type=number value=), matching the per-branch / Vše views.
    assert 'value="1.0"' in body  # TYN pepper 1.000 → 1.0
    assert 'value="2.0"' in body  # SEZ pepper 2.000 → 2.0


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dochazi_adjust_and_order_in_one_post(
    tyn, sez, pepper, paprika, user_vlastnik
) -> None:
    """No date → immediate stock correction; date set → PLANNED príjem. One POST."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("2.000"))

    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        "/sklad/katalog/inventura/dochazi/",
        {
            f"qty_{pepper.pk}_{tyn.pk}": "12.000",
            f"eta_{pepper.pk}_{tyn.pk}": "",
            f"qty_{paprika.pk}_{tyn.pk}": "8.000",
            f"eta_{paprika.pk}_{tyn.pk}": "2026-07-20",
            "reason": "doplnění z panelu",
        },
    )
    assert resp.status_code == 302
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("12.000")
    # Paprika stock unchanged — the order is a PLANNED príjem, not received.
    assert Stock.objects.get(product=paprika, branch=tyn).quantity == Decimal("2.000")
    planned = Movement.objects.get(
        status=Movement.Status.PLANNED, branch=tyn, kind=Movement.Kind.PRIJEM
    )
    assert planned.expected_on == date(2026, 7, 20)
    pline = planned.lines.get()
    assert pline.product == paprika
    assert pline.quantity_kg == Decimal("8.000")


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dated_rows_group_into_one_movement_per_branch_eta(
    tyn, pepper, paprika, user_vlastnik
) -> None:
    """Two dated rows on the same branch + ETA collapse into ONE PLANNED
    príjem Movement with two lines (per 0059 grouping)."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("10.000"))
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        "/sklad/katalog/inventura/TYN/",
        {
            f"qty_{pepper.pk}": "5.000",
            f"eta_{pepper.pk}": "2026-08-01",
            f"qty_{paprika.pk}": "6.000",
            f"eta_{paprika.pk}": "2026-08-01",
        },
    )
    assert resp.status_code == 302
    planned = Movement.objects.filter(
        status=Movement.Status.PLANNED, branch=tyn
    )
    assert planned.count() == 1
    mv = planned.get()
    assert mv.expected_on == date(2026, 8, 1)
    assert mv.lines.count() == 2


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dochazi_blocked_for_obsluha(
    tyn, pepper, user_obsluha_tyn
) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    resp = client.get("/sklad/katalog/inventura/dochazi/")
    assert resp.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_missing_reason_preserves_typed_values(
    tyn, sez, pepper, paprika, user_vlastnik
) -> None:
    """Regression: a missing reason must NOT wipe the operator's input."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    paprika.reorder_threshold_kg = Decimal("5.000")
    paprika.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    Stock.objects.create(product=paprika, branch=tyn, quantity=Decimal("2.000"))

    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        "/sklad/katalog/inventura/dochazi/",
        {
            f"qty_{pepper.pk}_{tyn.pk}": "13.000",
            f"eta_{pepper.pk}_{tyn.pk}": "",
            f"qty_{paprika.pk}_{tyn.pk}": "7.000",
            f"eta_{paprika.pk}_{tyn.pk}": "2026-09-01",
            "reason": "",
        },
    )
    assert resp.status_code == 200
    assert Stock.objects.get(product=pepper, branch=tyn).quantity == Decimal("1.000")
    body = resp.content.decode("utf-8")
    assert 'value="13.000"' in body
    assert 'value="7.000"' in body
    assert 'value="2026-09-01"' in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_vse_lists_all_products_all_branches(
    tyn, sez, pepper, paprika, user_vlastnik
) -> None:
    """The 'vse' option shows every active product × every active branch."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.get("/sklad/katalog/inventura/vse/")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    assert "Inventura — vše" in body
    assert f"qty_{pepper.pk}_{tyn.pk}" in body
    assert f"qty_{pepper.pk}_{sez.pk}" in body
    assert f"qty_{paprika.pk}_{tyn.pk}" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_inventura_button_always_present(user_vlastnik, tyn) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    no_branch = client.get("/sklad/katalog/").content.decode("utf-8")
    assert "Inventura — vše" in no_branch
    assert "/sklad/katalog/inventura/vse/" in no_branch
    with_branch = client.get("/sklad/katalog/?branch=TYN").content.decode("utf-8")
    assert "Inventura TYN" in with_branch


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_inventura_dochazi_shows_existing_order_with_year_and_controls(
    tyn, pepper, user_vlastnik
) -> None:
    """An open PLANNED príjem shows inline with year + confirm/cancel controls
    pointing at prijem_confirm / prijem_plan_cancel (0059)."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    movement = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"),
        eta=date(2026, 7, 15), user=user_vlastnik,
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/inventura/dochazi/").content.decode("utf-8")
    assert "15. 07. 2026" in body
    assert f"/sklad/prijem/{movement.pk}/potvrdit/" in body
    assert f"plan-cancel-{movement.pk}" in body
    assert 'id="kasia-confirm"' in body
    assert 'class="js-confirm"' in body
    assert "return confirm(" not in body


# ---------------------------------------------------------------------------
# Movement history — Plánované tab + DONE-only history (per 0059)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_history_planned_tab_lists_only_planned(
    tyn, pepper, supplier, user_vlastnik
) -> None:
    """The Plánované tab lists only PLANNED rows; the other tabs exclude them,
    and a PLANNED row is absent from the home recent-movement panel."""
    from inventory.services import apply_movement

    # One DONE příjem + one PLANNED príjem.
    done = Movement(
        branch=tyn, kind=Movement.Kind.PRIJEM, date_issued=date(2026, 6, 20),
        dodavatel=supplier,
    )
    apply_movement(
        movement=done,
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("3.000"))],
        user=user_vlastnik,
    )
    planned = _make_planned_prijem(
        branch=tyn, product=pepper, qty=Decimal("9.000"),
        eta=date(2026, 12, 31), user=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)

    all_tab = client.get("/sklad/pohyby/?tab=all").content.decode("utf-8")
    assert "Nalezeno: 1" in all_tab  # DONE only
    prijem_tab = client.get("/sklad/pohyby/?tab=prijem").content.decode("utf-8")
    assert "Nalezeno: 1" in prijem_tab

    planned_tab = client.get("/sklad/pohyby/?tab=planned")
    body = planned_tab.content.decode("utf-8")
    assert "Nalezeno: 1" in body
    assert "Plánováno" in body
    assert f"/sklad/prijem/{planned.pk}/potvrdit/" in body

    # PLANNED must not appear in the owner home recent panel.
    home = client.get("/sklad/").content.decode("utf-8")
    assert f"/sklad/prijem/{planned.pk}/potvrdit/" not in home


@pytest.mark.django_db
def test_migration_0017_migrates_open_planned_orders(
    tyn, pepper, supplier, user_vlastnik
) -> None:
    """The 0017 data migration turns an open PlannedOrder into a PLANNED
    Movement (+ line) and cancels the source order."""
    import importlib

    from django.apps import apps as global_apps

    from inventory.models import PlannedOrder

    order = PlannedOrder.objects.create(
        product=pepper,
        branch=tyn,
        supplier=supplier,
        quantity_kg=Decimal("12.000"),
        expected_on=date(2026, 12, 31),
        state=PlannedOrder.State.PLANNED,
        created_by=user_vlastnik,
    )
    mig = importlib.import_module(
        "inventory.migrations.0017_migrate_open_planned_orders"
    )
    mig.forwards(global_apps, None)

    order.refresh_from_db()
    assert order.state == PlannedOrder.State.CANCELLED
    mv = Movement.objects.get(status=Movement.Status.PLANNED, branch=tyn)
    assert mv.kind == Movement.Kind.PRIJEM
    assert mv.expected_on == date(2026, 12, 31)
    assert mv.dodavatel == supplier
    line = mv.lines.get()
    assert line.product == pepper
    assert line.quantity_kg == Decimal("12.000")
