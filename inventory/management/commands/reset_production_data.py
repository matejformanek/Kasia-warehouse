"""Wipe production back to a clean go-live baseline (decision 0087).

Hard-deletes every operational + entered-catalogue row while keeping a small
reviewed keep-set: the owner/admin users, both branches, the Settings singleton
+ its recipients, and the seeded internal counterparties (+ Říčany). Deletion
runs in one ``transaction.atomic()`` in a PROTECT-safe dependency order.

Dry-run by default; ``--commit`` is required to mutate. A startup guard asserts
the keep-set is present before touching anything and aborts (no mutation) on any
gap. It deliberately does NOT gate on DEBUG — this command must run on prod,
where DEBUG=False.

See ``context/decisions/0087-production-data-wipe-for-go-live.md``.
"""

from __future__ import annotations

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError, Q

from inventory.models import (
    Customer,
    DodaciList,
    DodaciListNumberSequence,
    EmailLog,
    Feedback,
    MixingJob,
    MixingJobLine,
    Movement,
    MovementAudit,
    MovementLine,
    PlannedOrder,
    PlannedTransfer,
    Product,
    RecipeComponent,
    ScreenVisit,
    Stock,
    StockThresholdOverride,
    Supplier,
)
from inventory.services import counterparties

User = get_user_model()

# Reviewed keep-set — the four owner/admin logins (passwords untouched). Matched
# case-insensitively against the stored email. Per decision 0087.
KEEP_USER_EMAILS = (
    "admin@kasia.cz",
    "petr@kasia.cz",
    "karolina@kasia.cz",
    "matej.formanek@kasia.cz",
)


