from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("o-nas/", views.o_nas, name="o_nas"),
    path("produkty/", views.produkty, name="produkty"),
    path("provozovny/", views.provozovny, name="provozovny"),
    path("kontakt/", views.kontakt, name="kontakt"),
    # Modern essentials — hand-rolled, right-sized for the public pages (0051/0058).
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap_xml"),
]
