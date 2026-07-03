"""Movement-form shared helpers.

Package-local to ``views/movements/`` (imported as ``._shared``). Distinct from
the cross-view ``inventory/views/_shared`` module (``.._shared``, which holds
``_safe_next`` / ``_require_vlastnik`` / …). These are the line-building /
error-surfacing / recent-list helpers the create + edit flows share.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

from ...models import Movement, MovementLine

_RECENT_MOVEMENTS_ON_FORM_LIMIT = 5


def _recent_movements_for_form(user, kind: str):
    """Last N movements of the given kind, scoped to obsluha's branch
    when applicable. Rendered under the create form so operators can
    eyeball what happened on this branch in the last few days without
    leaving the page."""
    qs = (
        Movement.objects.filter(kind=kind, status=Movement.Status.DONE)
        .select_related("branch", "dodavatel", "odberatel", "dodaci_list")
        .prefetch_related("lines__product")
        .order_by("-date_issued", "-id")
    )
    if user.is_obsluha and user.branch_id:
        qs = qs.filter(branch_id=user.branch_id)
    return list(qs[:_RECENT_MOVEMENTS_ON_FORM_LIMIT])


def _build_lines(formset) -> list[MovementLine]:
    lines: list[MovementLine] = []
    for line_form in formset:
        data = line_form.cleaned_data
        if not data or data.get("DELETE"):
            continue
        if data.get("product") is None or data.get("quantity_kg") in (None, ""):
            continue
        lines.append(
            MovementLine(
                product=data["product"],
                quantity_kg=data["quantity_kg"],
                sarze=data.get("sarze", "") or "",
                expiry=data.get("expiry"),
                note=data.get("note", "") or "",
            )
        )
    return lines


def _push_validation_error_to_formset(exc: ValidationError, formset) -> None:
    """Surface a service-layer ValidationError as a non-form error so
    the operator sees it above the line table."""
    msgs: list[str] = []
    if hasattr(exc, "message_dict"):
        for field, field_msgs in exc.message_dict.items():
            for msg in field_msgs:
                msgs.append(f"{field}: {msg}")
    else:
        msgs.extend(exc.messages)
    formset._non_form_errors = formset.error_class(msgs)
