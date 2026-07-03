"""Support feedback form."""

from __future__ import annotations

from django import forms

from ..models import (
    Feedback,
)


class FeedbackForm(forms.ModelForm):
    """Operator-facing form for submitting one feedback row on /podpora/."""

    class Meta:
        model = Feedback
        fields = ("page_url", "description")
        widgets = {
            "page_url": forms.TextInput(
                attrs={
                    "placeholder": "/katalog/ — volitelné",
                    "size": 40,
                }
            ),
            "description": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "page_url": "Stránka, které se hlášení týká (volitelné)",
            "description": "Popis problému, dotazu nebo nápadu",
        }


# ---------------------------------------------------------------------------
