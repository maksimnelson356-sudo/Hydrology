"""
core/services/import_service.py
Import of hydrological time series from CSV / TSV / Excel (stage P1.1).

The service turns a raw file into a domain `Dataset` (year -> value mapping).
It never mutates or "repairs" the series: gaps and non-numeric cells are
reported as errors or left as missing years — quality analysis stays in
`DataQualityService` (product rule: no silent data changes).

Services contain no mathematics: only parsing, mapping and validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from core.domain.models import Dataset, DatasetType

__all__ = [
    "ColumnMapping",
    "ImportPreview",
    "ImportService",
    "ImportServiceError",
]

SUPPORTED_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}

_YEAR_ALIASES = ("год", "year", "years", "года", "г")
_VALUE_ALIASES = ("значение", "value", "values", "q", "расход", "flow", "stok")

_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1251", "latin-1")


class ImportServiceError(ValueError):
    """Raised when a file cannot be turned into a Dataset."""


@dataclass(frozen=True)
class ColumnMapping:
    """User (or auto-detected) mapping of file columns to Dataset fields."""

    year_column: str
    value_column: str
    name: str
    unit: str = "m³/s"
    location: str = ""
    sheet_name: str | int | None = None
    delimiter: str | None = None
    encoding: str = "utf-8"


@dataclass
class ImportPreview:
    """Lightweight preview for the import dialog (headers + sample rows)."""

    path: str
    columns: list[str]
    rows: list[list[Any]]
    year_column: str | None = None
    value_column: str | None = None
    delimiter: str | None = None
    encoding: str = "utf-8"
    sheet_name: str | int | None = None
    sheet_names: list[str] = field(default_factory=list)
    n_rows_estimate: int = 0


def _normalize_header(value: Any) -> str:
    return str(value).strip().lower()


def _is_year_like(series: pd.Series) -> bool:
    """True when the column looks like integer years (not arbitrary numbers)."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return False
    as_int = numeric.astype(float)
    if not ((as_int == as_int.round()).all()):
        return False
    years = as_int.round().astype(int)
    return bool((years.between(1800, 2200)).all())


