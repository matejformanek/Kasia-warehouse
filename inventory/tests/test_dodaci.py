from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse

from inventory.models import (
    DodaciList,
    DodaciListEmailLog,
    DodaciListNumberSequence,
    Movement,
    MovementLine,
    Settings,
    Stock,
)
from inventory.services import (
    _reserve_dodak_number,
    apply_movement,
    edit_movement,
)
from inventory.tests._support import (
    _LOCMEM_EMAIL,
    _PLAIN_STATIC,
    _prijem,
    _vydej,
)

# Pass 2 — DodaciList + Settings + WeasyPrint + e-mail
# ---------------------------------------------------------------------------




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

    monkeypatch.setattr(services.dodaci_list.EmailMessage, "send", _raise)

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

    monkeypatch.setattr(services.email, "get_connection", _fake_get_connection)
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

    monkeypatch.setattr(services.email, "get_connection", _fake_get_connection)
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

    monkeypatch.setattr(services.dodaci_list, "_smtp_connection_from_settings", _spy)

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

    monkeypatch.setattr(services.dodaci_list.EmailMessage, "send", _raise)

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


# Obsluha branch-scoping (decision 0040 + screen 08) -----------------------


def _make_vydej_dodak(branch, ricany, user, product, qty="1.000"):
    """Post a výdej at `branch` and return the auto-issued DodaciList."""
    Stock.objects.create(product=product, branch=branch, quantity=Decimal("9.000"))
    mv = apply_movement(
        movement=Movement(
            branch=branch,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 6, 12),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=product, quantity_kg=Decimal(qty))],
        user=user,
    )
    return DodaciList.objects.get(movement=mv)


@pytest.mark.django_db(transaction=True)
@override_settings(**_PLAIN_STATIC, **_LOCMEM_EMAIL)
def test_dodaci_index_obsluha_scoped_to_own_branch(
    user_obsluha_sez, user_tyn, tyn, sez, ricany, pepper, paprika
) -> None:
    dl_tyn = _make_vydej_dodak(tyn, ricany, user_tyn, pepper)
    dl_sez = _make_vydej_dodak(sez, ricany, user_tyn, paprika)

    client = Client()
    client.force_login(user_obsluha_sez)
    response = client.get(reverse("inventory:dodaci_list_index"))
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "Nalezeno: 1" in body
    assert dl_sez.cislo in body
    assert dl_tyn.cislo not in body
    # No branch dropdown for obsluha.
    assert 'name="branch"' not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_PLAIN_STATIC, **_LOCMEM_EMAIL)
def test_dodaci_vlastnik_sees_all_branches(
    user_vlastnik, user_tyn, tyn, sez, ricany, pepper, paprika
) -> None:
    dl_tyn = _make_vydej_dodak(tyn, ricany, user_tyn, pepper)
    dl_sez = _make_vydej_dodak(sez, ricany, user_tyn, paprika)

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(reverse("inventory:dodaci_list_index"))
    body = response.content.decode("utf-8")
    assert "Nalezeno: 2" in body
    assert dl_tyn.cislo in body
    assert dl_sez.cislo in body
    # Vlastník keeps the branch dropdown.
    assert 'name="branch"' in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_PLAIN_STATIC, **_LOCMEM_EMAIL)
def test_dodaci_detail_obsluha_forbidden_other_branch(
    user_obsluha_sez, user_tyn, tyn, ricany, pepper
) -> None:
    dl_tyn = _make_vydej_dodak(tyn, ricany, user_tyn, pepper)

    client = Client()
    client.force_login(user_obsluha_sez)
    response = client.get(
        reverse("inventory:dodaci_list_detail", kwargs={"cislo": dl_tyn.cislo})
    )
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_PLAIN_STATIC, **_LOCMEM_EMAIL)
def test_dodaci_pdf_obsluha_forbidden_other_branch(
    user_obsluha_sez, user_tyn, tyn, ricany, pepper
) -> None:
    dl_tyn = _make_vydej_dodak(tyn, ricany, user_tyn, pepper)

    client = Client()
    client.force_login(user_obsluha_sez)
    response = client.get(
        reverse("inventory:dodaci_list_pdf", kwargs={"cislo": dl_tyn.cislo})
    )
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_PLAIN_STATIC, **_LOCMEM_EMAIL)
def test_dodaci_resend_obsluha_forbidden_other_branch(
    user_obsluha_sez, user_tyn, tyn, ricany, pepper
) -> None:
    dl_tyn = _make_vydej_dodak(tyn, ricany, user_tyn, pepper)

    client = Client()
    client.force_login(user_obsluha_sez)
    response = client.post(
        reverse("inventory:dodaci_list_resend", kwargs={"cislo": dl_tyn.cislo})
    )
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_PLAIN_STATIC, **_LOCMEM_EMAIL)
def test_dodaci_detail_obsluha_own_branch_ok(
    user_obsluha_sez, user_tyn, sez, ricany, paprika
) -> None:
    dl_sez = _make_vydej_dodak(sez, ricany, user_tyn, paprika)

    client = Client()
    client.force_login(user_obsluha_sez)
    response = client.get(
        reverse("inventory:dodaci_list_detail", kwargs={"cislo": dl_sez.cislo})
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
