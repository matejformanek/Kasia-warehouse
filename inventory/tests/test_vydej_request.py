"""Auto-notify branch obsluha on a vlastník-issued výdej (per 0099).

When a vlastník / správce (owner-level, no branch) creates a customer výdej for
a branch, the branch's active obsluha are e-mailed a „žádost o vyřízení výdeje"
with a link to the dodák. Fires in a `transaction.on_commit` callback, so every
test needs `django_db(transaction=True)` (so `on_commit` actually fires) + the
locmem outbox override.

Outbox trap: `apply_movement` also fires the 0074 low-stock alert on commit, and
the autouse `settings_with_recipients` seeds a low-stock recipient. So every case
seeds `Stock` strictly above the výdej qty (no threshold crossing) and asserts on
the specific VYDEJ_REQUEST category, never bare `len(mail.outbox)`.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from django.test.utils import override_settings

from inventory.models import Customer, DodaciList, EmailLog, Movement, MovementLine
from inventory.services import apply_movement

from ._support import _VIEW_TEST_OVERRIDES


def _requests():
    """VYDEJ_REQUEST EmailLog rows in the DB."""
    return EmailLog.objects.filter(
        category=EmailLog.Category.VYDEJ_REQUEST
    )


def _alerts():
    """Low-stock alert e-mails in the outbox (subject carries 'Dochází')."""
    return [m for m in mail.outbox if "Dochází" in m.subject]


def _vydej(branch, customer, user, product, line_qty="2.000"):
    return apply_movement(
        movement=Movement(
            branch=branch,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 7, 5),
            odberatel=customer,
        ),
        lines=[MovementLine(product=product, quantity_kg=Decimal(line_qty))],
        user=user,
    )


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vlastnik_vydej_notifies_branch_obsluha(
    tyn, ricany, pepper, user_vlastnik, user_obsluha_tyn
):
    """Vlastník výdej for a branch that has obsluha → exactly one VYDEJ_REQUEST
    row (SENT) to the branch obsluha, with the dodák number + detail URL in the
    mail. The row is not linked to the dodák. No co-fired low-stock alert."""
    from inventory.models import Stock

    # Stock strictly above the výdej qty → no threshold crossing, no alert.
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))

    mv = _vydej(tyn, ricany, user_vlastnik, pepper, "2.000")
    dl = DodaciList.objects.get(movement=mv)

    reqs = _requests()
    assert reqs.count() == 1
    row = reqs.get()
    assert row.status == EmailLog.Status.SENT
    assert row.recipients == user_obsluha_tyn.email
    assert row.dodaci_list_id is None  # standalone — no phantom dodák version row

    # The mail itself.
    outbox_reqs = [m for m in mail.outbox if m.subject.startswith("Žádost o vyřízení")]
    assert len(outbox_reqs) == 1
    msg = outbox_reqs[0]
    assert msg.to == [user_obsluha_tyn.email]
    assert dl.cislo in msg.subject
    assert dl.cislo in msg.body
    assert f"/dodaky/{dl.cislo}/" in msg.body  # clickable absolute detail link

    # No low-stock alert co-fired (100 → 98, well above threshold 0).
    assert _alerts() == []


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_obsluha_vydej_on_own_branch_no_request(
    tyn, ricany, pepper, user_obsluha_tyn
):
    """An obsluha creating a výdej on their own branch is the fulfiller — no
    VYDEJ_REQUEST is sent."""
    from inventory.models import Stock

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))

    _vydej(tyn, ricany, user_obsluha_tyn, pepper, "2.000")

    assert _requests().count() == 0
    assert not any(m.subject.startswith("Žádost o vyřízení") for m in mail.outbox)


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vlastnik_vydej_branch_without_obsluha_no_mail(
    sez, ricany, pepper, user_vlastnik
):
    """Vlastník výdej for a branch (SEZ) that has no obsluha → nothing sent,
    nothing logged, no crash (defensive early-return)."""
    from inventory.models import Stock

    Stock.objects.create(product=pepper, branch=sez, quantity=Decimal("100.000"))

    _vydej(sez, ricany, user_vlastnik, pepper, "2.000")

    assert _requests().count() == 0
    assert not any(m.subject.startswith("Žádost o vyřízení") for m in mail.outbox)


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_internal_vydej_no_request(tyn, pepper, user_vlastnik, user_obsluha_tyn):
    """An internal výdej (odberatel=Míchárna) makes no dodák → no VYDEJ_REQUEST,
    even though the creator is a vlastník and the branch has obsluha."""
    from inventory.models import Stock

    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    micharna = Customer.objects.get(name="Míchárna", is_internal=True)

    _vydej(tyn, micharna, user_vlastnik, pepper, "2.000")

    assert _requests().count() == 0
    assert not any(m.subject.startswith("Žádost o vyřízení") for m in mail.outbox)
