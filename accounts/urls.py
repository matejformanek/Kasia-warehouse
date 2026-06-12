from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.user_index, name="user_index"),
    path("novy/", views.user_create, name="user_create"),
    path("<int:pk>/upravit/", views.user_edit, name="user_edit"),
    path(
        "<int:pk>/deaktivovat/",
        views.user_deactivate,
        name="user_deactivate",
    ),
    path(
        "<int:pk>/aktivovat/",
        views.user_reactivate,
        name="user_reactivate",
    ),
    path(
        "<int:pk>/reset-hesla/",
        views.user_password_reset,
        name="user_password_reset",
    ),
]
