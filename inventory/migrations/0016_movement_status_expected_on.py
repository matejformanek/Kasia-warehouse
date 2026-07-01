"""Add Movement.status + Movement.expected_on and swap the counterparty
CHECK constraint to allow a supplier-less PLANNED příjem (per 0059).

Existing rows all backfill to status="done" with expected_on=NULL, so the
new DONE branch of the constraint is identical to the old one for them —
data-safe.
"""

from django.db import migrations, models
from django.db.models import CheckConstraint, Q


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0015_seed_order_supplier"),
    ]

    operations = [
        migrations.AddField(
            model_name="movement",
            name="status",
            field=models.CharField(
                choices=[("done", "hotovo"), ("planned", "plánováno")],
                default="done",
                help_text=(
                    "DONE = běžný pohyb (mění sklad). PLANNED = plánovaný"
                    " příjem (objednávka) — sklad se nemění, dokud se příjezd"
                    " nepotvrdí. Per rozhodnutí 0059."
                ),
                max_length=16,
                verbose_name="stav pohybu",
            ),
        ),
        migrations.AddField(
            model_name="movement",
            name="expected_on",
            field=models.DateField(
                blank=True,
                null=True,
                help_text=(
                    "Vyplněno jen u PLANNED příjmu (promise arrival date)."
                    " NULL u běžných (DONE) pohybů. Per rozhodnutí 0059."
                ),
                verbose_name="očekávaný příjezd",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="movement",
            name="movement_counterparty_matches_kind",
        ),
        migrations.AddConstraint(
            model_name="movement",
            constraint=CheckConstraint(
                condition=(
                    Q(kind="vydej")
                    & Q(odberatel__isnull=False)
                    & Q(dodavatel__isnull=True)
                )
                | (
                    Q(kind="prijem")
                    & Q(status="done")
                    & Q(odberatel__isnull=True)
                    & Q(dodavatel__isnull=False)
                )
                | (
                    Q(kind="prijem")
                    & Q(status="planned")
                    & Q(odberatel__isnull=True)
                ),
                name="movement_counterparty_matches_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="movement",
            constraint=CheckConstraint(
                condition=Q(status="done") | Q(kind="prijem"),
                name="movement_planned_implies_prijem",
            ),
        ),
    ]
