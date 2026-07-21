from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    EmailLog,
    Feedback,
    Product,
    RecipeComponent,
)
from inventory.tests._support import (
    _FIXTURE_XLS,
    _VIEW_TEST_OVERRIDES,
    _seed_vydej,
    _xls_upload,
)

# Pass 7 — Podpora (in-app docs + feedback log, per decision 0046)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_anonymous_redirects_to_login() -> None:
    response = Client().get("/sklad/podpora/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_get_renders_form_and_list_for_logged_in_user(
    user_vlastnik,
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/podpora/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Podpora" in body
    assert "Nahlásit chybu nebo požadavek" in body
    assert "Historie hlášení" in body
    assert "Žádná otevřená hlášení" in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_post_creates_feedback_and_redirects(
    user_vlastnik,
) -> None:
    """Per 0079: page_url is now a dropdown whose value == the Czech screen
    name; the friendly label is stored verbatim. (transaction=True so the
    on_commit feedback-notification send fires.)"""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "Katalog", "description": "Chybí mi sloupec X."},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/podpora/"
    f = Feedback.objects.get()
    assert f.description == "Chybí mi sloupec X."
    assert f.page_url == "Katalog"
    assert f.created_by_id == user_vlastnik.pk
    assert f.resolved_at is None
    assert f.is_open


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_post_sends_feedback_notification_email(user_vlastnik) -> None:
    """Per 0079: submitting a report schedules an admin notification e-mail
    (on_commit → needs transaction=True to fire) and logs a FEEDBACK row."""
    from django.core import mail

    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "Výdej", "description": "Něco nefunguje."},
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Nové hlášení z Podpory"
    log = EmailLog.objects.filter(
        category=EmailLog.Category.FEEDBACK
    ).get()
    assert log.status == EmailLog.Status.SENT


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_routes_to_feedback_recipients(user_vlastnik) -> None:
    """Per 0081: with a is_feedback_recipient row configured, the Podpora mail
    goes there — not to the fixed FEEDBACK_NOTIFY_EMAIL fallback."""
    from django.core import mail

    from inventory.models import SettingsRecipient

    SettingsRecipient.objects.create(
        email="matej@kasia.cz",
        label="Matej",
        is_active=True,
        is_dodaci_recipient=False,
        is_feedback_recipient=True,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "Katalog", "description": "Test."},
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["matej@kasia.cz"]
    # Per 0082: the Podpora link is an absolute, clickable URL.
    assert "http://localhost/sklad/podpora/" in mail.outbox[0].body
    log = EmailLog.objects.get(category=EmailLog.Category.FEEDBACK)
    assert log.recipients == "matej@kasia.cz"


