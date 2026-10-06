"""Cross-module view helpers (permissions, dodak-failed flag, safe next)."""

from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.permissions import require_vlastnik

from ..models import DodaciList, EmailLog


def _dl_failed_at_current_version(dodaci_list: DodaciList, logs) -> bool:
    """True iff there is ≥1 FAILED log at current_version AND no SENT log
    at current_version. Matches the dashboard's "K vyřešení" rule so the
    detail-screen banner drops out the moment a re-send succeeds.
    """
    at_cv = [
        log for log in logs if log.dodaci_version == dodaci_list.current_version
    ]
    if not at_cv:
        return False
    any_sent = any(log.status == EmailLog.Status.SENT for log in at_cv)
    if any_sent:
        return False
    return any(log.status == EmailLog.Status.FAILED for log in at_cv)



DENY_OTHER_BRANCH_MESSAGE = "Nemáte oprávnění k datům jiné pobočky."


def deny_other_branch(request, branch_id, message: str = DENY_OTHER_BRANCH_MESSAGE):
    """Return a 403 response if an obsluha reaches another branch's object.

    The shared own-branch guard (decision 0040 dodáky, extended to movements by
    0104). ``None`` means allowed — callers do
    ``if (denied := deny_other_branch(...)) is not None: return denied``.
    An obsluha without a branch is denied everything branch-owned.
    """
    if request.user.is_obsluha and request.user.branch_id != branch_id:
        return HttpResponse(
            message, status=403, content_type="text/plain; charset=utf-8"
        )
    return None


def _require_vlastnik(request) -> None:
    require_vlastnik(request, "Nemáte oprávnění upravovat nastavení.")



def _safe_next(request, default_url: str) -> str:
    """Return a safe internal `next` (POST first, then GET query) if present
    and same-site, else default."""
    candidate = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default_url


