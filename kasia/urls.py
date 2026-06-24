from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.urls import include, path, reverse_lazy


@login_not_required
def healthz(_request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Password reset flow — public (the magic link arrives by e-mail). Used
    # both by the operator "Resetovat heslo" admin action and for any future
    # self-service reset surface.
    path(
        "reset-hesla/",
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
        "reset-hesla/odeslano/",
        login_not_required(
            auth_views.PasswordResetDoneView.as_view(
                template_name="registration/password_reset_done.html",
            )
        ),
        name="password_reset_done",
    ),
    path(
        "reset-hesla/potvrzeni/<uidb64>/<token>/",
        login_not_required(
            auth_views.PasswordResetConfirmView.as_view(
                template_name="registration/password_reset_confirm.html",
                success_url=reverse_lazy("password_reset_complete"),
            )
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset-hesla/hotovo/",
        login_not_required(
            auth_views.PasswordResetCompleteView.as_view(
                template_name="registration/password_reset_complete.html",
            )
        ),
        name="password_reset_complete",
    ),
    # In-app self-service password change for already-authenticated users.
    # Lives under /accounts/ to mirror Django's auth convention; we mount
    # only these two views (not django.contrib.auth.urls wholesale) so the
    # custom /login/ + /logout/ routes above stay authoritative.
    path(
        "accounts/zmena-hesla/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url=reverse_lazy("password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "accounts/zmena-hesla/hotovo/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),
    path("uzivatele/", include("accounts.urls", namespace="accounts")),
    path("", include("inventory.urls", namespace="inventory")),
]
