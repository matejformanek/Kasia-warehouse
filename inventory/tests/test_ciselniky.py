from datetime import date
from decimal import Decimal

import pytest
from django.test import Client, override_settings

from inventory.models import (
    Customer,
    DodaciList,
    DodaciListNumberSequence,
    Movement,
    Product,
    RecipeComponent,
    Stock,
)
from inventory.tests._support import (
    _VIEW_TEST_OVERRIDES,
)

# Pass 5 — Supplier + Customer CRUD (per decision 0040)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_index_requires_login() -> None:
    response = Client().get("/sklad/dodavatele/")
    assert response.status_code == 302
    assert "/sklad/prihlaseni/" in response["Location"]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_index_renders_for_obsluha(user_obsluha_tyn, supplier) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/dodavatele/")
    assert response.status_code == 200
    assert supplier.name.encode() in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_index_hides_internal(user_obsluha_tyn) -> None:
    from inventory.models import Supplier as Sup

    Sup.objects.create(name="Visible Dodavatel")
    # The "Míchárna" internal supplier was seeded; verify it doesn't show.
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/dodavatele/")
    assert b"Visible Dodavatel" in response.content
    assert b"M\xc3\xadch\xc3\xa1rna" not in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_create_by_obsluha(user_obsluha_tyn) -> None:
    from inventory.models import Supplier as Sup

    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/dodavatele/novy/",
        {
            "name": "Nový Dodavatel s.r.o.",
            "ico": "12345678",
            "address": "Praha 5",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    sup = Sup.objects.get(name="Nový Dodavatel s.r.o.")
    assert sup.ico == "12345678"
    assert sup.is_active is True
    assert sup.is_internal is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_create_rejects_duplicate_name(user_vlastnik, supplier) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/dodavatele/novy/",
        {"name": supplier.name, "is_active": "on"},
    )
    assert response.status_code == 200
    assert (
        b"Aktivn\xc3\xad dodavatel s t\xc3\xadmto n\xc3\xa1zvem u\xc5\xbe existuje"
        in response.content
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_edit_updates_fields(user_vlastnik, supplier) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/dodavatele/{supplier.pk}/upravit/",
        {
            "name": supplier.name,
            "ico": "99887766",
            "address": "Brno",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    supplier.refresh_from_db()
    assert supplier.ico == "99887766"
    assert supplier.address == "Brno"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_archive(user_obsluha_tyn, supplier) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/dodavatele/{supplier.pk}/archivovat/")
    assert response.status_code == 302
    supplier.refresh_from_db()
    assert supplier.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_archive_internal_refused(user_vlastnik) -> None:
    from inventory.models import Supplier as Sup

    micharna = Sup.objects.get(name="Míchárna", is_internal=True)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/dodavatele/{micharna.pk}/archivovat/", follow=True
    )
    assert response.status_code == 200
    micharna.refresh_from_db()
    assert micharna.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_supplier_reactivate(user_obsluha_tyn) -> None:
    from inventory.models import Supplier as Sup

    sup = Sup.objects.create(name="Archivovaný", is_active=False)
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/dodavatele/{sup.pk}/aktivovat/")
    assert response.status_code == 302
    sup.refresh_from_db()
    assert sup.is_active is True


# Customer ----------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_index_requires_login() -> None:
    response = Client().get("/sklad/odberatele/")
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_index_renders_for_obsluha(user_obsluha_tyn, ricany) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/odberatele/")
    assert response.status_code == 200
    assert b"\xc5\x98\xc3\xad\xc4\x8dany" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_index_hides_internal(user_obsluha_tyn) -> None:
    """Internal Míchárna customer is hidden from the operator list."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/odberatele/")
    assert response.status_code == 200
    assert b"M\xc3\xadch\xc3\xa1rna" not in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_create_by_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/odberatele/novy/",
        {
            "name": "Hospůdka U Lípy",
            "ico": "11223344",
            "dic": "CZ11223344",
            "address": "Hradec Králové",
            "email": "ulipy@example.cz",
            "phone": "+420 111 222 333",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    cust = Customer.objects.get(name="Hospůdka U Lípy")
    assert cust.email == "ulipy@example.cz"
    assert cust.is_default_recipient is False  # not flipped by operator


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_archive_refused_for_default_recipient(
    user_vlastnik, ricany
) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/odberatele/{ricany.pk}/archivovat/", follow=True
    )
    assert response.status_code == 200
    ricany.refresh_from_db()
    assert ricany.is_active is True
    assert ricany.is_default_recipient is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_archive(user_obsluha_tyn) -> None:
    cust = Customer.objects.create(name="Půjčující odběratel")
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/odberatele/{cust.pk}/archivovat/")
    assert response.status_code == 302
    cust.refresh_from_db()
    assert cust.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_supplier_customer_links_visible_to_all(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    assert response.status_code == 200
    assert b"Dodavatel" in response.content
    assert b"Odb\xc4\x9bratel" in response.content


# ---------------------------------------------------------------------------
# Pass 5b — Product + Recipe CRUD (per decision 0040)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_requires_login() -> None:
    response = Client().get("/sklad/katalog/novy/")
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_by_obsluha(user_obsluha_tyn) -> None:
    """Per 0040: workers can add a new product."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/katalog/novy/",
        {
            "name_cs": "Tymián",
            "kind": "raw_spice",
            "notes": "Nově převzato od dodavatele.",
        },
    )
    assert response.status_code == 302
    p = Product.objects.get(name_cs="Tymián")
    assert p.kind == "raw_spice"
    assert p.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_redirects_vlastnik_into_recipe_edit_for_mixtures(
    user_vlastnik,
) -> None:
    """When a vlastník creates a mixture, redirect to the edit form so
    they can add components immediately."""
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/katalog/novy/",
        {"name_cs": "Nová směs", "kind": "mixture"},
    )
    p = Product.objects.get(name_cs="Nová směs")
    assert response.status_code == 302
    assert response["Location"].endswith(f"/sklad/katalog/{p.pk}/upravit/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_obsluha_mixture_lands_on_detail(user_obsluha_tyn) -> None:
    """Obsluha can create a mixture but doesn't get redirected into
    recipe edit (they can't edit recipes per 0040)."""
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/katalog/novy/",
        {"name_cs": "Směs B", "kind": "mixture"},
    )
    p = Product.objects.get(name_cs="Směs B")
    assert response.status_code == 302
    assert response["Location"].endswith(f"/sklad/katalog/{p.pk}/")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_create_rejects_duplicate_name(user_obsluha_tyn, pepper) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        "/sklad/katalog/novy/",
        {"name_cs": pepper.name_cs, "kind": "raw_spice"},
    )
    assert response.status_code == 200
    assert (
        b"Aktivn\xc3\xad produkt s t\xc3\xadmto n\xc3\xa1zvem u\xc5\xbe existuje"
        in response.content
    )


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_edit_updates_name(user_obsluha_tyn, pepper) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/upravit/",
        {
            "name_cs": "Pepř (přejmenovaný)",
            "kind": "raw_spice",
            "notes": "",
            # No recipe formset — obsluha can't edit recipe; template won't render it.
        },
    )
    assert response.status_code == 302
    pepper.refresh_from_db()
    assert pepper.name_cs == "Pepř (přejmenovaný)"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_edit_locks_kind_when_stock_exists(
    user_vlastnik, pepper, tyn
) -> None:
    """Kind field is disabled once Stock or RecipeComponent references exist."""
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.000"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{pepper.pk}/upravit/")
    assert response.status_code == 200
    assert b"Typ produktu je zam\xc4\x8den\xc3\xbd" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_archive_vlastnik_only(user_obsluha_tyn, pepper) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(f"/sklad/katalog/{pepper.pk}/archivovat/")
    assert response.status_code == 403
    pepper.refresh_from_db()
    assert pepper.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_archive_by_vlastnik(user_vlastnik, pepper) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(f"/sklad/katalog/{pepper.pk}/archivovat/")
    assert response.status_code == 302
    pepper.refresh_from_db()
    assert pepper.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_reactivate_blocks_name_collision(
    user_vlastnik, pepper
) -> None:
    """Can't re-activate when another active product has the same name."""
    pepper.is_active = False
    pepper.save()
    Product.objects.create(name_cs=pepper.name_cs, kind=pepper.kind)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{pepper.pk}/aktivovat/", follow=True
    )
    assert response.status_code == 200
    pepper.refresh_from_db()
    assert pepper.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_visible_only_to_vlastnik(
    user_vlastnik, user_obsluha_tyn, pepper, paprika
) -> None:
    """Recipe formset is rendered only when can_edit_recipe = True."""
    mixture = Product.objects.create(name_cs="Směs X", kind="mixture")
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("0.500"),
    )
    # As vlastník — should see recipe section.
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get(f"/sklad/katalog/{mixture.pk}/upravit/")
    assert response.status_code == 200
    assert b"Receptura" in response.content
    assert b"recipe-TOTAL_FORMS" in response.content
    # As obsluha — recipe section hidden (mixture's recipe is vlastník-only).
    client2 = Client()
    client2.force_login(user_obsluha_tyn)
    response2 = client2.get(f"/sklad/katalog/{mixture.pk}/upravit/")
    assert response2.status_code == 200
    assert b"recipe-TOTAL_FORMS" not in response2.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_saves_changes(user_vlastnik, pepper, paprika) -> None:
    """Vlastník can change ratio of an existing recipe row."""
    mixture = Product.objects.create(name_cs="Směs Y", kind="mixture")
    rc = RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("0.300"),
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{mixture.pk}/upravit/",
        {
            "name_cs": mixture.name_cs,
            "kind": "mixture",
            "notes": "",
            "recipe-TOTAL_FORMS": "1",
            "recipe-INITIAL_FORMS": "1",
            "recipe-MIN_NUM_FORMS": "0",
            "recipe-MAX_NUM_FORMS": "1000",
            "recipe-0-id": str(rc.pk),
            "recipe-0-component_product": str(pepper.pk),
            "recipe-0-ratio": "0.700",
            "threshold-TOTAL_FORMS": "0",
            "threshold-INITIAL_FORMS": "0",
            "threshold-MIN_NUM_FORMS": "0",
            "threshold-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 302
    rc.refresh_from_db()
    assert rc.ratio == Decimal("0.700")


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_product_form_renders_default_batch_for_vlastnik(
    user_vlastnik, user_obsluha_tyn
) -> None:
    """Per 0089: the „Výchozí dávka" field is actually rendered on the
    create + edit form for a vlastník, and hidden for obsluha. (0089 added it
    to the form object but the template — which renders fields explicitly —
    initially omitted it; this guards the render.)"""
    mixture = Product.objects.create(
        name_cs="Směs D", kind="mixture", default_batch_kg=Decimal("337.000")
    )
    client = Client()
    client.force_login(user_vlastnik)
    # create form
    create_body = client.get("/sklad/katalog/novy/").content.decode("utf-8")
    assert 'name="default_batch_kg"' in create_body
    assert "Výchozí dávka" in create_body
    # edit form — value prefilled (dot decimal, safe for a number input)
    edit_body = client.get(
        f"/sklad/katalog/{mixture.pk}/upravit/"
    ).content.decode("utf-8")
    assert 'name="default_batch_kg"' in edit_body
    assert 'value="337.000"' in edit_body
    # obsluha never sees the field
    client2 = Client()
    client2.force_login(user_obsluha_tyn)
    obsluha_body = client2.get("/sklad/katalog/novy/").content.decode("utf-8")
    assert 'name="default_batch_kg"' not in obsluha_body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_renders_note_column(user_vlastnik, pepper) -> None:
    """Per 0090: the recipe formset exposes an editable „Poznámka" column."""
    mixture = Product.objects.create(name_cs="Směs P", kind="mixture")
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("1.000"), note="hrubě mletý",
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{mixture.pk}/upravit/").content.decode("utf-8")
    assert "Poznámka" in body
    assert 'name="recipe-0-note"' in body
    assert "hrubě mletý" in body  # existing note prefilled into the input


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_saves_component_note(user_vlastnik, pepper) -> None:
    """Per 0090: a note typed on the operator recipe formset is persisted."""
    mixture = Product.objects.create(name_cs="Směs Q", kind="mixture")
    rc = RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("1.000"), note="",
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{mixture.pk}/upravit/",
        {
            "name_cs": mixture.name_cs,
            "kind": "mixture",
            "notes": "",
            "recipe-TOTAL_FORMS": "1",
            "recipe-INITIAL_FORMS": "1",
            "recipe-MIN_NUM_FORMS": "0",
            "recipe-MAX_NUM_FORMS": "1000",
            "recipe-0-id": str(rc.pk),
            "recipe-0-component_product": str(pepper.pk),
            "recipe-0-ratio": "1.000",
            "recipe-0-note": "navážit přesně",
            "threshold-TOTAL_FORMS": "0",
            "threshold-INITIAL_FORMS": "0",
            "threshold-MIN_NUM_FORMS": "0",
            "threshold-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 302
    rc.refresh_from_db()
    assert rc.note == "navážit přesně"


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_catalogue_has_new_product_button(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/katalog/")
    assert response.status_code == 200
    assert b"Nov\xc3\xbd produkt" in response.content


# ---------------------------------------------------------------------------
# Pass 5c — Branch CRUD (per decision 0040, vlastník-only)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_index_requires_login() -> None:
    response = Client().get("/sklad/pobocky/")
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_index_forbidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocky/")
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_index_renders_for_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pobocky/")
    assert response.status_code == 200
    assert b"TYN" in response.content
    assert b"SEZ" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_create_by_vlastnik(user_vlastnik) -> None:
    from inventory.models import Branch as B

    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/pobocky/novy/",
        {
            "code": "prh",  # lower-case input; clean_code uppercases
            "name": "Praha (sklad)",
            "address": "Praha 5",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    new_branch = B.objects.get(code="PRH")
    assert new_branch.name == "Praha (sklad)"
    assert new_branch.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_create_rejects_invalid_code(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/pobocky/novy/",
        {"code": "TY", "name": "Test", "address": "", "is_active": "on"},
    )
    assert response.status_code == 200
    assert b"3 p\xc3\xadsmena" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_create_rejects_duplicate_code(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/pobocky/novy/",
        {"code": "TYN", "name": "Dup", "address": "", "is_active": "on"},
    )
    assert response.status_code == 200
    assert b"s t\xc3\xadmto k\xc3\xb3dem u\xc5\xbe existuje" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_edit_locks_code_after_first_dodak(
    user_vlastnik, tyn
) -> None:
    """Per 0008, the code is part of dodák number — locked once issued."""


    # Synthesise a dodák for TYN so the gate triggers.
    DodaciListNumberSequence.objects.create(
        branch=tyn, year=date.today().year, last_counter=1
    )
    # No movement required for the gate — _branch_code_locked looks at
    # DodaciList table directly.
    # Create a placeholder movement so the dodák FK is valid.
    mv = Movement.objects.create(
        branch=tyn,
        kind=Movement.Kind.VYDEJ,
        odberatel=Customer.objects.get(is_default_recipient=True),
        date_issued=date.today(),
        note="",
        created_by=user_vlastnik,
    )
    DodaciList.objects.create(
        movement=mv,
        branch=tyn,
        odberatel=mv.odberatel,
        date_issued=date.today(),
        year_issued=date.today().year,
        counter=1,
        cislo=f"TYN-{date.today().year}-0001",
        current_version=1,
        created_by=user_vlastnik,
    )

    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/pobocky/TYN/upravit/")
    assert response.status_code == 200
    assert b"K\xc3\xb3d je zam\xc4\x8den\xc3\xbd" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_archive_refuses_with_stock(
    user_vlastnik, tyn, pepper
) -> None:
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("1.0"))
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        "/sklad/pobocky/TYN/archivovat/", follow=True
    )
    assert response.status_code == 200
    tyn.refresh_from_db()
    assert tyn.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_archive_refuses_with_active_users(
    user_vlastnik, sez
) -> None:
    """SEZ has obsluha-sez user (autouse seed) — archive should refuse."""
    from accounts.models import User as UserModel
    # Ensure at least one active user is on SEZ.
    UserModel.objects.create_user(
        email="sez-active@example.cz", password="x" * 12, branch=sez
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post("/sklad/pobocky/SEZ/archivovat/", follow=True)
    assert response.status_code == 200
    sez.refresh_from_db()
    assert sez.is_active is True


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_branch_archive_succeeds_when_clean(user_vlastnik) -> None:
    """A branch with no stock + no active users can be archived."""
    from inventory.models import Branch as B
    new_branch = B.objects.create(code="ZZZ", name="Test", is_active=True)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/pobocky/{new_branch.code}/archivovat/", follow=True
    )
    assert response.status_code == 200
    new_branch.refresh_from_db()
    assert new_branch.is_active is False


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_pobocky_link_visible_to_vlastnik(user_vlastnik) -> None:
    client = Client()
    client.force_login(user_vlastnik)
    response = client.get("/sklad/")
    assert response.status_code == 200
    assert b"Pobo\xc4\x8dky" in response.content


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_nav_pobocky_link_hidden_for_obsluha(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get("/sklad/pobocka/TYN/")
    assert response.status_code == 200
    # The text "Pobočky" must not appear as a nav anchor for obsluha.
    # The branch dashboard h1 might have "pobočka" — sanity check on
    # the /pobocky/ URL not appearing in the anchors.
    assert b'href="/sklad/pobocky/"' not in response.content


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Recipe component mixing order (per 0092)
# ---------------------------------------------------------------------------


def _recipe_edit_payload(mixture, rows):
    """Base POST payload for product_edit with `rows` recipe form dicts."""
    payload = {
        "name_cs": mixture.name_cs,
        "kind": "mixture",
        "notes": "",
        "recipe-TOTAL_FORMS": str(len(rows)),
        "recipe-INITIAL_FORMS": str(len(rows)),
        "recipe-MIN_NUM_FORMS": "0",
        "recipe-MAX_NUM_FORMS": "1000",
        "threshold-TOTAL_FORMS": "0",
        "threshold-INITIAL_FORMS": "0",
        "threshold-MIN_NUM_FORMS": "0",
        "threshold-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        for key, value in row.items():
            payload[f"recipe-{i}-{key}"] = value
    return payload


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_renders_move_buttons_and_position(
    user_vlastnik, pepper
) -> None:
    """Per 0092: the formset row carries the hidden position input and the
    ↑/↓ move buttons (the .row-move-btn locked hook)."""
    mixture = Product.objects.create(name_cs="Směs R", kind="mixture")
    RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("1.000"), position=0,
    )
    client = Client()
    client.force_login(user_vlastnik)
    body = client.get(f"/sklad/katalog/{mixture.pk}/upravit/").content.decode("utf-8")
    assert 'name="recipe-0-position"' in body
    assert 'class="row-move-btn"' in body
    assert 'data-dir="up"' in body
    assert 'data-dir="down"' in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_reorder_persists(user_vlastnik, pepper, paprika) -> None:
    """Per 0092: swapped position values on the POST persist — including on
    rows whose OTHER fields are unchanged (the save loop must not rely on
    save(commit=False)'s changed-only return)."""
    mixture = Product.objects.create(name_cs="Směs S", kind="mixture")
    rc_pepper = RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("0.600"), position=0,
    )
    rc_paprika = RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika,
        ratio=Decimal("0.400"), position=1,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{mixture.pk}/upravit/",
        _recipe_edit_payload(
            mixture,
            [
                {
                    "id": str(rc_pepper.pk),
                    "component_product": str(pepper.pk),
                    "ratio": "0.600",
                    "position": "1",
                },
                {
                    "id": str(rc_paprika.pk),
                    "component_product": str(paprika.pk),
                    "ratio": "0.400",
                    "position": "0",
                },
            ],
        ),
    )
    assert response.status_code == 302
    rc_pepper.refresh_from_db()
    rc_paprika.refresh_from_db()
    assert rc_paprika.position == 0
    assert rc_pepper.position == 1


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_recipe_edit_without_position_falls_back_to_form_order(
    user_vlastnik, pepper, paprika
) -> None:
    """Per 0092: the hidden position field is lenient (required=False) — a
    POST without it (old payload shape / no-JS) still saves, positions
    normalized dense 0..n-1 by form index."""
    mixture = Product.objects.create(name_cs="Směs T", kind="mixture")
    rc_pepper = RecipeComponent.objects.create(
        mixture_product=mixture, component_product=pepper,
        ratio=Decimal("0.600"), position=5,
    )
    rc_paprika = RecipeComponent.objects.create(
        mixture_product=mixture, component_product=paprika,
        ratio=Decimal("0.400"), position=7,
    )
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(
        f"/sklad/katalog/{mixture.pk}/upravit/",
        _recipe_edit_payload(
            mixture,
            [
                {
                    "id": str(rc_pepper.pk),
                    "component_product": str(pepper.pk),
                    "ratio": "0.600",
                },
                {
                    "id": str(rc_paprika.pk),
                    "component_product": str(paprika.pk),
                    "ratio": "0.400",
                },
            ],
        ),
    )
    assert response.status_code == 302
    rc_pepper.refresh_from_db()
    rc_paprika.refresh_from_db()
    # Formset queryset order is (position, id) → pepper (5) before paprika
    # (7); form index fallback keeps that order, renumbered densely.
    assert rc_pepper.position == 0
    assert rc_paprika.position == 1
