"""
tests/test_import_service.py
Unit tests for CSV/TSV/Excel import (stage P1.1 of DOCS/ROADMAP.md).

Acceptance criteria covered:
- CSV happy path builds a Dataset with correct year/value mapping;
- a year gap is preserved (not filled) so DataQualityService reports DATA_GAPS;
- missing year column, empty file and duplicate years raise ImportServiceError;
- Excel (xlsx) import works for a simple sheet;
- imported Dataset round-trips through ProjectService `.hsp`;
- the service never invents values for empty cells.

The tests run without GUI: only `core.domain` and `core.services` are touched.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from core.domain import Dataset, DatasetType, ValidationSeverity
from core.services import DataQualityService, ProjectService
from core.services.import_service import (
    ColumnMapping,
    ImportService,
    ImportServiceError,
)

CSV_HEADER = "year,value\n"
CSV_BODY = (
    "1990,10.5\n"
    "1991,11.0\n"
    "1992,9.8\n"
    "1994,12.1\n"  # gap: 1993 missing
    "1995,10.0\n"
)


def write_csv(tmp_path: Path, body: str, *, header: str = CSV_HEADER) -> Path:
    path = tmp_path / "series.csv"
    path.write_text(header + body, encoding="utf-8")
    return path


def mapping(name: str = "Пост CSV") -> ColumnMapping:
    return ColumnMapping(year_column="year", value_column="value", name=name)


# ----------------------------------------------------------------------
# CSV happy path
# ----------------------------------------------------------------------
def test_csv_happy_path_builds_dataset(tmp_path: Path):
    path = write_csv(tmp_path, CSV_BODY)
    service = ImportService()

    dataset = service.import_file(path, mapping())

    assert isinstance(dataset, Dataset)
    assert dataset.name == "Пост CSV"
    assert dataset.dataset_type == DatasetType.OBSERVED
    assert dataset.unit == "m³/s"
    assert dataset.length == 5
    assert dataset.start_year == 1990
    assert dataset.end_year == 1995
    assert dataset.data[1990] == pytest.approx(10.5)
    assert dataset.data[1992] == pytest.approx(9.8)
    assert dataset.metadata["import_format"] == "csv"
    assert dataset.metadata["year_column"] == "year"


def test_csv_gap_is_preserved_and_quality_reports_data_gaps(tmp_path: Path):
    path = write_csv(tmp_path, CSV_BODY)
    service = ImportService()
    dataset = service.import_file(path, mapping())

    # 1993 is absent — not filled by the importer.
    assert 1993 not in dataset.data
    assert dataset.length == 5

    report = DataQualityService().analyze(dataset)
    codes = {issue.code for issue in report.issues}
    assert "DATA_GAPS" in codes
    gap_issue = next(i for i in report.issues if i.code == "DATA_GAPS")
    assert 1993 in gap_issue.details.get("missing_years", [])
    assert gap_issue.severity in (
        ValidationSeverity.WARNING,
        ValidationSeverity.ERROR,
    )


def test_csv_empty_value_cell_is_skipped_not_filled(tmp_path: Path):
    path = write_csv(tmp_path, "1990,10.5\n1991,\n1992,9.0\n")
    service = ImportService()

    dataset = service.import_file(path, mapping())

    assert 1991 not in dataset.data
    assert dataset.length == 2


def test_csv_comma_decimal_and_russian_headers(tmp_path: Path):
    path = write_csv(
        tmp_path,
        "1990,10,5\n1991,11,25\n",
        header="Год,Значение\n",
    )
    # Russian CSV often uses semicolon + comma decimals; use explicit delimiter.
    path.write_text(
        "Год;Значение\n1990;10,5\n1991;11,25\n",
        encoding="utf-8",
    )
    service = ImportService()

    dataset = service.import_file(
        path,
        ColumnMapping(year_column="Год", value_column="Значение", name="RU"),
    )

    assert dataset.data[1990] == pytest.approx(10.5)
    assert dataset.data[1991] == pytest.approx(11.25)


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------
def test_missing_year_column_raises(tmp_path: Path):
    path = write_csv(tmp_path, CSV_BODY, header="a,b\n")
    service = ImportService()

    with pytest.raises(ImportServiceError, match="год"):
        service.import_file(path, mapping())


def test_empty_file_raises(tmp_path: Path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    service = ImportService()

    with pytest.raises(ImportServiceError, match="пуст"):
        service.import_file(path, mapping())


def test_duplicate_years_raise(tmp_path: Path):
    path = write_csv(tmp_path, "1990,1.0\n1990,2.0\n")
    service = ImportService()

    with pytest.raises(ImportServiceError, match="Дублируется год"):
        service.import_file(path, mapping())


def test_unsupported_extension_raises(tmp_path: Path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"\x00\x01")
    service = ImportService()

    with pytest.raises(ImportServiceError, match="Неподдерживаемый"):
        service.import_file(path, mapping())


def test_non_integer_year_raises(tmp_path: Path):
    path = write_csv(tmp_path, "1990.5,1.0\n1991,2.0\n")
    service = ImportService()

    with pytest.raises(ImportServiceError, match="целым"):
        service.import_file(path, mapping())


def test_year_out_of_range_raises(tmp_path: Path):
    path = write_csv(tmp_path, "1200,1.0\n1991,2.0\n")
    service = ImportService()

    with pytest.raises(ImportServiceError, match="1800"):
        service.import_file(path, mapping())


def test_missing_file_raises(tmp_path: Path):
    service = ImportService()
    with pytest.raises(ImportServiceError, match="не найден"):
        service.import_file(tmp_path / "nope.csv", mapping())


# ----------------------------------------------------------------------
# Preview / auto-detect
# ----------------------------------------------------------------------
def test_preview_detects_year_and_value_columns(tmp_path: Path):
    path = write_csv(tmp_path, CSV_BODY)
    service = ImportService()

    preview = service.preview(path)

    assert preview.columns == ["year", "value"]
    assert preview.year_column == "year"
    assert preview.value_column == "value"
    assert preview.n_rows_estimate == 5
    assert len(preview.rows) == 5


def test_import_auto_uses_preview_hints(tmp_path: Path):
    path = write_csv(tmp_path, "1990,10.5\n1991,11.0\n")
    service = ImportService()
    preview = service.preview(path)
    assert preview.year_column and preview.value_column

    dataset = service.import_file(
        path,
        ColumnMapping(
            year_column=preview.year_column or "",
            value_column=preview.value_column or "",
            name="Auto",
            delimiter=preview.delimiter,
            encoding=preview.encoding,
        ),
    )
    assert dataset.length == 2


# ----------------------------------------------------------------------
# Excel
# ----------------------------------------------------------------------
def test_xlsx_happy_path(tmp_path: Path):
    path = tmp_path / "series.xlsx"
    pd.DataFrame({"year": [1990, 1991, 1992], "value": [1.0, 2.0, 3.0]}).to_excel(
        path, index=False
    )
    service = ImportService()

    preview = service.preview(path)
    assert preview.sheet_names
    dataset = service.import_file(path, mapping(name="Пост XLSX"))

    assert dataset.length == 3
    assert dataset.data[1991] == pytest.approx(2.0)
    assert dataset.metadata["import_format"] == "xlsx"


# ----------------------------------------------------------------------
# .hsp roundtrip
# ----------------------------------------------------------------------
def test_imported_dataset_hsp_roundtrip(tmp_path: Path):
    path = write_csv(tmp_path, CSV_BODY)
    service = ImportService()
    dataset = service.import_file(path, mapping(name="Ряд для .hsp"))

    project_path = tmp_path / "project.hsp"
    store = ProjectService()
    store.create_project("Импорт", path=project_path)
    store.add_dataset(dataset)
    store.save_project(project_path)

    restored = ProjectService.from_file(project_path)
    loaded = restored.get_dataset("Ряд для .hsp")

    assert loaded is not None
    assert loaded.data == dataset.data
    assert loaded.unit == dataset.unit
    assert loaded.name == dataset.name
    assert str(loaded.id) == str(dataset.id)
