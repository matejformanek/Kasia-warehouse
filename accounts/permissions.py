"""Role-permission helpers (decision 0068).

Single home for the vlastník gate, previously duplicated as two
``_require_vlastnik`` functions (inventory + accounts) plus inline
``if not request.user.is_vlastnik`` checks. Lives in ``accounts`` because
role logic belongs with the ``User`` model. Pairs with the global
``LoginRequiredMiddleware`` — these only add the vlastník-vs-obsluha gate.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied

DEFAULT_DENY = "Nemáte oprávnění k této akci."


def require_vlastnik(request, message: str | None = None) -> None:
    """Raise ``PermissionDenied`` (403) unless the user is a vlastník."""
    if not request.user.is_vlastnik:
        raise PermissionDenied(message or DEFAULT_DENY)


class RequireVlastnikMixin:
    """CBV mixin: 403 for non-vlastník users. Set ``vlastnik_denied_message``
    on the subclass to customize the message."""

    vlastnik_denied_message: str | None = None

    def dispatch(self, request, *args, **kwargs):
        require_vlastnik(request, self.vlastnik_denied_message)
        return super().dispatch(request, *args, **kwargs)
