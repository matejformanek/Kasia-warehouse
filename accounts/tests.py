import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse

from inventory.models import Branch

User = get_user_model()


@pytest.mark.django_db
def test_create_user_with_email() -> None:
    user = User.objects.create_user(email="petr@example.cz", password="x" * 12)
    assert user.email == "petr@example.cz"
    assert user.username is None
    assert user.check_password("x" * 12)


@pytest.mark.django_db
def test_email_unique() -> None:
    User.objects.create_user(email="karolina@example.cz", password="x" * 12)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create_user(email="karolina@example.cz", password="y" * 12)


@pytest.mark.django_db
def test_create_superuser() -> None:
    admin = User.objects.create_superuser(email="admin@example.cz", password="x" * 12)
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.is_active is True


@pytest.mark.django_db
def test_user_branch_nullable_for_vlastnik() -> None:
    user = User.objects.create_user(email="vlastnik@example.cz", password="x" * 12)
    assert user.branch is None


@pytest.mark.django_db
def test_user_branch_assigned_for_obsluha() -> None:
    tyn = Branch.objects.get(code="TYN")
    user = User.objects.create_user(
        email="obsluha-tyn@example.cz",
        password="x" * 12,
        branch=tyn,
    )
    assert user.branch == tyn


@pytest.mark.django_db
def test_seed_migration_creates_groups() -> None:
    assert Group.objects.filter(name="vlastnik").exists()
    assert Group.objects.filter(name="obsluha").exists()


# ---------------------------------------------------------------------------
# Screen 13 — Správa uživatelů
# ---------------------------------------------------------------------------


_LOCMEM_EMAIL = {"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}

_PLAIN_STATIC = {
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
}

_TEST_OVERRIDES = {**_PLAIN_STATIC, **_LOCMEM_EMAIL}


pytestmark_views = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _view_overrides(request):
    """Apply plain-static + locmem-email to every test in this module.

    The base.html nav references `vendor/htmx.min.js`; under the default
    CompressedManifestStaticFilesStorage, rendering it in tests blows up
    on a missing manifest entry. Pair with locmem for outbox assertions.
    """
    if "no_overrides" in request.keywords:
        yield
        return
    with override_settings(**_TEST_OVERRIDES):
        yield


@pytest.fixture
def vlastnik(db) -> User:
    return User.objects.create_user(
        email="vlastnik@example.cz", password="x" * 12
    )


@pytest.fixture
def obsluha(db) -> User:
    tyn = Branch.objects.get(code="TYN")
    u = User.objects.create_user(
        email="obsluha@example.cz", password="x" * 12, branch=tyn
    )
    grp, _ = Group.objects.get_or_create(name="obsluha")
    u.groups.add(grp)
    return u


@pytest.mark.django_db
def test_user_index_requires_login() -> None:
    response = Client().get(reverse("accounts:user_index"))
    assert response.status_code == 302
    assert "/login/" in response["Location"]


@pytest.mark.django_db
def test_user_index_forbidden_for_obsluha(obsluha) -> None:
    client = Client()
    client.force_login(obsluha)
    response = client.get(reverse("accounts:user_index"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_index_renders_for_vlastnik(vlastnik) -> None:
    client = Client()
    client.force_login(vlastnik)
    response = client.get(reverse("accounts:user_index"))
    assert response.status_code == 200
    assert b"U\xc5\xbeivatel\xc3\xa9" in response.content  # "Uživatelé"
    assert b"Aktivn\xc3\xadch" in response.content  # "Aktivních"
    assert b"vlastnik@example.cz" in response.content


@pytest.mark.django_db
def test_user_create_vlastnik(vlastnik) -> None:
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_create"),
        {
            "first_name": "Nový",
            "last_name": "Vlastník",
            "email": "novy@example.cz",
            "role": "vlastnik",
            "branch": "",
            "password1": "tajneheslo123",
            "password2": "tajneheslo123",
        },
    )
    assert response.status_code == 302
    u = User.objects.get(email="novy@example.cz")
    assert u.is_vlastnik
    assert u.branch is None
    assert u.first_name == "Nový"


@pytest.mark.django_db
def test_user_create_obsluha(vlastnik) -> None:
    tyn = Branch.objects.get(code="TYN")
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_create"),
        {
            "first_name": "Jan",
            "last_name": "Novák",
            "email": "jan@example.cz",
            "role": "obsluha",
            "branch": str(tyn.pk),
            "password1": "tajneheslo123",
            "password2": "tajneheslo123",
        },
    )
    assert response.status_code == 302
    u = User.objects.get(email="jan@example.cz")
    assert u.is_obsluha
    assert u.branch_id == tyn.pk


@pytest.mark.django_db
def test_user_create_obsluha_without_branch_rejected(vlastnik) -> None:
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_create"),
        {
            "first_name": "Eva",
            "email": "eva@example.cz",
            "role": "obsluha",
            "branch": "",
            "password1": "tajneheslo123",
            "password2": "tajneheslo123",
        },
    )
    assert response.status_code == 200
    assert not User.objects.filter(email="eva@example.cz").exists()
    assert b"mus\xc3\xad m\xc3\xadt p\xc5\x99i\xc5\x99azenou" in response.content


