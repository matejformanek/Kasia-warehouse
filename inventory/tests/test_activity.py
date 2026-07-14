"""Screen-visit tracking: `ScreenVisitMiddleware` + the vlastník-only
„Aktivita" page (0077).

The middleware writes one `ScreenVisit` per authenticated, full-page,
successful GET under /sklad/ — and nothing else: no htmx fragments, no
anonymous requests (the login page serves 200 to anonymous visitors under
/sklad/, so the `is_authenticated` guard is load-bearing), no public pages,
no POSTs, no 404s. A failing write never breaks the request.
"""

from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from inventory.middleware import EXCLUDED_URL_NAMES
from inventory.models import ScreenVisit

from ._support import _VIEW_TEST_OVERRIDES

# --- middleware ---------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_sklad_get_writes_visit_row(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(reverse("inventory:catalogue_index"))
    assert response.status_code == 200
    visit = ScreenVisit.objects.get()
    assert visit.user == user_vlastnik
    assert visit.url_name == "catalogue_index"
    assert visit.namespace == "inventory"
    assert visit.path == "/sklad/katalog/"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_root_namespace_password_change_tracked(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(reverse("password_change"))
    assert response.status_code == 200
    visit = ScreenVisit.objects.get()
    assert visit.url_name == "password_change"
    assert visit.namespace == ""


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_htmx_request_not_tracked(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        reverse("inventory:catalogue_index"), HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 200
    assert ScreenVisit.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_partial_endpoint_not_tracked_even_without_htmx_header(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        reverse("inventory:line_row_partial"), {"index": "1"}
    )
    assert response.status_code == 200
    assert ScreenVisit.objects.count() == 0


def test_excluded_url_names_pinned():
    # The complete set of GET fragment endpoints; a new GET partial must be
    # added to the middleware's exclusion list (frontend-and-templates.md).
    assert EXCLUDED_URL_NAMES == frozenset(
        {"line_row_partial", "mixing_preview_partial"}
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_public_page_not_tracked(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(reverse("web:home"))
    assert response.status_code == 200
    assert ScreenVisit.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_anonymous_sklad_get_not_tracked():
    response = Client().get(reverse("inventory:catalogue_index"))
    assert response.status_code == 302  # LoginRequiredMiddleware redirect
    assert ScreenVisit.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_anonymous_login_page_200_not_tracked():
    # /sklad/prihlaseni/ is @login_not_required and serves 200 to anonymous
    # visitors — this pins the load-bearing is_authenticated guard.
    response = Client().get(reverse("login"))
    assert response.status_code == 200
    assert ScreenVisit.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_404_not_tracked(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        reverse("inventory:product_detail", args=[999999])
    )
    assert response.status_code == 404
    assert ScreenVisit.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_post_not_tracked(user_vlastnik):
    client = Client()
    client.force_login(user_vlastnik)
    client.post(reverse("inventory:catalogue_index"))  # 405 — require_GET
    assert ScreenVisit.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_failing_write_never_breaks_the_request(user_vlastnik, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("DB down")

    monkeypatch.setattr(ScreenVisit.objects, "create", _boom)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(reverse("inventory:catalogue_index"))
    assert response.status_code == 200
    assert ScreenVisit.objects.count() == 0


# --- Aktivita page ------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_activity_page_obsluha_403(user_obsluha_tyn):
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(reverse("inventory:activity_index"))
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_activity_page_summary_counts(user_vlastnik, user_obsluha_tyn):
    # Three visits for the obsluha: now / 10 days ago / 40 days ago.
    for days_ago in (0, 10, 40):
        visit = ScreenVisit.objects.create(
            user=user_obsluha_tyn,
            url_name="catalogue_index",
            namespace="inventory",
            path="/sklad/katalog/",
        )
        if days_ago:
            # Backdate via .update() — auto_now_add wins on create()
            # (freezegun is not a dependency; 0019-migration precedent).
            ScreenVisit.objects.filter(pk=visit.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(reverse("inventory:activity_index"))
    assert response.status_code == 200
    by_pk = {u.pk: u for u in response.context["users"]}
    obsluha = by_pk[user_obsluha_tyn.pk]
    assert obsluha.visits_7d == 1
    assert obsluha.visits_30d == 2
    assert obsluha.last_visit is not None
    # Top screens (30 d) show the Czech label for catalogue_index.
    assert any(s["label"] == "Katalog" for s in response.context["top_screens"])


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_activity_page_filters(user_vlastnik, user_obsluha_tyn):
    for user, url_name, path in (
        (user_obsluha_tyn, "catalogue_index", "/sklad/katalog/"),
        (user_obsluha_tyn, "movement_history", "/sklad/pohyby/"),
        (user_vlastnik, "catalogue_index", "/sklad/katalog/"),
    ):
        ScreenVisit.objects.create(
            user=user, url_name=url_name, namespace="inventory", path=path
        )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        reverse("inventory:activity_index"),
        {"user": str(user_obsluha_tyn.pk), "screen": "catalogue_index"},
    )
    assert response.status_code == 200
    visits = response.context["visits"]
    assert visits  # at least the seeded row
    assert all(
        v.user_id == user_obsluha_tyn.pk and v.url_name == "catalogue_index"
        for v in visits
    )
    # An invalid filter value is dropped, not 500ed.
    response = client.get(
        reverse("inventory:activity_index"), {"user": "nonsense", "screen": "x"}
    )
    assert response.status_code == 200
    assert response.context["filter_user"] == ""
    assert response.context["filter_screen"] == ""


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_activity_pagination_preserves_querystring(user_vlastnik, user_obsluha_tyn):
    for _ in range(51):
        ScreenVisit.objects.create(
            user=user_obsluha_tyn,
            url_name="catalogue_index",
            namespace="inventory",
            path="/sklad/katalog/",
        )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(
        reverse("inventory:activity_index"),
        {"user": str(user_obsluha_tyn.pk)},
    )
    assert response.status_code == 200
    assert response.context["page_obj"].paginator.num_pages >= 2
    assert f"user={user_obsluha_tyn.pk}&page=2" in response.content.decode()
