"""Odběratel kontaktní e-maily (decision 0103): form handling + dodák sends."""

from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from inventory.forms import CustomerForm
from inventory.models import (
    Customer,
    DodaciList,
    EmailLog,
    Movement,
    MovementLine,
    Stock,
)
from inventory.services import apply_movement, edit_movement, send_first_dodaci
from inventory.tests._support import _LOCMEM_EMAIL, _VIEW_TEST_OVERRIDES

INTERNAL = {"petr@example.cz", "karolina@example.cz", "user-tyn@example.cz"}


def _post_data(emails, **extra):
    from django.http import QueryDict

    qd = QueryDict(mutable=True)
    qd.update({"name": extra.pop("name", "Hospůdka U Lípy"), "is_active": "on"})
    for k, v in extra.items():
        qd[k] = v
    qd.setlist("emails", emails)
    return qd


# Form ---------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("submitted", "expected"),
    [
        ([], []),
        ([""], []),
        (["a@example.cz"], ["a@example.cz"]),
        (
            ["a@example.cz", "b@example.cz", "c@example.cz"],
            ["a@example.cz", "b@example.cz", "c@example.cz"],
        ),
        # Blanks dropped, whitespace stripped, case-insensitive dupes → first spelling.
        (
            ["  Info@Example.cz ", "", "info@example.cz", "b@example.cz", "INFO@EXAMPLE.CZ"],
            ["Info@Example.cz", "b@example.cz"],
        ),
    ],
)
def test_customer_form_saves_emails(submitted, expected) -> None:
    form = CustomerForm(_post_data(submitted))
    assert form.is_valid(), form.errors
    cust = form.save()
    cust.refresh_from_db()
    assert cust.emails == expected


@pytest.mark.django_db
def test_customer_form_edit_replaces_emails() -> None:
    cust = Customer.objects.create(name="Bistro", emails=["old@example.cz", "keep@example.cz"])
    form = CustomerForm(
        _post_data(["keep@example.cz", "new@example.cz"], name="Bistro"), instance=cust
    )
    assert form.is_valid(), form.errors
    form.save()
    cust.refresh_from_db()
    assert cust.emails == ["keep@example.cz", "new@example.cz"]


@pytest.mark.django_db
def test_customer_form_rejects_invalid_email() -> None:
    form = CustomerForm(_post_data(["ok@example.cz", "not-an-email"]))
    assert not form.is_valid()
    assert "emails" in form.errors
    assert "not-an-email" in form.errors["emails"][0]
    assert "Neplatná e-mailová adresa" in form.errors["emails"][0]


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_create_view_rerenders_submitted_emails_on_error(user_obsluha_tyn) -> None:
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.post(
        reverse("inventory:customer_create"),
        # A plain dict with a list: the test client sends each value as a
        # repeated field (a QueryDict would only send the last one).
        {
            "name": "Hospůdka U Lípy",
            "is_active": "on",
            "emails": ["first@example.cz", "broken@", ""],
        },
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert 'value="first@example.cz"' in body
    assert 'value="broken@"' in body
    assert "Neplatná e-mailová adresa" in body
    assert not Customer.objects.filter(name="Hospůdka U Lípy").exists()


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_edit_page_renders_email_rows(user_obsluha_tyn) -> None:
    cust = Customer.objects.create(name="Bistro", emails=["a@example.cz", "b@example.cz"])
    client = Client()
    client.force_login(user_obsluha_tyn)
    response = client.get(reverse("inventory:customer_edit", kwargs={"pk": cust.pk}))
    assert response.status_code == 200
    body = response.content.decode()
    assert "{#" not in body and "#}" not in body
    assert body.count('name="emails"') == 3  # two saved rows + the <template> row
    assert 'value="a@example.cz"' in body
    assert 'value="b@example.cz"' in body
    assert 'id="customer-email-add-row"' in body
    assert "Na tyto adresy se posílá dodací list (PDF) při každém odeslání." in body
    assert "css/pages/customer_form.css" in body


@pytest.mark.django_db
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_customer_index_lists_emails(user_obsluha_tyn) -> None:
    Customer.objects.create(name="Bistro", emails=["a@example.cz", "b@example.cz"])
    client = Client()
    client.force_login(user_obsluha_tyn)
    body = client.get(reverse("inventory:customer_index")).content.decode()
    assert "a@example.cz, b@example.cz" in body
    assert 'data-filter-text="Bistro  a@example.cz b@example.cz"' in body


# Send paths ---------------------------------------------------------------


def _dodak(tyn, customer, user, product) -> DodaciList:
    Stock.objects.create(product=product, branch=tyn, quantity=Decimal("9.000"))
    mv = apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 9, 30),
            odberatel=customer,
        ),
        lines=[MovementLine(product=product, quantity_kg=Decimal("2.000"))],
        user=user,
    )
    return DodaciList.objects.get(movement=mv)


