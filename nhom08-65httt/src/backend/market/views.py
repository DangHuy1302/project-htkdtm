from django.shortcuts import render
from rest_framework import generics, permissions, serializers
from rest_framework.pagination import PageNumberPagination

from market.models import PriceObservation


def current_prices():
    return (
        PriceObservation.objects.filter(is_current=True)
        .select_related("series__source", "run__raw_document")
        .defer("run__raw_document__payload")
        .order_by("-effective_date", "series__code", "id")
    )


class PriceSerializer(serializers.ModelSerializer):
    source = serializers.CharField(source="series.source.code")
    source_name = serializers.CharField(source="series.source.name")
    source_url = serializers.URLField(source="run.source_url")
    collected_at = serializers.DateTimeField(source="run.collected_at")
    run_id = serializers.IntegerField(read_only=True)
    content_hash = serializers.CharField(source="run.raw_document.content_hash")
    series = serializers.CharField(source="series.code")
    series_name = serializers.CharField(source="series.name")
    commodity = serializers.CharField(source="series.commodity")
    price_type = serializers.CharField(source="series.price_type")
    market = serializers.CharField(source="series.market")
    contract_code = serializers.CharField(source="series.contract_code")
    currency = serializers.CharField(source="series.currency")
    unit = serializers.CharField(source="series.unit")

    class Meta:
        model = PriceObservation
        fields = (
            "id", "source", "source_name", "source_url", "collected_at", "content_hash",
            "run_id", "series", "series_name", "commodity", "price_type", "market",
            "contract_code", "currency", "unit", "effective_date", "value", "revision",
        )


class PricePagination(PageNumberPagination):
    page_size = 25


class PriceList(generics.ListAPIView):
    serializer_class = PriceSerializer
    pagination_class = PricePagination
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        prices = current_prices()
        for parameter, field in (
            ("source", "series__source__code"),
            ("series", "series__code"),
            ("price_type", "series__price_type"),
        ):
            if parameter in self.request.query_params:
                prices = prices.filter(**{field: self.request.query_params[parameter]})
        return prices


def price_page(request):
    return render(request, "market/prices.html", {"prices": current_prices()[:25]})
