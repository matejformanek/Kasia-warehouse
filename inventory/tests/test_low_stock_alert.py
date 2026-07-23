"""Event-driven low-stock alert e-mail (per 0074).

The alert fires the moment a stock movement pushes a (product, branch) pair
into the Katalog "Dochází"/"Prázdné" state when it wasn't there before. It runs
in a `transaction.on_commit` callback, so every test needs
`django_db(transaction=True)` (so `on_commit` actually fires) + the locmem
outbox override.

The conftest autouse fixture seeds Petr (is_low_stock_recipient=True) and
Karolína (False), so the alert (unlike the dodák, which goes to all active
recipients) reaches Petr only. Alerts are distinguished from dodák e-mails by
the "Dochází" subject (default `Settings.template_low_stock_subject`).
"""

from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from django.test.utils import override_settings

from inventory.models import Movement, MovementLine, SettingsRecipient, Stock
from inventory.services import apply_movement, apply_stock_adjustment, start_mixing_job

from ._support import _VIEW_TEST_OVERRIDES, _mk_mixture_with_recipe


def _alerts():
    """The low-stock alert e-mails in the outbox (subject carries 'Dochází')."""
    return [m for m in mail.outbox if "Dochází" in m.subject]


def _vydej(branch, customer, user, product, line_qty):
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
def test_vydej_crossing_below_positive_threshold_alerts(tyn, ricany, pepper, user_tyn):
    """Výdej taking effective from above→below a positive threshold sends the
    alert (to Petr only). Per 0096 the dodák no longer auto-sends at výdej, so
    the alert is the only e-mail."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("6.000"))

    _vydej(tyn, ricany, user_tyn, pepper, "2.000")  # 6 → 4, crosses below 5

    # Only the low-stock alert — no dodák e-mail at výdej anymore (0096).
    assert len(mail.outbox) == 1
    alerts = _alerts()
    assert len(alerts) == 1
    assert alerts[0].to == ["petr@example.cz"]  # Karolína not subscribed
    assert "karolina@example.cz" not in alerts[0].to
    assert pepper.name_cs in alerts[0].body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_vydej_staying_above_threshold_no_alert(tyn, ricany, pepper, user_tyn):
    """Výdej that leaves effective ≥ threshold → no alert (and no dodák e-mail
    at výdej per 0096) → empty outbox."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))

    _vydej(tyn, ricany, user_tyn, pepper, "3.000")  # 10 → 7, still ≥ 5

    assert len(mail.outbox) == 0  # no alert, no dodák e-mail (0096)
    assert _alerts() == []


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_already_below_further_vydej_no_new_alert(tyn, ricany, pepper, user_tyn):
    """A product already below threshold that drops further does NOT re-alert."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("3.000"))

    _vydej(tyn, ricany, user_tyn, pepper, "1.000")  # 3 → 2, already below before

    assert len(mail.outbox) == 0  # no re-alert, no dodák e-mail (0096)
    assert _alerts() == []


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_zero_threshold_taken_to_exactly_zero_alerts(tyn, ricany, pepper, user_tyn):
    """Threshold 0, stock taken to exactly 0 → alert fires (Prázdné case)."""
    assert pepper.reorder_threshold_kg == Decimal("0.000")  # default
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("5.000"))

    _vydej(tyn, ricany, user_tyn, pepper, "5.000")  # 5 → 0, effective ≤ 0

    assert len(_alerts()) == 1


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_two_products_crossing_in_one_movement_single_alert(
    tyn, ricany, pepper, paprika, user_tyn
):
    """Two products crossing below in one výdej → one alert listing both."""
    for p in (pepper, paprika):
        p.reorder_threshold_kg = Decimal("5.000")
        p.save()
        Stock.objects.create(product=p, branch=tyn, quantity=Decimal("6.000"))

    apply_movement(
        movement=Movement(
            branch=tyn,
            kind=Movement.Kind.VYDEJ,
            date_issued=date(2026, 7, 5),
            odberatel=ricany,
        ),
        lines=[
            MovementLine(product=pepper, quantity_kg=Decimal("2.000")),
            MovementLine(product=paprika, quantity_kg=Decimal("2.000")),
        ],
        user=user_tyn,
    )

    alerts = _alerts()
    assert len(alerts) == 1
    assert pepper.name_cs in alerts[0].body
    assert paprika.name_cs in alerts[0].body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_down_adjustment_crossing_alerts(tyn, pepper, user_vlastnik):
    """A stock-down inventura adjustment crossing below threshold → alert
    (internal counterparty → no dodák, so the alert is the only e-mail)."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))

    apply_stock_adjustment(
        product=pepper,
        branch=tyn,
        new_quantity=Decimal("1.000"),  # 10 → 1, crosses below 5
        reason="inventura",
        user=user_vlastnik,
    )

    assert len(mail.outbox) == 1
    assert len(_alerts()) == 1


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_stock_up_adjustment_no_alert(tyn, pepper, user_vlastnik):
    """A stock-up adjustment cannot cross into the alert set → no alert."""
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))

    apply_stock_adjustment(
        product=pepper,
        branch=tyn,
        new_quantity=Decimal("12.000"),  # 10 → 12, still ≥ 5
        reason="inventura",
        user=user_vlastnik,
    )

    assert mail.outbox == []


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_consume_crossing_component_alerts(tyn, pepper, user_vlastnik):
    """Mixing consume (internal výdej via apply_movement) crossing a component
    below its threshold → alert, even though the dodák is skipped."""
    pepper.reorder_threshold_kg = Decimal("8.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("10.000"))
    mixture = _mk_mixture_with_recipe(components=[(pepper, "1.0")])

    start_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("5.000"),  # consume 5 kg pepper → 5 < 8
        user=user_vlastnik,
    )

    assert len(mail.outbox) == 1  # no dodák (internal), just the alert
    alerts = _alerts()
    assert len(alerts) == 1
    assert pepper.name_cs in alerts[0].body


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_mixing_untracked_component_never_alerts(tyn, pepper, voda, user_vlastnik):
    """An untracked component (per 0088) with a would-be-critical threshold
    never triggers a low-stock alert: it produces no consume line and is
    filtered out of the alert-pair set. The tracked component here keeps plenty
    of stock, so the whole mix sends zero alerts."""
    voda.reorder_threshold_kg = Decimal("100.000")
    voda.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("100.000"))
    mixture = _mk_mixture_with_recipe(components=[(pepper, "0.5"), (voda, "0.5")])

    start_mixing_job(
        branch=tyn,
        mixture=mixture,
        target_qty=Decimal("10.000"),  # pepper 5 of 100 → no cross
        user=user_vlastnik,
    )

    assert _alerts() == []
    assert not any(voda.name_cs in m.body for m in mail.outbox)


@pytest.mark.django_db(transaction=True)
@override_settings(**_VIEW_TEST_OVERRIDES)
def test_no_low_stock_subscriber_no_alert_no_error(tyn, ricany, pepper, user_tyn):
    """No is_low_stock_recipient=True subscriber → the crossing sends no alert
    and raises no error. Per 0096 the dodák doesn't auto-send → empty outbox."""
    SettingsRecipient.objects.update(is_low_stock_recipient=False)
    pepper.reorder_threshold_kg = Decimal("5.000")
    pepper.save()
    Stock.objects.create(product=pepper, branch=tyn, quantity=Decimal("6.000"))

    _vydej(tyn, ricany, user_tyn, pepper, "2.000")  # crosses below, but no subscriber

    assert _alerts() == []
    assert len(mail.outbox) == 0  # no alert, no dodák e-mail (0096)
