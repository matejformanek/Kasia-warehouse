"""Tests for the public marketing site (decisions 0049 + 0050).

Covers: public pages render 200 anonymously; the warehouse app under /sklad/
still 302s anonymously (the URL move is provably gated); the kontakt form
persists a ContactInquiry and a failed e-mail send never loses the row.
"""

import pytest
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from .models import ContactInquiry

# Public templates use {% static %}; under tests the manifest storage has no
# manifest, and the kontakt form sends e-mail — mirror inventory/tests.py.
_OVERRIDES = {
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
}

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _view_overrides():
    """Plain-static (no manifest under tests) + locmem e-mail for outbox."""
    with override_settings(**_OVERRIDES):
        yield


# --- Public pages render 200 anonymously -----------------------------------


@pytest.mark.parametrize(
    "name",
    ["web:home", "web:o_nas", "web:provozovny", "web:kontakt", "web:kontakt_ok"],
)
def test_public_page_renders_anonymously(name) -> None:
    response = Client().get(reverse(name))
    assert response.status_code == 200


def test_home_renders_proof_stat_and_sklad_link() -> None:
    body = Client().get(reverse("web:home")).content.decode("utf-8")
    assert "369" in body  # proof stat
    assert "236" in body
    # Discreet "Sklad / Přihlášení" footer link points into the app.
    assert "/sklad/" in body
    assert "Přihlášení" in body


def test_robots_txt() -> None:
    response = Client().get("/robots.txt")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode("utf-8")
    assert "Disallow: /sklad/" in body
    assert "Sitemap:" in body


def test_sitemap_xml() -> None:
    response = Client().get("/sitemap.xml")
    assert response.status_code == 200
    assert "xml" in response["Content-Type"]
    body = response.content.decode("utf-8")
    assert "<urlset" in body
    assert "/o-nas/" in body


# --- The warehouse app moved under /sklad/ and is still gated ----------------


def test_root_is_public_not_the_app() -> None:
    # "/" now serves the public homepage (200), not the login-gated dashboard.
    response = Client().get("/")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path",
    ["/sklad/", "/sklad/katalog/", "/sklad/pohyby/", "/sklad/uzivatele/"],
)
def test_sklad_paths_redirect_anonymous_to_login(path) -> None:
    response = Client().get(path)
    assert response.status_code == 302
    assert response["Location"].startswith("/sklad/prihlaseni/")


def test_sklad_login_page_renders() -> None:
    response = Client().get("/sklad/prihlaseni/")
    assert response.status_code == 200


# --- Kontakt form persists + e-mails (durability over uptime, 0050) ---------

_VALID_POST = {
    "name": "Jan Novák",
    "email": "jan@example.cz",
    "phone": "+420 777 123 456",
    "message": "Mám zájem o velkoobchodní spolupráci.",
    "consent": "on",
}


def test_kontakt_post_persists_inquiry_and_redirects() -> None:
    response = Client().post(reverse("web:kontakt"), _VALID_POST)
    assert response.status_code == 302
    assert response["Location"] == reverse("web:kontakt_ok")
    inquiry = ContactInquiry.objects.get()
    assert inquiry.name == "Jan Novák"
    assert inquiry.email == "jan@example.cz"
    assert inquiry.handled is False
    # Best-effort notification e-mail was sent.
    assert len(mail.outbox) == 1


def test_kontakt_post_without_consent_does_not_save() -> None:
    payload = dict(_VALID_POST)
    del payload["consent"]
    response = Client().post(reverse("web:kontakt"), payload)
    assert response.status_code == 200  # re-renders with errors
    assert ContactInquiry.objects.count() == 0


def test_kontakt_post_missing_required_does_not_save() -> None:
    response = Client().post(reverse("web:kontakt"), {"consent": "on"})
    assert response.status_code == 200
    assert ContactInquiry.objects.count() == 0


def test_kontakt_email_failure_does_not_lose_the_row(monkeypatch) -> None:
    """A broken/missing SMTP config must never lose a saved inquiry (0050)."""

    def _boom(self, *args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("web.views.EmailMessage.send", _boom)
    response = Client().post(reverse("web:kontakt"), _VALID_POST)
    assert response.status_code == 302
    assert response["Location"] == reverse("web:kontakt_ok")
    assert ContactInquiry.objects.count() == 1  # row survived the failed send
    assert len(mail.outbox) == 0
