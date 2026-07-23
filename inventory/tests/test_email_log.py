"""E-mail outbox: `send_and_log` seam + the vlastník-only „E-maily" page (0075).

The outbox unifies every app send into one `EmailLog`. `send_and_log` sends +
logs (SENT, or FAILED + error) and never re-raises. The page lists rows, filters
them, and offers a per-row resend (re-render for dodák rows, stored content
otherwise). All three views are vlastník-gated (obsluha → 403).
"""

from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from inventory.models import EmailLog, Movement, MovementLine, SettingsRecipient, Stock
from inventory.services import apply_movement, send_and_log

from ._support import _VIEW_TEST_OVERRIDES, _seed_vydej

# --- send_and_log seam -----------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_send_and_log_success_writes_sent_row():
    log = send_and_log(
        category=EmailLog.Category.SMTP_TEST,
        trigger_reason="test SMTP",
        subject="Předmět",
        body="Tělo",
        recipients=["a@example.cz", "b@example.cz"],
        from_email="no-reply@example.cz",
    )
    assert log.status == EmailLog.Status.SENT
    assert log.error_message == ""
    assert log.recipients == "a@example.cz, b@example.cz"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Předmět"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_send_and_log_failure_writes_failed_row_no_reraise(monkeypatch):
    def _boom(self, *a, **k):
        raise RuntimeError("SMTP down")

    monkeypatch.setattr("django.core.mail.EmailMessage.send", _boom)

    log = send_and_log(  # must NOT raise
        category=EmailLog.Category.SMTP_TEST,
        trigger_reason="test SMTP",
        subject="Předmět",
        body="Tělo",
        recipients=["a@example.cz"],
        from_email=None,
    )
    assert log.status == EmailLog.Status.FAILED
    assert "SMTP down" in log.error_message


# --- low-stock alert now writes a row --------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_low_stock_crossing_writes_alert_row(tyn, ricany, pepper, user_tyn):
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("6.000"))

    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 7, 5),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )

    alerts = EmailLog.objects.filter(category=EmailLog.Category.LOW_STOCK_ALERT)
    assert alerts.count() == 1
    row = alerts.get()
    assert row.status == EmailLog.Status.SENT
    assert row.recipients == "petr@example.cz"
    assert pepper.name_cs in row.body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_low_stock_no_subscriber_writes_no_alert_row(tyn, ricany, pepper, user_tyn):
    SettingsRecipient.objects.update(is_low_stock_recipient=False)
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("6.000"))

    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 7, 5),
            odberatel=ricany,
        ),
        lines=[MovementLine(product=pepper, quantity_kg=Decimal("2.000"))],
        user=user_tyn,
    )

    assert not EmailLog.objects.filter(
        category=EmailLog.Category.LOW_STOCK_ALERT
    ).exists()


# --- SMTP test writes a row ------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_smtp_test_writes_sent_row(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        reverse("inventory:settings_test_smtp"), {"to_email": "x@example.cz"}
    )
    assert resp.status_code == 302
    row = EmailLog.objects.get(category=EmailLog.Category.SMTP_TEST)
    assert row.status == EmailLog.Status.SENT
    assert row.recipients == "x@example.cz"
    assert row.sent_by_id == user_vlastnik.pk


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_smtp_test_failure_writes_failed_row(user_vlastnik, monkeypatch):
    def _boom(self, *a, **k):
        raise RuntimeError("SMTP down")

    monkeypatch.setattr("django.core.mail.EmailMessage.send", _boom)
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        reverse("inventory:settings_test_smtp"), {"to_email": "x@example.cz"}
    )
    assert resp.status_code == 302
    row = EmailLog.objects.get(category=EmailLog.Category.SMTP_TEST)
    assert row.status == EmailLog.Status.FAILED
    assert "SMTP down" in row.error_message


# --- outbox index / detail access + rendering ------------------------------


