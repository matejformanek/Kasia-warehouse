"""Seed realistic-looking historical data for the local walkthrough.

Idempotent up to the catalogue + accounts seeding (uses get_or_create).
Movement seeding only runs when no Movement rows exist — re-running on a
populated DB is a no-op.

DEBUG=1 required: this is dev-only convenience, not production data.

Creates:
- Demo users (vlastník + 2× obsluha) with a known password
- Suppliers + customers (incl. one external customer for dodáky)
- 5 raw spices + 1 mixture with a recipe
- Initial stock at TYN + SEZ via real příjem Movements
- A handful of výdeje (mix of Říčany + externí — dodáky generated)
- One edited výdej to demo current_version=2 + [OPRAVA] flow
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from inventory.models import (
    Branch,
    Customer,
    MixingJob,
    Movement,
    MovementLine,
    PlannedTransfer,
    Product,
    RecipeComponent,
    Settings,
    Supplier,
)
from inventory.services import apply_movement, edit_movement, plan_mixing_job

User = get_user_model()


class Command(BaseCommand):
    help = "Seed walkthrough data for local dev (DEBUG only)."

    def handle(self, *args, **options) -> None:
        if not django_settings.DEBUG:
            raise CommandError(
                "Refusing to seed walkthrough data with DEBUG=False."
            )

        self.stdout.write("=== Seeding walkthrough data ===")

        # --- Settings + users + catalogue (idempotent) ---------------
        # Sender must be a REAL @kasia.cz address, not a fake .local one, or
        # every outgoing mail (credentials, password reset, dodák) is accepted
        # by the relay but dropped by the recipient (SPF/DKIM). Default to the
        # authenticated SMTP account (EMAIL_HOST_USER) so a freshly-seeded dev DB
        # actually delivers; fall back to the app address. Per 0083.
        s = Settings.load()
        s.email_from_address = (
            django_settings.EMAIL_HOST_USER or "aplikace@kasia.cz"
        )
        s.email_from_name = "Kasia vera"
        s.save()

        # Seed SettingsRecipient pair per 0052 (idempotent — uses
        # get_or_create on the email column).
        from inventory.models import SettingsRecipient

        SettingsRecipient.objects.get_or_create(
            email="petr@kasia.local",
            defaults={
                "label": "Petr",
                "is_active": True,
                "is_low_stock_recipient": True,
                "sort_order": 0,
            },
        )
        SettingsRecipient.objects.get_or_create(
            email="karolina@kasia.local",
            defaults={
                "label": "Karolína",
                "is_active": True,
                "is_low_stock_recipient": False,
                "sort_order": 1,
            },
        )
        self.stdout.write("• Settings recipients filled.")

        tyn = Branch.objects.get(code="TYN")
        sez = Branch.objects.get(code="SEZ")
        obsluha_group, _ = Group.objects.get_or_create(name="obsluha")

        karolina, _ = User.objects.get_or_create(
            email="karolina@kasia.local",
            defaults={"first_name": "Karolína", "last_name": "Formánková"},
        )
        karolina.set_password("heslo1234")
        karolina.save()

        for email, fname, lname, branch in [
            ("tyn@kasia.local", "Eva", "Týnišťská", tyn),
            ("sez@kasia.local", "Pavel", "Sezimovský", sez),
        ]:
            u, _ = User.objects.get_or_create(
                email=email,
                defaults={"first_name": fname, "last_name": lname, "branch": branch},
            )
            u.set_password("heslo1234")
            u.branch = branch
            u.save()
            u.groups.add(obsluha_group)
        self.stdout.write("• Users seeded.")

        supplier, _ = Supplier.objects.get_or_create(
            name="Koření CZ s.r.o.",
            defaults={"address": "Praha"},
        )
        zak1, _ = Customer.objects.get_or_create(
            name="Hospůdka U Lípy",
            defaults={"address": "Hradec Králové"},
        )
        zak2, _ = Customer.objects.get_or_create(
            name="Restaurace Na Růžku",
            defaults={"address": "Brno"},
        )
        ricany = Customer.objects.get(is_default_recipient=True)
        self.stdout.write("• Suppliers + customers seeded.")

        spice_names = [
            "Pepř černý mletý",
            "Paprika sladká",
            "Kmín celý",
            "Skořice mletá",
            "Oregano",
        ]
        spices = {}
        for name in spice_names:
            p, _ = Product.objects.get_or_create(
                name_cs=name, defaults={"kind": Product.Kind.RAW_SPICE}
            )
            spices[name] = p

        mix, _ = Product.objects.get_or_create(
            name_cs="Gulášové koření",
            defaults={"kind": Product.Kind.MIXTURE},
        )
        recipe_targets = {
            "Paprika sladká": Decimal("0.500"),
            "Pepř černý mletý": Decimal("0.300"),
            "Kmín celý": Decimal("0.200"),
        }
        for sp_name, ratio in recipe_targets.items():
            RecipeComponent.objects.update_or_create(
                mixture_product=mix,
                component_product=spices[sp_name],
                defaults={"ratio": ratio},
            )
        self.stdout.write("• Products + recipe seeded.")

        # --- Reservations + threshold demo (per 0043 + 0044) ----------
        # Runs unconditionally — each item has its own .exists() guard
        # so re-runs are no-ops. Lifted above the movement-seed early-
        # return so it shows up on already-seeded DBs.
        today_for_reservations = date.today()
        if not PlannedTransfer.objects.exists():
            pt = PlannedTransfer.objects.create(
                source_branch=tyn,
                target_branch=sez,
                product=spices["Pepř černý mletý"],
                quantity_kg=Decimal("2.000"),
                scheduled_for=today_for_reservations + timedelta(days=2),
                notes="ukázkový plánovaný převod",
                created_by=karolina,
            )
            self.stdout.write(
                f"• Plánovaný převod #{pt.pk} naplánován "
                f"({pt.source_branch.code} → {pt.target_branch.code}, "
                f"{pt.product.name_cs}, {pt.quantity_kg} kg)"
            )

        if not MixingJob.objects.filter(state=MixingJob.State.PLANNED).exists():
            try:
                job = plan_mixing_job(
                    branch=tyn,
                    mixture=mix,
                    target_qty=Decimal("3.000"),
                    user=karolina,
                    planned_for=today_for_reservations + timedelta(days=1),
                    note="ukázková plánovaná dávka",
                )
                self.stdout.write(
                    f"• Plánovaná míchací dávka #{job.pk} ({job.mixture.name_cs}, "
                    f"{job.target_qty} kg) vytvořena."
                )
            except Exception as exc:  # noqa: BLE001 — seed demo, skip on failure
                self.stdout.write(
                    f"• (plan_mixing_job přeskočeno: {exc})"
                )

        # Per 0072 the threshold defaults to 0 (was NULL), so gate the demo
        # values on None-or-0 rather than None only.
        oregano = spices.get("Oregano")
        if oregano and oregano.reorder_threshold_kg in (None, Decimal("0.000")):
            oregano.reorder_threshold_kg = Decimal("5.000")
            oregano.save(update_fields=["reorder_threshold_kg"])
            self.stdout.write(
                "• Objednací bod 5,000 kg nastaven pro Oregano (demo)."
            )
        pepper_default = spices.get("Pepř černý mletý")
        if pepper_default and pepper_default.reorder_threshold_kg in (
            None,
            Decimal("0.000"),
        ):
            pepper_default.reorder_threshold_kg = Decimal("8.000")
            pepper_default.save(update_fields=["reorder_threshold_kg"])
            self.stdout.write(
                "• Objednací bod 8,000 kg nastaven pro Pepř černý mletý (demo)."
            )

        # --- Movement-based seeding -----------------------------------
        # Gate on dodáky, not on raw Movement count: the user might have
        # already created a couple of test movements manually. We only
        # skip if the seed has clearly run before (= sentinel dodák).
        from inventory.models import DodaciList

        sentinel_note = "rozvoz do Říčan"
        if DodaciList.objects.filter(movement__note=sentinel_note).exists():
            self.stdout.write(
                "• Seed-signature dodáky already present — skipping "
                "movement seed (re-run on a wiped DB to regenerate)."
            )
            self._print_login_block()
            return

        today = date.today()

        def mk_lines(items: list[tuple[str, str, str]]) -> list[MovementLine]:
            """items = list of (product_name, qty, sarze)."""
            return [
                MovementLine(
                    product=spices.get(name) or mix,
                    quantity_kg=Decimal(qty),
                    sarze=sarze,
                )
                for name, qty, sarze in items
            ]

        def do_apply(
            *, branch, kind, counterparty, days_ago: int, note: str, items
        ) -> Movement:
            kwargs = {
                "branch": branch,
                "kind": kind,
                "date_issued": today - timedelta(days=days_ago),
                "note": note,
                "created_by": karolina,
            }
            if kind == Movement.Kind.PRIJEM:
                kwargs["dodavatel"] = counterparty
            else:
                kwargs["odberatel"] = counterparty
            mv = Movement(**kwargs)
            return apply_movement(
                movement=mv, lines=mk_lines(items), user=karolina
            )

        # Initial stocking ------------------------------------------------
        prijemy = [
            do_apply(
                branch=tyn,
                kind=Movement.Kind.PRIJEM,
                counterparty=supplier,
                days_ago=14,
                note="počáteční zásobování TYN",
                items=[
                    ("Pepř černý mletý", "25.000", "BATCH-001"),
                    ("Paprika sladká", "18.500", "BATCH-002"),
                    ("Kmín celý", "12.000", "BATCH-003"),
                ],
            ),
            do_apply(
                branch=tyn,
                kind=Movement.Kind.PRIJEM,
                counterparty=supplier,
                days_ago=10,
                note="dorovnání",
                items=[
                    ("Skořice mletá", "8.250", "BATCH-101"),
                    ("Oregano", "4.000", ""),
                ],
            ),
            do_apply(
                branch=sez,
                kind=Movement.Kind.PRIJEM,
                counterparty=supplier,
                days_ago=12,
                note="počáteční zásobování SEZ",
                items=[
                    ("Pepř černý mletý", "11.000", "BATCH-001"),
                    ("Paprika sladká", "9.500", "BATCH-002"),
                    ("Oregano", "2.500", ""),
                ],
            ),
        ]
        self.stdout.write(
            f"• {len(prijemy)} příjmy zaevidovány (#"
            + ", #".join(str(p.pk) for p in prijemy) + ")"
        )

        # Výdeje (dodáky se generují) -------------------------------------
        vydej_specs = [
            (tyn, ricany, 8, "rozvoz do Říčan",
             [("Pepř černý mletý", "3.000", "BATCH-001"),
              ("Paprika sladká", "2.000", "BATCH-002")]),
            (tyn, zak1, 6, "objednávka U Lípy",
             [("Skořice mletá", "1.500", "BATCH-101")]),
            (sez, zak2, 5, "objednávka Na Růžku",
             [("Oregano", "0.500", "")]),
            (tyn, zak1, 3, "doobjednávka",
             [("Kmín celý", "1.000", "BATCH-003"),
              ("Pepř černý mletý", "0.750", "BATCH-001")]),
            (sez, ricany, 2, "rozvoz do Říčan",
             [("Paprika sladká", "1.000", "BATCH-002")]),
        ]
        vydeje = [
            do_apply(
                branch=b,
                kind=Movement.Kind.VYDEJ,
                counterparty=cp,
                days_ago=ago,
                note=note,
                items=items,
            )
            for b, cp, ago, note, items in vydej_specs
        ]
        self.stdout.write(
            f"• {len(vydeje)} výdejů zaevidováno (dodáky generovány)"
        )

        # Edit cycle on the first výdej → [OPRAVA] verze 2 ----------------
        first = vydeje[0]
        first_line = first.lines.order_by("id").first()
        edit_movement(
            movement=first,
            changes={},
            line_changes=[
                {
                    "op": "update",
                    "line_id": first_line.pk,
                    "fields": {"quantity_kg": Decimal("2.900")},
                }
            ],
            reason="oprava hmotnosti — vážil jsem 2,9 ne 3,0",
            user=karolina,
        )
        self.stdout.write(
            f"• Výdej #{first.pk} editován — dodák bumped na verzi 2"
        )

        self._print_login_block()

    def _print_login_block(self) -> None:
        self.stdout.write("")
        self.stdout.write("=== READY ===")
        self.stdout.write("Open http://localhost/sklad/  (public site is at /)")
        self.stdout.write("  karolina@kasia.local / heslo1234  (vlastník)")
        self.stdout.write("  tyn@kasia.local      / heslo1234  (obsluha TYN)")
        self.stdout.write("  sez@kasia.local      / heslo1234  (obsluha SEZ)")
