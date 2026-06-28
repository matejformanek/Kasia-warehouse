"""Daily summary e-mail of (product, branch) pairs below their reorder
threshold per decisions 0045 + 0052. Exit 0 always; one-line stdout."""

from django.core.management.base import BaseCommand

from inventory.models import SettingsRecipient
from inventory.services import send_low_stock_summary


class Command(BaseCommand):
    help = (
        "Send the daily low-stock summary e-mail to every active "
        "SettingsRecipient with is_low_stock_recipient=True (per 0052)."
    )

    def handle(self, *args, **options):
        count = send_low_stock_summary()
        if count is None:
            self.stdout.write("no low stock today")
        else:
            targets = list(
                SettingsRecipient.objects.filter(
                    is_active=True, is_low_stock_recipient=True
                ).values_list("email", flat=True)
            ) or ["(no recipient)"]
            self.stdout.write(f"sent N={count} to {', '.join(targets)}")
