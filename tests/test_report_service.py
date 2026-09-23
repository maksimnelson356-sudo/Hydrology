"""
tests/test_report_service.py
Stage 6 acceptance tests (DOCS/ROADMAP.md, stage 6): engineering report.

Covered:
- all 13 sections are present in canonical order;
- key values (Qср, Cv, Cs, calculation outputs) appear when provided;
- missing data does not break the build (section content is «нет данных»);
- chart_count equals the number of selected charts;
- scenarios / comparison rows are included when provided;
- include filter keeps the document at 13 sections.
"""

from __future__ import annotations

from pathlib import Path

from core.domain.models import (
    CalculationMetadata,
    CalculationResult,
    DataQualityReport,
    Dataset,
    Methodology,
    Scenario,
    ValidationResult,
    ValidationSeverity,
)
from core.services.report_service import (
    EXCLUDED,
    NO_DATA,
    SECTION_IDS,
    SECTION_TITLES,
    ReportService,
)


def make_dataset(name: str = "Пост 1", start: int = 1990, count: int = 5) -> Dataset:
    return Dataset(name=name, data={start + index: 100.0 + index for index in range(count)})


def make_result(output: dict | None = None, *, completed: bool = True) -> CalculationResult:
    metadata = CalculationMetadata(
        methodology=Methodology(
            name="stats_parameters",
            version="1.0",
            standard="СП 33-101-2003",
            description="Статистические параметры ряда",
        ),
        input_parameters={"Cv": 0.25},
    )
    if completed:
        metadata.mark_completed()
    else:
        metadata.mark_failed("boom")
    return CalculationResult(metadata=metadata, output_data=output or {"Q_p95": 1240.0})


def make_quality() -> DataQualityReport:
    return DataQualityReport(
        dataset_id=make_dataset().id,
        dataset_name="Пост 1",
        n_points=5,
        n_missing=0,
        n_outliers=0,
        homogeneity_passed=True,
        stationarity_passed=True,
        completeness_ratio=1.0,
        quality_score=0.95,
        issues=[],
        statistics={"mean": 102.0},
    )


def build(**kwargs) -> dict:
    """Build a report and return the dict form (plus service for convenience)."""
    service = ReportService()
    report = service.build_report(**kwargs)
    return {"service": service, "report": report, "data": report.to_dict()}


# ----------------------------------------------------------------------
# 13 sections
# ----------------------------------------------------------------------
def test_report_contains_all_13_sections_in_order():
    result = build(title="Проект X")

    assert result["data"]["section_count"] == 13
    ids = [section["id"] for section in result["data"]["sections"]]
    assert ids == list(SECTION_IDS)
    titles = [section["title"] for section in result["data"]["sections"]]
    assert titles == [SECTION_TITLES[sid] for sid in SECTION_IDS]


def test_empty_report_marks_every_section_no_data():
    result = build()

    for section in result["data"]["sections"]:
        assert section["has_data"] is False
        assert section["content"] == NO_DATA


# ----------------------------------------------------------------------
# Key values (Qср, Cv, Cs, расчётные расходы)
# ----------------------------------------------------------------------
def test_parameters_section_shows_qsr_cv_cs():
    result = build(parameters={"Q_mean": 150.2, "Cv": 0.25, "Cs": 0.5})

    section = result["report"].get("parameters")
    assert section is not None and section.has_data
    assert "Qср" in section.content
    assert "Cv" in section.content
    assert "Cs" in section.content
    assert "150.2" in section.content


def test_results_section_contains_parameter_and_calculation_values():
    result = build(
        parameters={"Q_mean": 150.2, "Cv": 0.25, "Cs": 0.5},
        calculations=[make_result({"Q_p95": 1240.0})],
    )

    section = result["report"].get("results")
    assert section is not None and section.has_data
    assert "Qср = 150.2" in section.content
    assert "Q_p95 = 1240" in section.content


# ----------------------------------------------------------------------
# Missing data tolerance
# ----------------------------------------------------------------------
def test_missing_quality_report_is_no_data_not_crash():
    result = build(quality_report=None)

    section = result["report"].get("data_quality")
    assert section is not None
    assert section.has_data is False
    assert section.content == NO_DATA


def test_failed_calculation_does_not_break_results_section():
    result = build(calculations=[make_result(completed=False)])

    calc_section = result["report"].get("calculation")
    assert calc_section is not None and calc_section.has_data
    assert "failed" in calc_section.content

    results_section = result["report"].get("results")
    assert results_section is not None
    # failed outputs are skipped in итоговые значения
    assert results_section.has_data is False
    assert results_section.content == NO_DATA


