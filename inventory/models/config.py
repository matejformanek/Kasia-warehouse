"""Configuration singleton: Settings + SettingsRecipient."""

from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from .catalogue import Branch


class Settings(models.Model):
    """Single-row configuration object. Loaded via Settings.load(); enforced
    single-row via singleton_key + UniqueConstraint per 0037.

    Field list mirrors screens/14-nastaveni.md verbatim. Defaults are the
    Matej-ratified MVP values; recipient pair (Petr, Karolína) is left blank
    intentionally so an operator fills them on first run.
    """

    singleton_key = models.CharField(
        max_length=16,
        default="singleton",
        editable=False,
    )

    # Company header (Společnost / hlavička dokumentu).
    company_name = models.CharField(
        "název firmy", max_length=128, default="Kasia vera s.r.o."
    )
    company_ico = models.CharField("IČO", max_length=16, default="25756729")
    company_dic = models.CharField("DIČ", max_length=16, blank=True)
    company_address = models.TextField("adresa", default="Říčany u Prahy")
    company_phone = models.CharField("telefon", max_length=32, blank=True)
    company_email = models.EmailField("kontaktní e-mail", blank=True)
    logo = models.FileField("logo", upload_to="logos/", blank=True)
    footer_text = models.TextField(
        "patička",
        blank=True,
        default="Kasia vera s.r.o. · IČO 25756729 · Říčany u Prahy",
    )

    # SMTP configuration.
    smtp_host = models.CharField("SMTP server", max_length=128, blank=True)
    smtp_port = models.PositiveIntegerField("SMTP port", default=587)
    smtp_use_tls = models.BooleanField("použít TLS", default=True)
    smtp_user = models.CharField("SMTP uživatel", max_length=128, blank=True)
    smtp_password = models.CharField("SMTP heslo", max_length=128, blank=True)
    email_from_address = models.EmailField("odesílatel — adresa", blank=True)
    email_from_name = models.CharField("odesílatel — jméno", max_length=128, blank=True)

    # Dodák recipients are an N-list in SettingsRecipient per 0052.
    # The recipient_petr / recipient_karolina columns were dropped.

    # E-mail templates per screens/14.
    template_initial_subject = models.CharField(
        "předmět — nový dodák",
        max_length=256,
        default="Dodací list <číslo> — Kasia vera",
    )
    template_initial_body = models.TextField(
        "tělo — nový dodák",
        default=(
            "Dobrý den, v příloze posíláme dodací list <číslo> ze dne "
            "<datum>. S pozdravem, Kasia vera s.r.o."
        ),
    )
    template_oprava_subject = models.CharField(
        "předmět — oprava",
        max_length=256,
        default="[OPRAVA] Dodací list <číslo> — Kasia vera",
    )
    template_oprava_body = models.TextField(
        "tělo — oprava",
        default=(
            "Dobrý den, opravujeme dříve zaslaný dodací list <číslo>. "
            "Důvod: <text zdůvodnění od operátorky>. Nová verze v příloze "
            "nahrazuje předchozí. S pozdravem, Kasia vera s.r.o."
        ),
    )
    template_low_stock_subject = models.CharField(
        "předmět — dochází zboží",
        max_length=256,
        default="Dochází zboží — <datum>",
    )
    template_low_stock_body = models.TextField(
        "tělo — dochází zboží",
        default=(
            "Dobrý den, dnes je pod hranicí těchto produktů: <seznam>. "
            "S pozdravem, Kasia vera s.r.o."
        ),
    )

    class Meta:
        verbose_name = "nastavení"
        verbose_name_plural = "nastavení"
        constraints = [
            UniqueConstraint(fields=["singleton_key"], name="settings_singleton"),
        ]

    @classmethod
    def load(cls) -> Settings:
        obj, _ = cls.objects.get_or_create(singleton_key="singleton")
        return obj

    def __str__(self) -> str:
        return "Nastavení"


class SettingsRecipient(models.Model):
    """One internal e-mail recipient for dodáky + optional low-stock summary.

    Per [`0052`](../context/decisions/0052-n-list-recipients-supersedes-0031.md):
    operator-managed N-list replaces the fixed pair from
    [`0031`](../context/decisions/0031-emails-internal-only-supersedes-0009.md).
    Each row has an explicit subscription flag for the daily low-stock
    summary so subscribers don't have to be derived from row order.
    """

    email = models.EmailField("e-mail")
    label = models.CharField("popisek", max_length=64, blank=True)
    # is_active is the master switch (per 0081): an inactive row receives
    # nothing, regardless of the per-flow flags below.
    is_active = models.BooleanField("aktivní", default=True)
    is_dodaci_recipient = models.BooleanField(
        "dostává dodací listy", default=True
    )
    is_low_stock_recipient = models.BooleanField(
        "dostává souhrn dochází zboží", default=False
    )
    is_feedback_recipient = models.BooleanField(
        "dostává hlášení z Podpory", default=False
    )
    # Per 0081: when set, this row only receives dodáky from that branch;
    # NULL = all branches.
    dodaci_branch = models.ForeignKey(
        Branch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dodaci_recipients",
        verbose_name="pobočka (dodáky)",
    )
    sort_order = models.PositiveSmallIntegerField("pořadí", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "příjemce nastavení"
        verbose_name_plural = "příjemci nastavení"
        ordering = ["-is_active", "sort_order", "id"]
        constraints = [
            UniqueConstraint(
                Lower("email"), name="recipient_email_unique_ci"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label or self.email}"


# ---------------------------------------------------------------------------
# Mixing job (screen 15, per 0005 / 0032 / 0039)
# ---------------------------------------------------------------------------


