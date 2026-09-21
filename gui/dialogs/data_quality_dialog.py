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
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.domain.models import DataQualityReport, Dataset
from core.domain.models import ValidationSeverity
from gui.workers import DataQualityWorker

# Цвета severity (в стиле gui/plot_style.COLORS)
_SEVERITY_COLORS = {
    "critical": "#C62828",
    "error": "#E65100",
    "warning": "#F9A825",
    "info": "#1565C0",
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

        title = QLabel("Качество данных и рекомендации")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0D47A1;")
        layout.addWidget(title)

        hint = QLabel(
            "Данные не изменяются автоматически: каждая проблема сопровождается "
            "объяснением и доступными действиями. Исправление выполняется только "
            "по явному выбору пользователя."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "color: #666; font-style: italic; padding: 6px; "
            "background: #f0f0f0; border-radius: 4px;"
        )
        layout.addWidget(hint)

        # Сводка: score / grade / краткие метрики
        summary_group = QGroupBox("Сводка")
        self._summary_grid = QGridLayout(summary_group)
        layout.addWidget(summary_group)

        # Таблица проблем
        issues_group = QGroupBox("Обнаруженные проблемы")
        issues_layout = QVBoxLayout(issues_group)
        self._issues_table = QTableWidget(0, 3)
        self._issues_table.setHorizontalHeaderLabels(
            ["Серьёзность", "Что обнаружено", "Почему это важно / что делать"]
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
        self._recommendations_group = QGroupBox("Рекомендуемые действия")
        self._recommendations_layout = QVBoxLayout(self._recommendations_group)
        layout.addWidget(self._recommendations_group, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._btn_close = QPushButton("Закрыть")
        self._btn_close.clicked.connect(self.accept)
        buttons.addWidget(self._btn_close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    # Анализ (в фоне)
    # ------------------------------------------------------------------
    def _run_analysis(self, methodology_id: str | None, parameters: dict[str, Any] | None) -> None:
        self._progress = QProgressDialog("Оценка качества данных...", None, 0, 100, self)
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
        QMessageBox.critical(self, "Ошибка оценки качества", message)
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
        # Очищаем сводку (кроме самого layout)
        while self._summary_grid.count():
            item = self._summary_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._add_summary_cell(
            0, 0, "Оценка качества",
            f"{report.quality_grade} ({report.quality_score:.2f} / 1.0)",
        )
        self._add_summary_cell(
            0, 1, "Комплектность ряда",
            f"{report.completeness_ratio * 100:.0f} %",
        )
        self._add_summary_cell(1, 0, "Точек / пропусков",
                               f"{report.n_points} / {report.n_missing}")
        self._add_summary_cell(1, 1, "Выбросы (IQR)", str(report.n_outliers))
        self._add_summary_cell(2, 0, "Однородность",
                               "пройдена" if report.homogeneity_passed else "нарушена",
                               ok=report.homogeneity_passed)
        self._add_summary_cell(2, 1, "Стационарность",
                               "пройдена" if report.stationarity_passed else "нарушена",
                               ok=report.stationarity_passed)
        stats = report.statistics or {}
        if stats:
            self._add_summary_cell(
                3, 0, "Среднее / Cv",
                f"{stats.get('mean', float('nan')):.2f} / {stats.get('cv', float('nan')):.3f}",
            )
            self._add_summary_cell(
                3, 1, "Min / Max",
                f"{stats.get('min', float('nan')):.1f} / {stats.get('max', float('nan')):.1f}",
            )

        # --- Проблемы --------------------------------------------------
        self._issues_table.setRowCount(0)
        for issue in report.issues:
            row_idx = self._issues_table.rowCount()
            self._issues_table.insertRow(row_idx)
            severity_item = QTableWidgetItem(issue.severity.value)
            color = QColor(_SEVERITY_COLORS.get(issue.severity.value, "#1565C0"))
            severity_item.setForeground(color)
            font = severity_item.font()
            font.setBold(True)
            severity_item.setFont(font)
            self._issues_table.setItem(row_idx, 0, severity_item)
            self._issues_table.setItem(row_idx, 1, QTableWidgetItem(issue.message))
            why = issue.details.get("why_it_matters", "")
            actions = issue.details.get("recommended_actions", [])
            action_text = "; ".join(a.get("title", "") for a in actions)
            details_text = why + (f" → {action_text}" if action_text else "")
            self._issues_table.setItem(row_idx, 2, QTableWidgetItem(details_text))
        self._issues_table.resizeRowsToContents()

        # --- Рекомендации ---------------------------------------------
        # Очищаем предыдущие кнопки
        while self._recommendations_layout.count():
            item = self._recommendations_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        seen: set[tuple[str, str]] = set()
        for rec in self._recommendations:
            code = rec.get("code", "")
            title = rec.get("title", "")
            key = (code, title)
            if code in ("none", "") or key in seen:
                continue
            seen.add(key)
            btn = QPushButton(f"→ {title}")
            btn.setToolTip(rec.get("description", ""))
            btn.clicked.connect(lambda _, c=code, ctx=rec: self._on_action(c, ctx))
            self._recommendations_layout.addWidget(btn)
        if self._recommendations_layout.count() == 0:
            self._recommendations_layout.addWidget(QLabel("Проблем не обнаружено — данные готовы к расчётам."))

    def _add_summary_cell(self, row: int, col: int, label: str, value: str, ok: bool | None = None) -> None:
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        box.setStyleSheet("QFrame { background: #F5F7FA; border-radius: 4px; }")
        inner = QVBoxLayout(box)
        inner.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #666; font-size: 11px;")
        val = QLabel(value)
        val.setStyleSheet("font-weight: bold; font-size: 13px;")
        if ok is True:
            val.setStyleSheet("font-weight: bold; font-size: 13px; color: #2E7D32;")
        elif ok is False:
            val.setStyleSheet("font-weight: bold; font-size: 13px; color: #C62828;")
        inner.addWidget(lbl)
        inner.addWidget(val)
        self._summary_grid.addWidget(box, row, col)

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