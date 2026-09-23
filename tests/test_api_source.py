"""
tests/test_api_source.py
Unit tests for HTTP/API series import (stage P1.2 of DOCS/ROADMAP.md).

Acceptance criteria covered:
- success JSON list → Dataset with correct year/value mapping and provenance;
- timeout → human-readable ApiSourceError (bounded, no hang);
- HTTP 4xx → ApiSourceError without retries on the client error;
- HTTP 5xx → ApiSourceError after bounded retries;
- field-map (explicit year/value keys) works for non-aliased payloads;
- offline / connection error → ApiSourceError, offline mode does not break P0;
- provenance on Dataset.metadata round-trips through ProjectService `.hsp`.

All tests use mocks: no real network.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from core.domain import Dataset, DatasetType
from core.services import DataQualityService, ProjectService, QualityPipeline
from core.services.api_source import (
    ApiSourceError,
    DataSource,
    FieldMap,
    HttpApiSource,
)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def make_response(
    *,
    status_code: int = 200,
    json_data: object | None = None,
    json_error: bool = False,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if json_error:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = json_data
    return response


SAMPLE_LIST = [
    {"year": 1990, "value": 10.5},
    {"year": 1991, "value": 11.0},
    {"year": 1992, "value": 9.8},
    {"year": 1994, "value": 12.1},  # gap: 1993 missing
    {"year": 1995, "value": 10.0},
]


def source(session: MagicMock, **kwargs) -> HttpApiSource:
    kwargs.setdefault("timeout", 2.0)
    kwargs.setdefault("retries", 1)
    return HttpApiSource("https://api.example.test/series", session=session, **kwargs)


# ----------------------------------------------------------------------
# Protocol
# ----------------------------------------------------------------------
def test_http_api_source_satisfies_data_source_protocol():
    src = source(MagicMock())
    assert isinstance(src, DataSource)


def test_empty_base_url_rejected():
    with pytest.raises(ApiSourceError, match="URL"):
        HttpApiSource("")


# ----------------------------------------------------------------------
# Success path
# ----------------------------------------------------------------------
def test_success_list_builds_dataset_with_provenance():
    session = MagicMock()
    session.get.return_value = make_response(json_data=SAMPLE_LIST)
    src = source(session)

    dataset = src.fetch_series("post-1", name="Пост API", location="р. Тест")

    assert isinstance(dataset, Dataset)
    assert dataset.name == "Пост API"
    assert dataset.dataset_type == DatasetType.OBSERVED
    assert dataset.unit == "m³/s"
    assert dataset.location == "р. Тест"
    assert dataset.length == 5
    assert dataset.start_year == 1990
    assert dataset.end_year == 1995
    assert dataset.data[1990] == pytest.approx(10.5)
    assert 1993 not in dataset.data  # gap preserved, not filled

    meta = dataset.metadata
    assert meta["source"] == "http_api"
    assert meta["post_id"] == "post-1"
    assert meta["source_url"].endswith("/post-1")
    assert "fetched_at" in meta
    session.get.assert_called_once()
    # timeout passed through to requests
    assert session.get.call_args.kwargs["timeout"] == 2.0


def test_nested_series_key_and_parallel_arrays():
    session = MagicMock()
    session.get.return_value = make_response(
        json_data={"series": [{"year": 2000, "value": 5.0}]}
    )
    ds = source(session).fetch_series("n1")
    assert ds.data[2000] == pytest.approx(5.0)

    session = MagicMock()
    session.get.return_value = make_response(
        json_data={"years": [2001, 2002], "values": [6.0, 7.5]}
    )
    ds2 = source(session).fetch_series("n2")
    assert ds2.data[2001] == pytest.approx(6.0)
    assert ds2.data[2002] == pytest.approx(7.5)


def test_empty_post_id_rejected():
    src = source(MagicMock())
    with pytest.raises(ApiSourceError, match="идентификатор"):
        src.fetch_series("  ")


def test_empty_payload_rejected():
    session = MagicMock()
    session.get.return_value = make_response(json_data=[])
    with pytest.raises(ApiSourceError, match="не вернул данных"):
        source(session).fetch_series("empty")


# ----------------------------------------------------------------------
# Timeouts / connection errors (bounded, human-readable)
# ----------------------------------------------------------------------
def test_timeout_raises_readable_error():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("read timed out")
    src = source(session, retries=1)

    with pytest.raises(ApiSourceError) as exc_info:
        src.fetch_series("t1")

    message = str(exc_info.value)
    assert "таймаут" in message.lower() or "не ответил" in message.lower()
    assert "2" in message or "с" in message  # mentions the timeout budget
    assert session.get.call_count == 2  # retries=1 → 1 initial + 1 retry


def test_connection_error_raises_readable_error():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("refused")
    with pytest.raises(ApiSourceError, match="Нет соединения"):
        source(session, retries=0).fetch_series("c1")
    assert session.get.call_count == 1


def test_retry_recovers_from_transient_failure():
    session = MagicMock()
    session.get.side_effect = [
        requests.exceptions.ConnectionError("blip"),
        make_response(json_data=SAMPLE_LIST),
    ]
    ds = source(session, retries=1).fetch_series("r1")
    assert ds.length == 5
    assert session.get.call_count == 2


# ----------------------------------------------------------------------
# HTTP status codes
# ----------------------------------------------------------------------
def test_4xx_no_retry():
    session = MagicMock()
    session.get.return_value = make_response(status_code=404)
    with pytest.raises(ApiSourceError) as exc_info:
        source(session, retries=3).fetch_series("missing")
    assert "404" in str(exc_info.value)
    assert session.get.call_count == 1  # client errors are not retried


def test_5xx_retries_then_fails():
    session = MagicMock()
    session.get.return_value = make_response(status_code=503)
    with pytest.raises(ApiSourceError) as exc_info:
        source(session, retries=2).fetch_series("down")
    assert "503" in str(exc_info.value)
    assert session.get.call_count == 3  # initial + 2 retries


def test_non_json_200_rejected():
    session = MagicMock()
    session.get.return_value = make_response(json_error=True)
    with pytest.raises(ApiSourceError, match="не JSON"):
        source(session).fetch_series("bad")


# ----------------------------------------------------------------------
# Field map (non-aliased keys)
# ----------------------------------------------------------------------
def test_field_map_explicit_keys():
    session = MagicMock()
    session.get.return_value = make_response(
        json_data=[
            {"yr": 1990, "q_m3s": 10.0},
            {"yr": 1991, "q_m3s": 11.5},
        ]
    )
    src = source(
        session,
        field_map=FieldMap(year_key="yr", value_key="q_m3s"),
    )
    ds = src.fetch_series("fm1")
    assert ds.data[1990] == pytest.approx(10.0)
    assert ds.metadata["field_map"]["year_key"] == "yr"


def test_field_map_missing_keys_rejected():
    session = MagicMock()
    session.get.return_value = make_response(json_data=[{"a": 1}])
    src = source(
        session,
        field_map=FieldMap(year_key="yr", value_key="q"),
    )
    with pytest.raises(ApiSourceError, match="маппинга"):
        src.fetch_series("fm2")


def test_duplicate_year_rejected():
    session = MagicMock()
    session.get.return_value = make_response(
        json_data=[
            {"year": 1990, "value": 1.0},
            {"year": 1990, "value": 2.0},
        ]
    )
    with pytest.raises(ApiSourceError, match="Дубликат"):
        source(session).fetch_series("dup")


def test_year_out_of_range_rejected():
    session = MagicMock()
    session.get.return_value = make_response(
        json_data=[{"year": 1200, "value": 1.0}]
    )
    with pytest.raises(ApiSourceError, match="1800"):
        source(session).fetch_series("yr")


# ----------------------------------------------------------------------
# Pipeline integration: API → quality → .hsp (offline-safe, no network)
# ----------------------------------------------------------------------
def test_api_dataset_roundtrips_through_project_and_quality(tmp_path: Path):
    session = MagicMock()
    session.get.return_value = make_response(json_data=SAMPLE_LIST)
    dataset = source(session).fetch_series("post-rt", name="Ряд API")

    # Quality pipeline: report-only, does not mutate provenance.
    gate = QualityPipeline(quality=DataQualityService()).after_import(dataset)
    assert gate.report.n_points == 5
    assert any(i.code == "DATA_GAPS" for i in gate.report.issues)
    assert dataset.metadata["source"] == "http_api"

    # Round-trip through .hsp
    service = ProjectService()
    service.create_project("API RT")
    service.add_dataset(dataset)
    path = tmp_path / "api_rt.hsp"
    service.save_project(path)

    reopened = ProjectService()
    reopened.open_project(path)
    restored = next(d for d in reopened.datasets if d.name == "Ряд API")
    assert restored.data == dataset.data
    assert restored.metadata["source"] == "http_api"
    assert restored.metadata["post_id"] == "post-rt"


def test_offline_mode_does_not_break_file_import(tmp_path: Path):
    """P0/P1.1 file import must work when API is unreachable (no network call)."""
    from core.services.import_service import ColumnMapping, ImportService

    path = tmp_path / "offline.csv"
    path.write_text("year,value\n1990,1.0\n1991,2.0\n", encoding="utf-8")
    ds = ImportService().import_file(
        path,
        ColumnMapping(year_column="year", value_column="value", name="Offline"),
    )
    assert ds.length == 2
    # A failing API source must not be required for this path.
    failing = HttpApiSource(
        "https://127.0.0.1:9/never", session=MagicMock(), retries=0, timeout=0.01
    )
    failing_session = failing._session
    failing_session.get.side_effect = requests.exceptions.ConnectionError("offline")
    with pytest.raises(ApiSourceError):
        failing.fetch_series("x")
    # File path still works after the failed API attempt.
    ds2 = ImportService().import_file(
        path,
        ColumnMapping(year_column="year", value_column="value", name="Offline2"),
    )
    assert ds2.length == 2
