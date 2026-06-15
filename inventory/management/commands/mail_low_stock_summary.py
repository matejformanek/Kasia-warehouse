"""Daily summary e-mail of (product, branch) pairs below their reorder
threshold per decision 0045. Exit 0 always; one-line stdout."""

from django.core.management.base import BaseCommand

from inventory.models import Settings
from inventory.services import send_low_stock_summary


class Command(BaseCommand):
    help = "Send the daily low-stock summary e-mail to Settings.recipient_petr."

    def handle(self, *args, **options):
        count = send_low_stock_summary()
        if count is None:
            self.stdout.write("no low stock today")
        else:
            target = Settings.load().recipient_petr or "(no recipient)"
            self.stdout.write(f"sent N={count} to {target}")
