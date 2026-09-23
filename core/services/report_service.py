"""
core/services/report_service.py
Engineering report assembly for the HydroSphere P0 architecture (stage 6 of
DOCS/ROADMAP.md).

The service turns project state (datasets, parameters, quality report,
calculations, scenarios, validation) into a structured engineering document with
13 sections. It contains no mathematics: formulas stay in the calculation core,
this module only formats what the project already knows.

Missing data never breaks the build: an empty section is rendered as
«нет данных» (has_data=False). The plain-text renderer is suitable for the GUI
preview and for saving into the project `reports/` folder.
"""

from __future__ import annotations

import os
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.domain.models import (
    CalculationResult,
    DataQualityReport,
    Dataset,
    Scenario,
    ValidationResult,
)

try:
    from version import VERSION_FULL as ENGINE_VERSION
except Exception:  # pragma: no cover - very early bootstrap failures
    ENGINE_VERSION = "unknown"

NO_DATA = "нет данных"
EXCLUDED = "раздел не включён в отчёт"

# Stable section ids (order is the report order).
SECTION_IDS: tuple[str, ...] = (
    "source_data",
    "data_quality",
    "methodology",
    "parameters",
    "formulas",
    "calculation",
    "checks",
    "charts",
    "tables",
    "scenarios",
    "results",
    "warnings",
    "conclusion",
)

# Russian titles per ROADMAP stage 6.
SECTION_TITLES: dict[str, str] = {
    "source_data": "Исходные данные",
    "data_quality": "Качество данных",
    "methodology": "Нормативная методика",
    "parameters": "Исходные параметры",
    "formulas": "Формулы и алгоритм",
    "calculation": "Расчёт",
    "checks": "Проверки",
    "charts": "Графики",
    "tables": "Таблицы",
    "scenarios": "Сценарии",
    "results": "Итоговые значения",
    "warnings": "Предупреждения",
    "conclusion": "Вывод",
}

# Optional sections controlled by the GUI checkboxes («что включать»).
OPTIONAL_SECTION_IDS: frozenset[str] = frozenset({"scenarios", "charts", "checks"})

# User-facing parameter labels (Q_mean is «Qср» in Russian engineering text).
PARAMETER_LABELS: dict[str, str] = {
    "Q_mean": "Qср",
    "Qsr": "Qср",
    "Q_ср": "Qср",
    "Qavg": "Qср",
    "Q_avg": "Qср",
}


def _fmt_value(value: Any) -> str:
    """Format a scalar for the text report without losing precision noise."""
    if value is None:
        return NO_DATA
    if isinstance(value, float):
        if value != value:  # NaN
            return NO_DATA
        return f"{value:g}"
    return str(value)


def _label_for(key: str) -> str:
    """Human label for a parameter key (Q_mean -> Qср, otherwise the key)."""
    return PARAMETER_LABELS.get(key, key)


@dataclass
class ReportSection:
    """A single section of the engineering report."""

    id: str
    title: str
    content: str = NO_DATA
    has_data: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "has_data": self.has_data,
        }


@dataclass
class Report:
    """Structured engineering report (13 sections, always complete)."""

    title: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    engine_version: str = ENGINE_VERSION
    sections: list[ReportSection] = field(default_factory=list)
    chart_count: int = 0

    @property
    def section_count(self) -> int:
        return len(self.sections)

    def get(self, section_id: str) -> ReportSection | None:
        for section in self.sections:
            if section.id == section_id:
                return section
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "engine_version": self.engine_version,
            "chart_count": self.chart_count,
            "section_count": self.section_count,
            "sections": [section.to_dict() for section in self.sections],
        }


