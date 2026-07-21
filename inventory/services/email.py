"""SMTP connection + recipient helpers."""

from __future__ import annotations

from django.conf import settings as django_settings
from django.core.mail import EmailMessage, get_connection
from django.db.models import Q
from django.urls import reverse

from ..models import (
    EmailLog,
    Settings,
    SettingsRecipient,
)


def _absolute_url(url_name: str, *args, **kwargs) -> str:
    """Full clickable URL (scheme + host + path) for an e-mail link.

    E-mails send off-request, so there is no request to build an absolute URI
    from; we prepend ``settings.SITE_BASE_URL`` to ``reverse()`` instead. A bare
    path (``/sklad/prihlaseni/``) isn't clickable in a mail client.
    """
    return f"{django_settings.SITE_BASE_URL}{reverse(url_name, args=args, kwargs=kwargs or None)}"


def _smtp_connection_from_settings(s: Settings):
    """Build an SMTP connection from `Settings` DB, with env as fallback.

    Per decision 0049:
      - host / username / password: ``None`` when the DB field is
        blank → Django's default backend reads `EMAIL_HOST*` from env.
      - port: `Settings.smtp_port` is non-nullable with default 587, so
        the DB value effectively always wins. Env `EMAIL_PORT` is not
        consulted by this helper. To change ports, operators flip the
        DB field; no migration needed for the dominant prod case.
      - use_tls: same shape as port — `Settings.smtp_use_tls` is
        non-nullable with default True; DB always wins, env
        `EMAIL_USE_TLS` is not consulted.
      - Call at execution time (not registration time) so a live
        `Settings.load()` is read — not a snapshot from when the
        výdej started.
    """
    return get_connection(
        host=s.smtp_host or None,
        port=s.smtp_port or None,
        username=s.smtp_user or None,
        password=s.smtp_password or None,
        use_tls=s.smtp_use_tls,
        timeout=10,
    )


def _active_dodak_recipients(branch) -> list[str]:
    """Active dodák recipients for a given branch, ordered for the send-to list.

    Per 0081 (amends 0052): a row receives dodáky only when it is active AND
    opted into dodáky AND either unscoped (`dodaci_branch` NULL = all branches)
    or scoped to this dodák's branch. Caller iterates them as the dodák `to=`
    recipients (unioned with the issuer in `send_dodaci_list_email`).
    """
    return list(
        SettingsRecipient.objects.filter(
            is_active=True, is_dodaci_recipient=True
        )
        .filter(Q(dodaci_branch__isnull=True) | Q(dodaci_branch=branch))
        .order_by("sort_order", "id")
        .values_list("email", flat=True)
    )


def _active_low_stock_recipients() -> list[str]:
    """All active SettingsRecipient e-mails subscribed to the daily summary."""
    return list(
        SettingsRecipient.objects.filter(
            is_active=True, is_low_stock_recipient=True
        )
        .order_by("sort_order", "id")
        .values_list("email", flat=True)
    )


def _active_feedback_recipients() -> list[str]:
    """All active SettingsRecipient e-mails opted into Podpora reports (0081)."""
    return list(
        SettingsRecipient.objects.filter(
            is_active=True, is_feedback_recipient=True
        )
        .order_by("sort_order", "id")
        .values_list("email", flat=True)
    )


def send_and_log(
    *,
    category: str,
    trigger_reason: str,
    subject: str,
    body: str,
    recipients: list[str],
    from_email: str | None,
    connection=None,
    attachments: list[tuple[str, bytes, str]] | None = None,
    dodaci_list=None,
    dodaci_version: int | None = None,
    sent_by=None,
) -> EmailLog:
    """Single interception point for every app e-mail (per 0075): send, then
    write one ``EmailLog`` row (SENT, or FAILED + error) and return it.

    Wrapped in try/except that never re-raises — the same swallow-and-log
    posture ``send_dodaci_list_email`` already had (0019), so a send failure
    inside an ``on_commit`` callback or a request never propagates. Builds the
    SMTP connection from live ``Settings`` (per 0049) when one isn't passed.
    ``recipients`` is stored comma-joined; ``attachments`` is a list of
    ``(filename, content, mimetype)`` tuples.
    """
    recipients_joined = ", ".join(recipients)
    if connection is None:
        connection = _smtp_connection_from_settings(Settings.load())

    status = EmailLog.Status.SENT
    error_message = ""
    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email or None,
            to=recipients,
            connection=connection,
        )
        for filename, content, mimetype in attachments or []:
            msg.attach(filename, content, mimetype)
        msg.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — logged on the row, never re-raised
        status = EmailLog.Status.FAILED
        error_message = str(exc)

    return EmailLog.objects.create(
        category=category,
        trigger_reason=trigger_reason,
        recipients=recipients_joined,
        from_email=from_email or "",
        subject=subject,
        body=body,
        status=status,
        error_message=error_message,
        dodaci_list=dodaci_list,
        dodaci_version=dodaci_version,
        sent_by=sent_by,
    )


