"""Inventory models — first real pass, simplified per Petr's 2026-06-09 brief.

Schema scope per:
- 0001 šarže optional
- 0002 one catalogue, branch-specific stock
- 0003 primary unit kg with 3 dp
- 0005 mixture recipe model
- 0020 custom user with branch FK (in accounts.User)
- 0021 audit trail: hand-rolled movement_audit table (see 0035 for column extension)
- 0028 mass-only (no Variant)
- 0029 no prices
- 0030 default odběratel Říčany — a seeded Customer, not a Branch; movement kinds
  ∈ {prijem, vydej} (no separate převod)
- 0031 Customer.email = contact only
- 0032 míchání in MVP
- 0035 movement_audit line events (target_kind, line_id, event columns)
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
