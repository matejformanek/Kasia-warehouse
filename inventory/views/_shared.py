"""Cross-module view helpers (permissions, dodak-failed flag, safe next)."""

from django.utils.http import url_has_allowed_host_and_scheme

from accounts.permissions import require_vlastnik

from ..models import DodaciList, DodaciListEmailLog


def _dl_failed_at_current_version(dodaci_list: DodaciList, logs) -> bool:
    """True iff there is ≥1 FAILED log at current_version AND no SENT log
    at current_version. Matches the dashboard's "K vyřešení" rule so the
    detail-screen banner drops out the moment a re-send succeeds.
    """
    at_cv = [log for log in logs if log.version == dodaci_list.current_version]
    if not at_cv:
        return False
    any_sent = any(log.status == DodaciListEmailLog.Status.SENT for log in at_cv)
    if any_sent:
        return False
    return any(log.status == DodaciListEmailLog.Status.FAILED for log in at_cv)



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


