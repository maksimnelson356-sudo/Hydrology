"""
core/services/data_quality_service.py
Оценка качества данных (Этап 2 дорожной карты) для HydroSphere.

Сервис — организующий слой поверх ValidationService (базовые проверки и
статистика) и MethodologyRegistry (требования методик к данным). Собственной
математики нет: формулы остаются в core.stats.

Принцип «не изменять данные молча» (см. DOCS/ROADMAP.md, Этап 2):
сервис только оценивает ряд и для каждой проблемы формулирует
«что обнаружено → почему это важно → что можно сделать».
Реальное исправление данных выполняет пользователь явным действием в GUI.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.domain.models import (
    DataQualityReport,
    Dataset,
    ValidationIssue,
    ValidationSeverity,
)
from core.services.methodology_registry import (
    MethodologyDescriptor,
    MethodologyRegistry,
    build_default_registry,
)
from core.services.validation_service import ValidationService

# ------------------------------------------------------------------
# Карта рекомендаций: код проблемы → (почему важно, доступные действия)
# Действия ссылаются на существующие инструменты GUI по коду:
# fill_interpolation / fill_correlation / homogeneity_report / outliers_review /
# series_extension / composite_curve / trend_report / save_report / none
# ------------------------------------------------------------------
RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    "DATA_GAPS": {
        "why": "Пропущенные годы искажают статистические параметры и кривую обеспеченности",
        "actions": [
            (
                "fill_interpolation",
                "Заполнить пропуски интерполяцией",
                "Линейная интерполяция между соседними годами (быстро, но сглаживает ход ряда)",
            ),
            (
                "fill_correlation",
                "Восстановить по посту-аналогу",
                "Регрессия по коррелирующему посту — надёжнее при длительных пропусках",
            ),
        ],
    },
    "DUPLICATE_YEARS": {
        "why": "Дубликаты лет дают ложный вес наблюдениям и искажают расчёт",
        "actions": [("none", "Проверить исходный файл", "Исправить данные в источнике и перезагрузить ряд")],
    },
    "ZERO_VALUES": {
        "why": "Нулевые расходы возможны только на пересыхающих участках; проверьте корректность",
        "actions": [("none", "Проверить исходный файл", "Убедиться, что нули не являются пропусками")],
    },
    "NEGATIVE_VALUES": {
        "why": "Отрицательные значения расхода физически невозможны",
        "actions": [("none", "Проверить исходный файл", "Исправить знак или убрать ошибочные записи")],
    },
    "INSUFFICIENT_DATA": {
        "why": "Короткий ряд даёт ненадёжные оценки нормы и обеспеченности",
        "actions": [
            (
                "series_extension",
                "Удлинить ряд по аналогу",
                "Регрессионное восстановление по длинному ряду поста-аналога (СП 33, раздел 6.2)",
            ),
        ],
    },
    "OUTLIERS_DETECTED": {
        "why": "Экстремальные значения смещают Cv, Cs и положение кривой обеспеченности",
        "actions": [
            (
                "outliers_review",
                "Проверить выбросы (Диксон/Граббс)",
                "Критерии однородности покажут, случайны ли экстремумы; удалять только подтверждённые",
            ),
        ],
    },
    "HOMOGENEITY_FAILED": {
        "why": "Неоднородный ряд нельзя описывать одной кривой обеспеченности",
        "actions": [
            (
                "homogeneity_report",
                "Открыть отчёт об однородности",
                "12 критериев Диксона/Граббса покажут, какие именно нарушены",
            ),
            (
                "composite_curve",
                "Разбить ряд на периоды",
                "Составная кривая (Рождественский) объединяет однородные части (СП 33, п. 5.12)",
            ),
        ],
    },
    "STATIONARITY_FAILED": {
        "why": "Тренд или смена дисперсии нарушают предположение о неизменности режима",
        "actions": [
            (
                "trend_report",
                "Проанализировать тренд",
                "Линейный тренд, Манн-Кендалл, Сен и Pettitt покажут характер изменений",
            ),
            (
                "composite_curve",
                "Разбить ряд на периоды",
                "До/после года смены режима с составной кривой",
            ),
        ],
    },
    "SERIES_LENGTH_WARNING": {
        "why": "Требования СП к длине ряда не выполнены — точность параметров снижена",
        "actions": [("series_extension", "Удлинить ряд по аналогу", "Увеличить длину ряда до нормативной")],
    },
    "SERIES_LENGTH_INFO": {
        "why": "Для надёжных статистических оценок СП 33 рекомендует ряд не короче 30 лет",
        "actions": [("series_extension", "Удлинить ряд по аналогу", "Увеличить длину ряда сверх 30 лет")],
    },
    "SERIES_LENGTH_CRITICAL": {
        "why": "Ряд критически короткий: результаты статистического анализа ненадёжны",
        "actions": [
            ("series_extension", "Удлинить ряд по аналогу", "Единственный путь к надёжным оценкам"),
        ],
    },
    "METHODOLOGY_MIN_POINTS": {
        "why": "Выбранная методика предъявляет обязательные требования к длине ряда",
        "actions": [("series_extension", "Удлинить ряд по аналогу", "Довести длину ряда до требования методики")],
    },
}

# Приоритет сортировки: сначала наиболее серьёзные
_SEVERITY_ORDER = {
    ValidationSeverity.CRITICAL: 0,
    ValidationSeverity.ERROR: 1,
    ValidationSeverity.WARNING: 2,
    ValidationSeverity.INFO: 3,
}


class DataQualityService:
    """
    Оценка качества данных без изменения самих данных.

    Единая точка входа — analyze(): собирает DataQualityReport из
    ValidationService и дополняет каждую проблему рекомендациями
    («почему важно» + «что можно сделать»).
    """

    def __init__(
        self,
        validation_service: ValidationService | None = None,
        registry: MethodologyRegistry | None = None,
    ) -> None:
        self._validation = validation_service or ValidationService()
        self._registry = registry or build_default_registry()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def registry(self) -> MethodologyRegistry:
        """Реестр методик (для проверки применимости)."""
        return self._registry

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    def analyze(
        self,
        dataset: Dataset,
        *,
        methodology_id: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> DataQualityReport:
        """
        Оценить качество ряда и подготовить рекомендации.

        Args:
            dataset: проверяемый ряд (не изменяется).
            methodology_id: методика, под которую проверяется ряд (опционально).
            parameters: параметры методики для check_applicability.

        Returns:
            DataQualityReport с issues, дополненными рекомендациями.
        """
        report = self._validation.generate_quality_report(dataset)
        extra: list[ValidationIssue] = []

        # Требования СП 482/СП 33 к длине ряда (тексты из core.stats.parameters).
        extra.extend(self._length_findings(dataset))

        # Применимость выбранной методики к ряду.
        if methodology_id:
            extra.extend(self._methodology_findings(dataset, methodology_id, parameters))

        report.issues = self._annotate(report.issues + extra)
        return report

    # ------------------------------------------------------------------
    # Внутренние проверки
    # ------------------------------------------------------------------
    def _length_findings(self, dataset: Dataset) -> list[ValidationIssue]:
        """Требования СП 482/СП 33 к длине ряда (тексты из core.stats.parameters)."""
        from core.stats.parameters import validate_series_length

        findings: list[ValidationIssue] = []
        for warning in validate_series_length(dataset.length):
            if warning.startswith("❌"):
                code, severity = "SERIES_LENGTH_CRITICAL", ValidationSeverity.ERROR
            elif warning.startswith("⚠️"):
                code, severity = "SERIES_LENGTH_WARNING", ValidationSeverity.WARNING
            else:
                code, severity = "SERIES_LENGTH_INFO", ValidationSeverity.INFO
            findings.append(
                ValidationIssue(code=code, message=warning, severity=severity, field="data")
            )
        return findings

    def _methodology_findings(
        self,
        dataset: Dataset,
        methodology_id: str,
        parameters: dict[str, Any] | None,
    ) -> list[ValidationIssue]:
        """Применимость выбранной методики к ряду (из MethodologyRegistry)."""
        descriptor = self._registry.get_optional(methodology_id)
        if descriptor is None:
            return []
        try:
            check = self._registry.check_applicability(methodology_id, dataset, parameters)
        except KeyError:
            return []
        for issue in check.issues:
            issue.message = f"{descriptor.name}: {issue.message}"
            if issue.code == "INSUFFICIENT_DATA":
                # Отличаем от базовой проверки длины, чтобы не путать рекомендации.
                issue.code = "METHODOLOGY_MIN_POINTS"
        return check.issues

    def _annotate(self, issues: list[ValidationIssue]) -> list[ValidationIssue]:
        """Дополнить каждую проблему блоком рекомендаций и отсортировать по серьёзности."""
        annotated: list[ValidationIssue] = []
        for issue in issues:
            info = RECOMMENDATIONS.get(issue.code)
            if info is None:
                annotated.append(issue)
                continue
            details = dict(issue.details)
            details["why_it_matters"] = info["why"]
            details["recommended_actions"] = [
                {"code": code, "title": title, "description": description}
                for code, title, description in info["actions"]
            ]
            annotated.append(
                ValidationIssue(
                    code=issue.code,
                    message=issue.message,
                    severity=issue.severity,
                    field=issue.field,
                    details=details,
                )
            )
        annotated.sort(key=lambda item: _SEVERITY_ORDER.get(item.severity, 9))
        return annotated

    # ------------------------------------------------------------------
    # Отчёты
    # ------------------------------------------------------------------
    def recommendations(self, report: DataQualityReport) -> list[dict[str, Any]]:
        """Плоский список рекомендаций по отчёту (для GUI)."""
        actions: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for issue in report.issues:
            for action in issue.details.get("recommended_actions", []):
                key = (issue.code, action.get("code", ""))
                if key in seen:
                    continue
                seen.add(key)
                actions.append(
                    {
                        "issue_code": issue.code,
                        "severity": issue.severity.value,
                        "message": issue.message,
                        **action,
                    }
                )
        return actions

    def to_json(self, report: DataQualityReport) -> dict[str, Any]:
        """Сериализовать отчёт (для хранения в проекте)."""
        payload = report.to_dict()
        payload["recommendations"] = self.recommendations(report)
        return payload

    def register_report(
        self,
        report: DataQualityReport,
        dataset_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Подготовить запись отчёта для ProjectService.register_report()."""
        payload = self.to_json(report)
        if dataset_id is not None:
            payload["dataset_id"] = str(dataset_id)
        payload["report_type"] = "data_quality"
        return payload


__all__ = ["DataQualityService", "RECOMMENDATIONS"]