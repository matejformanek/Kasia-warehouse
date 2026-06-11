"""Render one Movement's dodací list as a PDF to disk; no e-mail.

Used as a WeasyPrint smoke test before screen 07 lands. If the Movement
doesn't yet have a linked DodaciList (e.g. created before Pass 2), the
command creates one inline using the same allocate-number flow as
apply_movement's vydej path.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import DodaciList, Movement
from inventory.services import (
    _create_dodaci_list_for_movement,
    render_dodaci_list_pdf,
)


class Command(BaseCommand):
    help = "Render a dodací list PDF for one Movement (no e-mail)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("movement_id", type=int)
        parser.add_argument("--output", type=str, default=None)

    def handle(self, *args, movement_id: int, output: str | None, **opts) -> None:
        try:
            movement = Movement.objects.select_related("branch", "odberatel").get(
                pk=movement_id
            )
        except Movement.DoesNotExist as exc:
            raise CommandError(f"Movement {movement_id} not found.") from exc

        if movement.kind != Movement.Kind.VYDEJ:
            raise CommandError("Dodací list lze vygenerovat pouze pro výdej.")

        dodaci_list = DodaciList.objects.filter(movement=movement).first()
        if dodaci_list is None:
            with transaction.atomic():
                dodaci_list = _create_dodaci_list_for_movement(movement)

        pdf_bytes = render_dodaci_list_pdf(dodaci_list)

        out_path = (
            Path(output)
            if output is not None
            else Path.cwd() / f"dodaci_list_{dodaci_list.cislo}.pdf"
        )
        out_path.write_bytes(pdf_bytes)
        self.stdout.write(
            self.style.SUCCESS(
                f"Vygenerováno: {out_path} ({len(pdf_bytes)} B, "
                f"{dodaci_list.cislo} v{dodaci_list.current_version})"
            )
        )
