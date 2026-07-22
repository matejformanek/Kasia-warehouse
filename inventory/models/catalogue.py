"""Catalogue masters: branches, products, customers, suppliers, stock, recipe."""

from decimal import Decimal

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
    is_stock_tracked = models.BooleanField(
        "sledovat sklad",
        default=True,
        help_text=(
            "Odškrtnuté produkty (např. „Voda“) se skladově nesledují: nemají"
            " skladové řádky, nezobrazují se v Katalogu / Přehledu / inventuře,"
            " nikdy nejsou „Prázdné“/„Dochází“, neblokují výdej ani míchání a"
            " neposílají upozornění. Nastavuje se pouze při založení produktu"
            " (per 0088)."
        ),
    )
    notes = models.TextField("poznámky", blank=True)
    reorder_threshold_kg = models.DecimalField(
        "objednací bod (kg)",
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=True,
        default=Decimal("0.000"),
        help_text=(
            "Hranice, pod kterou se produkt objeví na panelu „Dochází zboží"
            " a v denním e-mailu příjemcům upozornění „dochází zboží"
            " (per 0043/0072). Nové produkty mají"
            " výchozí 0; produkt s nulovým efektivním stavem se vždy zobrazí"
            " ve skupině „Prázdné“."
        ),
    )
    default_batch_kg = models.DecimalField(
        "výchozí dávka (kg)",
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=True,
        default=Decimal("0.000"),
        help_text=(
            "Výchozí velikost dávky, kterou systém předvyplní do míchání"
            " (pole „Cílové množství“) a do kalkulačky dávky na detailu"
            " produktu (per 0089). 0 = nenastaveno (chová se jako dřív)."
            " Má smysl jen u směsí."
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
    note = models.CharField(
        "poznámka ke složce", max_length=255, blank=True, default=""
    )

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


