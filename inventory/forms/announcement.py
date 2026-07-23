"""Oznámení (broadcast e-mail) composer form (per 0097)."""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from ..models import Branch

User = get_user_model()


class AnnouncementForm(forms.Form):
    """Vlastník-composed broadcast e-mail to app users (per 0097).

    Three audience modes: ``all`` (every active user), ``branch`` (active users
    of one branch), ``selected`` (a manually-checked subset). The resolved,
    deduped recipient list — from ``recipient_emails()`` — becomes the BCC
    audience of a single ``send_announcement`` send.
    """

    AUDIENCE_ALL = "all"
    AUDIENCE_BRANCH = "branch"
    AUDIENCE_SELECTED = "selected"
    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL, "Všem aktivním uživatelům"),
        (AUDIENCE_BRANCH, "Jedné pobočce"),
        (AUDIENCE_SELECTED, "Vybraným uživatelům"),
    ]

    # subject must fit EmailLog.subject (CharField(255)) — an over-long subject
    # would 500 on the log write after the mail already went out.
    subject = forms.CharField(label="Předmět", max_length=255)
    body = forms.CharField(label="Text", widget=forms.Textarea(attrs={"rows": 5}))
    audience = forms.ChoiceField(
        label="Komu",
        choices=AUDIENCE_CHOICES,
        initial=AUDIENCE_ALL,
    )
    branch = forms.ModelChoiceField(
        label="Pobočka",
        queryset=Branch.objects.filter(is_active=True),
        required=False,
        empty_label="— vyberte pobočku —",
    )
    users = forms.ModelMultipleChoiceField(
        label="Uživatelé",
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["users"].label_from_instance = self._user_label

    @staticmethod
    def _user_label(u) -> str:
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def clean(self) -> dict:
        cleaned = super().clean()
        audience = cleaned.get("audience")
        if audience == self.AUDIENCE_BRANCH and not cleaned.get("branch"):
            self.add_error("branch", "Vyberte pobočku.")
        if audience == self.AUDIENCE_SELECTED and not cleaned.get("users"):
            self.add_error("users", "Vyberte alespoň jednoho uživatele.")
        return cleaned

    def recipient_emails(self) -> list[str]:
        """Resolved, deduped, blank-dropped recipient e-mails for the send.

        Deterministic order (``dict.fromkeys`` preserves first-seen) for test
        stability. Call only on a valid form.
        """
        audience = self.cleaned_data["audience"]
        if audience == self.AUDIENCE_SELECTED:
            qs = self.cleaned_data["users"].order_by("id")
        elif audience == self.AUDIENCE_BRANCH:
            qs = User.objects.filter(
                is_active=True, branch=self.cleaned_data["branch"]
            ).order_by("id")
        else:
            qs = User.objects.filter(is_active=True).order_by("id")
        emails = [(u.email or "").strip() for u in qs]
        return list(dict.fromkeys(e for e in emails if e))
