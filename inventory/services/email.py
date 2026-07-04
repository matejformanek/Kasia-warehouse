"""SMTP connection + recipient helpers."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.mail import get_connection

from ..models import (
    Settings,
    SettingsRecipient,
)


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


def _active_dodak_recipients() -> list[str]:
    """All active SettingsRecipient e-mails, ordered for the send-to list.

    Per 0052: replaces the fixed pair from 0031 with an operator-managed
    N-list. Caller iterates them as the dodák `to=` recipients.
    """
    return list(
        SettingsRecipient.objects.filter(is_active=True)
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


def _assert_recipients_set() -> None:
    """Refuse to start a vydej apply / edit if there is no active recipient.

    Per 0052 (supersedes 0031 in part): at least one active
    SettingsRecipient row must exist. The migration seeds the rows from
    the old (Petr, Karolína) pair; if both were blank, the operator must
    add at least one in Nastavení before any výdej.
    """
    if not SettingsRecipient.objects.filter(is_active=True).exists():
        raise ValidationError(
            {
                "recipients": (
                    "V nastavení chybí příjemci dodacího listu. "
                    "Přidejte alespoň jednoho aktivního příjemce "
                    "v Nastavení před výdejem."
                )
            }
        )


