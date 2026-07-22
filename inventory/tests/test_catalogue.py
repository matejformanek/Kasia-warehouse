from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    Product,
    RecipeComponent,
    Stock,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
)

# Pass 3f — catalogue (screens 04 + 05, read-only)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_requires_login() -> None:
    response = Client().get("/sklad/katalog/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sklad/prihlaseni/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_lists_active_only_by_default(
    user_vlastnik, pepper, paprika
) -> None:
    paprika.is_active = False
    paprika.save()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_archived_filter(user_vlastnik, pepper, paprika) -> None:
    paprika.is_active = False
    paprika.save()
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?status=archived")
    body = response.content.decode("utf-8")
    assert paprika.name_cs in body
    assert pepper.name_cs not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_search_filter(user_vlastnik, pepper, paprika) -> None:
    # Per 0063: `q` is a client-side filter — the server renders ALL rows
    # regardless of `q`, each carrying data-filter-text for the browser to
    # fold/match. (Folding/typo matching is verified in-browser.)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/?q={pepper.name_cs[:4]}")
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert paprika.name_cs in body
    assert f'data-filter-text="{pepper.name_cs}"' in body
    assert f'data-filter-text="{paprika.name_cs}"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_kind_filter(user_vlastnik) -> None:
    Product.objects.create(name_cs="Surovina", kind=Product.Kind.RAW_SPICE)
    Product.objects.create(name_cs="Směs", kind=Product.Kind.MIXTURE)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/?kind=mixture")
    body = response.content.decode("utf-8")
    assert "Směs" in body
    assert "Surovina" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_state_ok_filter(user_vlastnik, tyn) -> None:
    """?state=ok lists only rows that are neither low nor empty."""
    ok = Product.objects.create(
        name_cs="OK zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    low = Product.objects.create(
        name_cs="Dochazi zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    empty = Product.objects.create(
        name_cs="Prazdne zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    Stock.objects.create(product=ok, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=low, branch=tyn, quantity=Decimal("3.000"))
    Stock.objects.create(product=empty, branch=tyn, quantity=Decimal("0.000"))
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/?state=ok").content.decode("utf-8")
    assert ok.name_cs in body
    assert low.name_cs not in body
    assert empty.name_cs not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_kpis_reflect_state_filter(user_vlastnik, tyn) -> None:
    """The server KPI strip reflects the ?state= narrowing (combined with the
    other server filters), so the top numbers match the displayed rows — not
    the whole scope before state. Per 0084."""
    ok = Product.objects.create(
        name_cs="OK zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    low = Product.objects.create(
        name_cs="Dochazi zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    empty = Product.objects.create(
        name_cs="Prazdne zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    Stock.objects.create(product=ok, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=low, branch=tyn, quantity=Decimal("3.000"))
    Stock.objects.create(product=empty, branch=tyn, quantity=Decimal("0.000"))
    client = Client()
    client.force_login(user_vlastnik)
    # Whole scope: 3 products, 1 low, 1 empty.
    body = client.get("/sklad/katalog/").content.decode("utf-8")
    assert 'data-kpi-live="products">3</span>' in body
    # ?state=low → KPIs reflect only the low group (1 product, 1 low, 0 empty).
    low_body = client.get("/sklad/katalog/?state=low").content.decode("utf-8")
    assert 'data-kpi-live="products">1</span>' in low_body
    assert 'data-kpi-live="low">1</span>' in low_body
    assert 'data-kpi-live="empty">0</span>' in low_body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_renders_live_kpi_hooks(user_vlastnik, tyn) -> None:
    """Per 0084: the group tbodies carry data-filter-bucket, rows carry a
    dot-decimal data-filter-kg, and the KPI spans carry data-kpi-live — the
    server contract the live-recompute JS depends on."""
    ok = Product.objects.create(
        name_cs="OK zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    low = Product.objects.create(
        name_cs="Dochazi zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    empty = Product.objects.create(
        name_cs="Prazdne zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    Stock.objects.create(product=ok, branch=tyn, quantity=Decimal("10.000"))
    Stock.objects.create(product=low, branch=tyn, quantity=Decimal("3.000"))
    Stock.objects.create(product=empty, branch=tyn, quantity=Decimal("0.000"))
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/").content.decode("utf-8")
    assert 'data-filter-bucket="empty"' in body
    assert 'data-filter-bucket="low"' in body
    assert 'data-filter-bucket="ok"' in body
    # kg is dot-decimal (|unlocalize) so JS parseFloat works.
    assert 'data-filter-kg="10.000"' in body
    assert 'data-kpi-live="products"' in body
    assert 'data-kpi-live="total-kg"' in body


@pytest.mark.django_db
def test_new_product_defaults_threshold_zero(db) -> None:
    """Per 0072: a new product's reorder_threshold_kg defaults to 0 (not NULL)."""
    p = Product.objects.create(name_cs="Bez prahu", kind=Product.Kind.RAW_SPICE)
    p.refresh_from_db()
    assert p.reorder_threshold_kg == Decimal("0.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_zero_stock_product_groups_as_empty_without_threshold(
    user_vlastnik, tyn
) -> None:
    """Per 0072: a product at 0 kg with the default (0) threshold groups as
    "Prázdné" — the empty gate no longer requires a threshold to be set."""
    empty = Product.objects.create(
        name_cs="Prazdne bez prahu", kind=Product.Kind.RAW_SPICE
    )
    Stock.objects.create(product=empty, branch=tyn, quantity=Decimal("0.000"))
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/?state=empty").content.decode("utf-8")
    assert empty.name_cs in body
    # And it must NOT be considered "ok".
    ok_body = client.get("/sklad/katalog/?state=ok").content.decode("utf-8")
    assert empty.name_cs not in ok_body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_empty_group_shows_branch_chip_at_zero_threshold(
    user_vlastnik, tyn
) -> None:
    """Per 0091: a product empty on a branch (effective ≤ 0) at the default
    threshold 0 lists that branch in the „Prázdný na" column — the chip no
    longer requires effective < a nonzero threshold."""
    empty = Product.objects.create(
        name_cs="Prazdne na TYN", kind=Product.Kind.RAW_SPICE
    )
    Stock.objects.create(product=empty, branch=tyn, quantity=Decimal("0.000"))
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/?state=empty").content.decode("utf-8")
    assert '<span class="empty-branch">TYN</span>' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_shows_zero_threshold_not_dash(
    user_vlastnik, tyn, pepper
) -> None:
    """Per 0072: product detail shows the threshold value (0) rather than a
    dash, since the field is always set now."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("2.000"))
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{pepper.pk}/").content.decode("utf-8")
    assert "Objednací bod" in body
    # The default 0 renders as "0,0" (1 dp, Czech comma per 0061), not "—".
    assert "0,0" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_shows_total_kg_for_vlastnik(
    user_vlastnik, tyn, sez, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("3.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    body = response.content.decode("utf-8")
    # 11.5 → Czech "11,5" at 1 dp (per 0061)
    assert "11,5" in body
    # New (Pass 6) header "Na skladě" + scope hint over both branches.
    assert "Na skladě" in body
    # Copy updated per Podpora feedback #4 — N-branch ready.
    assert "všechny aktivní pobočky" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_shows_branch_kg_for_obsluha(
    user_obsluha_tyn, tyn, sez, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("99.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/")
    body = response.content.decode("utf-8")
    # Pass 6: scope hint replaces the column header for branch scoping.
    assert "pro pobočku" in body and "TYN" in body
    assert "8,0" in body
    assert "99,0" not in body and "99.0" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_marks_mixture_with_recipe(user_vlastnik, pepper) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/")
    body = response.content.decode("utf-8")
    assert mixture.name_cs in body
    assert "má recepturu" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_renders_for_raw_spice(
    user_vlastnik, tyn, sez, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("3.500"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert pepper.name_cs in body
    assert "8,0" in body
    assert "3,5" in body
    assert "11,5" in body
    # Recipe section absent for raw spice. Match the section heading
    # specifically — the per-page help panel (0078) mentions "Receptura" too.
    assert "Receptura</h2>" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_renders_recipe_for_mixture(
    user_vlastnik, pepper, paprika
) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("0.7")
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika, ratio=Decimal("0.3")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/")
    body = response.content.decode("utf-8")
    assert "Receptura" in body
    assert pepper.name_cs in body
    assert paprika.name_cs in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_recipe_scaler_ratio_has_dot_decimal(
    user_vlastnik, pepper
) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("0.5")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/")
    assert b'data-ratio="0.500000"' in response.content
    assert b'data-ratio="0,500000"' not in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_shows_mixing_notes_and_pdf_link(user_vlastnik, pepper) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření",
        kind=Product.Kind.MIXTURE,
        notes="BALIT Á 5 KG",
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{mixture.pk}/").content.decode("utf-8")
    assert "Poznámky k míchání" in body  # XLS notes surfaced with the recipe
    assert "BALIT Á 5 KG" in body
    assert f"/sklad/katalog/{mixture.pk}/receptura/pdf/" in body
    assert "Stáhnout recepturu" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_shows_component_note(user_vlastnik, pepper, paprika) -> None:
    """Per 0088: the per-component note renders in the mixture detail recipe
    table (PDF is binary, so we assert the detail page here)."""
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("0.7"), note="hrubě mletý",
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika,
        ratio=Decimal("0.3"), note="",
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{mixture.pk}/").content.decode("utf-8")
    assert "Poznámka" in body  # the new column header
    assert "hrubě mletý" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_raw_ingredient_detail_omits_component_note(user_vlastnik, pepper) -> None:
    """The note lives on the mixture's recipe table only — the raw
    ingredient's own page (its `used_in` table) must NOT show it (per 0088)."""
    mixture = Product.objects.create(
        name_cs="Směs X", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("1.0"), note="TAJNÁ POZNÁMKA",
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{pepper.pk}/").content.decode("utf-8")
    assert "TAJNÁ POZNÁMKA" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_scaler_seeds_from_default_batch(
    user_vlastnik, pepper
) -> None:
    """Per 0089: a mixture with default_batch_kg set (> 0) seeds the
    „Spočítat dávku" scaler with a dot value and shows the „Výchozí dávka" line."""
    mixture = Product.objects.create(
        name_cs="Gulášové koření",
        kind=Product.Kind.MIXTURE,
        default_batch_kg=Decimal("337.000"),
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{mixture.pk}/").content.decode("utf-8")
    assert 'id="recipe-scaler-target" value="337.0"' in body
    assert "Výchozí dávka" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_scaler_falls_back_to_ten_without_default(
    user_vlastnik, pepper
) -> None:
    """Per 0089: default_batch_kg=0 (the unset sentinel) → the scaler keeps
    its historic "10" default and the „Výchozí dávka" line is hidden."""
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{mixture.pk}/").content.decode("utf-8")
    assert 'id="recipe-scaler-target" value="10"' in body
    assert "Výchozí dávka" not in body


@pytest.mark.django_db
def test_product_form_exposes_default_batch_for_vlastnik() -> None:
    """Per 0089: the default-batch field is editable for a vlastník (the
    view passes can_edit_threshold=True)."""
    from inventory.forms import ProductForm

    form = ProductForm(can_edit_threshold=True)
    assert "default_batch_kg" in form.fields


@pytest.mark.django_db
def test_product_form_hides_default_batch_for_obsluha() -> None:
    """Per 0089: the field is popped for a non-vlastník so an obsluha POST
    can't null out a value an admin set (mirrors reorder_threshold_kg)."""
    from inventory.forms import ProductForm

    form = ProductForm(can_edit_threshold=False)
    assert "default_batch_kg" not in form.fields
    assert "reorder_threshold_kg" not in form.fields


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_excludes_untracked_product(user_vlastnik, pepper, voda) -> None:
    """Per 0088: an untracked product never appears in the Katalog and is not
    counted in the product KPI."""
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/").content.decode("utf-8")
    assert pepper.name_cs in body
    assert voda.name_cs not in body
    # KPI counts one product (pepper), not the untracked Voda.
    assert 'data-kpi-live="products">1</span>' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_pdf_download(user_vlastnik, pepper, paprika) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření",
        kind=Product.Kind.MIXTURE,
        notes="BALIT Á 5 KG\ndoba míchání 8 min",
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("0.7")
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika, ratio=Decimal("0.3")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/receptura/pdf/")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert "receptura-" in response.headers["Content-Disposition"]
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 1000


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_pdf_404_for_raw_spice(user_vlastnik, pepper) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/receptura/pdf/")
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_pdf_respects_qty(user_vlastnik, pepper, paprika) -> None:
    mixture = Product.objects.create(name_cs="Gulášové koření", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("0.7")
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika, ratio=Decimal("0.3")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/receptura/pdf/?qty=25")
    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"


def test_recipe_amounts_sum_exactly_to_total() -> None:
    """Largest-line rounding: % column sums to exactly 100, kg to the target —
    even for ratios whose naive per-row rounding drifts (Knedlík → 100.01)."""
    from inventory.services import _amounts_summing_to

    ratios = [Decimal("0.333333"), Decimal("0.333333"), Decimal("0.333334")]
    pcts = _amounts_summing_to(ratios, Decimal("100"), 2)
    assert sum(pcts, Decimal("0")) == Decimal("100.00")
    kgs = _amounts_summing_to(ratios, Decimal("25"), 3)
    assert sum(kgs, Decimal("0")) == Decimal("25.000")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_create_preselects_mixture_from_query(user_vlastnik, pepper) -> None:
    mixture = Product.objects.create(name_cs="Gulášové koření", kind=Product.Kind.MIXTURE)
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/michani/novy/?mixture={mixture.pk}").content.decode("utf-8")
    assert f'value="{mixture.pk}" selected' in body  # směs pre-selected from recipe page


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_shows_used_in_for_raw_spice(
    user_vlastnik, pepper
) -> None:
    mixture = Product.objects.create(
        name_cs="Gulášové koření", kind=Product.Kind.MIXTURE
    )
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper, ratio=Decimal("1.0")
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/")
    body = response.content.decode("utf-8")
    assert "Použito v směsích" in body
    assert mixture.name_cs in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_404_for_unknown(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/katalog/99999/")
    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_detail_obsluha_sees_only_own_branch_stock(
    user_obsluha_tyn, tyn, sez, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("8.000"))
    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("99.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(f"/sklad/katalog/{pepper.pk}/")
    body = response.content.decode("utf-8")
    assert "8,0" in body
    assert "99,0" not in body and "99.0" not in body


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Single-branch catalogue drops the "Prázdný na / Dochází na" branch column
# entirely (per 0079-adjacent sklad UX round: the column is pointless when only
# one branch is in scope — obsluha, or a vlastník who picked a branch).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_branch_column_hidden_for_obsluha_single_branch(
    user_obsluha_tyn, tyn
) -> None:
    low = Product.objects.create(
        name_cs="Dochazi zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    Stock.objects.create(product=low, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get("/sklad/katalog/").content.decode("utf-8")
    # The low group renders (the product is below threshold)…
    assert low.name_cs in body
    # …but the per-branch chip column header is gone in single-branch scope.
    assert "Dochází na" not in body
    assert "Prázdný na" not in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_branch_column_shown_for_vlastnik_all_branches(
    user_vlastnik, tyn
) -> None:
    low = Product.objects.create(
        name_cs="Dochazi zbozi", kind=Product.Kind.RAW_SPICE,
        reorder_threshold_kg=Decimal("5.000"),
    )
    Stock.objects.create(product=low, branch=tyn, quantity=Decimal("3.000"))
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get("/sklad/katalog/").content.decode("utf-8")
    assert low.name_cs in body
    # All-branches vlastník view keeps the per-branch chip column.
    assert "Dochází na" in body
