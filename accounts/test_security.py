"""Decision 0104 — roles fail closed, login gate, axes lockout, reset
throttle, SECRET_KEY guard."""

import importlib
import os
import subprocess
import sys

import pytest
from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from inventory.models import Branch

from .forms import NO_ROLE_LOGIN_MESSAGE, _count_other_active_vlastnik, _sync_role

User = get_user_model()
PW = "Spravne-heslo-123"

_OVERRIDES = {
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
}


def _group(name: str) -> Group:
    return Group.objects.get_or_create(name=name)[0]


def _user(email: str, *groups: str, **extra) -> User:
    u = User.objects.create_user(email=email, password=PW, **extra)
    for g in groups:
        u.groups.add(_group(g))
    return u


def _login(client: Client, email: str, password: str = PW, ip: str = "203.0.113.1"):
    return client.post(
        reverse("login"),
        {"username": email, "password": password},
        HTTP_X_FORWARDED_FOR=ip,
    )


# --- roles fail closed --------------------------------------------------------


@pytest.mark.django_db
def test_role_properties_fail_closed() -> None:
    tyn = Branch.objects.get(code="TYN")
    none = _user("none@example.cz")
    owner = _user("owner@example.cz", "vlastnik")
    staff = _user("staff@example.cz", "obsluha", branch=tyn)
    both = _user("both@example.cz", "vlastnik", "obsluha", branch=tyn)
    su = User.objects.create_superuser(email="su@example.cz", password=PW)
    assert (none.is_vlastnik, none.is_obsluha, none.has_valid_role) == (False, False, False)
    assert (owner.is_vlastnik, owner.has_valid_role) == (True, True)
    assert (staff.is_vlastnik, staff.is_obsluha, staff.has_valid_role) == (False, True, True)
    # obsluha wins over a stray vlastnik group — never more rights than staff.
    assert (both.is_vlastnik, both.is_obsluha) == (False, True)
    assert (su.is_vlastnik, su.has_valid_role) == (True, True)


@pytest.mark.django_db
def test_branchless_obsluha_has_no_valid_role() -> None:
    assert _user("nob@example.cz", "obsluha").has_valid_role is False


@pytest.mark.django_db
def test_sync_role_sets_both_groups() -> None:
    tyn = Branch.objects.get(code="TYN")
    u = _user("u@example.cz", branch=tyn)
    _sync_role(u, "vlastnik")
    assert set(u.groups.values_list("name", flat=True)) == {"vlastnik"}
    assert u.is_vlastnik
    _sync_role(u, "obsluha")
    assert set(u.groups.values_list("name", flat=True)) == {"obsluha"}
    assert u.is_obsluha and not u.is_vlastnik
    _sync_role(u, "vlastnik")
    assert set(u.groups.values_list("name", flat=True)) == {"vlastnik"}


@pytest.mark.django_db
def test_count_other_active_vlastnik_ignores_groupless_and_dedupes() -> None:
    tyn = Branch.objects.get(code="TYN")
    me = _user("me@example.cz", "vlastnik")
    _user("none@example.cz")  # groupless: NOT an owner any more
    _user("staff@example.cz", "obsluha", branch=tyn)
    _user("off@example.cz", "vlastnik", is_active=False)
    assert _count_other_active_vlastnik(me.pk) == 0
    # A second owner in two groups (vlastnik + an unrelated one) counts once.
    other = _user("other@example.cz", "vlastnik")
    other.groups.add(_group("extra"))
    assert _count_other_active_vlastnik(me.pk) == 1
    User.objects.create_superuser(email="su@example.cz", password=PW)
    assert _count_other_active_vlastnik(me.pk) == 2


@pytest.mark.django_db
def test_assign_vlastnik_migration_function() -> None:
    """0003 gives `vlastnik` to every non-superuser not in obsluha (incl.
    inactive) and touches nobody else."""
    mig = importlib.import_module("accounts.migrations.0003_assign_vlastnik_group")
    tyn = Branch.objects.get(code="TYN")
    groupless = _user("g@example.cz")
    inactive = _user("i@example.cz", is_active=False)
    staff = _user("s@example.cz", "obsluha", branch=tyn)
    su = User.objects.create_superuser(email="su@example.cz", password=PW)
    mig.assign_vlastnik(django_apps, None)
    names = lambda u: set(u.groups.values_list("name", flat=True))  # noqa: E731
    assert names(groupless) == {"vlastnik"}
    assert names(inactive) == {"vlastnik"}
    assert names(staff) == {"obsluha"}
    assert names(su) == set()
    # Idempotent.
    mig.assign_vlastnik(django_apps, None)
    assert names(groupless) == {"vlastnik"}
    assert not User.objects.filter(is_superuser=False, groups__isnull=True).exists()


@pytest.mark.django_db
@override_settings(**_OVERRIDES)
def test_user_create_vlastnik_gets_group() -> None:
    owner = _user("owner@example.cz", "vlastnik")
    c = Client()
    c.force_login(owner)
    r = c.post(
        reverse("accounts:user_create"),
        {"first_name": "N", "last_name": "", "email": "n@example.cz",
         "role": "vlastnik", "branch": ""},
    )
    assert r.status_code == 302
    new = User.objects.get(email="n@example.cz")
    assert new.is_vlastnik and new.has_valid_role


# --- login gate ----------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_OVERRIDES)
def test_login_refuses_groupless_user() -> None:
    _user("none@example.cz")
    r = _login(Client(), "none@example.cz")
    assert r.status_code == 200
    assert NO_ROLE_LOGIN_MESSAGE in r.content.decode()
    assert "_auth_user_id" not in r.wsgi_request.session


