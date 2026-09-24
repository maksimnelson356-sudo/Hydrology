"""Вкладка «Качество данных» для интерфейса HydroSphere."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.domain.models import DataQualityReport
from i18n import t

_SEVERITY_LABELS = {
    "critical": "Критично",
    "error": "Ошибка",
    "warning": "Предупреждение",
    "info": "Информация",
}


class TabDataQuality(QWidget):
    """Экран отчёта о качестве выбранного ряда и доступных действиях."""

    check_requested = pyqtSignal()
    fill_missing_requested = pyqtSignal()
    fill_missing_with_correlation_requested = pyqtSignal()
    check_homogeneity_requested = pyqtSignal()
    detect_outliers_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._report: DataQualityReport | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel(t("quality_tab_title", "Качество данных"))
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0D47A1;")
        layout.addWidget(title)

        guide_group = QGroupBox(t("quality_usage_title", "Как пользоваться"))
        guide_layout = QVBoxLayout(guide_group)
        guide = QLabel(
            t(
                "quality_usage_text",
                "1. Загрузите ряд в разделе «Данные и статистика».\n"
                "2. Нажмите «Проверить качество» и дождитесь отчёта.\n"
                "3. Сначала устраните блокирующие проблемы: пропуски и отрицательные значения.\n"
                "4. Запускайте только нужное действие — исходные данные не изменяются автоматически.\n"
                "5. После исправлений повторите проверку.",
            )
        )
        guide.setWordWrap(True)
        guide.setStyleSheet("color: #546E7A; font-size: 11px;")
        guide_layout.addWidget(guide)
        layout.addWidget(guide_group)

        actions_top = QHBoxLayout()
        self.btn_check_quality = QPushButton(t("quality_check", "Проверить качество"))
        self.btn_check_quality.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "font-weight: bold; padding: 8px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #0D47A1; }"
        )
        self.btn_check_quality.clicked.connect(self.check_requested.emit)
        actions_top.addWidget(self.btn_check_quality)
        actions_top.addStretch()
        layout.addLayout(actions_top)

        info_group = QGroupBox(t("quality_dataset_info", "Информация о ряде"))
        info_layout = QFormLayout(info_group)
        self.dataset_name_label = QLabel("—")
        self.dataset_id_label = QLabel("—")
        self.n_points_label = QLabel("—")
        info_layout.addRow(t("quality_dataset_name", "Название:"), self.dataset_name_label)
        info_layout.addRow(t("quality_dataset_id", "ID:"), self.dataset_id_label)
        info_layout.addRow(t("quality_dataset_points", "Количество точек:"), self.n_points_label)
        layout.addWidget(info_group)

        metrics_group = QGroupBox(t("quality_metrics", "Метрики качества"))
        metrics_layout = QFormLayout(metrics_group)
        self.completeness_label = QLabel("—")
        self.quality_score_label = QLabel("—")
        self.quality_grade_label = QLabel("—")
        self.homogeneity_label = QLabel("—")
        self.stationarity_label = QLabel("—")
        self.n_missing_label = QLabel("—")
        self.n_outliers_label = QLabel("—")
        metrics_layout.addRow(t("quality_completeness", "Полнота:"), self.completeness_label)
        metrics_layout.addRow(t("quality_score", "Оценка качества:"), self.quality_score_label)
        metrics_layout.addRow(t("quality_grade", "Класс качества:"), self.quality_grade_label)
        metrics_layout.addRow(t("quality_homogeneity", "Однородность:"), self.homogeneity_label)
        metrics_layout.addRow(t("quality_stationarity", "Стационарность:"), self.stationarity_label)
        metrics_layout.addRow(t("quality_missing_years", "Пропущенные годы:"), self.n_missing_label)
        metrics_layout.addRow(t("quality_outliers", "Выбросы:"), self.n_outliers_label)
        layout.addWidget(metrics_group)

        issues_group = QGroupBox(t("quality_issues", "Проблемы и рекомендации"))
        issues_layout = QVBoxLayout(issues_group)
        self.issues_edit = QTextEdit()
        self.issues_edit.setReadOnly(True)
        self.issues_edit.setMinimumHeight(180)
        issues_layout.addWidget(self.issues_edit)
        layout.addWidget(issues_group, 1)

        actions_group = QGroupBox(t("quality_actions", "Рекомендуемые действия"))
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(8)
        self.btn_fill_missing = self._action_button(
            t("quality_fill_interpolation", "Заполнить пропуски (интерполяция)"),
            self.fill_missing_requested.emit,
        )
        self.btn_fill_missing_corr = self._action_button(
            t("quality_fill_correlation", "Заполнить пропуски (корреляция)"),
            self.fill_missing_with_correlation_requested.emit,
        )
        self.btn_check_homogeneity = self._action_button(
            t("quality_homogeneity_action", "Проверить однородность"),
            self.check_homogeneity_requested.emit,
        )
        self.btn_detect_outliers = self._action_button(
            t("quality_outliers_action", "Проверить выбросы"),
            self.detect_outliers_requested.emit,
        )
        for button in (
            self.btn_fill_missing,
            self.btn_fill_missing_corr,
            self.btn_check_homogeneity,
            self.btn_detect_outliers,
        ):
            actions_layout.addWidget(button)
        layout.addWidget(actions_group)

        layout.addStretch(1)

    @staticmethod
    def _action_button(text: str, callback: Callable[[], None]) -> QPushButton:
        """Create a full-width action button that cannot merge with its neighbours."""
        button = QPushButton(text)
        button.clicked.connect(callback)
        button.setMinimumHeight(36)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return button

    def update_report(self, report: DataQualityReport | None) -> None:
        """Update the tab with a new data quality report."""
        self._report = report
        if report is None:
            self._clear()
            return

        self.dataset_name_label.setText(report.dataset_name)
        self.dataset_id_label.setText(str(report.dataset_id))
        self.n_points_label.setText(str(report.n_points))
        self.completeness_label.setText(f"{report.completeness_ratio:.2%}")
        self.quality_score_label.setText(f"{report.quality_score:.3f}")
        self.quality_grade_label.setText(report.quality_grade)
        self.homogeneity_label.setText(
            t("quality_yes", "Да") if report.homogeneity_passed else t("quality_no", "Нет")
        )
        self.stationarity_label.setText(
            t("quality_yes", "Да") if report.stationarity_passed else t("quality_no", "Нет")
        )
        self.n_missing_label.setText(str(report.n_missing))
        self.n_outliers_label.setText(str(report.n_outliers))

        lines: list[str] = []
        if report.issues:
            lines.append(t("quality_issue_count", "Обнаружено проблем: {count}").format(count=len(report.issues)))
            for index, issue in enumerate(report.issues, 1):
                severity = _SEVERITY_LABELS.get(issue.severity.value, issue.severity.value)
                lines.append(f"{index}. [{severity}] {issue.message}")
                details = issue.details or {}
                why = details.get("why_it_matters")
                if why:
                    lines.append(f"   {t('quality_why', 'Почему это важно:')} {why}")
                actions = details.get("recommended_actions", [])
                if actions:
                    lines.append(f"   {t('quality_recommended', 'Рекомендуемые действия:')}")
                    for action in actions:
                        lines.append(f"     - {action.get('description', '')}")
                lines.append("")
        else:
            lines.append(t("quality_no_issues", "Проблем не обнаружено — данные готовы к расчётам."))
        self.issues_edit.setPlainText("\n".join(lines))
        self._update_action_buttons(report)

    def _update_action_buttons(self, report: DataQualityReport) -> None:
        action_codes = {
            action.get("code")
            for issue in report.issues
            for action in (issue.details or {}).get("recommended_actions", [])
        }
        self.btn_fill_missing.setVisible("fill_interpolation" in action_codes)
        self.btn_fill_missing_corr.setVisible("fill_correlation" in action_codes)
        self.btn_check_homogeneity.setVisible("homogeneity_investigate" in action_codes)
        self.btn_detect_outliers.setVisible("outliers_review" in action_codes)

    def _clear(self) -> None:
        """Clear the tab display and action controls."""
        for label in (
            self.dataset_name_label,
            self.dataset_id_label,
            self.n_points_label,
            self.completeness_label,
            self.quality_score_label,
            self.quality_grade_label,
            self.homogeneity_label,
            self.stationarity_label,
            self.n_missing_label,
            self.n_outliers_label,
        ):
            label.setText("—")
        self.issues_edit.clear()
        self._report = None
        for button in (
            self.btn_fill_missing,
            self.btn_fill_missing_corr,
            self.btn_check_homogeneity,
            self.btn_detect_outliers,
        ):
            button.setVisible(False)


__all__ = ["TabDataQuality"]
