import re
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.test import Client, override_settings

from inventory.models import (
    Branch,
    DodaciList,
    EmailLog,
    Movement,
    MovementLine,
    Settings,
    Stock,
)
from inventory.services import (
    apply_movement,
    send_first_dodaci,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
    _recipient_formset_keepall,
    _seed_vydej,
)

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
    from inventory.models import SettingsRecipient

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
    # Per 0096: apply no longer sends — trigger the first send to exercise the
    # (unchanged) recipient resolution and produce the EmailLog.
    send_first_dodaci(DodaciList.objects.get(movement=mv), sent_by=user_tyn)
    log = EmailLog.objects.get(dodaci_list__movement=mv)
    assert log.status == EmailLog.Status.SENT
    # 2 seeded active rows + new one, plus the issuer (0081) always copied.
    recips = [r.strip() for r in log.recipients.split(",")]
    assert set(recips) == {
        "petr@example.cz",
        "karolina@example.cz",
        "uctarna@kasia.cz",
        "user-tyn@example.cz",
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
    # Per 0096: apply no longer sends — trigger the first send to exercise the
    # (unchanged) recipient resolution and produce the EmailLog.
    send_first_dodaci(DodaciList.objects.get(movement=mv), sent_by=user_tyn)
    log = EmailLog.objects.get(dodaci_list__movement=mv)
    recips = [r.strip() for r in log.recipients.split(",")]
    # Karolína inactive → Petr + the issuer (0081) always copied.
    assert set(recips) == {"petr@example.cz", "user-tyn@example.cz"}


@pytest.mark.django_db(transaction=True)
def test_send_dodaci_list_branch_scoped_recipient_skipped(
    tyn, sez, ricany, pepper, user_tyn
) -> None:
    """Per 0081: a SEZ-scoped recipient does not receive a TYN dodák; the
    Všechny recipients + the issuer do."""
    from inventory.models import SettingsRecipient

    SettingsRecipient.objects.create(
        email="sez-only@kasia.cz",
        label="SEZ only",
        is_active=True,
        is_dodaci_recipient=True,
        dodaci_branch=sez,
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
    # Per 0096: apply no longer sends — trigger the first send to exercise the
    # (unchanged) recipient resolution and produce the EmailLog.
    send_first_dodaci(DodaciList.objects.get(movement=mv), sent_by=user_tyn)
    log = EmailLog.objects.get(dodaci_list__movement=mv)
    recips = {r.strip() for r in log.recipients.split(",")}
    # Both seeded rows are unscoped (all branches) → they get it; the issuer
    # too. The SEZ-scoped row is excluded from this TYN dodák.
    assert recips == {
        "petr@example.cz",
        "karolina@example.cz",
        "user-tyn@example.cz",
    }
    assert "sez-only@kasia.cz" not in recips


@pytest.mark.django_db(transaction=True)
def test_send_dodaci_list_excludes_non_dodaci_recipient(
    tyn, ricany, pepper, user_tyn
) -> None:
    """Per 0081: a row opted out of dodáky (is_dodaci_recipient=False) is
    skipped even while active."""
    from inventory.models import SettingsRecipient

    SettingsRecipient.objects.filter(label="Karolína").update(
        is_dodaci_recipient=False
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
    # Per 0096: apply no longer sends — trigger the first send to exercise the
    # (unchanged) recipient resolution and produce the EmailLog.
    send_first_dodaci(DodaciList.objects.get(movement=mv), sent_by=user_tyn)
    log = EmailLog.objects.get(dodaci_list__movement=mv)
    recips = {r.strip() for r in log.recipients.split(",")}
    assert recips == {"petr@example.cz", "user-tyn@example.cz"}


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
    # Per 0081: the per-flag columns + branch dropdown render, and the hidden
    # empty-row template offers „Všechny" as the first (null) branch option.
    assert "is_dodaci_recipient" in body
    assert "is_feedback_recipient" in body
    assert "dodaci_branch" in body
    assert ">Všechny<" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipient_creation_via_settings_form(user_vlastnik) -> None:
    """POSTing /nastaveni/ with a new (extra) recipient row creates it."""
    from inventory.forms import SettingsForm
    from inventory.models import SettingsRecipient

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
    EmailLog.objects.filter(
        dodaci_list=dl, dodaci_version=dl.current_version
    ).delete()
    EmailLog.objects.create(
        dodaci_list=dl,
        dodaci_version=dl.current_version,
        recipients="petr@kasia.cz",
        trigger_reason="initial send",
        status=EmailLog.Status.FAILED,
        error_message="SMTP timeout",
    )
    EmailLog.objects.create(
        dodaci_list=dl,
        dodaci_version=dl.current_version,
        recipients="petr@kasia.cz",
        trigger_reason="ruční opětovné odeslání",
        status=EmailLog.Status.SENT,
    )
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/{dl.cislo}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Poslední odeslání selhalo." not in body


# ---------------------------------------------------------------------------
