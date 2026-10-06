"""Custom user model per context/decisions/0020-auth-django-builtin.md.

E-mail is the login identifier. ``branch`` is nullable so vlastník
(Petr / Karolína) — who is not branch-scoped per
``context/people-and-roles.md`` — can exist without a Branch FK.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("e-mail", unique=True)
    branch = models.ForeignKey(
        "inventory.Branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
        verbose_name="pobočka",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "uživatel"
        verbose_name_plural = "uživatelé"

    def __str__(self) -> str:
        return self.email

    @property
    def is_obsluha(self) -> bool:
        """True iff this user is branch staff (in the seeded `obsluha`
        group). Superusers are not obsluha even if they happen to be
        in the group."""
        if self.is_superuser:
            return False
        return self.groups.filter(name="obsluha").exists()

    @property
    def is_vlastnik(self) -> bool:
        """True iff this user is owner-level — superuser, or in the
        `vlastnik` group (and not also in `obsluha`).

        Per 0104 roles **fail closed**: a user in neither group has no role
        (neither vlastník nor obsluha) and is refused at login. This reverses
        the old "unassigned → vlastník" shadow-run default (0034/0099); the
        0003 data migration gave every then-groupless user the group."""
        if self.is_superuser:
            return True
        if self.is_obsluha:
            return False
        return self.groups.filter(name="vlastnik").exists()

    @property
    def has_valid_role(self) -> bool:
        """Login gate (0104): superuser, vlastník, or obsluha WITH a branch.
        Anything else (no group, or a branch-less obsluha that would be
        unscoped everywhere) must not get a session."""
        if self.is_superuser or self.is_vlastnik:
            return True
        return self.is_obsluha and self.branch_id is not None