class ReportService:
    """Assemble an engineering report from plain project inputs."""

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def build_report(
        self,
        *,
        title: str = "",
        datasets: Sequence[Dataset] | None = None,
        parameters: Mapping[str, Any] | None = None,
        quality_report: DataQualityReport | None = None,
        calculations: Sequence[CalculationResult] | None = None,
        scenarios: Sequence[Scenario] | None = None,
        scenario_comparison: Sequence[Mapping[str, Any]] | None = None,
        validation: ValidationResult | None = None,
        charts: Sequence[str] | None = None,
        project_warnings: Sequence[str] | None = None,
        norms: Sequence[str] | None = None,
        include: Collection[str] | None = None,
        engine_version: str | None = None,
    ) -> Report:
        """Build a report with all 13 sections.

        Args:
            title: Project / report title.
            datasets: Input datasets (section 1).
            parameters: Project parameters Qср, Cv, Cs, ... (section 4).
            quality_report: Data quality assessment (section 2).
            calculations: Calculation results (sections 6, 11).
            scenarios: Scenario list (section 10).
            scenario_comparison: Comparison table rows from ScenarioService.
            validation: Validation outcome (section 7).
            charts: Titles of selected charts; ``chart_count == len(charts)``.
            project_warnings: Project / calculation warnings (section 12).
            norms: Normative references for section 3/5 (methodology standards).
            include: Section ids to include; None means all 13.
                Sections outside ``include`` keep their slot with EXCLUDED text.
            engine_version: Override the version stamp (defaults to VERSION_FULL).

        Returns:
            Report with exactly 13 sections in canonical order. Never raises
            on missing inputs.
        """
        datasets = list(datasets or [])
        parameters = dict(parameters or {})
        calculations = list(calculations or [])
        scenarios = list(scenarios or [])
        scenario_comparison = [dict(row) for row in (scenario_comparison or [])]
        charts = list(charts or [])
        project_warnings = list(project_warnings or [])
        norms = list(norms or [])

        if include is None:
            included = set(SECTION_IDS)
        else:
            included = set(include)
            # Core sections are always present in the document.
            included.update(set(SECTION_IDS) - OPTIONAL_SECTION_IDS)

        contents: dict[str, tuple[str, bool]] = {
            "source_data": self._build_source_data(datasets),
            "data_quality": self._build_data_quality(quality_report),
            "methodology": self._build_methodology(norms, calculations),
            "parameters": self._build_parameters(parameters),
            "formulas": self._build_formulas(norms, calculations),
            "calculation": self._build_calculation(calculations),
            "checks": self._build_checks(validation),
            "charts": self._build_charts(charts),
            "tables": self._build_tables(scenario_comparison, calculations),
            "scenarios": self._build_scenarios(scenarios, scenario_comparison),
            "results": self._build_results(calculations, parameters),
            "warnings": self._build_warnings(project_warnings, calculations, quality_report),
            "conclusion": self._build_conclusion(
                calculations, quality_report, validation, project_warnings
            ),
        }

        sections: list[ReportSection] = []
        for section_id in SECTION_IDS:
            if section_id not in included:
                sections.append(
                    ReportSection(
                        id=section_id,
                        title=SECTION_TITLES[section_id],
                        content=EXCLUDED,
                        has_data=False,
                    )
                )
                continue
            content, has_data = contents[section_id]
            sections.append(
                ReportSection(
                    id=section_id,
                    title=SECTION_TITLES[section_id],
                    content=content,
                    has_data=has_data,
                )
            )

        return Report(
            title=title,
            sections=sections,
            chart_count=len(charts),
            engine_version=engine_version or ENGINE_VERSION,
        )

    # ------------------------------------------------------------------
    # Section builders (each returns content + has_data)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_source_data(datasets: Sequence[Dataset]) -> tuple[str, bool]:
        if not datasets:
            return NO_DATA, False
        lines: list[str] = []
        for dataset in datasets:
            years = dataset.years
            period = f"{years[0]}–{years[-1]}" if years else NO_DATA
            lines.append(
                f"Пост: {dataset.name}; точек: {dataset.length}; период: {period}; "
                f"единица: {dataset.unit}"
            )
            if dataset.location:
                lines.append(f"  Местоположение: {dataset.location}")
        return "\n".join(lines), True

    @staticmethod
    def _build_data_quality(report: DataQualityReport | None) -> tuple[str, bool]:
        if report is None:
            return NO_DATA, False
        lines = [
            f"Набор: {report.dataset_name}",
            f"Оценка: {report.quality_grade} (скор {report.quality_score:.2f})",
            f"Полнота: {report.completeness_ratio:.1%}; пропусков: {report.n_missing}; "
            f"выбросов: {report.n_outliers}",
            f"Однородность: {'пройдена' if report.homogeneity_passed else 'не пройдена'}; "
            f"стационарность: {'пройдена' if report.stationarity_passed else 'не пройдена'}",
        ]
        if report.issues:
            lines.append("Замечания:")
            for issue in report.issues:
                lines.append(f"  [{issue.severity.value}] {issue.code}: {issue.message}")
        return "\n".join(lines), True

    @staticmethod
    def _build_methodology(
        norms: Sequence[str], calculations: Sequence[CalculationResult]
    ) -> tuple[str, bool]:
        seen: list[str] = list(dict.fromkeys(norms))
        for result in calculations:
            standard = result.metadata.methodology.standard
            if standard and standard not in seen:
                seen.append(standard)
        if not seen:
            return NO_DATA, False
        return "\n".join(f"• {item}" for item in seen), True

    @staticmethod
    def _build_parameters(parameters: Mapping[str, Any]) -> tuple[str, bool]:
        if not parameters:
            return NO_DATA, False
        lines = []
        for key, value in parameters.items():
            lines.append(f"{_label_for(key)} ({key}): {_fmt_value(value)}")
        return "\n".join(lines), True

    @staticmethod
    def _build_formulas(
        norms: Sequence[str], calculations: Sequence[CalculationResult]
    ) -> tuple[str, bool]:
        lines: list[str] = []
        for result in calculations:
            methodology = result.metadata.methodology
            standard = methodology.standard or "норматив не указан"
            lines.append(
                f"• {methodology.name} v{methodology.version} — {standard}"
                + (f"; {methodology.description}" if methodology.description else "")
            )
        for norm in norms:
            line = f"• Нормативная база: {norm}"
            if line not in lines:
                lines.append(line)
        if not lines:
            return NO_DATA, False
        return "\n".join(lines), True

    @staticmethod
    def _build_calculation(calculations: Sequence[CalculationResult]) -> tuple[str, bool]:
        if not calculations:
            return NO_DATA, False
        lines: list[str] = []
        for index, result in enumerate(calculations, start=1):
            label = getattr(result.metadata, "label", None) or f"Расчёт #{index}"
            status = result.metadata.status.value
            lines.append(f"{label}: {result.metadata.methodology.qualified_name} — {status}")
            for key, value in list(result.output_data.items())[:10]:
                lines.append(f"  {key} = {_fmt_value(value)}")
        return "\n".join(lines), True

    @staticmethod
    def _build_checks(validation: ValidationResult | None) -> tuple[str, bool]:
        if validation is None or not validation.issues:
            if validation is not None:
                verdict = "проверки пройдены" if validation.is_valid else "проверки не пройдены"
                return verdict, True
            return NO_DATA, False
        lines = [
            f"Статус: {'валиден' if validation.is_valid else 'найдены проблемы'}"
        ]
        for issue in validation.issues:
            lines.append(f"  [{issue.severity.value}] {issue.code}: {issue.message}")
        return "\n".join(lines), True

    @staticmethod
    def _build_charts(charts: Sequence[str]) -> tuple[str, bool]:
        if not charts:
            return NO_DATA, False
        lines = [f"{index}. {title}" for index, title in enumerate(charts, start=1)]
        lines.append(f"Всего графиков: {len(charts)}")
        return "\n".join(lines), True

    @staticmethod
    def _build_tables(
        comparison: Sequence[Mapping[str, Any]],
        calculations: Sequence[CalculationResult],
    ) -> tuple[str, bool]:
        lines: list[str] = []
        if comparison:
            lines.append("Таблица сравнения параметров сценариев:")
            for row in comparison:
                pairs = ", ".join(f"{k}={_fmt_value(v)}" for k, v in row.items())
                lines.append(f"  {pairs}")
        if calculations:
            lines.append("Сводка расчётов:")
            for index, result in enumerate(calculations, start=1):
                label = getattr(result.metadata, "label", None) or f"Расчёт #{index}"
                first = next(iter(result.output_data.items()), None)
                if first:
                    lines.append(f"  {label}: {first[0]} = {_fmt_value(first[1])}")
        if not lines:
            return NO_DATA, False
        return "\n".join(lines), True

    @staticmethod
    def _build_scenarios(
        scenarios: Sequence[Scenario],
        comparison: Sequence[Mapping[str, Any]],
    ) -> tuple[str, bool]:
        if not scenarios and not comparison:
            return NO_DATA, False
        lines: list[str] = []
        if scenarios:
            lines.append("Сценарии:")
            for scenario in scenarios:
                lines.append(f"  • {scenario.name} — {scenario.description or 'без описания'}")
                for key, value in scenario.parameters.items():
                    lines.append(f"      {key} = {_fmt_value(value)}")
        if comparison:
            lines.append("Сравнение параметров:")
            for row in comparison:
                pairs = ", ".join(f"{k}={_fmt_value(v)}" for k, v in row.items())
                lines.append(f"  {pairs}")
        return "\n".join(lines), True

    @staticmethod
    def _build_results(
        calculations: Sequence[CalculationResult],
        parameters: Mapping[str, Any],
    ) -> tuple[str, bool]:
        lines: list[str] = []
        for key in ("Q_mean", "Cv", "Cs"):
            if key in parameters:
                lines.append(f"{_label_for(key)} = {_fmt_value(parameters[key])}")
        for result in calculations:
            if not result.is_successful:
                continue
            for key, value in result.output_data.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lines.append(f"{key} = {_fmt_value(value)}")
        if not lines:
            return NO_DATA, False
        # de-duplicate while preserving order
        return "\n".join(dict.fromkeys(lines)), True

    @staticmethod
    def _build_warnings(
        project_warnings: Sequence[str],
        calculations: Sequence[CalculationResult],
        quality: DataQualityReport | None,
    ) -> tuple[str, bool]:
        lines: list[str] = list(project_warnings)
        for result in calculations:
            for warning in getattr(result, "warnings", []) or []:
                lines.append(str(warning))
            if result.metadata.error_message:
                lines.append(result.metadata.error_message)
        if quality is not None:
            for issue in quality.issues:
                if issue.severity.value in ("warning", "error", "critical"):
                    lines.append(f"{issue.code}: {issue.message}")
        if not lines:
            return NO_DATA, False
        return "\n".join(f"• {item}" for item in lines), True

    @staticmethod
    def _build_conclusion(
        calculations: Sequence[CalculationResult],
        quality: DataQualityReport | None,
        validation: ValidationResult | None,
        warnings: Sequence[str],
    ) -> tuple[str, bool]:
        if not calculations and quality is None and validation is None:
            return NO_DATA, False
        parts: list[str] = []
        completed = sum(1 for item in calculations if item.is_successful)
        if calculations:
            parts.append(f"Выполнено расчётов: {completed} из {len(calculations)}.")
        if quality is not None:
            parts.append(
                f"Качество данных: {quality.quality_grade} "
                f"(полнота {quality.completeness_ratio:.0%})."
            )
        if validation is not None:
            parts.append(
                "Проверки пройдены." if validation.is_valid else "Есть замечания по проверкам."
            )
        if warnings:
            parts.append("Учтены предупреждения раздела 12.")
        return " ".join(parts), True

    # ------------------------------------------------------------------
    # Rendering and export
    # ------------------------------------------------------------------
    @staticmethod
    def render_text(report: Report) -> str:
        """Render the report as plain text (UTF-8 friendly, numbered sections)."""
        lines: list[str] = []
        lines.append("=" * 80)
        lines.append("ИНЖЕНЕРНЫЙ ОТЧЁТ")
        if report.title:
            lines.append(report.title)
        lines.append("HydroSphere — гидростатистическое ПО")
        lines.append("=" * 80)
        lines.append(f"Дата формирования: {report.generated_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Версия движка: {report.engine_version}")
        lines.append("")

        for index, section in enumerate(report.sections, start=1):
            lines.append(f"{index}. {section.title.upper()}")
            lines.append("-" * 40)
            lines.append(section.content)
            lines.append("")

        lines.append("=" * 80)
        lines.append("Отчёт сформирован автоматически программой HydroSphere")
        lines.append("=" * 80)
        return "\n".join(lines)

    @staticmethod
    def save_report(report: Report, path: str | Path) -> Path:
        """Write the plain-text report to `path` (creates parent folders).

        utf-8-sig BOM for Notepad/Excel compatibility on Russian Windows.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = ReportService.render_text(report)
        # atomic-ish write: temp next to the target
        temp = target.with_name(target.name + ".tmp")
        with temp.open("w", encoding="utf-8-sig", newline="") as handle:
            handle.write(text)
        os.replace(temp, target)
        return target


__all__ = [
    "ENGINE_VERSION",
    "EXCLUDED",
    "NO_DATA",
    "OPTIONAL_SECTION_IDS",
    "PARAMETER_LABELS",
    "Report",
    "ReportSection",
    "ReportService",
    "SECTION_IDS",
    "SECTION_TITLES",
]
