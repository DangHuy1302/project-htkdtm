from django.db.models import F
from django.shortcuts import render

from market.models import PriceSeries
from market.views import current_prices


def overview(request):
    ico_price = (
        current_prices()
        .filter(
            series__source__code="ico",
            series__code="robustas",
            series__price_type=PriceSeries.PriceType.INDICATOR,
            value__gt=0,
        )
        .order_by("-effective_date", "-pk")
        .values(
            "value", "effective_date",
            unit=F("series__unit"),
            source_name=F("series__source__name"),
            source_url=F("run__source_url"),
        )
        .first()
    )
    return render(request, "cafeflow/overview.html", {"ico_price": ico_price})