@pytest.fixture
def bistro(db) -> Customer:
    # Second address equals the issuer's in a different case → sent once.
    return Customer.objects.create(
        name="Bistro", emails=["objednavky@bistro.cz", "USER-TYN@example.cz"]
    )


def _assert_customer_recipients(log: EmailLog, msg) -> None:
    expected = INTERNAL | {"objednavky@bistro.cz"}
    assert set(msg.to) == expected
    assert len(msg.to) == len(expected)  # issuer not duplicated
    assert {r.strip() for r in log.recipients.split(",")} == expected


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_first_send_includes_customer_emails(tyn, bistro, pepper, user_tyn) -> None:
    dl = _dodak(tyn, bistro, user_tyn, pepper)
    log = send_first_dodaci(dl, sent_by=user_tyn)
    assert log.status == EmailLog.Status.SENT
    assert len(mail.outbox) == 1
    _assert_customer_recipients(log, mail.outbox[0])


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_resend_includes_customer_emails(tyn, bistro, pepper, user_tyn, user_vlastnik) -> None:
    dl = _dodak(tyn, bistro, user_tyn, pepper)
    send_first_dodaci(dl, sent_by=user_tyn)
    client = Client()
    client.force_login(user_vlastnik)
    response = client.post(reverse("inventory:dodaci_list_resend", kwargs={"cislo": dl.cislo}))
    assert response.status_code == 302
    assert len(mail.outbox) == 2
    log = EmailLog.objects.filter(dodaci_list=dl).order_by("-pk").first()
    assert log.trigger_reason == "ruční opětovné odeslání"
    _assert_customer_recipients(log, mail.outbox[-1])


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_oprava_includes_customer_emails(tyn, bistro, pepper, user_tyn) -> None:
    dl = _dodak(tyn, bistro, user_tyn, pepper)
    send_first_dodaci(dl, sent_by=user_tyn)
    mv = dl.movement
    line = mv.lines.get()
    edit_movement(
        movement=mv,
        changes={},
        line_changes=[
            {"op": "update", "line_id": line.pk, "fields": {"quantity_kg": Decimal("3.000")}}
        ],
        reason="oprava hmotnosti",
        user=user_tyn,
    )
    assert len(mail.outbox) == 2
    assert mail.outbox[-1].subject.startswith("[OPRAVA]")
    log = EmailLog.objects.get(dodaci_list=dl, dodaci_version=2)
    _assert_customer_recipients(log, mail.outbox[-1])


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
def test_customer_without_emails_sends_as_before(tyn, ricany, pepper, user_tyn) -> None:
    assert ricany.emails == []
    dl = _dodak(tyn, ricany, user_tyn, pepper)
    log = send_first_dodaci(dl, sent_by=user_tyn)
    assert set(mail.outbox[0].to) == INTERNAL
    assert len(mail.outbox[0].to) == 3
    assert {r.strip() for r in log.recipients.split(",")} == INTERNAL


@pytest.mark.django_db(transaction=True)
@override_settings(**_LOCMEM_EMAIL)
@pytest.mark.parametrize(
    ("bad", "extra"),
    [
        ("x@y.cz", set()),
        ({"a": 1}, set()),
        ([1, "a@b.cz", None, "  "], {"a@b.cz"}),
    ],
)
def test_bad_stored_emails_still_send_to_internal(tyn, pepper, user_tyn, bad, extra) -> None:
    cust = Customer.objects.create(name="Bistro", emails=bad)
    dl = _dodak(tyn, cust, user_tyn, pepper)
    log = send_first_dodaci(dl, sent_by=user_tyn)
    assert log.status == EmailLog.Status.SENT
    assert set(mail.outbox[0].to) == INTERNAL | extra
