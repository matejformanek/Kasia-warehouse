from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.urls import include, path, reverse_lazy

from web.content import COMPANY, NAV


@login_not_required
def healthz(_request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    # The /navrhy/ design-review gallery (decision 0047) was retired per 0067 —
    # the mockups stay in the repo (design-options/) but are no longer served.
    # --- Warehouse app — fully login-gated, all under /sklad/ ----------------
    # Per context/decisions/0050-public-site-and-sklad-split.md. View names are
    # left unchanged (login, logout, password_*, the inventory/accounts
    # namespaces), so every {% url %} / reverse() / LOGIN_URL re-resolves to
    # the new /sklad/ paths automatically. The flat "sklad/..." prefixes (no
    # wrapper namespace) keep the bare auth names at the root namespace.
    path(
        "sklad/prihlaseni/",
        # Public-branded login: extends web/base.html so it carries the marketing
        # chrome (decision 0050–0052 refinement). redirect_authenticated_user
        # sends an already-logged-in visitor straight to LOGIN_REDIRECT_URL
        # (inventory:home). extra_context feeds the public header/footer (rendered
        # on both GET and invalid POST).
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
            extra_context={"company": COMPANY, "nav": NAV, "active": ""},
        ),
        name="login",
    ),
    path("sklad/odhlaseni/", auth_views.LogoutView.as_view(), name="logout"),
    # Password reset flow — public (the magic link arrives by e-mail). Used
    # both by the operator "Resetovat heslo" admin action and for any future
    # self-service reset surface.
    path(
        "sklad/reset-hesla/",
        login_not_required(
            auth_views.PasswordResetView.as_view(
                template_name="registration/password_reset_form.html",
                email_template_name="registration/password_reset_email.html",
                subject_template_name="registration/password_reset_subject.txt",
                success_url=reverse_lazy("password_reset_done"),
            )
        ),
        name="password_reset",
    ),
    path(
        "sklad/reset-hesla/odeslano/",
        login_not_required(
            auth_views.PasswordResetDoneView.as_view(
                template_name="registration/password_reset_done.html",
            )
        ),
        name="password_reset_done",
    ),
    path(
        "sklad/reset-hesla/potvrzeni/<uidb64>/<token>/",
        login_not_required(
            auth_views.PasswordResetConfirmView.as_view(
                template_name="registration/password_reset_confirm.html",
                success_url=reverse_lazy("password_reset_complete"),
            )
        ),
        name="password_reset_confirm",
    ),
    path(
        "sklad/reset-hesla/hotovo/",
        login_not_required(
            auth_views.PasswordResetCompleteView.as_view(
                template_name="registration/password_reset_complete.html",
            )
        ),
        name="password_reset_complete",
    ),
    # In-app self-service password change for already-authenticated users
    # (Pass 8). We mount only these two views (not django.contrib.auth.urls
    # wholesale) so the custom login/logout routes above stay authoritative.
    path(
        "sklad/zmena-hesla/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url=reverse_lazy("password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "sklad/zmena-hesla/hotovo/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),
    path("sklad/uzivatele/", include("accounts.urls", namespace="accounts")),
    path("sklad/", include("inventory.urls", namespace="inventory")),
    # --- Public marketing site at root — MUST stay last (per 0050) ----------
    # Mounted in Phase 3 once the `web` app exists. Until then "/" 404s and
    # only /sklad/* serves the app.
    path("", include("web.urls", namespace="web")),
]
