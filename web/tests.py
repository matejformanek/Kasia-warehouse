"""Tests for the public marketing site (decisions 0050 + 0051; 0052 info-only Kontakt).

Covers: public pages render 200 anonymously; the warehouse app under /sklad/
still 302s anonymously (the URL move is provably gated); the info-only Kontakt
page renders the executive directory + a tel: link; Provozovny renders the real
branch addresses. The public site stores no data (the contact form was removed
in 0052).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

User = get_user_model()

# Public templates use {% static %}; under tests the manifest storage has no
# manifest — mirror inventory/tests.py with plain static storage.
_OVERRIDES = {
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
}

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _view_overrides():
    """Plain-static (no manifest under tests)."""
    with override_settings(**_OVERRIDES):
        yield


# --- Public pages render 200 anonymously -----------------------------------


@pytest.mark.parametrize(
    "name",
    ["web:home", "web:o_nas", "web:provozovny", "web:kontakt"],
)
def test_public_page_renders_anonymously(name) -> None:
    response = Client().get(reverse(name))
    assert response.status_code == 200


def test_home_renders_proof_stat_and_sklad_link() -> None:
    body = Client().get(reverse("web:home")).content.decode("utf-8")
    assert "369" in body  # proof stat
    assert "236" in body
    # Přihlášení is footer-only now (pass 2): the header link is gone, the
    # footer "Přihlášení do skladu" link points into the app.
    assert 'class="login-link"' not in body  # header login link removed
    assert reverse("login") in body  # footer link to /sklad/prihlaseni/
    assert "Přihlášení do skladu" in body


def test_home_is_enriched_for_b2b() -> None:
    """Pass 2 enrichment: capabilities / segments / why-us sections render."""
    body = Client().get(reverse("web:home")).content.decode("utf-8")
    assert "Co děláme" in body
    assert "Komu dodáváme" in body
    assert "Proč Kasia" in body


def test_o_nas_renders_long_form_history() -> None:
    """Pass 2: O nás is a real article with heritage + export content."""
    body = Client().get(reverse("web:o_nas")).content.decode("utf-8")
    assert "1993" in body
    assert "majoránce" in body  # the spice-position paragraph
    assert "export" in body.lower()  # dovoz a export section
    assert "Polsko" in body  # an export market


def test_kontakt_is_info_only_with_directory() -> None:
    """Kontakt is an info page (0052): exec directory + a callable phone, no form."""
    body = Client().get(reverse("web:kontakt")).content.decode("utf-8")
    assert "Šulc" in body  # executive directory rendered
    assert 'href="tel:+420323601422"' in body  # primary phone is callable
    assert "<form" not in body  # the poptávkový formulář is gone


def test_kontakt_ok_route_is_gone() -> None:
    """The form thank-you route was removed with the form (0052)."""
    response = Client().get("/kontakt/odeslano/")
    assert response.status_code == 404


def test_provozovny_renders_real_branch_address() -> None:
    body = Client().get(reverse("web:provozovny")).content.decode("utf-8")
    assert "Pod Kovosvitem" in body  # Sezimovo Ústí real street
    assert "Toužim" in body  # the fourth location


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


def test_sklad_login_page_renders_public_branded() -> None:
    """Pass 2: login uses the public chrome + dual employee/customer guidance."""
    response = Client().get("/sklad/prihlaseni/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Kasia vera s.r.o." in body  # public chrome (company name in footer)
    assert "Zaměstnanci" in body  # employee sign-in panel
    assert "Zákazníci" in body  # customer-guidance panel
    assert 'name="password"' in body  # the sign-in form


def test_sklad_login_redirects_authenticated_user() -> None:
    """An already-logged-in visitor is bounced to the sklad homepage, not the form."""
    user = User.objects.create_user(email="staff@example.cz", password="x" * 12)
    client = Client()
    client.force_login(user)
    response = client.get("/sklad/prihlaseni/")
    assert response.status_code == 302
    assert response["Location"].startswith("/sklad/")
