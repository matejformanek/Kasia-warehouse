"""Inventory models — first real pass, simplified per Petr's 2026-06-09 brief.

Schema scope per:
- 0001 šarže optional
- 0002 one catalogue, branch-specific stock
- 0003 primary unit kg with 3 dp
- 0005 mixture recipe model
- 0007 dodák auto-reissue + monotonic version (current_version column per 0036)
- 0008 dodák number <BRANCH>-<YYYY>-<NNNN> per (branch, year)
- 0020 custom user with branch FK (in accounts.User)
- 0021 audit trail: hand-rolled movement_audit table (see 0035 for column extension)
- 0028 mass-only (no Variant)
- 0029 no prices
- 0030 default odběratel Říčany — a seeded Customer, not a Branch; movement kinds
  ∈ {prijem, vydej} (no separate převod)
- 0031 dodák e-mails to fixed (Petr, Karolína) pair from Settings
- 0032 míchání in MVP
- 0035 movement_audit line events (target_kind, line_id, event columns)
- 0036 dodák shape: two tables (DodaciList + EmailLog), sequence row, live FK to Customer
- 0037 Settings singleton via singleton_key + UniqueConstraint
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint


class Branch(models.Model):
    """A physical Kasia branch (TYN, SEZ). Říčany is NOT a Branch — see Customer."""

    code = models.CharField("kód", max_length=3, unique=True)
    name = models.CharField("název", max_length=64)
    address = models.CharField("adresa", max_length=256, blank=True)
    is_active = models.BooleanField("aktivní", default=True)

    class Meta:
        verbose_name = "pobočka"
        verbose_name_plural = "pobočky"
        ordering = ("code",)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Customer(models.Model):
    """Odběratel (recipient of výdej). Říčany is seeded with is_default_recipient=True per 0030."""

    name = models.CharField("název", max_length=128)
    ico = models.CharField("IČO", max_length=8, blank=True)
    dic = models.CharField("DIČ", max_length=16, blank=True)
    address = models.TextField("adresa", blank=True)
    email = models.EmailField("e-mail", blank=True)
    phone = models.CharField("telefon", max_length=32, blank=True)
    is_default_recipient = models.BooleanField("výchozí odběratel", default=False)
    is_internal = models.BooleanField(
        "interní (míchárna apod.)",
        default=False,
        help_text=(
            "Interní odběratele systém používá pro účetně-vnitřní pohyby "
            "(např. míchání směsí per 0039). Skrývají se v pickeru výdeje "
            "a vystavení dodacího listu se na ně přeskočí."
        ),
    )
    is_active = models.BooleanField("aktivní", default=True)

    class Meta:
        verbose_name = "odběratel"
        verbose_name_plural = "odběratelé"
        ordering = ("name",)
        constraints = [
            UniqueConstraint(
                fields=["is_default_recipient"],
                condition=Q(is_default_recipient=True),
                name="one_default_customer",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Supplier(models.Model):
    name = models.CharField("název", max_length=128)
    ico = models.CharField("IČO", max_length=8, blank=True)
    address = models.TextField("adresa", blank=True)
    is_internal = models.BooleanField(
        "interní (míchárna apod.)",
        default=False,
        help_text=(
            "Interní dodavatele systém používá pro účetně-vnitřní pohyby "
            "(např. míchání směsí per 0039). Skrývají se v pickeru příjmu."
        ),
    )
    is_active = models.BooleanField("aktivní", default=True)

    class Meta:
        verbose_name = "dodavatel"
        verbose_name_plural = "dodavatelé"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """One row per ingredient (raw spice or mixture). Mass-only per 0028, no price per 0029."""

    class Kind(models.TextChoices):
        RAW_SPICE = "raw_spice", "surovina"
        MIXTURE = "mixture", "směs"

    name_cs = models.CharField("název", max_length=128)
    kind = models.CharField("typ", max_length=16, choices=Kind.choices)
    is_active = models.BooleanField("aktivní", default=True)
    notes = models.TextField("poznámky", blank=True)
    reorder_threshold_kg = models.DecimalField(
        "objednací bod (kg)",
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=(
            "Hranice, pod kterou se produkt objeví na panelu „Dochází zboží"
            " a v denním e-mailu Petrovi (per 0043). Prázdné = bez upozornění;"
            " 0 znamená alert při skutečně nulovém efektivním stavu."
        ),
    )

    class Meta:
        verbose_name = "produkt"
        verbose_name_plural = "produkty"
        ordering = ("name_cs",)
        constraints = [
            UniqueConstraint(
                fields=["name_cs"],
                condition=Q(is_active=True),
                name="unique_active_product_name",
            ),
        ]

    def __str__(self) -> str:
        return self.name_cs


class StockThresholdOverride(models.Model):
    """Per-(product, branch) override of `Product.reorder_threshold_kg`.

    Per [0043](../context/decisions/0043-reorder-threshold.md): one row
    per branch that needs a different threshold than the product default.
    Looked up by `inventory.services.threshold_for(product, branch)`.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="threshold_overrides",
        verbose_name="produkt",
    )
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.CASCADE,
        related_name="threshold_overrides",
        verbose_name="pobočka",
    )
    threshold_kg = models.DecimalField(
        "objednací bod (kg)",
        max_digits=10,
        decimal_places=3,
    )

    class Meta:
        verbose_name = "objednací bod (pobočka)"
        verbose_name_plural = "objednací body (pobočky)"
        ordering = ("product__name_cs", "branch__code")
        constraints = [
            UniqueConstraint(
                fields=["product", "branch"],
                name="unique_threshold_override_per_product_branch",
            ),
            CheckConstraint(
                condition=Q(threshold_kg__gte=0),
                name="threshold_override_nonneg",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} @ {self.branch.code}: {self.threshold_kg} kg"


class Stock(models.Model):
    """Quantity in kg of one product at one branch. Non-negative per výdej rules on screen 07."""

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stocks",
        verbose_name="produkt",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="stocks",
        verbose_name="pobočka",
    )
    quantity = models.DecimalField(
        "množství (kg)",
        max_digits=10,
        decimal_places=3,
    )

    class Meta:
        verbose_name = "stav skladu"
        verbose_name_plural = "stavy skladu"
        ordering = ("branch__code", "product__name_cs")
        constraints = [
            UniqueConstraint(
                fields=["product", "branch"],
                name="unique_stock_per_product_branch",
            ),
            CheckConstraint(
                condition=Q(quantity__gte=0),
                name="stock_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} @ {self.branch.code}: {self.quantity} kg"


class RecipeComponent(models.Model):
    """One ingredient row of a mixture's recipe. Ratios sum to 1.000 across the
    mixture — that sum-to-one check is enforced at form level by the mixing-job
    screen (next pass), not at the DB level."""

    mixture_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="recipe_components",
        verbose_name="směs",
    )
    component_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="used_in_recipes",
        verbose_name="surovina",
    )
    ratio = models.DecimalField("podíl", max_digits=7, decimal_places=6)

    class Meta:
        verbose_name = "složka receptury"
        verbose_name_plural = "složky receptury"
        ordering = ("mixture_product__name_cs", "component_product__name_cs")
        constraints = [
            UniqueConstraint(
                fields=["mixture_product", "component_product"],
                name="unique_component_per_mixture",
            ),
            CheckConstraint(
                condition=Q(ratio__gt=0) & Q(ratio__lte=1),
                name="recipe_ratio_in_range",
            ),
        ]

    def clean(self) -> None:
        if self.mixture_product_id and self.mixture_product.kind != Product.Kind.MIXTURE:
            raise ValidationError(
                {"mixture_product": "Receptura může být přiřazena pouze produktu typu směs."}
            )
        if (
            self.mixture_product_id
            and self.component_product_id
            and self.mixture_product_id == self.component_product_id
        ):
            raise ValidationError(
                {"component_product": "Směs nemůže být složkou sama sebe."}
            )

    def __str__(self) -> str:
        return f"{self.mixture_product} ← {self.component_product} ({self.ratio})"


