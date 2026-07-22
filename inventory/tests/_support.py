"""Shared test helpers, fixtures-data, and settings overrides.

Extracted from the former monolithic tests.py (decision 0068) so every
test_*.py module can import them.
"""

from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from inventory.models import (
    DodaciList,
    Movement,
    MovementLine,
    Product,
    RecipeComponent,
    Stock,
)
from inventory.services import (
    apply_movement,
)


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



def _make_vydej(tyn, ricany, pepper, user_tyn, stock_qty="5.000", line_qty="2.000"):
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal(stock_qty))
    return apply_movement(
        movement=_vydej(tyn, ricany, user_tyn),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal(line_qty))],
        user=user_tyn,
    )



_PLAIN_STATIC = {
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
}

_LOCMEM_EMAIL = {"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}

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
        payload[f"recipient-{i}-dodaci_branch"] = str(r.dodaci_branch_id or "")
        if r.is_active:
            payload[f"recipient-{i}-is_active"] = "on"
        if r.is_dodaci_recipient:
            payload[f"recipient-{i}-is_dodaci_recipient"] = "on"
        if r.is_low_stock_recipient:
            payload[f"recipient-{i}-is_low_stock_recipient"] = "on"
        if r.is_feedback_recipient:
            payload[f"recipient-{i}-is_feedback_recipient"] = "on"
    return payload



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



def _mk_mixture_with_recipe(name="Gulášové koření", components=None):
    """Helper: returns the mixture Product.

    ``components`` is a list of ``(component, ratio)`` or
    ``(component, ratio, note)`` — the optional 3rd element sets the
    per-component ``RecipeComponent.note`` (per 0088).
    """

    mixture = Product.objects.create(name_cs=name, kind=Product.Kind.MIXTURE)
    components = components or []
    for spec in components:
        component, ratio = spec[0], spec[1]
        note = spec[2] if len(spec) > 2 else ""
        RecipeComponent.objects.create(
            mixture_product=mixture,
            component_product=component,
            ratio=Decimal(str(ratio)),
            note=note,
        )
    return mixture



_FIXTURE_XLS = "inventory/tests/fixtures/touzimsky.xls"

def _load_fixture_xls() -> bytes:
    with open(_FIXTURE_XLS, "rb") as f:
        return f.read()


def _xls_upload(name: str = "touzimsky.xls"):

    return SimpleUploadedFile(
        name,
        _load_fixture_xls(),
        content_type="application/vnd.ms-excel",
    )



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


