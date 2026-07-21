"""Forms for Správa uživatelů (screen 13).

Two roles per `context/people-and-roles.md` + the
`is_vlastnik` / `is_obsluha` properties on `accounts.User`:

- `vlastnik` — owner-level (Petr, Karolína). No branch FK.
- `obsluha` — branch staff. Exactly one branch FK (TYN or SEZ).

The role choice maps onto Django's group membership (`obsluha`
group present ↔ obsluha) and `User.branch_id`.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import Group
from django.template import loader
from django.utils.crypto import get_random_string

from inventory.models import Branch

from .models import User


class LoggedPasswordResetForm(PasswordResetForm):
    """Password-reset form that routes the e-mail through the app's
    ``send_and_log`` interception point (per 0075/0083) so the send appears in
    the „E-maily" outbox as a ``PASSWORD_RESET`` row, like every other app
    e-mail. Django's built-in ``PasswordResetForm`` sends via its own mailer and
    never logs. Token/uid/context generation is unchanged — only the delivery is
    overridden.

    Set ``form.sent_by`` to the vlastník triggering the reset before ``save()``.
    """

    sent_by = None

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ) -> None:
        # Lazy import: accounts must not import inventory.services at module load.
        from inventory.models import EmailLog, Settings
        from inventory.services import send_and_log

        subject = "".join(
            loader.render_to_string(subject_template_name, context).splitlines()
        )
        body = loader.render_to_string(email_template_name, context)

        # Prefer the configured Settings sender (same as credentials/Podpora) so
        # delivery doesn't depend on DEFAULT_FROM_EMAIL being a real address.
        s = Settings.load()
        resolved_from = (
            f"{s.email_from_name} <{s.email_from_address}>"
            if s.email_from_name and s.email_from_address
            else (s.email_from_address or from_email or None)
        )
        send_and_log(
            category=EmailLog.Category.PASSWORD_RESET,
            trigger_reason="Reset hesla (Správa uživatelů)",
            subject=subject,
            body=body,
            recipients=[to_email],
            from_email=resolved_from,
            sent_by=self.sent_by,
        )

ROLE_VLASTNIK = "vlastnik"
ROLE_OBSLUHA = "obsluha"

# Unambiguous alphabet — excludes O/0/I/l/1 so a mailed password can be typed
# back reliably. ~12 chars over this set easily passes the default validators.
_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def generate_initial_password(length: int = 12) -> str:
    """Generate a random initial password for a new user (per 0082).

    Django 5.2: ``make_random_password`` was removed in 5.1, so we use
    ``get_random_string`` over an unambiguous alphabet.
    """
    return get_random_string(length, _PASSWORD_ALPHABET)

ROLE_CHOICES = [
    (ROLE_VLASTNIK, "Vlastník / správce"),
    (ROLE_OBSLUHA, "Obsluha pobočky"),
]


class _UserBaseForm(forms.Form):
    first_name = forms.CharField(label="Jméno", max_length=150)
    last_name = forms.CharField(label="Příjmení", max_length=150, required=False)
    email = forms.EmailField(label="E-mail")
    role = forms.ChoiceField(label="Role", choices=ROLE_CHOICES)
    branch = forms.ModelChoiceField(
        label="Pobočka",
        queryset=Branch.objects.filter(is_active=True),
        required=False,
        empty_label="— bez pobočky —",
    )

    def clean(self) -> dict:
        cleaned = super().clean()
        role = cleaned.get("role")
        branch = cleaned.get("branch")
        if role == ROLE_OBSLUHA and branch is None:
            self.add_error(
                "branch",
                "Obsluha pobočky musí mít přiřazenou jednu pobočku.",
            )
        if role == ROLE_VLASTNIK and branch is not None:
            # Owner-level users have no branch — they see both.
            cleaned["branch"] = None
        return cleaned


class UserCreateForm(_UserBaseForm):
    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Uživatel s tímto e-mailem již existuje."
            )
        return email

    def save(self) -> User:
        """Create the user with a system-generated password (per 0082).

        The raw password is stashed on ``user._raw_password`` so the view can
        e-mail it to the new user via ``send_new_user_credentials``.
        """
        cleaned = self.cleaned_data
        raw_password = generate_initial_password()
        user = User.objects.create_user(
            email=cleaned["email"],
            password=raw_password,
            first_name=cleaned["first_name"],
            last_name=cleaned.get("last_name", ""),
            branch=cleaned.get("branch"),
        )
        user._raw_password = raw_password
        _sync_role(user, cleaned["role"])
        return user


class UserEditForm(_UserBaseForm):
    """Edit existing user. E-mail is read-only — changing the login
    identifier would orphan saved sessions and confuse audit; instead,
    deactivate and create a new account.
    """

    def __init__(self, *args, instance: User, editor: User, **kwargs) -> None:
        self.instance = instance
        self.editor = editor
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("first_name", instance.first_name)
        initial.setdefault("last_name", instance.last_name)
        initial.setdefault("email", instance.email)
        initial.setdefault(
            "role", ROLE_OBSLUHA if instance.is_obsluha else ROLE_VLASTNIK
        )
        initial.setdefault("branch", instance.branch_id)
        super().__init__(*args, **kwargs)
        self.fields["email"].disabled = True
        self.fields["email"].help_text = (
            "E-mail nelze měnit. Pro změnu identifikátoru deaktivujte "
            "stávající účet a vytvořte nový."
        )

    def clean(self) -> dict:
        cleaned = super().clean()
        new_role = cleaned.get("role")
        # Last-owner protection: refuse demoting the last active vlastník.
        if (
            new_role == ROLE_OBSLUHA
            and self.instance.is_vlastnik
            and self.instance.is_active
            and _count_other_active_vlastnik(self.instance.pk) == 0
        ):
            raise forms.ValidationError(
                "Nelze degradovat posledního aktivního vlastníka — "
                "alespoň jeden účet s rolí Vlastník musí zůstat aktivní."
            )
        return cleaned

    def save(self) -> User:
        cleaned = self.cleaned_data
        self.instance.first_name = cleaned["first_name"]
        self.instance.last_name = cleaned.get("last_name", "")
        self.instance.branch = cleaned.get("branch")
        self.instance.save(
            update_fields=["first_name", "last_name", "branch"]
        )
        _sync_role(self.instance, cleaned["role"])
        return self.instance


def _sync_role(user: User, role: str) -> None:
    """Translate the chosen role into group membership.

    Per `accounts.User.is_obsluha` / `is_vlastnik`: obsluha = member of
    the `obsluha` group. Owner-level = absence from that group.
    """
    obsluha_group, _ = Group.objects.get_or_create(name="obsluha")
    if role == ROLE_OBSLUHA:
        user.groups.add(obsluha_group)
    else:
        user.groups.remove(obsluha_group)


def _count_other_active_vlastnik(exclude_pk: int) -> int:
    """How many active vlastník users exist *besides* the given pk."""
    return (
        User.objects.filter(is_active=True)
        .exclude(pk=exclude_pk)
        .exclude(groups__name="obsluha")
        .count()
    )
