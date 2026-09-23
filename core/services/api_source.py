"""
core/services/api_source.py
Import of hydrological time series from an HTTP API (stage P1.2).

`DataSource` is a small protocol so any source (open hydro API, internal REST,
fixture/mock) can feed the same pipeline. `HttpApiSource` is the default
requests-based adapter: bounded timeouts, bounded retries, human-readable
`ApiSourceError`, provenance recorded on `Dataset.metadata`.

The service never mutates or \"repairs\" the series: gaps stay gaps; quality
analysis stays in `DataQualityService` / `QualityPipeline` (product rule:
no silent data changes).

Services contain no mathematics: only fetch, map and validate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from core.domain.models import Dataset, DatasetType

__all__ = [
    "ApiSourceError",
    "DataSource",
    "FieldMap",
    "HttpApiSource",
]

# Year aliases accepted when auto-detecting the year field in a JSON series.
_YEAR_ALIASES = ("year", "год", "years", "года", "г", "date", "time")
_VALUE_ALIASES = (
    "value", "значение", "values", "q", "flow", "расход", "stok",
    "discharge", "runoff",
)

DEFAULT_TIMEOUT = 10.0  # seconds, hard upper bound per request
DEFAULT_RETRIES = 2     # extra attempts after the first (bounded total)


class ApiSourceError(ValueError):
    """Raised when a series cannot be fetched or mapped from a data source.

    Messages are human-readable so the GUI can show them directly.
    """


@runtime_checkable
class DataSource(Protocol):
    """Minimal protocol for anything that can produce a time series."""

    def fetch_series(
        self,
        post_id: str,
        *,
        name: str = "",
        unit: str = "m³/s",
        location: str = "",
    ) -> Dataset:
        """Return a Dataset for `post_id` or raise `ApiSourceError`."""
        ...


@dataclass(frozen=True)
class FieldMap:
    """How a JSON object maps onto (year, value) pairs."""

    year_key: str
    value_key: str
    series_key: str | None = None  # nested list under this key, if any


class HttpApiSource:
    """HTTP adapter over `requests` implementing `DataSource`.

    Expected response shapes (tried in order):
    - a list of ``{"year": ..., "value": ...}`` objects;
    - an object with a nested list under `series_key` (default: \"series\",
      \"data\", \"points\", \"values\", \"items\");
    - an object with parallel arrays ``years``/``values`` (or aliases).
    """

    def __init__(
        self,
        base_url: str,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        headers: dict[str, str] | None = None,
        field_map: FieldMap | None = None,
    ) -> None:
        if not base_url or not str(base_url).strip():
            raise ApiSourceError("Не задан URL источника данных.")
        self.base_url = str(base_url).rstrip("/")
        self.timeout = float(timeout)
        self.retries = max(0, int(retries))
        self._headers = dict(headers or {})
        self._field_map = field_map
        self._session = session

    # ------------------------------------------------------------------
    # DataSource protocol
    # ------------------------------------------------------------------
    def fetch_series(
        self,
        post_id: str,
        *,
        name: str = "",
        unit: str = "m³/s",
        location: str = "",
    ) -> Dataset:
        if not post_id or not str(post_id).strip():
            raise ApiSourceError("Не задан идентификатор поста.")

        url = f"{self.base_url}/{str(post_id).strip()}"
        payload = self._get_json(url)

        try:
            points = self._extract_points(payload)
            data = self._points_to_map(points)
        except ApiSourceError:
            raise
        except (TypeError, ValueError, KeyError) as error:
            raise ApiSourceError(
                f"Некорректный ответ источника для поста «{post_id}»: {error}"
            ) from error

        if not data:
            raise ApiSourceError(
                f"Источник не вернул данных для поста «{post_id}»."
            )

        display_name = (name or "").strip() or str(post_id)
        return Dataset(
            name=display_name,
            data=data,
            dataset_type=DatasetType.OBSERVED,
            unit=unit or "m³/s",
            location=location or "",
            metadata=self._provenance(url, post_id),
        )

    # ------------------------------------------------------------------
    # HTTP (bounded timeout + bounded retries)
    # ------------------------------------------------------------------
    def _get_json(self, url: str) -> Any:
        import requests  # local import keeps module import light for tools

        session = self._session if self._session is not None else requests
        attempts = self.retries + 1
        last_error: Exception | None = None

        for _attempt in range(attempts):
            try:
                response = session.get(
                    url,
                    timeout=self.timeout,
                    headers=self._headers,
                )
            except requests.exceptions.Timeout as error:
                last_error = ApiSourceError(
                    f"Источник не ответил за {self.timeout:g} с (таймаут): {url}"
                )
                last_error.__cause__ = error
                continue
            except requests.exceptions.ConnectionError as error:
                last_error = ApiSourceError(
                    f"Нет соединения с источником: {url}"
                )
                last_error.__cause__ = error
                continue
            except requests.exceptions.RequestException as error:
                last_error = ApiSourceError(
                    f"Ошибка запроса к источнику: {error}"
                )
                last_error.__cause__ = error
                continue

            status = int(getattr(response, "status_code", 0) or 0)
            if 200 <= status < 300:
                try:
                    return response.json()
                except ValueError as error:
                    raise ApiSourceError(
                        "Источник вернул не JSON — проверьте адрес и формат."
                    ) from error
            if 400 <= status < 500:
                # Client errors are not retried: the request will not improve.
                raise ApiSourceError(
                    f"Источник отклонил запрос (HTTP {status}): {url}"
                )
            last_error = ApiSourceError(
                f"Ошибка источника (HTTP {status}): {url}"
            )

        assert last_error is not None  # attempts >= 1
        raise last_error

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    def _extract_points(self, payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            raise ApiSourceError(
                f"Неожиданный формат ответа: {type(payload).__name__}."
            )

        # Parallel year/value arrays first: `values` as a top-level key
        # must not be mistaken for a nested list of point objects.
        year_key = self._find_key(payload, _YEAR_ALIASES)
        value_key = self._find_key(payload, _VALUE_ALIASES)
        if year_key and value_key:
            years = payload[year_key]
            values = payload[value_key]
            if isinstance(years, list) and isinstance(values, list):
                if len(years) != len(values):
                    raise ApiSourceError(
                        "Массивы годов и значений разной длины в ответе источника."
                    )
                return [
                    {year_key: y, value_key: v}
                    for y, v in zip(years, values, strict=True)
                ]

        # Nested series under a known key (list of point objects).
        for key in ("series", "data", "points", "items", "rows"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return nested
        nested_values = payload.get("values")
        if isinstance(nested_values, list) and (
            not nested_values or isinstance(nested_values[0], dict)
        ):
            return nested_values

        raise ApiSourceError(
            "В ответе источника не найден список точек ряда "
            "(ожидался массив или поля год/значение)."
        )

    def _points_to_map(self, points: list[Any]) -> dict[int, float]:
        data: dict[int, float] = {}
        for item in points:
            year, value = self._point_pair(item)
            if year in data:
                raise ApiSourceError(f"Дубликат года {year} в ответе источника.")
            data[year] = value
        return data

    def _point_pair(self, item: Any) -> tuple[int, float]:
        if not isinstance(item, dict):
            raise ApiSourceError(
                f"Ожидался объект точки ряда, получен: {type(item).__name__}."
            )

        year_key = None
        value_key = None
        if self._field_map is not None:
            year_key = self._field_map.year_key
            value_key = self._field_map.value_key
            if year_key not in item or value_key not in item:
                raise ApiSourceError(
                    f"Колонки маппинга не найдены в точке: "
                    f"{year_key!r}/{value_key!r}."
                )
        else:
            year_key = self._find_key(item, _YEAR_ALIASES)
            value_key = self._find_key(item, _VALUE_ALIASES)
            if not year_key or not value_key:
                raise ApiSourceError(
                    "Не удалось определить поля года и значения в ответе "
                    "источника (задайте FieldMap вручную)."
                )

        try:
            year = int(float(item[year_key]))
            value = float(item[value_key])
        except (TypeError, ValueError, KeyError) as error:
            raise ApiSourceError(
                f"Некорректная точка ряда {item!r}: {error}"
            ) from error
        if not 1800 <= year <= 2200:
            raise ApiSourceError(
                f"Год вне допустимого диапазона 1800–2200: {year}"
            )
        if value != value:  # NaN from JSON null / bad cast
            raise ApiSourceError(f"Пустое значение для года {year}.")
        return year, value

    @staticmethod
    def _find_key(obj: dict[str, Any], aliases: tuple[str, ...]) -> str | None:
        lowered = {str(k).strip().lower(): k for k in obj}
        for alias in aliases:
            hit = lowered.get(alias)
            if hit is not None:
                return str(hit)
        return None

    def _provenance(self, url: str, post_id: str) -> dict[str, Any]:
        """Provenance block persisted on `Dataset.metadata` (and `.hsp`)."""
        return {
            "source": "http_api",
            "source_url": url,
            "post_id": str(post_id),
            "fetched_at": datetime.now(UTC).isoformat(),
            "timeout_s": self.timeout,
            "retries": self.retries,
            "field_map": (
                {
                    "year_key": self._field_map.year_key,
                    "value_key": self._field_map.value_key,
                    "series_key": self._field_map.series_key,
                }
                if self._field_map is not None
                else None
            ),
        }
