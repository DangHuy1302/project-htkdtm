from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from market import ico
from market.models import CollectionRun, RawDocument, Source

TEST_INTERNAL_TOKEN = "test-only-internal-token-value"


class InternalIcoCollectViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = Source.objects.create(
            code="ico", name="International Coffee Organization (ICO)"
        )
        cls.url = reverse("internal-collect-ico")

    def setUp(self):
        self.client = APIClient()

    def _auth_headers(self, token=TEST_INTERNAL_TOKEN):
        return {"HTTP_X_INTERNAL_TOKEN": token}

    def test_get_method_is_not_allowed(self):
        response = self.client.get(self.url, **self._auth_headers())
        self.assertEqual(response.status_code, 405)

    def test_returns_503_when_internal_token_is_not_configured(self):
        with (
            patch.dict("os.environ", {"N8N_INTERNAL_TOKEN": ""}, clear=False),
            patch("market.collection.collect_ico") as mock_collect,
        ):
            response = self.client.post(self.url, {}, format="json", **self._auth_headers())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "internal_token_not_configured")
        mock_collect.assert_not_called()

    def test_rejects_missing_or_invalid_token_with_403(self):
        with (
            patch.dict("os.environ", {"N8N_INTERNAL_TOKEN": TEST_INTERNAL_TOKEN}, clear=False),
            patch("market.collection.collect_ico") as mock_collect,
        ):
            missing = self.client.post(self.url, {}, format="json")
            wrong = self.client.post(self.url, {}, format="json", **self._auth_headers("wrong-token"))

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(missing.json()["code"], "forbidden")
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(wrong.json()["code"], "forbidden")
        mock_collect.assert_not_called()

    def test_rejects_arbitrary_url_and_invalid_month_with_400(self):
        invalid_bodies = [
            ({"url": "https://example.com/custom.pdf"}, "url"),
            ({"month": "2026/10"}, "month"),
            ({"month": "2026-13"}, "month"),
            (["2026-10"], "non_field_errors"),
        ]
        with (
            patch.dict("os.environ", {"N8N_INTERNAL_TOKEN": TEST_INTERNAL_TOKEN}, clear=False),
            patch("market.collection.collect_ico") as mock_collect,
        ):
            for body, error_field in invalid_bodies:
                with self.subTest(body=body):
                    response = self.client.post(
                        self.url, body, format="json", **self._auth_headers()
                    )
                    self.assertEqual(response.status_code, 400)
                    payload = response.json()
                    self.assertEqual(payload["code"], "invalid_payload")
                    self.assertIn(error_field, payload["fields"])

        mock_collect.assert_not_called()

    def test_triggers_current_ico_collection_and_returns_run_summary(self):
        now = datetime(2026, 11, 29, 1, 30, 0, tzinfo=dt_timezone.utc)
        raw = RawDocument.objects.create(
            source=self.source,
            source_url=ico.CURRENT_URL,
            content_hash="a" * 64,
            payload=b"%PDF-1.4",
            first_collected_at=now,
        )
        run = CollectionRun.objects.create(
            source=self.source,
            source_url=ico.CURRENT_URL,
            raw_document=raw,
            collected_at=now,
            finished_at=now,
            status=CollectionRun.Status.SUCCEEDED,
            http_status=200,
            rows_received=19,
            created_count=1,
            revised_count=0,
            unchanged_count=18,
            rejected_count=0,
        )

        with (
            patch.dict("os.environ", {"N8N_INTERNAL_TOKEN": TEST_INTERNAL_TOKEN}, clear=False),
            patch("market.collection.collect_ico", return_value=run) as mock_collect,
        ):
            response = self.client.post(self.url, {}, format="json", **self._auth_headers())

        self.assertEqual(response.status_code, 200)
        mock_collect.assert_called_once_with(ico.CURRENT_URL, None)
        data = response.json()
        self.assertEqual(data["run_id"], run.pk)
        self.assertEqual(data["source"], "ico")
        self.assertEqual(data["status"], "succeeded")
        self.assertEqual(data["http_status"], 200)
        self.assertEqual(data["raw_document_id"], raw.pk)
        self.assertEqual(data["rows_received"], 19)
        self.assertEqual(data["created_count"], 1)
        self.assertEqual(data["unchanged_count"], 18)
        self.assertTrue(data["started_at"].endswith("+07:00"))
        self.assertTrue(data["finished_at"].endswith("+07:00"))

    def test_triggers_archive_month_collection_when_valid_month_provided(self):
        now = datetime(2026, 11, 29, 1, 30, 0, tzinfo=dt_timezone.utc)
        expected_url = ico.ARCHIVE_URL.format(year=2026, month=10)
        run = CollectionRun.objects.create(
            source=self.source,
            source_url=expected_url,
            collected_at=now,
            finished_at=now,
            status=CollectionRun.Status.SUCCEEDED,
            http_status=200,
        )

        with (
            patch.dict("os.environ", {"N8N_INTERNAL_TOKEN": TEST_INTERNAL_TOKEN}, clear=False),
            patch("market.collection.collect_ico", return_value=run) as mock_collect,
        ):
            response = self.client.post(
                self.url, {"month": "2026-10"}, format="json", **self._auth_headers()
            )

        self.assertEqual(response.status_code, 200)
        mock_collect.assert_called_once_with(expected_url, (2026, 10))

    def test_returns_409_when_advisory_lock_is_already_held(self):
        with (
            patch.dict("os.environ", {"N8N_INTERNAL_TOKEN": TEST_INTERNAL_TOKEN}, clear=False),
            patch(
                "market.collection.collect_ico",
                side_effect=RuntimeError("An ICO collection is already running"),
            ),
        ):
            response = self.client.post(self.url, {}, format="json", **self._auth_headers())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "collection_locked")

    def test_returns_502_when_upstream_collection_fails(self):
        with (
            patch.dict("os.environ", {"N8N_INTERNAL_TOKEN": TEST_INTERNAL_TOKEN}, clear=False),
            patch(
                "market.collection.collect_ico",
                side_effect=ValueError("ICO response is not a PDF"),
            ),
        ):
            response = self.client.post(self.url, {}, format="json", **self._auth_headers())

        self.assertEqual(response.status_code, 502)
        payload = response.json()
        self.assertEqual(payload["code"], "collection_failed")
        self.assertIn("ICO response is not a PDF", payload["detail"])
