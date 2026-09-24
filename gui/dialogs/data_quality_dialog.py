"""
gui/dialogs/data_quality_dialog.py
Диалог «Качество данных» (Этап 2 дорожной карты).

Показывает отчёт DataQualityService: сводку качества, список проблем
(обнаружено → почему важно → что делать), рекомендации с кнопками-действиями.
Диалог ничего не считает сам — расчёт выполняет DataQualityWorker в фоне,
а действия делегируются колбэку MainWindow (принцип: данные не изменяются молча).
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.domain.models import DataQualityReport, Dataset
from gui.dialogs.data_quality_summary import render_summary
from gui.workers import DataQualityWorker
from i18n import t

# Цвета severity (в стиле gui/plot_style.COLORS)
_SEVERITY_COLORS = {
    "critical": "#C62828",
    "error": "#E65100",
    "warning": "#F9A825",
    "info": "#1565C0",
}
_SEVERITY_LABELS = {
    "critical": "Критично",
    "error": "Ошибка",
    "warning": "Предупреждение",
    "info": "Информация",
}


class DataQualityDialog(QDialog):
    """Обзор качества ряда: score/grade, проблемы, рекомендации."""

    def __init__(
        self,
        dataset: Dataset,
        post_name: str,
        parent: QWidget | None = None,
        methodology_id: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Качество данных — {post_name}")
        self.setMinimumSize(860, 620)
        self._dataset = dataset
        self._post_name = post_name
        self._report: DataQualityReport | None = None
        self._recommendations: list[dict[str, Any]] = []
        self._worker: DataQualityWorker | None = None
        self._progress: QProgressDialog | None = None
        # Колбэки MainWindow: выполнение действия и сохранение отчёта в проект.
        self.action_requested = None   # Callable[[str, dict], None]
        self.report_finished = None    # Callable[[DataQualityReport, dict], None]
        self._build_ui()
        self._run_analysis(methodology_id, parameters)

    # ------------------------------------------------------------------
    # Интерфейс
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(t("quality_dialog_title", "Качество данных и рекомендации"))
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0D47A1;")
        layout.addWidget(title)

        hint = QLabel(
            t(
                "quality_dialog_hint",
                "Данные не изменяются автоматически: каждая проблема сопровождается "
                "объяснением и доступными действиями. Исправление выполняется только "
                "по явному выбору пользователя.",
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "color: #666; font-style: italic; padding: 6px; "
            "background: #f0f0f0; border-radius: 4px;"
        )
        layout.addWidget(hint)

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

        # Сводка: score / grade / краткие метрики
        summary_group = QGroupBox(t("quality_summary", "Сводка"))
        self._summary_grid = QGridLayout(summary_group)
        layout.addWidget(summary_group)

        # Таблица проблем
        issues_group = QGroupBox(t("quality_detected_issues", "Обнаруженные проблемы"))
        issues_layout = QVBoxLayout(issues_group)
        self._issues_table = QTableWidget(0, 3)
        self._issues_table.setHorizontalHeaderLabels(
            [
                t("quality_severity", "Серьёзность"),
                t("quality_found", "Что обнаружено"),
                t("quality_why_action", "Почему это важно / что делать"),
            ]
        )
        self._issues_table.horizontalHeader().setStretchLastSection(True)
        self._issues_table.setColumnWidth(0, 90)
        self._issues_table.setColumnWidth(1, 280)
        self._issues_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._issues_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._issues_table.setWordWrap(True)
        issues_layout.addWidget(self._issues_table)
        layout.addWidget(issues_group, 1)

        # Рекомендации с кнопками действий
        self._recommendations_group = QGroupBox(t("quality_actions", "Рекомендуемые действия"))
        self._recommendations_layout = QVBoxLayout(self._recommendations_group)
        self._recommendations_layout.setSpacing(8)
        layout.addWidget(self._recommendations_group, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._btn_close = QPushButton(t("quality_close", "Закрыть"))
        self._btn_close.clicked.connect(self.accept)
        buttons.addWidget(self._btn_close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    # Анализ (в фоне)
    # ------------------------------------------------------------------
    def _run_analysis(self, methodology_id: str | None, parameters: dict[str, Any] | None) -> None:
        self._progress = QProgressDialog(
            t("quality_progress", "Оценка качества данных..."), None, 0, 100, self
        )
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setValue(5)

        # Воркер без parent: диалог может закрыться раньше завершения потока —
        # уничтожать работающий QThread вместе с диалогом нельзя (краш Qt).
        self._worker = DataQualityWorker(
            self._dataset,
            methodology_id=methodology_id,
            parameters=parameters,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def done(self, result: int) -> None:  # noqa: D102 - override QDialog
        # При закрытии диалога корректно останавливаем фоновый поток.
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait(3000)
        super().done(result)

    def _on_progress(self, value: int, message: str) -> None:
        # QProgressDialog.setValue() может реентерабельно обработать события
        # (в т.ч. finished -> _on_worker_done, обнуляющий self._progress),
        # поэтому работаем с локальной ссылкой.
        progress = self._progress
        if progress is None:
            return
        progress.setValue(value)
        progress.setLabelText(message)

    def _on_worker_error(self, message: str) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        QMessageBox.critical(self, t("quality_error_title", "Ошибка оценки качества"), message)
        self.reject()

    def _on_worker_done(self, result: dict) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        self._report = result.get("report")
        self._recommendations = result.get("recommendations", [])
        self._apply_report()
        if self.report_finished is not None and self._report is not None:
            try:
                self.report_finished(self._report, result.get("report_dict", {}))
            except (TypeError, ValueError, AttributeError) as error:
                print(f"[WARN] Не удалось зарегистрировать отчёт в проекте: {error}")

    # ------------------------------------------------------------------
    # Отображение отчёта
    # ------------------------------------------------------------------
    def _apply_report(self) -> None:
        if self._report is None:
            return
        report = self._report

        # --- Сводка ---------------------------------------------------
        render_summary(self._summary_grid, report)

        # --- Проблемы --------------------------------------------------
        self._issues_table.setRowCount(0)
        for issue in report.issues:
            row_idx = self._issues_table.rowCount()
            self._issues_table.insertRow(row_idx)
            severity_item = QTableWidgetItem(
                _SEVERITY_LABELS.get(issue.severity.value, issue.severity.value)
            )
            color = QColor(_SEVERITY_COLORS.get(issue.severity.value, "#1565C0"))
            severity_item.setForeground(color)
            font = severity_item.font()
            font.setBold(True)
            severity_item.setFont(font)
            self._issues_table.setItem(row_idx, 0, severity_item)
            self._issues_table.setItem(row_idx, 1, QTableWidgetItem(issue.message))
            why = issue.details.get("why_it_matters", "")
            actions = issue.details.get("recommended_actions", [])
            action_text = "; ".join(
                str(action.get("description", "")) for action in actions
            )
            details_text = why + (f" → {action_text}" if action_text else "")
            self._issues_table.setItem(row_idx, 2, QTableWidgetItem(details_text))
        self._issues_table.resizeRowsToContents()

        # --- Рекомендации ---------------------------------------------
        while self._recommendations_layout.count():
            item = self._recommendations_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        seen: set[str] = set()
        for rec in self._recommendations:
            code = str(rec.get("code", ""))
            description = str(rec.get("description", "")).strip()
            if not code or code in seen or not description:
                continue
            seen.add(code)
            btn = QPushButton(f"→ {description}")
            btn.setToolTip(description)
            btn.setMinimumHeight(36)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _, c=code, ctx=rec: self._on_action(c, ctx))
            self._recommendations_layout.addWidget(btn)
        if self._recommendations_layout.count() == 0:
            self._recommendations_layout.addWidget(
                QLabel(t("quality_no_issues", "Проблем не обнаружено — данные готовы к расчётам."))
            )

    def _on_action(self, code: str, context: dict) -> None:
        """Передать выбранное действие в MainWindow (данные не меняются молча)."""
        if self.action_requested is None:
            QMessageBox.information(self, "Действие",
                                    f"Действие «{context.get('title', code)}» недоступно.")
            return
        self.accept()
        try:
            self.action_requested(code, context)
        except (TypeError, ValueError, RuntimeError) as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить действие: {error}")
