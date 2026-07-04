"""Shared form helpers (decision 0068).

``validate_active_name_unique`` centralizes the soft-uniqueness check that was
copy-pasted across the Supplier / Customer / Product forms: don't let a worker
create a second active row with the same name (case-insensitive), while still
allowing an archived row to share the name. BranchForm does NOT use this — a
branch code is globally unique regardless of ``is_active``.
"""

from __future__ import annotations

from django import forms


def validate_active_name_unique(model, field_name: str, value, *, instance, label: str) -> str:
    """Return the stripped value, or raise if another *active* row of ``model``
    already has this name (``field_name`` iexact). ``label`` is the Czech noun
    for the error message (e.g. "dodavatel")."""
    value = (value or "").strip()
    qs = model.objects.filter(**{f"{field_name}__iexact": value}, is_active=True)
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise forms.ValidationError(f"Aktivní {label} s tímto názvem už existuje.")
    return value
