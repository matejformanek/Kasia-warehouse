from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("o-nas/", views.o_nas, name="o_nas"),
    path("provozovny/", views.provozovny, name="provozovny"),
    path("kontakt/", views.kontakt, name="kontakt"),
    path("kontakt/odeslano/", views.kontakt_ok, name="kontakt_ok"),
    # Modern essentials — hand-rolled, right-sized for four pages (0050).
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap_xml"),
]
