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
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password

from inventory.models import Branch

from .models import User

ROLE_VLASTNIK = "vlastnik"
ROLE_OBSLUHA = "obsluha"

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
    password1 = forms.CharField(
        label="Heslo",
        widget=forms.PasswordInput,
        min_length=8,
    )
    password2 = forms.CharField(
        label="Heslo (potvrzení)",
        widget=forms.PasswordInput,
    )

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Uživatel s tímto e-mailem již existuje."
            )
        return email

    def clean(self) -> dict:
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Hesla se neshodují.")
        if p1:
            try:
                validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self) -> User:
        cleaned = self.cleaned_data
        user = User.objects.create_user(
            email=cleaned["email"],
            password=cleaned["password1"],
            first_name=cleaned["first_name"],
            last_name=cleaned.get("last_name", ""),
            branch=cleaned.get("branch"),
        )
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
