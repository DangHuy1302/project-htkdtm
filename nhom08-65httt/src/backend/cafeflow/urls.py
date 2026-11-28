from django.urls import include, path
from wagtail.admin import urls as wagtailadmin_urls

from market.views import PriceList, price_page

urlpatterns = [
    path("", price_page, name="price-page"),
    path("api/v1/prices/", PriceList.as_view(), name="price-list"),
    path("cms/", include(wagtailadmin_urls)),
]