def _mk_row(**kw):
    defaults = dict(
        category=EmailLog.Category.SMTP_TEST,
        trigger_reason="test SMTP",
        recipients="a@example.cz",
        from_email="no-reply@example.cz",
        subject="Předmět",
        body="Tělo",
        status=EmailLog.Status.SENT,
    )
    defaults.update(kw)
    return EmailLog.objects.create(**defaults)


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_index_vlastnik_ok_with_rows_and_filter_hooks(user_vlastnik):
    _mk_row()
    _mk_row(status=EmailLog.Status.FAILED, error_message="boom")
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.get(reverse("inventory:email_log_index"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="email-log-table"' in body
    assert 'data-filter-rows="#email-log-table tbody"' in body
    assert "data-filter-empty" in body
    assert "data-filter-count" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_index_status_filter(user_vlastnik):
    _mk_row()
    _mk_row(status=EmailLog.Status.FAILED)
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.get(
        reverse("inventory:email_log_index"), {"status": EmailLog.Status.FAILED}
    )
    assert resp.status_code == 200
    # Only the failed row is in the page's object list.
    assert list(resp.context["logs"]) == list(
        EmailLog.objects.filter(status=EmailLog.Status.FAILED)
    )


@pytest.mark.django_db
def test_index_obsluha_403(user_obsluha_tyn):
    client = Client()
    client.force_login(user_obsluha_tyn)
    resp = client.get(reverse("inventory:email_log_index"))
    assert resp.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_detail_vlastnik_ok_obsluha_403(user_vlastnik, user_obsluha_tyn):
    row = _mk_row()
    vlast = Client()
    vlast.force_login(user_vlastnik)
    assert (
        vlast.get(
            reverse("inventory:email_log_detail", args=[row.pk])
        ).status_code
        == 200
    )
    obs = Client()
    obs.force_login(user_obsluha_tyn)
    assert (
        obs.get(reverse("inventory:email_log_detail", args=[row.pk])).status_code
        == 403
    )


# --- resend ----------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_resend_non_dodaci_resends_stored_content(user_vlastnik):
    row = _mk_row(subject="Uložený předmět", body="Uložené tělo", recipients="a@example.cz")
    before = EmailLog.objects.count()
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(reverse("inventory:email_log_resend", args=[row.pk]))
    assert resp.status_code == 302
    assert EmailLog.objects.count() == before + 1
    new = EmailLog.objects.exclude(pk=row.pk).latest("id")
    assert new.trigger_reason == "ruční opětovné odeslání"
    assert new.subject == "Uložený předmět"
    assert new.sent_by_id == user_vlastnik.pk
    assert mail.outbox[-1].subject == "Uložený předmět"
    assert mail.outbox[-1].body == "Uložené tělo"
    assert mail.outbox[-1].to == ["a@example.cz"]


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_resend_dodaci_rerenders_pdf(user_tyn, tyn, ricany, pepper):
    from inventory.services import send_first_dodaci

    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    # Per 0096: the first send is manual — trigger it so there's a log to resend.
    send_first_dodaci(dl, sent_by=user_tyn)
    row = EmailLog.objects.filter(dodaci_list=dl).latest("id")
    mail.outbox.clear()
    before = EmailLog.objects.count()

    client = Client()
    client.force_login(user_tyn)
    resp = client.post(reverse("inventory:email_log_resend", args=[row.pk]))
    assert resp.status_code == 302
    assert EmailLog.objects.count() == before + 1
    new = EmailLog.objects.filter(dodaci_list=dl).latest("id")
    assert new.trigger_reason == "ruční opětovné odeslání"
    assert new.category == EmailLog.Category.DODACI_RESEND
    assert new.sent_by_id == user_tyn.pk  # manual resend records the operator
    # A fresh PDF was attached.
    assert mail.outbox
    assert any(att[0] == f"{dl.cislo}.pdf" for att in mail.outbox[-1].attachments)


@pytest.mark.django_db
def test_resend_obsluha_403(user_obsluha_tyn):
    row = _mk_row()
    client = Client()
    client.force_login(user_obsluha_tyn)
    resp = client.post(reverse("inventory:email_log_resend", args=[row.pk]))
    assert resp.status_code == 403


# --- feedback notification (per 0079) --------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_send_feedback_notification_sends_and_logs(user_vlastnik):
    from django.conf import settings as dj_settings

    from inventory.models import Feedback
    from inventory.services import send_feedback_notification

    f = Feedback.objects.create(
        created_by=user_vlastnik, page_url="Katalog", description="Chybí sloupec."
    )
    log = send_feedback_notification(f)

    assert log.status == EmailLog.Status.SENT
    assert log.category == EmailLog.Category.FEEDBACK
    assert dj_settings.FEEDBACK_NOTIFY_EMAIL in log.recipients
    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert "Katalog" in body
    assert user_vlastnik.email in body
    assert mail.outbox[0].subject == "Nové hlášení z Podpory"


# --- Oznámení broadcast (per 0097) -----------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_send_announcement_uses_bcc_and_logs_audience():
    from inventory.services import send_announcement

    audience = [f"user{i}@example.cz" for i in range(30)]
    log = send_announcement(
        subject="Novinka",
        body="Nasadili jsme to, co jste chtěli.",
        recipients=audience,
    )
    assert log.status == EmailLog.Status.SENT
    assert log.category == EmailLog.Category.ANNOUNCEMENT
    # Audience is BCC; `to` is the app from-address, never the audience.
    msg = mail.outbox[-1]
    assert msg.bcc == audience
    assert msg.to == ["no-reply@example.cz"]
    # The log stores the BCC audience (the real recipients), not the `to`.
    for addr in audience:
        assert addr in log.recipients
    assert "no-reply@example.cz" not in log.recipients  # the `to` addr is not logged
    assert len(log.recipients) > 512  # TextField widening exercised


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_announcement_send_all_active_users(user_vlastnik, user_obsluha_tyn):
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        reverse("inventory:announcement_send"),
        {"subject": "Ahoj", "body": "Text", "audience": "all"},
    )
    assert resp.status_code == 302
    log = EmailLog.objects.get(category=EmailLog.Category.ANNOUNCEMENT)
    assert log.status == EmailLog.Status.SENT
    assert log.sent_by_id == user_vlastnik.pk
    assert set(mail.outbox[-1].bcc) == {user_vlastnik.email, user_obsluha_tyn.email}


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_announcement_send_branch_mode(user_vlastnik, user_obsluha_tyn, user_obsluha_sez):
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        reverse("inventory:announcement_send"),
        {
            "subject": "Pobočka",
            "body": "Jen Týniště",
            "audience": "branch",
            "branch": str(user_obsluha_tyn.branch_id),
        },
    )
    assert resp.status_code == 302
    assert mail.outbox[-1].bcc == [user_obsluha_tyn.email]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_announcement_send_selected_mode(user_vlastnik, user_obsluha_tyn, user_obsluha_sez):
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        reverse("inventory:announcement_send"),
        {
            "subject": "Vybraní",
            "body": "Text",
            "audience": "selected",
            "users": [str(user_obsluha_sez.pk)],
        },
    )
    assert resp.status_code == 302
    assert mail.outbox[-1].bcc == [user_obsluha_sez.email]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_announcement_send_invalid_rerenders_with_errors(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        reverse("inventory:announcement_send"),
        {"subject": "", "body": "", "audience": "branch"},  # missing subject/body/branch
    )
    assert resp.status_code == 200
    assert resp.context["announcement_form"].errors
    assert not EmailLog.objects.filter(category=EmailLog.Category.ANNOUNCEMENT).exists()
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_announcement_send_failed_status_flashes_error(user_vlastnik, monkeypatch):
    def _boom(self, *a, **k):
        raise RuntimeError("SMTP down")

    monkeypatch.setattr("django.core.mail.EmailMessage.send", _boom)
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(
        reverse("inventory:announcement_send"),
        {"subject": "X", "body": "Y", "audience": "all"},
    )
    assert resp.status_code == 302
    log = EmailLog.objects.get(category=EmailLog.Category.ANNOUNCEMENT)
    assert log.status == EmailLog.Status.FAILED