@pytest.mark.django_db(transaction=True)
@override_settings(
    FEEDBACK_NOTIFY_EMAIL="fallback@kasia.cz", **_VIEW_TEST_OVERRIDES
)
def test_feedback_falls_back_to_notify_email_when_none_configured(
    user_vlastnik,
) -> None:
    """Per 0081: no is_feedback_recipient row → fall back to the fixed address."""
    from django.core import mail

    from inventory.models import SettingsRecipient

    # Ensure no feedback recipient exists (conftest doesn't seed inventory
    # fixtures here, but be explicit).
    SettingsRecipient.objects.update(is_feedback_recipient=False)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "Katalog", "description": "Test."},
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["fallback@kasia.cz"]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_post_without_description_fails_validation(
    user_vlastnik,
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "/sklad/katalog/", "description": ""},
    )
    assert response.status_code == 200
    assert Feedback.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_post_with_optional_page_url(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/podpora/",
        {"page_url": "", "description": "Obecný nápad bez konkrétní stránky."},
    )
    assert response.status_code == 302
    f = Feedback.objects.get()
    assert f.page_url == ""


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_toggle_marks_resolved_as_vlastnik(user_vlastnik) -> None:
    f = Feedback.objects.create(
        created_by=user_vlastnik, description="test"
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(f"/sklad/podpora/{f.pk}/vyresit/")
    assert response.status_code == 302
    f.refresh_from_db()
    assert f.resolved_at is not None
    assert f.resolved_by_id == user_vlastnik.pk
    assert not f.is_open


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_toggle_reopens_already_resolved_as_vlastnik(
    user_vlastnik,
) -> None:
    f = Feedback.objects.create(
        created_by=user_vlastnik, description="test"
    )
    client = Client()
    client.force_login(user_vlastnik)
    client.post(f"/sklad/podpora/{f.pk}/vyresit/")
    client.post(f"/sklad/podpora/{f.pk}/vyresit/")
    f.refresh_from_db()
    assert f.resolved_at is None
    assert f.resolved_by is None
    assert f.is_open


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_support_hides_resolved_by_default_and_reveals_on_click(
    user_vlastnik,
) -> None:
    """Per 0059-part-B: resolved reports are hidden by default (only open +
    a reveal link render); ?show_resolved=1 renders the resolved rows."""
    from django.utils import timezone as _tz

    older_open = Feedback.objects.create(
        created_by=user_vlastnik, description="OLDER_OPEN_MARKER"
    )
    resolved = Feedback.objects.create(
        created_by=user_vlastnik, description="RESOLVED_MARKER"
    )
    resolved.resolved_at = _tz.now()
    resolved.resolved_by = user_vlastnik
    resolved.save()
    newer_open = Feedback.objects.create(
        created_by=user_vlastnik, description="NEWER_OPEN_MARKER"
    )

    client = Client()
    client.force_login(user_vlastnik)

    # Default GET: open rows render, resolved is NOT rendered, reveal link shown.
    body = client.get("/sklad/podpora/").content.decode("utf-8")
    pos_newer_open = body.find("NEWER_OPEN_MARKER")
    pos_older_open = body.find("OLDER_OPEN_MARKER")
    assert pos_newer_open != -1
    assert pos_older_open != -1
    assert "RESOLVED_MARKER" not in body  # hidden by default
    assert "Zobrazit vyřešená (1)" in body
    # Within open: newer comes before older.
    assert pos_newer_open < pos_older_open
    assert older_open.pk != newer_open.pk  # sanity

    # ?show_resolved=1 reveals the resolved row.
    revealed = client.get(
        "/sklad/podpora/?show_resolved=1"
    ).content.decode("utf-8")
    assert "RESOLVED_MARKER" in revealed
    assert "NEWER_OPEN_MARKER" in revealed


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_toggle_rejected_for_obsluha_with_message_redirect(
    user_obsluha_tyn, user_vlastnik,
) -> None:
    f = Feedback.objects.create(
        created_by=user_vlastnik, description="test"
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/podpora/{f.pk}/vyresit/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/sklad/podpora/"
    f.refresh_from_db()
    assert f.resolved_at is None
    assert f.is_open


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_feedback_visible_to_all_users_not_just_creator(
    user_vlastnik, user_obsluha_tyn,
) -> None:
    Feedback.objects.create(
        created_by=user_vlastnik, description="Hlášení od vlastníka"
    )
    Feedback.objects.create(
        created_by=user_obsluha_tyn, description="Hlášení od obsluhy"
    )
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/podpora/")
    body = response.content.decode("utf-8")
    assert "Hlášení od vlastníka" in body
    assert "Hlášení od obsluhy" in body
    # Obsluha must NOT see the toggle button.
    assert "Vyřešit" not in body


# ---------------------------------------------------------------------------
# XLS recipe importer (Pass 8, per decision 0048)
# ---------------------------------------------------------------------------


def test_parse_recipe_xls_sample() -> None:
    from inventory.services import parse_recipe_xls

    with open(_FIXTURE_XLS, "rb") as f:
        parsed = parse_recipe_xls(f, "touzimsky.xls")

    assert parsed.mixture_name == "Toužimský Knedlík"
    assert parsed.total_kg == Decimal("800.8")
    assert len(parsed.lines) == 5
    names = [line.name_cs for line in parsed.lines]
    assert "Krupička" in names
    assert "Škrob" in names
    assert "Sůl" in names
    assert "Kurkuma" in names
    # Notes capture the post-CELKEM rows.
    assert "BALIT" in parsed.notes
    assert "CELKOVÁ DOBA MÍCHÁNÍ" in parsed.notes
    assert parsed.warnings == []


def test_parse_recipe_xls_ratios_sum_to_one() -> None:
    from inventory.services import parse_recipe_xls

    with open(_FIXTURE_XLS, "rb") as f:
        parsed = parse_recipe_xls(f, "touzimsky.xls")

    total = sum((line.ratio for line in parsed.lines), Decimal("0"))
    assert total == Decimal("1.000000")
    for line in parsed.lines:
        assert line.ratio > 0


def test_parse_recipe_xls_title_cases_names() -> None:
    from inventory.services import parse_recipe_xls

    with open(_FIXTURE_XLS, "rb") as f:
        parsed = parse_recipe_xls(f, "touzimsky.xls")

    # Source XLS has "KRUPIČKA" (all caps) — must come back Title-Cased.
    assert "KRUPIČKA" not in [line.name_cs for line in parsed.lines]
    assert "Krupička" in [line.name_cs for line in parsed.lines]


def test_parse_recipe_xls_empty_file_raises_czech() -> None:
    import io

    from inventory.services import parse_recipe_xls

    # A 1-byte file is invalid XLS — both xlrd and openpyxl raise.
    # Our wrapper coerces all to ValueError with a Czech message
    # only for the "unknown extension" path; xlrd/openpyxl errors
    # bubble. Check that ValueError surfaces for the no-extension path.
    with pytest.raises(ValueError, match=".xls"):
        parse_recipe_xls(io.BytesIO(b"x"), "foo.txt")


@pytest.mark.django_db
def test_xls_import_upload_requires_login() -> None:
    response = Client().get("/sklad/katalog/import-xls/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_upload_obsluha_forbidden(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/import-xls/")
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_upload_vlastnik_renders_form(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/import-xls/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "XLS" in body
    assert "Načíst soubor" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_upload_post_parses_renders_review(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/import-xls/",
        {"xls_file": _xls_upload()},
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Toužimský" in body
    assert "Krupička" in body
    assert "Škrob" in body
    # No raw spices were seeded → every ingredient must show as new.
    assert "+ nová surovina" in body
    # Review form must be present.
    assert "Vytvořit směs" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_confirm_creates_mixture_and_components(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    # First POST: upload → review. We need to use the formset's management
    # form values that the review page rendered; easier to drive the service
    # path directly via the confirm endpoint with synthetic data that matches
    # what the review form would have posted.
    payload = {
        "name_cs": "Toužimský Knedlík",
        "notes": "BALIT Á 5 KG\nCELKOVÁ DOBA MÍCHÁNÍ 12 MINUT",
        "total_kg": "800.800",
        "form-TOTAL_FORMS": "5",
        "form-INITIAL_FORMS": "5",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-name_cs": "Krupička",
        "form-0-qty_kg": "317.000",
        "form-0-existing_product_id": "",
        "form-1-name_cs": "Škrob",
        "form-1-qty_kg": "112.000",
        "form-1-existing_product_id": "",
        "form-2-name_cs": "Vločky PF 51",
        "form-2-qty_kg": "355.000",
        "form-2-existing_product_id": "",
        "form-3-name_cs": "Sůl",
        "form-3-qty_kg": "16.000",
        "form-3-existing_product_id": "",
        "form-4-name_cs": "Kurkuma",
        "form-4-qty_kg": "0.800",
        "form-4-existing_product_id": "",
    }
    response = client.post("/sklad/katalog/import-xls/potvrdit/", payload)
    assert response.status_code == 302
    mixture = Product.objects.get(name_cs="Toužimský Knedlík")
    assert mixture.kind == Product.Kind.MIXTURE
    components = list(
        RecipeComponent.objects.filter(mixture_product=mixture)
        .order_by("component_product__name_cs")
    )
    assert len(components) == 5
    # Ratios sum to exactly 1.000000 — invariant from _normalize_ratios.
    assert sum((c.ratio for c in components), Decimal("0")) == Decimal("1.000000")
    # All five raw spices auto-created.
    raw_names = {c.component_product.name_cs for c in components}
    assert raw_names == {"Krupička", "Škrob", "Vločky PF 51", "Sůl", "Kurkuma"}
    for c in components:
        assert c.component_product.kind == Product.Kind.RAW_SPICE


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_confirm_reuses_existing_raw_spice_case_insensitive(
    user_vlastnik,
) -> None:
    """Seed "Krupička" in different case; import must reuse, not duplicate."""
    existing = Product.objects.create(
        name_cs="Krupička", kind=Product.Kind.RAW_SPICE
    )
    client = Client()
    client.force_login(user_vlastnik)
    payload = {
        "name_cs": "Test směs",
        "notes": "",
        "total_kg": "100.000",
        "form-TOTAL_FORMS": "2",
        "form-INITIAL_FORMS": "2",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        # All-caps to verify the casefold dedupe.
        "form-0-name_cs": "KRUPIČKA",
        "form-0-qty_kg": "80.000",
        "form-0-existing_product_id": "",
        "form-1-name_cs": "Pepř Nový",
        "form-1-qty_kg": "20.000",
        "form-1-existing_product_id": "",
    }
    response = client.post("/sklad/katalog/import-xls/potvrdit/", payload)
    assert response.status_code == 302
    # Only one "Krupička" exists — the existing one was reused.
    assert Product.objects.filter(name_cs__iexact="Krupička").count() == 1
    mixture = Product.objects.get(name_cs="Test směs")
    components = list(
        RecipeComponent.objects.filter(mixture_product=mixture)
    )
    assert any(c.component_product_id == existing.pk for c in components)


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_confirm_refuses_duplicate_mixture_name(
    user_vlastnik,
) -> None:
    Product.objects.create(
        name_cs="Toužimský Knedlík", kind=Product.Kind.MIXTURE
    )
    client = Client()
    client.force_login(user_vlastnik)
    payload = {
        "name_cs": "Toužimský Knedlík",
        "notes": "",
        "total_kg": "10.000",
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "1",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-name_cs": "Krupička",
        "form-0-qty_kg": "10.000",
        "form-0-existing_product_id": "",
    }
    response = client.post("/sklad/katalog/import-xls/potvrdit/", payload)
    assert response.status_code == 400
    body = response.content.decode("utf-8")
    assert "už v katalogu existuje" in body
    # Mixture count unchanged.
    assert Product.objects.filter(name_cs="Toužimský Knedlík").count() == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_xls_import_confirm_rejects_zero_ratio(user_vlastnik) -> None:
    """One ingredient too tiny to represent at 6 dp → Czech error.

    Form qty_kg is decimal_places=3, smallest accepted = 0.001. For the
    ratio to quantise to 0 at 6 dp we need 0.001 / total < 5e-7, i.e.
    total > 2000. Using 0.001 / 9999.999 ≈ 1e-7 gives a reliable trip.
    """
    client = Client()
    client.force_login(user_vlastnik)
    payload = {
        "name_cs": "Mikro směs",
        "notes": "",
        "total_kg": "10000.000",
        "form-TOTAL_FORMS": "2",
        "form-INITIAL_FORMS": "2",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-name_cs": "Mouka",
        "form-0-qty_kg": "9999.999",
        "form-0-existing_product_id": "",
        "form-1-name_cs": "Mikrokoření",
        "form-1-qty_kg": "0.001",
        "form-1-existing_product_id": "",
    }
    response = client.post("/sklad/katalog/import-xls/potvrdit/", payload)
    assert response.status_code == 400
    body = response.content.decode("utf-8")
    assert "příliš malý poměr" in body
    # No mixture committed.
    assert not Product.objects.filter(name_cs="Mikro směs").exists()


@pytest.mark.django_db
def test_catalogue_index_shows_xls_import_button_for_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    with override_settings(**_VIEW_TEST_OVERRIDES):
        response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    assert "Importovat z XLS" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_catalogue_index_hides_xls_import_button_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    with override_settings(**_VIEW_TEST_OVERRIDES):
        response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    assert "Importovat z XLS" not in response.content.decode("utf-8")


# ---------------------------------------------------------------------------
# Batch A — Podpora feedback: form defaults to today, FAILED banner on dodák
# detail (per /podpora/ feedback #1 + #5, 2026-06-26).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_planned_transfer_create_view_prefills_today(user_vlastnik) -> None:
    """GET /prevody/novy/ renders scheduled_for pre-filled with today."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/prevody/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # ISO YYYY-MM-DD — browsers only honour ISO in <input type="date">.
    assert f'value="{date.today().isoformat()}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_plan_form_prefills_today(user_vlastnik, tyn) -> None:
    """GET /michani/planovat/ renders planned_for pre-filled with today."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/michani/planovat/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # ISO YYYY-MM-DD — browsers only honour ISO in <input type="date">.
    assert f'value="{date.today().isoformat()}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_prijem_create_view_prefills_today_iso(user_obsluha_tyn) -> None:
    """GET /sklad/prijem/novy/ renders date_issued pre-filled with today (ISO)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/prijem/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert f'value="{date.today().isoformat()}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_create_view_has_no_date_field(user_obsluha_tyn) -> None:
    """Per 0086: výdej is always dated today — the form renders no date field."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/vydej/novy/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Datum vystavení" not in body
    assert 'id="id_date_issued"' not in body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_dodaci_list_detail_renders_failed_banner_when_unresolved(
    user_tyn, tyn, ricany, pepper
) -> None:
    """When current_version has FAILED log and no SENT log, banner shows."""
    mv, dl = _seed_vydej(user_tyn, tyn, ricany, pepper)
    # Replace all logs at current_version with a single FAILED row.
    EmailLog.objects.filter(
        dodaci_list=dl, dodaci_version=dl.current_version
    ).delete()
    EmailLog.objects.create(
        dodaci_list=dl,
        dodaci_version=dl.current_version,
        recipients="petr@kasia.cz",
        trigger_reason="initial send",
        status=EmailLog.Status.FAILED,
        error_message="SMTP timeout",
    )
    client = Client()
    client.force_login(user_tyn)
    response = client.get(f"/sklad/dodaky/{dl.cislo}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Poslední odeslání selhalo." in body


# ---------------------------------------------------------------------------