class Movement(models.Model):
    """A header row for one stock movement at one branch.

    Sign convention: lines store `quantity_kg` as positive; the parent's
    `kind` decides direction (příjem = +, výdej = −). See MovementLine.
    """

    class Kind(models.TextChoices):
        PRIJEM = "prijem", "příjem"
        VYDEJ = "vydej", "výdej"

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="pobočka",
    )
    kind = models.CharField("druh pohybu", max_length=16, choices=Kind.choices)
    date_issued = models.DateField("datum vystavení")
    odberatel = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vydej_movements",
        verbose_name="odběratel",
    )
    dodavatel = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prijem_movements",
        verbose_name="dodavatel",
    )
    note = models.TextField("poznámka", blank=True)
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_movements",
        verbose_name="vytvořil",
    )
    transfer = models.ForeignKey(
        "PlannedTransfer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="plánovaný převod",
        help_text=(
            "Set by `execute_planned_transfer` on both paired Movements"
            " (the výdej at source + the příjem at target) so the audit"
            " trail can link executed Movements back to their originating"
            " PlannedTransfer. NULL on every other Movement."
        ),
    )

    class Meta:
        verbose_name = "pohyb"
        verbose_name_plural = "pohyby"
        ordering = ("-date_issued", "-id")
        constraints = [
            CheckConstraint(
                condition=(
                    Q(kind="vydej")
                    & Q(odberatel__isnull=False)
                    & Q(dodavatel__isnull=True)
                )
                | (
                    Q(kind="prijem")
                    & Q(dodavatel__isnull=False)
                    & Q(odberatel__isnull=True)
                ),
                name="movement_counterparty_matches_kind",
            ),
        ]

    def clean(self) -> None:
        if self.kind == self.Kind.VYDEJ:
            if self.odberatel_id is None:
                raise ValidationError(
                    {"odberatel": "Výdej musí mít odběratele."}
                )
            if self.dodavatel_id is not None:
                raise ValidationError(
                    {"dodavatel": "Výdej nemůže mít dodavatele."}
                )
        elif self.kind == self.Kind.PRIJEM:
            if self.dodavatel_id is None:
                raise ValidationError(
                    {"dodavatel": "Příjem musí mít dodavatele."}
                )
            if self.odberatel_id is not None:
                raise ValidationError(
                    {"odberatel": "Příjem nemůže mít odběratele."}
                )

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.date_issued.isoformat()} @ {self.branch.code}"