class ImportService:
    """Parse CSV/TSV/Excel time series into a domain `Dataset`."""

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def preview(self, path: str | Path, *, max_rows: int = 20) -> ImportPreview:
        """Read headers and a few rows without building a Dataset."""
        resolved = self._require_file(path)
        suffix = resolved.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            return self._preview_excel(resolved, max_rows=max_rows)
        if suffix in {".csv", ".tsv", ".txt"}:
            return self._preview_delimited(resolved, max_rows=max_rows)
        raise ImportServiceError(
            f"Неподдерживаемый формат файла: {suffix or '(нет расширения)'}"
        )

    def _preview_delimited(self, path: Path, *, max_rows: int) -> ImportPreview:
        last_error: Exception | None = None
        for encoding in _CSV_ENCODINGS:
            try:
                separator = self._sniff_delimiter(path, encoding)
                frame = pd.read_csv(
                    path,
                    sep=separator,
                    encoding=encoding,
                    dtype=str,
                    nrows=max_rows,
                )
            except (UnicodeDecodeError, pd.errors.ParserError, OSError) as error:
                last_error = error
                continue
            if frame.empty and frame.columns.empty:
                raise ImportServiceError(f"Файл пуст: {path.name}")
            columns = [str(c) for c in frame.columns]
            year_col = self._guess_year_column(columns, frame)
            value_col = self._guess_value_column(columns, frame, year_col)
            n_rows = self._count_data_rows(path, separator, encoding)
            return ImportPreview(
                path=str(path),
                columns=columns,
                rows=self._rows_as_lists(frame),
                year_column=year_col,
                value_column=value_col,
                delimiter=separator,
                encoding=encoding,
                n_rows_estimate=n_rows,
            )
        raise ImportServiceError(
            f"Не удалось прочитать файл {path.name}: {last_error}"
        )

    def _preview_excel(self, path: Path, *, max_rows: int) -> ImportPreview:
        try:
            workbook = pd.ExcelFile(path)
        except (ValueError, OSError, ImportError) as error:
            raise ImportServiceError(f"Не удалось открыть Excel: {error}") from error
        sheet_names = list(workbook.sheet_names)
        if not sheet_names:
            raise ImportServiceError(f"В книге нет листов: {path.name}")
        sheet = sheet_names[0]
        try:
            frame = pd.read_excel(workbook, sheet_name=sheet, nrows=max_rows, dtype=str)
        except (ValueError, OSError) as error:
            raise ImportServiceError(f"Не удалось прочитать лист «{sheet}»: {error}") from error
        if frame.empty and list(frame.columns) == [0]:
            raise ImportServiceError(f"Лист «{sheet}» пуст")
        # Excel often has an unnamed first row used as header — keep as-is;
        # the mapping UI lets the user pick columns.
        columns = [str(c) for c in frame.columns]
        year_col = self._guess_year_column(columns, frame)
        value_col = self._guess_value_column(columns, frame, year_col)
        try:
            full = pd.read_excel(workbook, sheet_name=sheet)
            n_rows = max(0, len(full))
        except (ValueError, OSError):
            n_rows = 0
        return ImportPreview(
            path=str(path),
            columns=columns,
            rows=self._rows_as_lists(frame),
            year_column=year_col,
            value_column=value_col,
            sheet_name=sheet,
            sheet_names=sheet_names,
            n_rows_estimate=n_rows,
        )

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def import_file(
        self,
        path: str | Path,
        mapping: ColumnMapping,
        *,
        dataset_type: DatasetType = DatasetType.OBSERVED,
        metadata: dict[str, Any] | None = None,
    ) -> Dataset:
        """Build a `Dataset` from `path` using `mapping`.

        Raises:
            ImportServiceError: unreadable file, empty series, bad columns,
                duplicate years, or non-integer year cells.
        """
        resolved = self._require_file(path)
        frame = self._read_frame(resolved, mapping)
        data = self._series_from_frame(frame, mapping, resolved)
        if not data:
            raise ImportServiceError(
                f"После разбора нет ни одного значения ({resolved.name})"
            )
        name = (mapping.name or "").strip() or resolved.stem
        meta = {
            "import_source": resolved.name,
            "import_path": str(resolved),
            "import_format": resolved.suffix.lower().lstrip("."),
            "year_column": mapping.year_column,
            "value_column": mapping.value_column,
        }
        if mapping.sheet_name is not None:
            meta["sheet_name"] = str(mapping.sheet_name)
        if metadata:
            meta.update(metadata)
        return Dataset(
            name=name,
            data=data,
            dataset_type=dataset_type,
            unit=mapping.unit or "m³/s",
            location=mapping.location or "",
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_file(self, path: str | Path) -> Path:
        resolved = Path(path)
        if not resolved.exists() or not resolved.is_file():
            raise ImportServiceError(f"Файл не найден: {resolved}")
        if resolved.stat().st_size == 0:
            raise ImportServiceError(f"Файл пуст: {resolved.name}")
        suffix = resolved.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ImportServiceError(
                f"Неподдерживаемый формат: {suffix or '(нет расширения)'}; "
                f"ожидается {', '.join(sorted(SUPPORTED_SUFFIXES))}"
            )
        return resolved

    def _read_frame(self, path: Path, mapping: ColumnMapping) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            sheet = mapping.sheet_name if mapping.sheet_name is not None else 0
            try:
                frame = pd.read_excel(path, sheet_name=sheet)
            except (ValueError, OSError) as error:
                raise ImportServiceError(f"Не удалось прочитать Excel: {error}") from error
        else:
            separator = mapping.delimiter or self._sniff_delimiter(
                path, mapping.encoding or "utf-8"
            )
            encoding = mapping.encoding or "utf-8"
            frame = None
            encodings = (encoding, *[e for e in _CSV_ENCODINGS if e != encoding])
            last_error: Exception | None = None
            for enc in encodings:
                try:
                    frame = pd.read_csv(path, sep=separator, encoding=enc)
                    break
                except (UnicodeDecodeError, pd.errors.ParserError, OSError) as error:
                    last_error = error
            if frame is None:
                raise ImportServiceError(
                    f"Не удалось прочитать {path.name}: {last_error}"
                )
        if frame.empty:
            raise ImportServiceError(f"Нет строк данных: {path.name}")
        # Drop fully empty rows produced by trailing newlines — not a data fix.
        frame = frame.dropna(how="all")
        if frame.empty:
            raise ImportServiceError(f"Нет строк данных: {path.name}")
        return frame

    def _series_from_frame(
        self,
        frame: pd.DataFrame,
        mapping: ColumnMapping,
        path: Path,
    ) -> dict[int, float]:
        year_col = self._resolve_column(frame, mapping.year_column, "год", path)
        value_col = self._resolve_column(frame, mapping.value_column, "значение", path)
        if year_col == value_col:
            raise ImportServiceError(
                "Колонки года и значения совпадают — выберите разные столбцы"
            )
        years_raw = frame[year_col]
        values_raw = frame[value_col]
        data: dict[int, float] = {}
        for index, (year_cell, value_cell) in enumerate(
            zip(years_raw, values_raw, strict=False), start=1
        ):
            if pd.isna(year_cell) or str(year_cell).strip() == "":
                continue
            if pd.isna(value_cell) or str(value_cell).strip() == "":
                # Missing measurement: leave the year out (gap), do not invent a value.
                continue
            year = self._parse_year(year_cell, index, path)
            try:
                value = float(str(value_cell).replace(",", ".").strip())
            except (TypeError, ValueError) as error:
                raise ImportServiceError(
                    f"Строка {index}: не число в колонке "
                    f"«{value_col}»: {value_cell!r}"
                ) from error
            if year in data:
                raise ImportServiceError(
                    f"Дублируется год {year} — уберите повтор перед импортом"
                )
            data[year] = value
        if not data:
            raise ImportServiceError(
                f"Не найдено ни одной пары год/значение ({path.name})"
            )
        return data

    def _parse_year(self, cell: Any, row_number: int, path: Path) -> int:
        text = str(cell).strip().replace(",", ".")
        try:
            numeric = float(text)
        except ValueError as error:
            raise ImportServiceError(
                f"Строка {row_number}: не число в колонке года: {cell!r}"
            ) from error
        if numeric != round(numeric):
            raise ImportServiceError(
                f"Строка {row_number}: год должен быть целым: {cell!r}"
            )
        year = int(round(numeric))
        if not 1800 <= year <= 2200:
            raise ImportServiceError(
                f"Строка {row_number}: год вне диапазона 1800–2200: {year} "
                f"({path.name})"
            )
        return year

    def _resolve_column(
        self, frame: pd.DataFrame, key: str, role: str, path: Path
    ) -> str:
        columns = [str(c) for c in frame.columns]
        if key in columns:
            return key
        # Allow index-as-string from a stale preview.
        if key.isdigit() and int(key) < len(columns):
            return columns[int(key)]
        # Case-insensitive match.
        lowered = {c.lower(): c for c in columns}
        if key.lower() in lowered:
            return lowered[key.lower()]
        raise ImportServiceError(
            f"Колонка {role} «{key}» не найдена в {path.name}; "
            f"доступны: {', '.join(columns)}"
        )

    def _sniff_delimiter(self, path: Path, encoding: str) -> str:
        try:
            sample = path.read_text(encoding=encoding, errors="replace")
        except OSError:
            sample = ""
        first_lines = sample.splitlines()[:5]
        if not first_lines:
            return ","
        counts = {
            "\t": sum(line.count("\t") for line in first_lines),
            ";": sum(line.count(";") for line in first_lines),
            ",": sum(line.count(",") for line in first_lines),
            "|": sum(line.count("|") for line in first_lines),
        }
        best = max(counts, key=counts.get)
        if counts[best] == 0:
            return ","
        # Prefer tab for .tsv when counts are tied-ish.
        if path.suffix.lower() == ".tsv" and counts["\t"] > 0:
            return "\t"
        return best

    def _count_data_rows(self, path: Path, separator: str, encoding: str) -> int:
        try:
            frame = pd.read_csv(
                path, sep=separator, encoding=encoding, usecols=[0]
            )
            return int(len(frame))
        except (UnicodeDecodeError, pd.errors.ParserError, OSError, ValueError):
            return 0

    def _guess_year_column(
        self, columns: list[str], frame: pd.DataFrame
    ) -> str | None:
        for column in columns:
            if _normalize_header(column) in _YEAR_ALIASES:
                return column
        for column in columns:
            if column in frame.columns and _is_year_like(frame[column]):
                return column
        return columns[0] if columns else None

    def _guess_value_column(
        self,
        columns: list[str],
        frame: pd.DataFrame,
        year_column: str | None,
    ) -> str | None:
        for column in columns:
            if column == year_column:
                continue
            if _normalize_header(column) in _VALUE_ALIASES:
                return column
        for column in columns:
            if column == year_column:
                continue
            if column in frame.columns and _is_year_like(frame[column]):
                continue
            numeric = pd.to_numeric(frame[column], errors="coerce")
            if numeric.notna().any():
                return column
        return columns[-1] if columns else None

    @staticmethod
    def _rows_as_lists(frame: pd.DataFrame) -> list[list[Any]]:
        rows: list[list[Any]] = []
        for row in frame.itertuples(index=False, name=None):
            rows.append(["" if pd.isna(cell) else cell for cell in row])
        return rows