@pytest.mark.django_db
def test_announcement_send_obsluha_403(user_obsluha_tyn):
    client = Client()
    client.force_login(user_obsluha_tyn)
    resp = client.post(
        reverse("inventory:announcement_send"),
        {"subject": "X", "body": "Y", "audience": "all"},
    )
    assert resp.status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_resend_announcement_uses_bcc_not_to(user_vlastnik):
    """Regression: an ANNOUNCEMENT resend must go via BCC, never leak into `to`."""
    audience = "a@example.cz, b@example.cz, c@example.cz"
    row = _mk_row(
        category=EmailLog.Category.ANNOUNCEMENT,
        subject="Novinka",
        body="Text",
        recipients=audience,
    )
    mail.outbox.clear()
    client = Client()
    client.force_login(user_vlastnik)
    resp = client.post(reverse("inventory:email_log_resend", args=[row.pk]))
    assert resp.status_code == 302
    msg = mail.outbox[-1]
    assert msg.bcc == ["a@example.cz", "b@example.cz", "c@example.cz"]
    assert msg.to == ["no-reply@example.cz"]
    new = EmailLog.objects.exclude(pk=row.pk).latest("id")
    assert new.category == EmailLog.Category.ANNOUNCEMENT
    assert new.recipients == audience


# --- AnnouncementForm unit tests (per 0097) --------------------------------


