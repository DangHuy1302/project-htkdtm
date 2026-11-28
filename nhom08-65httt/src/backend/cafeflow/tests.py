from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from market.models import CollectionRun, PriceObservation, PriceSeries, Source


class OverviewIcoKpiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = Source.objects.create(code="ico", name="International Coffee Organization (ICO)")
        cls.series = PriceSeries.objects.create(
            source=cls.source,
            code="robustas",
            name="Robustas",
            commodity="coffee",
            price_type=PriceSeries.PriceType.INDICATOR,
            market="global",
            currency="USD",
            unit="usd_cent_per_lb",
        )
        cls.source_url = "https://ico.org/documents/prices/I-CIP_10.2026.pdf"
        cls.collection_run = CollectionRun.objects.create(
            source=cls.source,
            source_url=cls.source_url,
            collected_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            status=CollectionRun.Status.SUCCEEDED,
        )

    def test_no_observations_shows_empty_state(self):
        response = self.client.get(reverse("overview"))

        self.assertContains(response, "Chưa có dữ liệu")
        self.assertIsNone(response.context["ico_price"])
        self.assertNotContains(response, self.source_url)

    def test_shows_decimal_value_effective_date_and_actual_source(self):
        PriceObservation.objects.create(
            series=self.series, run=self.collection_run, effective_date=date(2026, 10, 30), value=Decimal("156.8400"),
        )

        with self.assertNumQueries(1):
            response = self.client.get(reverse("overview"))

        self.assertEqual(response.context["ico_price"]["value"], Decimal("156.8400"))
        self.assertContains(response, "156,8400")
        self.assertContains(response, "US cents/lb")
        self.assertContains(response, '<time datetime="2026-10-30">30/10/2026</time>', html=True)
        self.assertContains(response, f'<a href="{self.source_url}">{self.source.name}</a>', html=True)
        self.assertContains(response, "Giá chỉ báo Robustas của ICO")
        self.assertContains(response, "Giá kỳ hạn ICE")
        self.assertContains(response, f'href="{reverse("price-page")}"')

    def test_uses_latest_effective_date_even_when_older_price_was_collected_later(self):
        PriceObservation.objects.create(
            series=self.series, run=self.collection_run, effective_date=date(2026, 10, 30), value=Decimal("156.84"),
        )
        later_run = CollectionRun.objects.create(
            source=self.source,
            source_url=self.source_url,
            collected_at=datetime(2026, 11, 2, tzinfo=timezone.utc),
            status=CollectionRun.Status.SUCCEEDED,
        )
        PriceObservation.objects.create(
            series=self.series, run=later_run, effective_date=date(2026, 10, 29), value=Decimal("155.49"),
        )

        response = self.client.get(reverse("overview"))

        self.assertEqual(response.context["ico_price"]["effective_date"], date(2026, 10, 30))
        self.assertEqual(response.context["ico_price"]["value"], Decimal("156.84"))

    def test_uses_current_revision_instead_of_superseded_row(self):
        effective_date = date(2026, 10, 30)
        PriceObservation.objects.create(
            series=self.series, run=self.collection_run, effective_date=effective_date, value=Decimal("156.84"), revision=2,
        )
        PriceObservation.objects.create(
            series=self.series, run=self.collection_run, effective_date=effective_date, value=Decimal("159.12"), is_current=False,
        )

        response = self.client.get(reverse("overview"))

        self.assertEqual(response.context["ico_price"]["value"], Decimal("156.84"))

    def test_does_not_use_another_source_or_series(self):
        other_source = Source.objects.create(code="other", name="Other source")
        other_run = CollectionRun.objects.create(source=other_source, source_url="https://example.com/price")
        other_robustas = PriceSeries.objects.create(
            source=other_source, code="robustas", name="Robustas",
            price_type=PriceSeries.PriceType.INDICATOR, currency="USD", unit="usd_cent_per_lb",
        )
        composite = PriceSeries.objects.create(
            source=self.source, code="i-cip", name="I-CIP",
            price_type=PriceSeries.PriceType.INDICATOR, currency="USD", unit="usd_cent_per_lb",
        )
        PriceObservation.objects.create(
            series=other_robustas, run=other_run, effective_date=date(2026, 10, 30), value=Decimal("160"),
        )
        PriceObservation.objects.create(
            series=composite, run=self.collection_run, effective_date=date(2026, 10, 30), value=Decimal("161"),
        )

        response = self.client.get(reverse("overview"))

        self.assertContains(response, "Chưa có dữ liệu")
        self.assertIsNone(response.context["ico_price"])

    def test_does_not_use_non_indicator_robustas(self):
        self.series.price_type = PriceSeries.PriceType.FUTURES_REPUBLISHED
        self.series.save(update_fields=["price_type"])
        PriceObservation.objects.create(
            series=self.series, run=self.collection_run, effective_date=date(2026, 10, 30), value=Decimal("160"),
        )

        response = self.client.get(reverse("overview"))

        self.assertContains(response, "Chưa có dữ liệu")
        self.assertIsNone(response.context["ico_price"])

    def test_non_positive_prices_are_rejected_and_do_not_appear(self):
        for value in (Decimal("0"), Decimal("-5")):
            with self.subTest(value=value), self.assertRaises(IntegrityError), transaction.atomic():
                PriceObservation.objects.create(
                    series=self.series, run=self.collection_run, effective_date=date(2026, 10, 30), value=value,
                )

        response = self.client.get(reverse("overview"))

        self.assertContains(response, "Chưa có dữ liệu")
        self.assertIsNone(response.context["ico_price"])
