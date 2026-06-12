from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.home, name="home"),
    path("prijem/novy/", views.prijem_create, name="prijem_create"),
    path("vydej/novy/", views.vydej_create, name="vydej_create"),
    path(
        "_partials/line-row/",
        views.line_row_partial,
        name="line_row_partial",
    ),
    path(
        "_partials/stock-warn/",
        views.stock_warn_partial,
        name="stock_warn_partial",
    ),
    path("pohyby/<int:pk>/", views.movement_saved, name="movement_saved"),
]