class MovementLine(models.Model):
    """One product line of a Movement. `quantity_kg` is positive; signed
    quantity is derived from the parent's kind."""

    movement = models.ForeignKey(
        Movement,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="pohyb",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="movement_lines",
        verbose_name="produkt",
    )
    quantity_kg = models.DecimalField(
        "množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    sarze = models.CharField("šarže", max_length=64, blank=True)
    expiry = models.DateField("expirace", null=True, blank=True)
    note = models.CharField("poznámka", max_length=256, blank=True)

    class Meta:
        verbose_name = "položka pohybu"
        verbose_name_plural = "položky pohybu"
        ordering = ("movement_id", "id")
        constraints = [
            CheckConstraint(
                condition=Q(quantity_kg__gt=0),
                name="movement_line_quantity_positive",
            ),
        ]

    @property
    def signed_quantity(self):
        """Positive for příjem, negative for výdej. Requires `movement` loaded."""
        if self.movement.kind == Movement.Kind.PRIJEM:
            return self.quantity_kg
        return -self.quantity_kg

    def __str__(self) -> str:
        return f"{self.product} {self.quantity_kg} kg"


class MovementAudit(models.Model):
    """Append-only audit row per changed field (or per line lifecycle event)
    of a Movement edit. See decisions 0021 and 0035."""

    class TargetKind(models.TextChoices):
        MOVEMENT = "movement", "pohyb"
        LINE = "line", "položka"

    class Event(models.TextChoices):
        FIELD_CHANGED = "field_changed", "změna pole"
        LINE_ADDED = "line_added", "přidaná položka"
        LINE_REMOVED = "line_removed", "odebraná položka"

    movement = models.ForeignKey(
        Movement,
        on_delete=models.CASCADE,
        related_name="audit_entries",
        verbose_name="pohyb",
    )
    edited_at = models.DateTimeField("upraveno", auto_now_add=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movement_edits",
        verbose_name="upravil",
    )
    reason = models.TextField("důvod úpravy")
    target_kind = models.CharField(
        "cíl změny",
        max_length=16,
        choices=TargetKind.choices,
    )
    line_id = models.BigIntegerField("ID položky", null=True, blank=True)
    event = models.CharField("událost", max_length=24, choices=Event.choices)
    field = models.CharField("pole", max_length=64, blank=True, default="")
    old_value = models.TextField("původní hodnota", blank=True, default="")
    new_value = models.TextField("nová hodnota", blank=True, default="")

    class Meta:
        verbose_name = "záznam auditu"
        verbose_name_plural = "záznamy auditu"
        ordering = ("movement_id", "edited_at", "id")
        constraints = [
            CheckConstraint(
                condition=~Q(reason=""),
                name="movement_audit_reason_required",
            ),
        ]

    def __str__(self) -> str:
        suffix = f" ({self.field})" if self.field else ""
        return f"{self.movement_id} {self.event}{suffix} @ {self.edited_at.isoformat()}"


# ---------------------------------------------------------------------------
# Dodací list + send trail + numbering (per 0007 / 0008 / 0031 / 0036)
# ---------------------------------------------------------------------------


class DodaciListNumberSequence(models.Model):
    """Per-(branch, year) monotonic counter for dodák čísla per 0008. One row
    per (branch, year); allocated under SELECT … FOR UPDATE in services."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="number_sequences",
        verbose_name="pobočka",
    )
    year = models.PositiveSmallIntegerField("rok")
    last_counter = models.PositiveIntegerField("poslední pořadí", default=0)

    class Meta:
        verbose_name = "číselná řada dodacích listů"
        verbose_name_plural = "číselné řady dodacích listů"
        ordering = ("branch__code", "year")
        constraints = [
            UniqueConstraint(
                fields=["branch", "year"],
                name="unique_branch_year_sequence",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.branch.code} {self.year}: {self.last_counter}"


class DodaciList(models.Model):
    """One issued dodací list per výdej Movement. Číslo is the per-(branch,
    year) sequence rendered as TYN-2026-0042 per 0008; current_version is
    the monotonic internal counter per 0007 (initial issue = 1, each
    correction increments by one); odberatel is a live FK per 0036."""

    movement = models.OneToOneField(
        Movement,
        on_delete=models.PROTECT,
        related_name="dodaci_list",
        verbose_name="pohyb",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="dodaci_lists",
        verbose_name="pobočka",
    )
    odberatel = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="dodaci_lists",
        verbose_name="odběratel",
    )
    date_issued = models.DateField("datum vystavení")
    year_issued = models.PositiveSmallIntegerField("rok vystavení")
    counter = models.PositiveIntegerField("pořadí")
    cislo = models.CharField("číslo", max_length=24, unique=True)
    current_version = models.PositiveIntegerField("aktuální verze", default=1)
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_dodaci_lists",
        verbose_name="vytvořil",
    )

    class Meta:
        verbose_name = "dodací list"
        verbose_name_plural = "dodací listy"
        ordering = ("-date_issued", "-id")
        constraints = [
            UniqueConstraint(
                fields=["branch", "year_issued", "counter"],
                name="unique_dodaci_list_branch_year_counter",
            ),
            CheckConstraint(
                condition=Q(counter__gte=1),
                name="dodaci_list_counter_positive",
            ),
            CheckConstraint(
                condition=Q(current_version__gte=1),
                name="dodaci_list_version_positive",
            ),
        ]

    @property
    def is_edited(self) -> bool:
        """True iff the dodák has been re-issued at least once (per 0007)."""
        return self.current_version > 1

    @property
    def total_quantity_kg(self):
        """Sum of all line quantities — feeds screen 08's "hrubý objem" column."""
        return sum(
            (line.quantity_kg for line in self.movement.lines.all()),
            start=0,
        )

    def __str__(self) -> str:
        return self.cislo


class DodaciListEmailLog(models.Model):
    """One row per send attempt for one dodák version. Per 0007 + 0019:
    every send (successful or failed) writes a row. Screen 09's "verze a
    odeslání" audit table reads these rows ordered by sent_at."""

    class Status(models.TextChoices):
        SENT = "sent", "odesláno"
        FAILED = "failed", "selhalo"

    dodaci_list = models.ForeignKey(
        DodaciList,
        on_delete=models.CASCADE,
        related_name="email_logs",
        verbose_name="dodací list",
    )
    version = models.PositiveIntegerField("verze")
    sent_at = models.DateTimeField("odesláno v", auto_now_add=True)
    recipients = models.CharField("příjemci", max_length=512)
    trigger_reason = models.TextField("důvod odeslání")
    status = models.CharField(
        "stav",
        max_length=16,
        choices=Status.choices,
    )
    error_message = models.TextField("chybová zpráva", blank=True, default="")

    class Meta:
        verbose_name = "záznam odeslání dodacího listu"
        verbose_name_plural = "záznamy odeslání dodacích listů"
        ordering = ("dodaci_list_id", "sent_at", "id")
        constraints = [
            CheckConstraint(
                condition=Q(version__gte=1),
                name="email_log_version_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.dodaci_list.cislo} v{self.version} · {self.status}"


# ---------------------------------------------------------------------------
# Settings singleton (per 0037)
# ---------------------------------------------------------------------------


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

    # Dodák recipients per 0031.
    recipient_petr = models.EmailField("příjemce Petr", blank=True)
    recipient_karolina = models.EmailField("příjemce Karolína", blank=True)

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


# ---------------------------------------------------------------------------
# Mixing job (screen 15, per 0005 / 0032 / 0039)
# ---------------------------------------------------------------------------


class MixingJob(models.Model):
    """One execution of a mixture recipe at a branch.

    Per 0039: consume at start (consume_movement points at the vydej
    Movement written when the operator clicks Zahájit); produce at
    finish (produce_movement points at the prijem Movement written
    when the operator clicks Dokončit). Cancel is an audited correction
    that zeros out every line of consume_movement via edit_movement.
    Yield loss surfaces as the delta between target_qty and
    actual_produced_qty; no separate column.
    """

    class State(models.TextChoices):
        PLANNED = "planned", "naplánováno"
        RUNNING = "running", "probíhá"
        DONE = "done", "dokončeno"
        CANCELLED = "cancelled", "zrušeno"

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="mixing_jobs",
        verbose_name="pobočka",
    )
    mixture = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="mixing_jobs",
        verbose_name="směs",
    )
    target_qty = models.DecimalField(
        "cílové množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    actual_produced_qty = models.DecimalField(
        "skutečně vyrobeno (kg)",
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
    )
    state = models.CharField(
        "stav",
        max_length=16,
        choices=State.choices,
        default=State.RUNNING,
    )
    planned_for = models.DateField(
        "plánováno na",
        null=True,
        blank=True,
        help_text=(
            "Pouze pro state=PLANNED — kdy operátor předpokládá fyzické míchání."
            " Po přechodu na RUNNING už nemá smysl, pole zůstane jako historický záznam."
        ),
    )
    started_at = models.DateTimeField("zahájeno", auto_now_add=True)
    finished_at = models.DateTimeField("ukončeno", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_mixing_jobs",
        verbose_name="vytvořil",
    )
    cancel_reason = models.TextField(
        "důvod zrušení",
        blank=True,
        default="",
    )
    note = models.TextField("poznámka", blank=True, default="")
    consume_movement = models.ForeignKey(
        Movement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mixing_job_as_consume",
        verbose_name="pohyb spotřeby",
    )
    produce_movement = models.ForeignKey(
        Movement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mixing_job_as_produce",
        verbose_name="pohyb produkce",
    )

    class Meta:
        verbose_name = "míchací dávka"
        verbose_name_plural = "míchací dávky"
        ordering = ("-started_at", "-id")
        constraints = [
            CheckConstraint(
                condition=Q(target_qty__gt=0),
                name="mixing_job_target_qty_positive",
            ),
            CheckConstraint(
                condition=Q(actual_produced_qty__isnull=True)
                | Q(actual_produced_qty__gte=0),
                name="mixing_job_actual_produced_qty_non_negative",
            ),
            CheckConstraint(
                condition=~Q(state="cancelled") | ~Q(cancel_reason=""),
                name="mixing_job_cancel_reason_required",
            ),
        ]

    @property
    def is_terminal(self) -> bool:
        return self.state in (self.State.DONE, self.State.CANCELLED)

    @property
    def yield_delta(self):
        """Signed (actual - target). None if not finished. Used by
        screen 15 to surface dust loss / over-yield as a delta on the
        produced movement per 0039."""
        if self.actual_produced_qty is None:
            return None
        return self.actual_produced_qty - self.target_qty

    def __str__(self) -> str:
        return f"Míchání {self.mixture} {self.target_qty} kg @ {self.branch.code}"


class MixingJobLine(models.Model):
    """One per-component snapshot of a MixingJob's recipe.

    Per 0005: recipe is snapshotted at job start — `ratio_at_start`
    is copied from the live RecipeComponent row, and future recipe
    edits do not touch in-flight jobs. `derived_qty` is
    `target_qty * ratio_at_start` computed at start. `actual_qty`
    defaults to `derived_qty` and is editable at finish to record
    weighing tolerance.
    """

    mixing_job = models.ForeignKey(
        MixingJob,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="míchací dávka",
    )
    component_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="mixing_job_lines",
        verbose_name="surovina",
    )
    ratio_at_start = models.DecimalField(
        "podíl při zahájení",
        max_digits=7,
        decimal_places=6,
    )
    derived_qty = models.DecimalField(
        "odvozené množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    actual_qty = models.DecimalField(
        "skutečné množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    sarze = models.CharField("šarže", max_length=64, blank=True)

    class Meta:
        verbose_name = "položka míchání"
        verbose_name_plural = "položky míchání"
        ordering = ("mixing_job_id", "id")
        constraints = [
            UniqueConstraint(
                fields=["mixing_job", "component_product"],
                name="unique_mixing_job_component",
            ),
            CheckConstraint(
                condition=Q(derived_qty__gt=0),
                name="mixing_job_line_derived_positive",
            ),
            CheckConstraint(
                condition=Q(actual_qty__gt=0),
                name="mixing_job_line_actual_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.component_product} {self.actual_qty} kg"


# ---------------------------------------------------------------------------
# Planned inter-branch transfer (per decision 0044)
# ---------------------------------------------------------------------------


class PlannedTransfer(models.Model):
    """One scheduled transfer of a product from one branch to another.

    Per [0044](../context/decisions/0044-reservations-planned-states.md):
    PLANNED rows count as reserved at `source_branch`. Execution writes
    a pair of Movements via `execute_planned_transfer`: a výdej at the
    source (to the seeded "Převod mezi pobočkami" Customer) and a
    příjem at the target (from the seeded "Převod mezi pobočkami"
    Supplier). The counterparty pair is `is_internal=False` so the
    existing dodák auto-issue + e-mail hooks fire on the výdej leg —
    the dodák is the physical paper for the driver.
    """

    class State(models.TextChoices):
        PLANNED = "planned", "naplánováno"
        DONE = "done", "provedeno"
        CANCELLED = "cancelled", "zrušeno"

    source_branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="outgoing_planned_transfers",
        verbose_name="zdrojová pobočka",
    )
    target_branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="incoming_planned_transfers",
        verbose_name="cílová pobočka",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="planned_transfers",
        verbose_name="produkt",
    )
    quantity_kg = models.DecimalField(
        "množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    scheduled_for = models.DateField("plánováno na")
    state = models.CharField(
        "stav",
        max_length=16,
        choices=State.choices,
        default=State.PLANNED,
    )
    notes = models.TextField("poznámka", blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_planned_transfers",
        verbose_name="vytvořil",
    )
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)

    class Meta:
        verbose_name = "plánovaný převod"
        verbose_name_plural = "plánované převody"
        ordering = ("-scheduled_for", "-id")
        constraints = [
            CheckConstraint(
                condition=~Q(source_branch=models.F("target_branch")),
                name="planned_transfer_different_branches",
            ),
            CheckConstraint(
                condition=Q(quantity_kg__gt=0),
                name="planned_transfer_qty_positive",
            ),
        ]

    def clean(self) -> None:
        if (
            self.source_branch_id
            and self.target_branch_id
            and self.source_branch_id == self.target_branch_id
        ):
            raise ValidationError(
                {"target_branch": "Cílová pobočka se musí lišit od zdrojové."}
            )

    def __str__(self) -> str:
        return (
            f"{self.product} {self.quantity_kg} kg: "
            f"{self.source_branch.code} → {self.target_branch.code} "
            f"({self.scheduled_for.isoformat()})"
        )