@pytest.mark.django_db
@override_settings(**_OVERRIDES)
def test_login_refuses_branchless_obsluha() -> None:
    _user("nob@example.cz", "obsluha")
    r = _login(Client(), "nob@example.cz")
    assert r.status_code == 200
    assert NO_ROLE_LOGIN_MESSAGE in r.content.decode()


@pytest.mark.django_db
@override_settings(**_OVERRIDES)
def test_login_allows_vlastnik_and_obsluha() -> None:
    tyn = Branch.objects.get(code="TYN")
    _user("owner@example.cz", "vlastnik")
    _user("staff@example.cz", "obsluha", branch=tyn)
    assert _login(Client(), "owner@example.cz").status_code == 302
    assert _login(Client(), "staff@example.cz").status_code == 302


# --- django-axes lockout -------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_OVERRIDES)
def test_axes_locks_after_five_failures_keyed_on_username_and_ip() -> None:
    _user("owner@example.cz", "vlastnik")
    c = Client()
    for _ in range(settings.AXES_FAILURE_LIMIT - 1):
        r = _login(c, "owner@example.cz", "wrong", ip="198.51.100.7")
        assert r.status_code == 200  # plain bad-credentials re-render
    # The 5th failure trips the lock.
    assert _login(c, "owner@example.cz", "wrong", ip="198.51.100.7").status_code == 429
    # Locked now — even the right password from the same IP is refused.
    locked = _login(c, "owner@example.cz", ip="198.51.100.7")
    assert locked.status_code == 429
    assert "Příliš mnoho pokusů" in locked.content.decode()
    # Same username from a different client IP is NOT locked (not keyed on
    # the Caddy container address / username alone).
    assert _login(Client(), "owner@example.cz", ip="198.51.100.8").status_code == 302


@pytest.mark.django_db
@override_settings(**_OVERRIDES)
def test_axes_ip_lock_does_not_block_other_users() -> None:
    _user("a@example.cz", "vlastnik")
    _user("b@example.cz", "vlastnik")
    for _ in range(settings.AXES_FAILURE_LIMIT):
        _login(Client(), "a@example.cz", "wrong", ip="198.51.100.9")
    assert _login(Client(), "a@example.cz", ip="198.51.100.9").status_code == 429
    assert _login(Client(), "b@example.cz", ip="198.51.100.9").status_code == 302


@pytest.mark.django_db
@override_settings(**_OVERRIDES)
def test_axes_covers_admin_login() -> None:
    User.objects.create_superuser(email="su@example.cz", password=PW)
    for _ in range(settings.AXES_FAILURE_LIMIT):
        Client().post(
            "/admin/login/",
            {"username": "su@example.cz", "password": "wrong"},
            HTTP_X_FORWARDED_FOR="198.51.100.10",
        )
    r = Client().post(
        "/admin/login/",
        {"username": "su@example.cz", "password": PW},
        HTTP_X_FORWARDED_FOR="198.51.100.10",
    )
    assert r.status_code == 429


def test_client_ip_uses_rightmost_forwarded_entry() -> None:
    from django.test import RequestFactory

    from .security import client_ip

    rf = RequestFactory()
    req = rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.5", REMOTE_ADDR="172.18.0.3")
    assert client_ip(req) == "203.0.113.5"
    assert client_ip(rf.get("/", REMOTE_ADDR="172.18.0.3")) == "172.18.0.3"


# --- password-reset throttle ---------------------------------------------------


@pytest.mark.django_db
@override_settings(
    **_OVERRIDES, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
def test_password_reset_throttled_per_ip() -> None:
    from .security import PASSWORD_RESET_LIMIT

    cache.clear()
    url = reverse("password_reset")
    for _ in range(PASSWORD_RESET_LIMIT):
        r = Client().post(url, {"email": "x@example.cz"}, HTTP_X_FORWARDED_FOR="192.0.2.1")
        assert r.status_code == 302
    r = Client().post(url, {"email": "x@example.cz"}, HTTP_X_FORWARDED_FOR="192.0.2.1")
    assert r.status_code == 429
    # Another IP is unaffected.
    r = Client().post(url, {"email": "x@example.cz"}, HTTP_X_FORWARDED_FOR="192.0.2.2")
    assert r.status_code == 302
    cache.clear()


# --- SECRET_KEY guard ----------------------------------------------------------


def _import_settings(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", "import kasia.settings.base"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    "key",
    [None, "insecure-dev-key-do-not-use-in-prod", "change-me-to-a-long-random-string"],
)
def test_secret_key_guard_rejects_defaults_when_not_debug(key) -> None:
    env = {"DJANGO_DEBUG": "0"}
    if key is not None:
        env["DJANGO_SECRET_KEY"] = key
    result = _import_settings(env)
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr


def test_secret_key_guard_allows_real_key_and_debug() -> None:
    assert _import_settings({"DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": "x" * 50}).returncode == 0
    # Docker build's collectstatic key.
    assert _import_settings({"DJANGO_SECRET_KEY": "build-only"}).returncode == 0
    assert _import_settings({"DJANGO_DEBUG": "1"}).returncode == 0


@pytest.mark.django_db
@override_settings(**_OVERRIDES)
def test_admin_add_user_form_exposes_groups() -> None:
    """A user created in /admin/ can be given a role at creation (0104)."""
    su = User.objects.create_superuser(email="su@example.cz", password=PW)
    c = Client()
    c.force_login(su)
    r = c.get("/admin/accounts/user/add/")
    assert r.status_code == 200
    assert 'name="groups"' in r.content.decode()
