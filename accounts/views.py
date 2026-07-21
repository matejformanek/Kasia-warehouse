"""Správa uživatelů — screen 13.

Owner-only (`is_vlastnik`). Branch staff (`is_obsluha`) get 403.

Per `context/screens/13-sprava-uzivatelu.md`:
- index — table of all accounts with role / branch / active marker
- create — inline form
- edit — name, role, branch (e-mail read-only)
- deactivate / reactivate — preserves history attribution
- password reset — fires Django's password-reset e-mail
- no deletion — explicit business rule
"""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    LoggedPasswordResetForm,
    UserCreateForm,
    UserEditForm,
    _count_other_active_vlastnik,
)
from .models import User
from .permissions import require_vlastnik

USER_BUDGET = 20  # per context/people-and-roles.md § Capacity


def _require_vlastnik(request) -> None:
    """Only vlastník-level users may reach screen 13."""
    require_vlastnik(request, "Nemáte oprávnění spravovat uživatele.")


@require_GET
def user_index(request):
    _require_vlastnik(request)
    users = (
        User.objects.all()
        .select_related("branch")
        .order_by("-is_active", "email")
    )
    active_count = User.objects.filter(is_active=True).count()
    return render(
        request,
        "accounts/user_admin_index.html",
        {
            "users": users,
            "active_count": active_count,
            "budget": USER_BUDGET,
        },
    )


def user_create(request):
    _require_vlastnik(request)
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Per 0082: always e-mail the new user their login + generated
            # password. The send never re-raises (send_and_log swallows), so a
            # mail outage can't block user creation. Lazy import avoids pulling
            # the inventory services at module import time.
            from inventory.models import EmailLog
            from inventory.services import send_new_user_credentials

            log = send_new_user_credentials(
                user, user._raw_password, sent_by=request.user
            )
            messages.success(
                request, f"Uživatel {user.email} byl přidán."
            )
            # Surface a swallowed mail failure (send_and_log never re-raises) so
            # the vlastník knows the credentials didn't go out and can re-send.
            if log.status == EmailLog.Status.FAILED:
                messages.warning(
                    request,
                    "E-mail s přihlašovacími údaji se nepodařilo odeslat — "
                    "zkontrolujte «E-maily» a použijte «Reset hesla».",
                )
            return redirect("accounts:user_index")
    else:
        form = UserCreateForm()
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "mode": "create"},
    )


def user_edit(request, pk: int):
    _require_vlastnik(request)
    target = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserEditForm(
            request.POST, instance=target, editor=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Změny uloženy.")
            return redirect("accounts:user_index")
    else:
        form = UserEditForm(instance=target, editor=request.user)
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "mode": "edit", "target": target},
    )


@require_POST
def user_deactivate(request, pk: int):
    _require_vlastnik(request)
    target = get_object_or_404(User, pk=pk)
    if not target.is_active:
        return redirect("accounts:user_index")
    # Last-owner protection.
    if target.is_vlastnik and _count_other_active_vlastnik(target.pk) == 0:
        messages.error(
            request,
            "Nelze deaktivovat posledního aktivního vlastníka.",
        )
        return redirect("accounts:user_index")
    target.is_active = False
    target.save(update_fields=["is_active"])
    messages.success(request, f"Uživatel {target.email} byl deaktivován.")
    return redirect("accounts:user_index")


@require_POST
def user_reactivate(request, pk: int):
    _require_vlastnik(request)
    target = get_object_or_404(User, pk=pk)
    if target.is_active:
        return redirect("accounts:user_index")
    target.is_active = True
    target.save(update_fields=["is_active"])
    messages.success(request, f"Uživatel {target.email} byl aktivován.")
    return redirect("accounts:user_index")


@require_POST
def user_password_reset(request, pk: int):
    _require_vlastnik(request)
    target = get_object_or_404(User, pk=pk)
    if not target.is_active:
        messages.error(
            request,
            "Nelze resetovat heslo deaktivovanému uživateli.",
        )
        return redirect("accounts:user_index")
    form = LoggedPasswordResetForm({"email": target.email})
    if form.is_valid():
        # Per 0083: log the reset in the „E-maily" outbox + send from the
        # configured Settings sender (see LoggedPasswordResetForm).
        form.sent_by = request.user
        form.save(
            request=request,
            use_https=request.is_secure(),
            from_email=None,
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        )
        # send_and_log swallows SMTP errors; surface a failed send instead of a
        # misleading success (per PR #42 review).
        from inventory.models import EmailLog

        if form.email_log is not None and form.email_log.status == EmailLog.Status.FAILED:
            messages.warning(
                request,
                f"E-mail pro reset hesla se nepodařilo odeslat na "
                f"{target.email} — zkontrolujte «E-maily».",
            )
        else:
            messages.success(
                request,
                f"Odkaz pro reset hesla byl odeslán na {target.email}.",
            )
    else:
        messages.error(
            request,
            "E-mail uživatele není platný — reset nelze odeslat.",
        )
    return redirect("accounts:user_index")