def send_feedback_notification(feedback) -> EmailLog:
    """Notify the fixed admin address of one new Podpora report (per 0079).

    Routes through the single ``send_and_log`` interception point (0075), so the
    send is logged (SENT / FAILED) and never re-raises — a mail outage can't
    block the operator's save. Called from ``support_view`` inside an
    ``on_commit`` callback. Recipient is ``settings.FEEDBACK_NOTIFY_EMAIL`` (a
    fixed admin address, not a ``SettingsRecipient``).
    """
    s = Settings.load()
    who = getattr(feedback.created_by, "email", "") or "neznámý uživatel"
    page = feedback.page_url or "—"
    support_url = _absolute_url("inventory:support")
    subject = "Nové hlášení z Podpory"
    body = (
        f"Nové hlášení z Podpory od: {who}\n"
        f"Stránka: {page}\n\n"
        f"Popis:\n{feedback.description}\n\n"
        f"Otevřít Podporu: {support_url}"
    )
    # Mirror the from_email snippet used by the dodák / low-stock paths: pass
    # None when unset so Django applies DEFAULT_FROM_EMAIL implicitly.
    from_email = (
        f"{s.email_from_name} <{s.email_from_address}>"
        if s.email_from_name and s.email_from_address
        else (s.email_from_address or None)
    )
    # Per 0081: route to the configured Podpora recipients; fall back to the
    # fixed admin address only when none is opted in, so reports never vanish.
    recipients = _active_feedback_recipients() or [
        django_settings.FEEDBACK_NOTIFY_EMAIL
    ]
    return send_and_log(
        category=EmailLog.Category.FEEDBACK,
        trigger_reason="Nové hlášení z Podpory",
        subject=subject,
        body=body,
        recipients=recipients,
        from_email=from_email,
    )


def send_new_user_credentials(user, raw_password: str, sent_by=None) -> EmailLog:
    """E-mail a newly-created user their login (their e-mail) + password (0082).

    Routes through the single ``send_and_log`` interception point (0075), so the
    send is logged (SENT / FAILED) and never re-raises — a mail outage can't
    block user creation. Called from ``accounts.views.user_create`` after the
    user is saved. ``sent_by`` is the vlastník who created the account.
    """
    s = Settings.load()
    login_url = _absolute_url("login")
    change_url = _absolute_url("password_change")
    subject = "Přístup do skladového systému Kasia vera"
    body = (
        f"Dobrý den,\n\n"
        f"byl vám vytvořen účet do skladového systému Kasia vera.\n\n"
        f"Přihlašovací e-mail: {user.email}\n"
        f"Heslo: {raw_password}\n\n"
        f"Přihlásit se můžete zde: {login_url}\n\n"
        f"Z bezpečnostních důvodů si prosím po prvním přihlášení heslo "
        f"změňte na adrese: {change_url}\n\n"
        f"S pozdravem, Kasia vera s.r.o."
    )
    from_email = (
        f"{s.email_from_name} <{s.email_from_address}>"
        if s.email_from_name and s.email_from_address
        else (s.email_from_address or None)
    )
    return send_and_log(
        category=EmailLog.Category.NEW_USER_CREDENTIALS,
        trigger_reason="Vytvoření uživatele",
        subject=subject,
        body=body,
        recipients=[user.email],
        from_email=from_email,
        sent_by=sent_by,
    )


