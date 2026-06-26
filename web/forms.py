from django import forms

from .models import ContactInquiry


class ContactInquiryForm(forms.ModelForm):
    """Public kontakt / poptávka form.

    Plain Django form posted as a normal ``<form method="post">`` — the
    public base template ships no htmx (decision 0049/0050). CSRF is
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

    class Meta:
        model = ContactInquiry
        fields = ("name", "email", "phone", "message")
        widgets = {
            "message": forms.Textarea(attrs={"rows": 6}),
        }