class Command(BaseCommand):
    help = (
        "Wipe production data to a clean go-live baseline (per 0087). "
        "Dry-run unless --commit is given."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually delete. Without this flag the command only reports.",
        )

    # -- keep-set querysets ------------------------------------------------

    def _keep_user_qs(self):
        q = Q()
        for email in KEEP_USER_EMAILS:
            q |= Q(email__iexact=email)
        return User.objects.filter(q)

    def _keep_customer_qs(self):
        # Keep the default recipient (Říčany) + any counterparty Customer
        # matching a role tuple. Derived from _ROLES so it can't drift from
        # the runtime .get(name=…, is_internal=…) lookups (per 0087).
        q = Q(is_default_recipient=True)
        for name, is_internal in counterparties._ROLES.values():
            q |= Q(name=name, is_internal=is_internal)
        return Customer.objects.filter(q)

    def _keep_supplier_qs(self):
        q = Q(pk__in=[])
        for name, is_internal in counterparties._ROLES.values():
            q |= Q(name=name, is_internal=is_internal)
        return Supplier.objects.filter(q)

    # -- guard -------------------------------------------------------------

    def _check_keep_set(self) -> None:
        """Abort (CommandError, no mutation) unless the whole keep-set is
        present: every kept user exists, ≥1 is a superuser, Říčany exists,
        and each counterparty role resolves to a seeded Supplier row."""
        keep_users = self._keep_user_qs()
        found = {e.lower() for e in keep_users.values_list("email", flat=True)}
        missing = [e for e in KEEP_USER_EMAILS if e.lower() not in found]
        if missing:
            raise CommandError(
                "Keep-set users missing — aborting: " + ", ".join(missing)
            )
        if not keep_users.filter(is_superuser=True).exists():
            raise CommandError(
                "No superuser in the keep-set — aborting (refuse to lock "
                "everyone out)."
            )
        if not Customer.objects.filter(is_default_recipient=True).exists():
            raise CommandError(
                "Default recipient (Říčany) missing — aborting."
            )
        for name, is_internal in counterparties._ROLES.values():
            if not Supplier.objects.filter(
                name=name, is_internal=is_internal
            ).exists():
                raise CommandError(
                    f"Seeded counterparty Supplier missing — aborting: "
                    f"{name!r} (is_internal={is_internal})."
                )

    # -- report ------------------------------------------------------------

    def _report_rows(self) -> list[tuple[str, int, int]]:
        """(label, before, predicted_after) for every touched model, in
        deletion order. Cascade children (MovementLine/MovementAudit/
        MixingJobLine) are display-only — they go via their parent."""
        keep_customers = self._keep_customer_qs().count()
        keep_suppliers = self._keep_supplier_qs().count()
        keep_users = self._keep_user_qs().count()
        return [
            ("ScreenVisit", ScreenVisit.objects.count(), 0),
            ("Feedback", Feedback.objects.count(), 0),
            ("EmailLog", EmailLog.objects.count(), 0),
            ("DodaciList", DodaciList.objects.count(), 0),
            ("MixingJob", MixingJob.objects.count(), 0),
            ("  MixingJobLine (cascade)", MixingJobLine.objects.count(), 0),
            ("PlannedOrder", PlannedOrder.objects.count(), 0),
            ("Movement", Movement.objects.count(), 0),
            ("  MovementLine (cascade)", MovementLine.objects.count(), 0),
            ("  MovementAudit (cascade)", MovementAudit.objects.count(), 0),
            ("PlannedTransfer", PlannedTransfer.objects.count(), 0),
            ("Stock", Stock.objects.count(), 0),
            (
                "StockThresholdOverride",
                StockThresholdOverride.objects.count(),
                0,
            ),
            ("RecipeComponent", RecipeComponent.objects.count(), 0),
            ("Product", Product.objects.count(), 0),
            ("Customer", Customer.objects.count(), keep_customers),
            ("Supplier", Supplier.objects.count(), keep_suppliers),
            (
                "DodaciListNumberSequence",
                DodaciListNumberSequence.objects.count(),
                0,
            ),
            ("User", User.objects.count(), keep_users),
            ("django_session", Session.objects.count(), 0),
            ("admin.LogEntry", LogEntry.objects.count(), 0),
        ]

    def _print_table(self, rows: list[tuple[str, int, int]]) -> None:
        self.stdout.write("")
        self.stdout.write(
            f"  {'model':<28} {'before':>8} {'after':>8} {'deleted':>8}"
        )
        self.stdout.write(f"  {'-' * 28} {'-' * 8} {'-' * 8} {'-' * 8}")
        for label, before, after in rows:
            deleted = before - after
            self.stdout.write(
                f"  {label:<28} {before:>8} {after:>8} {deleted:>8}"
            )
        self.stdout.write("")

    # -- delete ------------------------------------------------------------

    def _delete_all(self) -> None:
        """Delete everything outside the keep-set in PROTECT-safe order,
        inside one atomic transaction. Order verified against the FK map in
        0087 — a wrong order raises ProtectedError, which we surface with the
        offending step and roll the whole thing back."""
        del_customers = Customer.objects.exclude(
            pk__in=self._keep_customer_qs().values("pk")
        )
        del_suppliers = Supplier.objects.exclude(
            pk__in=self._keep_supplier_qs().values("pk")
        )
        del_users = User.objects.exclude(
            pk__in=self._keep_user_qs().values("pk")
        )

        # (label, callable) — ordered so every PROTECT referrer is gone
        # before its referent. Cascades: MixingJob→lines, Movement→lines+audit.
        steps: list[tuple[str, object]] = [
            ("ScreenVisit", lambda: ScreenVisit.objects.all().delete()),
            ("Feedback", lambda: Feedback.objects.all().delete()),
            ("EmailLog", lambda: EmailLog.objects.all().delete()),
            ("DodaciList", lambda: DodaciList.objects.all().delete()),
            ("MixingJob", lambda: MixingJob.objects.all().delete()),
            ("PlannedOrder", lambda: PlannedOrder.objects.all().delete()),
            ("Movement", lambda: Movement.objects.all().delete()),
            ("PlannedTransfer", lambda: PlannedTransfer.objects.all().delete()),
            ("Stock", lambda: Stock.objects.all().delete()),
            (
                "StockThresholdOverride",
                lambda: StockThresholdOverride.objects.all().delete(),
            ),
            ("RecipeComponent", lambda: RecipeComponent.objects.all().delete()),
            ("Product", lambda: Product.objects.all().delete()),
            ("Customer", del_customers.delete),
            ("Supplier", del_suppliers.delete),
            (
                "DodaciListNumberSequence",
                lambda: DodaciListNumberSequence.objects.all().delete(),
            ),
            ("User", del_users.delete),
            ("django_session", lambda: Session.objects.all().delete()),
            ("admin.LogEntry", lambda: LogEntry.objects.all().delete()),
        ]

        with transaction.atomic():
            for label, run in steps:
                try:
                    run()
                except ProtectedError as exc:
                    raise CommandError(
                        f"ProtectedError while deleting {label}: {exc}. "
                        "Deletion order is wrong — nothing was committed."
                    ) from exc

    # -- entrypoint --------------------------------------------------------

    def handle(self, *args, commit: bool = False, **options) -> None:
        self._check_keep_set()

        rows = self._report_rows()
        mode = "COMMIT" if commit else "DRY-RUN"
        self.stdout.write(
            self.style.WARNING(f"=== reset_production_data ({mode}) ===")
        )
        self._print_table(rows)

        if not commit:
            total = sum(before - after for _, before, after in rows)
            self.stdout.write(
                self.style.NOTICE(
                    f"Dry-run — nothing deleted. {total} rows would be "
                    "removed. Re-run with --commit to apply."
                )
            )
            return

        self._delete_all()
        after_rows = self._report_rows()
        self.stdout.write(self.style.SUCCESS("Wipe committed. Final counts:"))
        self._print_table(after_rows)
        self.stdout.write(
            self.style.SUCCESS(
                "Done. Kept the owner/admin users, both branches, Settings + "
                "recipients, and the seeded counterparties."
            )
        )
