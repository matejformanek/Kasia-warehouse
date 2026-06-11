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
    Movement,
    MovementAudit,
    MovementLine,
    Product,
    RecipeComponent,
    Settings,
    Stock,
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
    s = Settings.load()
    s.recipient_petr = ""
    s.save()
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