@pytest.mark.django_db
def test_announcement_form_branch_required_iff_branch_mode(tyn):
    from inventory.forms import AnnouncementForm

    f = AnnouncementForm({"subject": "s", "body": "b", "audience": "branch"})
    assert not f.is_valid()
    assert "branch" in f.errors

    f = AnnouncementForm(
        {"subject": "s", "body": "b", "audience": "branch", "branch": str(tyn.pk)}
    )
    assert f.is_valid(), f.errors


@pytest.mark.django_db
def test_announcement_form_users_required_iff_selected_mode(user_vlastnik):
    from inventory.forms import AnnouncementForm

    f = AnnouncementForm({"subject": "s", "body": "b", "audience": "selected"})
    assert not f.is_valid()
    assert "users" in f.errors

    f = AnnouncementForm(
        {
            "subject": "s",
            "body": "b",
            "audience": "selected",
            "users": [str(user_vlastnik.pk)],
        }
    )
    assert f.is_valid(), f.errors
    assert f.recipient_emails() == [user_vlastnik.email]


@pytest.mark.django_db
def test_announcement_form_all_mode_dedups_and_orders(user_vlastnik, user_obsluha_tyn):
    from inventory.forms import AnnouncementForm

    f = AnnouncementForm({"subject": "s", "body": "b", "audience": "all"})
    assert f.is_valid(), f.errors
    emails = f.recipient_emails()
    # Deterministic id-order, deduped, no blanks.
    assert emails == list(dict.fromkeys(emails))
    assert set(emails) == {user_vlastnik.email, user_obsluha_tyn.email}


@pytest.mark.django_db
def test_announcement_form_all_mode_excludes_inactive(user_vlastnik, user_obsluha_tyn):
    from inventory.forms import AnnouncementForm

    user_obsluha_tyn.is_active = False
    user_obsluha_tyn.save(update_fields=["is_active"])
    f = AnnouncementForm({"subject": "s", "body": "b", "audience": "all"})
    assert f.is_valid(), f.errors
    assert user_obsluha_tyn.email not in f.recipient_emails()
