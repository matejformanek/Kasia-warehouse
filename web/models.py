from django.db import models


class ContactInquiry(models.Model):
    """A poptávka / contact-form submission from the public site.

    Persisted to the DB *first*, then an e-mail notification is attempted
    (see web/views.py:kontakt). Production SMTP is still deferred
    (state.md § Hetzner), so an e-mail-only form would silently lose every
    inquiry — durability-over-uptime per
    .claude/rules/right-sized-for-small-business.md and decision 0050.
    Mirrors the durable-capture shape of inventory.Feedback (decision 0046).

    The submitter is a member of the public, never a Kasia ``User`` — so
    ``email`` is a plain string, deliberately NOT an FK.
    """

    name = models.CharField("jméno", max_length=200)
    email = models.EmailField("e-mail", max_length=254)
    phone = models.CharField("telefon", max_length=40, blank=True)
    message = models.TextField("zpráva")
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)
    handled = models.BooleanField("vyřízeno", default=False)

    class Meta:
        verbose_name = "poptávka"
        verbose_name_plural = "poptávky"
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"{self.name} <{self.email}> ({self.created_at:%Y-%m-%d})"
