"""Summary-cell rendering for the Data Quality dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from core.domain.models import DataQualityReport
from i18n import t


def render_summary(grid: QGridLayout, report: DataQualityReport) -> None:
    """Render the compact quality score summary into a grid."""
    while grid.count():
        item = grid.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
    _add_cell(grid, 0, 0, t("quality_score", "Оценка качества"), f"{report.quality_grade} ({report.quality_score:.2f} / 1.0)")
    _add_cell(grid, 0, 1, t("quality_completeness", "Комплектность ряда"), f"{report.completeness_ratio * 100:.0f} %")
    _add_cell(grid, 1, 0, t("quality_points_missing", "Точек / пропусков"), f"{report.n_points} / {report.n_missing}")
    _add_cell(grid, 1, 1, t("quality_iqr_outliers", "Выбросы (IQR)"), str(report.n_outliers))
    _add_cell(grid, 2, 0, t("quality_homogeneity", "Однородность"), "пройдена" if report.homogeneity_passed else "нарушена", report.homogeneity_passed)
    _add_cell(grid, 2, 1, t("quality_stationarity", "Стационарность"), "пройдена" if report.stationarity_passed else "нарушена", report.stationarity_passed)
    stats = report.statistics or {}
    if stats:
        _add_cell(grid, 3, 0, t("quality_mean_cv", "Среднее / Cv"), f"{stats.get('mean', float('nan')):.2f} / {stats.get('cv', float('nan')):.3f}")
        _add_cell(grid, 3, 1, t("quality_min_max", "Мин. / Макс."), f"{stats.get('min', float('nan')):.1f} / {stats.get('max', float('nan')):.1f}")


def _add_cell(grid: QGridLayout, row: int, column: int, label: str, value: str, ok: bool | None = None) -> None:
    box = QFrame()
    box.setFrameShape(QFrame.Shape.StyledPanel)
    box.setStyleSheet("QFrame { background: #F5F7FA; border-radius: 4px; }")
    inner = QVBoxLayout(box)
    inner.setContentsMargins(8, 4, 8, 4)
    label_widget = QLabel(label)
    label_widget.setStyleSheet("color: #666; font-size: 11px;")
    value_widget = QLabel(value)
    value_widget.setStyleSheet("font-weight: bold; font-size: 13px;")
    if ok is True:
        value_widget.setStyleSheet("font-weight: bold; font-size: 13px; color: #2E7D32;")
    elif ok is False:
        value_widget.setStyleSheet("font-weight: bold; font-size: 13px; color: #C62828;")
    inner.addWidget(label_widget)
    inner.addWidget(value_widget)
    grid.addWidget(box, row, column)


__all__ = ["render_summary"]