@pytest.mark.django_db
def test_user_create_duplicate_email_rejected(vlastnik) -> None:
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_create"),
        {
            "first_name": "Dva",
            "email": "vlastnik@example.cz",  # same as the existing one
            "role": "vlastnik",
            "branch": "",
            "password1": "tajneheslo123",
            "password2": "tajneheslo123",
        },
    )
    assert response.status_code == 200
    assert User.objects.filter(email="vlastnik@example.cz").count() == 1


@pytest.mark.django_db
def test_user_create_password_mismatch_rejected(vlastnik) -> None:
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_create"),
        {
            "first_name": "Mismatch",
            "email": "mis@example.cz",
            "role": "vlastnik",
            "branch": "",
            "password1": "tajneheslo123",
            "password2": "tajneheslo456",
        },
    )
    assert response.status_code == 200
    assert not User.objects.filter(email="mis@example.cz").exists()


@pytest.mark.django_db
def test_user_edit_changes_role_and_branch(vlastnik) -> None:
    # Create a second vlastník so we don't trip the last-owner protection.
    other = User.objects.create_user(
        email="other@example.cz", password="x" * 12
    )
    tyn = Branch.objects.get(code="TYN")
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_edit", args=[other.pk]),
        {
            "first_name": "Other",
            "last_name": "Person",
            "email": other.email,
            "role": "obsluha",
            "branch": str(tyn.pk),
        },
    )
    assert response.status_code == 302
    other.refresh_from_db()
    assert other.first_name == "Other"
    assert other.is_obsluha
    assert other.branch_id == tyn.pk


@pytest.mark.django_db
def test_user_edit_last_vlastnik_demotion_refused(vlastnik) -> None:
    tyn = Branch.objects.get(code="TYN")
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_edit", args=[vlastnik.pk]),
        {
            "first_name": "Self",
            "email": vlastnik.email,
            "role": "obsluha",
            "branch": str(tyn.pk),
        },
    )
    assert response.status_code == 200
    vlastnik.refresh_from_db()
    assert vlastnik.is_vlastnik
    assert b"posledn\xc3\xadho aktivn\xc3\xadho vlastn\xc3\xadka" in response.content


@pytest.mark.django_db
def test_user_deactivate_success(vlastnik) -> None:
    # Need at least one other vlastník to deactivate this one.
    target = User.objects.create_user(
        email="leaving@example.cz", password="x" * 12
    )
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_deactivate", args=[target.pk])
    )
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.is_active is False


@pytest.mark.django_db
def test_user_deactivate_last_vlastnik_refused(vlastnik) -> None:
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_deactivate", args=[vlastnik.pk]),
        follow=True,
    )
    assert response.status_code == 200
    vlastnik.refresh_from_db()
    assert vlastnik.is_active is True


@pytest.mark.django_db
def test_user_reactivate(vlastnik) -> None:
    target = User.objects.create_user(
        email="back@example.cz", password="x" * 12, is_active=False
    )
    client = Client()
    client.force_login(vlastnik)
    response = client.post(
        reverse("accounts:user_reactivate", args=[target.pk])
    )
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.is_active is True


@pytest.mark.django_db
def test_user_password_reset_sends_email(vlastnik) -> None:
    target = User.objects.create_user(
        email="reset@example.cz", password="x" * 12
    )
    client = Client()
    client.force_login(vlastnik)
    outbox_before = len(mail.outbox)
    response = client.post(
        reverse("accounts:user_password_reset", args=[target.pk])
    )
    assert response.status_code == 302
    assert len(mail.outbox) == outbox_before + 1
    msg = mail.outbox[-1]
    assert "reset@example.cz" in msg.to
    assert "Reset hesla" in msg.subject


@pytest.mark.django_db
def test_user_password_reset_refused_for_deactivated(vlastnik) -> None:
    target = User.objects.create_user(
        email="off@example.cz", password="x" * 12, is_active=False
    )
    client = Client()
    client.force_login(vlastnik)
    outbox_before = len(mail.outbox)
    response = client.post(
        reverse("accounts:user_password_reset", args=[target.pk]),
        follow=True,
    )
    assert response.status_code == 200
    # No e-mail backend change for this test — assert no outbox grew if locmem;
    # default smtp backend won't actually send for failures either. Either way
    # the user record should still be inactive.
    target.refresh_from_db()
    assert target.is_active is False
    # The action should not have sent mail (we did not switch backend so this
    # checks the e-mail length stays unchanged).
    assert len(mail.outbox) == outbox_before


@pytest.mark.django_db
def test_nav_uzivatele_link_hidden_for_obsluha(obsluha) -> None:
    client = Client()
    client.force_login(obsluha)
    # Obsluha redirected to branch dashboard from /; check the nav there.
    response = client.get(
        reverse("inventory:branch_dashboard", args=["TYN"])
    )
    assert response.status_code == 200
    assert b"U\xc5\xbeivatel\xc3\xa9" not in response.content


@pytest.mark.django_db
def test_nav_uzivatele_link_shown_for_vlastnik(vlastnik) -> None:
    client = Client()
    client.force_login(vlastnik)
    response = client.get(reverse("inventory:home"))
    assert response.status_code == 200
    assert b"U\xc5\xbeivatel\xc3\xa9" in response.content