# ----------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------
def test_chart_count_equals_number_of_selected_charts():
    charts = ["Кривая обеспеченности", "Тренд", "Гистограмма"]
    result = build(charts=charts)

    assert result["data"]["chart_count"] == 3
    section = result["report"].get("charts")
    assert section is not None and section.has_data
    assert "Всего графиков: 3" in section.content


def test_empty_charts_section_is_no_data():
    result = build(charts=[])

    assert result["data"]["chart_count"] == 0
    assert result["report"].get("charts").content == NO_DATA


# ----------------------------------------------------------------------
# Scenarios
# ----------------------------------------------------------------------
def test_scenarios_section_includes_rows_and_comparison():
    scenario = Scenario(name="Маловодный год", project_id=make_dataset().id, parameters={"demand": 350.0})
    comparison = [
        {"parameter": "demand", "Базовый": 300, "Маловодный год": 350},
    ]
    result = build(scenarios=[scenario], scenario_comparison=comparison)

    section = result["report"].get("scenarios")
    assert section is not None and section.has_data
    assert "Маловодный год" in section.content
    assert "demand" in section.content
    assert "350" in section.content


# ----------------------------------------------------------------------
# include filter (GUI checkboxes)
# ----------------------------------------------------------------------
def test_include_filter_keeps_all_13_sections():
    include = set(SECTION_IDS) - {"scenarios", "charts"}
    result = build(include=include, charts=["График 1"])

    assert result["data"]["section_count"] == 13
    excluded = result["report"].get("scenarios")
    assert excluded is not None
    assert excluded.content == EXCLUDED
    assert excluded.has_data is False
    # charts was explicitly excluded despite input
    assert result["report"].get("charts").content == EXCLUDED
    # core section stays filled
    # (source_data empty here; parameters empty — use a core one with data)
    result2 = build(include=include, parameters={"Cv": 0.3})
    assert result2["report"].get("parameters").has_data is True


# ----------------------------------------------------------------------
# Quality, validation, methodology
# ----------------------------------------------------------------------
def test_quality_and_validation_and_methodology_sections_fill_in():
    validation = ValidationResult(is_valid=True)
    result = build(
        quality_report=make_quality(),
        validation=validation,
        norms=["СП 33-101-2003"],
        datasets=[make_dataset()],
        calculations=[make_result()],
    )

    quality = result["report"].get("data_quality")
    assert quality is not None and quality.has_data
    assert "Оценка: A" in quality.content

    checks = result["report"].get("checks")
    assert checks is not None and checks.has_data
    assert "проверки пройдены" in checks.content

    methodology = result["report"].get("methodology")
    assert methodology is not None and methodology.has_data
    assert "СП 33-101-2003" in methodology.content

    source = result["report"].get("source_data")
    assert source is not None and source.has_data
    assert "Пост 1" in source.content


# ----------------------------------------------------------------------
# Render and save
# ----------------------------------------------------------------------
def test_render_text_contains_all_section_titles_and_stamp():
    result = build(title="Река X", parameters={"Cv": 0.25})
    text = result["service"].render_text(result["report"])

    assert "ИНЖЕНЕРНЫЙ ОТЧЁТ" in text
    assert "Река X" in text
    assert "Версия движка:" in text
    for title in SECTION_TITLES.values():
        assert title.upper() in text
    assert "Cv" in text


def test_save_report_writes_utf8_sig_file(tmp_path: Path):
    result = build(title="Сохраняемый")
    target = tmp_path / "reports" / "report.txt"

    path = result["service"].save_report(result["report"], target)

    assert path.exists()
    assert path == target
    # no temp leftovers
    assert list(tmp_path.glob("*.tmp")) == []
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM
    assert "ИНЖЕНЕРНЫЙ ОТЧЁТ" in path.read_text(encoding="utf-8-sig")


# ----------------------------------------------------------------------
# Warnings / conclusion
# ----------------------------------------------------------------------
def test_warnings_section_collects_project_and_quality_issues():
    quality = make_quality()
    from core.domain.models import ValidationIssue

    quality.issues.append(
        ValidationIssue(
            code="DATA_GAPS",
            message="нет двух лет",
            severity=ValidationSeverity.WARNING,
        )
    )
    result = build(
        project_warnings=["Файл данных не найден: gone.xlsx"],
        quality_report=quality,
        calculations=[make_result()],
    )

    section = result["report"].get("warnings")
    assert section is not None and section.has_data
    assert "Файл данных не найден" in section.content
    assert "DATA_GAPS" in section.content


def test_conclusion_fills_when_calculations_present():
    result = build(calculations=[make_result(), make_result(completed=False)])

    section = result["report"].get("conclusion")
    assert section is not None and section.has_data
    assert "1 из 2" in section.content
