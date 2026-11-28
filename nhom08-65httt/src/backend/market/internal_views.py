import hmac
import os
import re
from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from market import collection, ico

MONTH_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}$")


def _error_response(http_status: int, code: str, detail: str, fields: dict | None = None) -> Response:
    payload: dict[str, object] = {"code": code, "detail": detail}
    if fields is not None:
        payload["fields"] = fields
    return Response(payload, status=http_status)


def _format_timestamp(value):
    return timezone.localtime(value).isoformat() if value is not None else None


def _parse_collection_target(data) -> tuple[str, tuple[int, int] | None]:
    if data in (None, {}):
        return ico.CURRENT_URL, None
    if not isinstance(data, dict):
        raise ValueError({"non_field_errors": ["Request body must be a JSON object."]})

    unknown_keys = sorted(key for key in data.keys() if key != "month")
    if unknown_keys:
        raise ValueError({key: ["This field is not allowed."] for key in unknown_keys})

    month_raw = data.get("month")
    if month_raw in (None, ""):
        return ico.CURRENT_URL, None
    if not isinstance(month_raw, str) or not MONTH_PATTERN.fullmatch(month_raw):
        raise ValueError({"month": ["month must be a valid YYYY-MM."]})

    try:
        archive_date = date.fromisoformat(f"{month_raw}-01")
    except ValueError as error:
        raise ValueError({"month": ["month must be a valid YYYY-MM."]}) from error

    expected_month = (archive_date.year, archive_date.month)
    url = ico.ARCHIVE_URL.format(year=archive_date.year, month=archive_date.month)
    return url, expected_month


class InternalIcoCollectView(APIView):
    """Machine-to-machine endpoint for n8n to trigger the existing ICO collector."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        expected_token = os.environ.get("N8N_INTERNAL_TOKEN", "")
        if not expected_token:
            return _error_response(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "internal_token_not_configured",
                "N8N_INTERNAL_TOKEN is not configured.",
            )

        provided_token = request.headers.get("X-Internal-Token", "")
        if not provided_token or not hmac.compare_digest(provided_token, expected_token):
            return _error_response(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "Invalid or missing internal collector token.",
            )

        try:
            source_url, expected_month = _parse_collection_target(request.data)
        except ValueError as error:
            return _error_response(
                status.HTTP_400_BAD_REQUEST,
                "invalid_payload",
                "Invalid request payload.",
                fields=error.args[0],
            )

        try:
            run = collection.collect_ico(source_url, expected_month)
        except RuntimeError as error:
            if "already running" in str(error).lower():
                return _error_response(
                    status.HTTP_409_CONFLICT,
                    "collection_locked",
                    "An ICO collection is already running.",
                )
            return _error_response(
                status.HTTP_502_BAD_GATEWAY,
                "collection_failed",
                f"{type(error).__name__}: {error}",
            )
        except Exception as error:
            return _error_response(
                status.HTTP_502_BAD_GATEWAY,
                "collection_failed",
                f"{type(error).__name__}: {error}",
            )

        return Response(
            {
                "run_id": run.pk,
                "source": run.source.code,
                "status": run.status,
                "http_status": run.http_status,
                "raw_document_id": run.raw_document_id,
                "rows_received": run.rows_received,
                "created_count": run.created_count,
                "revised_count": run.revised_count,
                "unchanged_count": run.unchanged_count,
                "rejected_count": run.rejected_count,
                "started_at": _format_timestamp(run.started_at),
                "finished_at": _format_timestamp(run.finished_at),
            },
            status=status.HTTP_200_OK,
        )
