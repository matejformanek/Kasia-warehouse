from django import forms

from .models import ContactInquiry


class ContactInquiryForm(forms.ModelForm):
    """Public kontakt / poptávka form.

    Plain Django form posted as a normal ``<form method="post">`` — the
    public base template ships no htmx (decision 0050/0051). CSRF is
    enforced by the already-active CsrfViewMiddleware via {% csrf_token %}.
    """

    # GDPR contact-consent gate. Not stored as a column (created_at records
    # when consent was given); required so the form cannot submit without it.
    consent = forms.BooleanField(
        label=(
            "Souhlasím se zpracováním uvedených osobních údajů za účelem "
            "vyřízení mé poptávky."
        ),
        required=True,
        error_messages={
            "required": "Pro odeslání je nutný souhlas se zpracováním údajů."
        },
    )

    # Honeypot — the form is a public, unauthenticated POST that writes a DB
    # row and (with SMTP live) sends e-mail, so a cheap spam gate is worth it
    # while staying right-sized (no captcha/rate-limit dependency). Humans
    # never see this field (hidden + tabindex -1 + autocomplete off); a bot
    # that fills it gets a silently-rejected submission. Not stored.
    website = forms.CharField(
        required=False,
        label="Nevyplňujte",
        widget=forms.TextInput(
            attrs={
                "tabindex": "-1",
                "autocomplete": "off",
                "aria-hidden": "true",
            }
        ),
    )

    class Meta:
        model = ContactInquiry
        fields = ("name", "email", "phone", "message")
        widgets = {
            "message": forms.Textarea(attrs={"rows": 6}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            # Bot tripped the honeypot — fail validation without saving.
            raise forms.ValidationError("Formulář se nepodařilo odeslat.")
        return cleaned
