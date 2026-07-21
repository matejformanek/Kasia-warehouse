"""Support feedback form."""

from __future__ import annotations

from django import forms

from ..models import (
    Feedback,
)

# Friendly Czech screen names offered in the „which page" dropdown (per 0079).
# The choice VALUE equals its LABEL so the friendly string is what gets stored
# in the unchanged Feedback.page_url CharField — the model keeps no `choices=`,
# so old free-text rows stay valid and no migration is needed. A leading blank
# choice makes an unselected dropdown post "" (page_url stays optional).
_PAGE_NAMES = [
    "Přehled",
    "Katalog",
    "Inventura",
    "Příjem",
    "Výdej",
    "Míchání",
    "Historie",
    "Dodací listy",
    "Detail produktu",
    "Dodavatelé",
    "Odběratelé",
    "Nastavení",
    "Uživatelé",
    "Podpora",
    "Jiné / nevím",
]
PAGE_URL_CHOICES = [("", "— vyberte stránku (volitelné) —")] + [
    (name, name) for name in _PAGE_NAMES
]


class FeedbackForm(forms.ModelForm):
    """Operator-facing form for submitting one feedback row on /podpora/."""

    # Explicitly declared: overrides the auto-generated ModelForm field with a
    # dropdown of Czech screen names (per 0079). Because it's declared here,
    # Meta.widgets/Meta.labels are ignored for it, so its label lives on the
    # field itself.
    page_url = forms.ChoiceField(
        label="Které stránky se hlášení týká? (volitelné)",
        choices=PAGE_URL_CHOICES,
        required=False,
        widget=forms.Select,
    )

    class Meta:
        model = Feedback
        fields = ("page_url", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "description": "Popis problému, dotazu nebo nápadu",
        }


# ---------------------------------------------------------------------------
