"""
gui/tabs/tab_report.py
Engineering report tab (stage 6 of DOCS/ROADMAP.md).

Assembles a 13-section report from the open project (data, quality, methodology,
parameters, calculations, scenarios), previews it as plain text and saves it to
the project `reports/` folder. Heavy assembly runs in a background QThread so
the UI does not freeze.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.services.report_service import OPTIONAL_SECTION_IDS, Report, ReportService
from core.services.scenario_service import ScenarioService

try:
    from i18n import t
except Exception:  # pragma: no cover - i18n optional at early bootstrap

    def t(key: str, fallback: str = "") -> str:
        return fallback


TITLE_STYLE = "font-size: 15px; font-weight: bold; color: #0D47A1;"
HINT_STYLE = (
    "color: #666; font-style: italic; padding: 8px; background: #f0f0f0; border-radius: 4px;"
)


class ReportBuildWorker(QThread):
    """Build the report off the UI thread (including quality analysis)."""

    report_ready = pyqtSignal(object)  # Report
    failed = pyqtSignal(str)

    def __init__(
        self,
        kwargs: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._kwargs = kwargs

    def run(self) -> None:  # noqa: D102 - QThread entry point
        try:
            self._fill_quality_report()
            service = ReportService()
            report = service.build_report(**self._kwargs)
            self.report_ready.emit(report)
        except Exception as exc:  # surface to the tab, never crash the app
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _fill_quality_report(self) -> None:
        """Analyze dataset quality in the worker thread, not on the UI thread."""
        if self._kwargs.get("quality_report") is not None:
            return
        context = self._kwargs.pop("_service_container", None)
        datasets = self._kwargs.get("datasets") or []
        if context is None or not datasets:
            return
        quality_service = getattr(context, "quality", None)
        if quality_service is None:
            return
        try:
            self._kwargs["quality_report"] = quality_service.analyze(datasets[0])
        except (ValueError, TypeError, AttributeError, NotImplementedError):
            self._kwargs["quality_report"] = None


class ReportTab(QWidget):
    """Панель «Отчёт»: параметры включения, сборка, предпросмотр, сохранение."""

    status_message = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        project_service=None,
        scenario_service: ScenarioService | None = None,
        service_container=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_service = project_service
        self._scenario_service = scenario_service
        self._container = service_container
        self._report: Report | None = None
        self._worker: ReportBuildWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel(t("report_title", "Инженерный отчёт"))
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            t(
                "report_hint",
                "Отчёт собирается из данных открытого проекта: 13 разделов, "
                "предупреждения и вывод. Сборка идёт в фоновом потоке.",
            )
        )
        hint.setStyleSheet(HINT_STYLE)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # --- Options: what to include ---
        options_group = QGroupBox(t("report_options", "Что включать в отчёт"))
        options_layout = QHBoxLayout(options_group)
        self.check_scenarios = QCheckBox(t("report_include_scenarios", "Сценарии"))
        self.check_scenarios.setChecked(True)
        self.check_charts = QCheckBox(t("report_include_charts", "Графики"))
        self.check_charts.setChecked(True)
        self.check_checks = QCheckBox(t("report_include_checks", "Проверки"))
        self.check_checks.setChecked(True)
        options_layout.addWidget(self.check_scenarios)
        options_layout.addWidget(self.check_charts)
        options_layout.addWidget(self.check_checks)
        options_layout.addStretch()
        layout.addWidget(options_group)

        # --- Title override + actions ---
        actions = QHBoxLayout()
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText(t("report_title_placeholder", "Заголовок отчёта (из проекта)"))
        actions.addWidget(self.edit_title, stretch=1)

        self.btn_build = QPushButton(t("report_build", "Сформировать"))
        self.btn_build.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; font-weight: bold; "
            "padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0D47A1; }"
            "QPushButton:disabled { background-color: #90A4AE; }"
        )
        self.btn_build.clicked.connect(self.build_report)
        actions.addWidget(self.btn_build)

        self.btn_save = QPushButton(t("report_save_as", "Сохранить как…"))
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_report_as)
        actions.addWidget(self.btn_save)
        layout.addLayout(actions)

        # --- Preview ---
        preview_group = QGroupBox(t("report_preview", "Предпросмотр"))
        preview_layout = QVBoxLayout(preview_group)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText(
            t("report_preview_placeholder", "Нажмите «Сформировать», чтобы увидеть отчёт…")
        )
        preview_layout.addWidget(self.preview)
        layout.addWidget(preview_group, stretch=1)

        self.setLayout(layout)

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """No-op placeholder: the report is built on demand, not on project change."""
        return None

    # ------------------------------------------------------------------
    # Build / save
    # ------------------------------------------------------------------
    def _included_sections(self) -> set[str]:
        """Section ids selected by the checkboxes (core sections are always on)."""
        from core.services.report_service import SECTION_IDS

        include = set(SECTION_IDS) - OPTIONAL_SECTION_IDS
        if self.check_scenarios.isChecked():
            include.add("scenarios")
        if self.check_charts.isChecked():
            include.add("charts")
        if self.check_checks.isChecked():
            include.add("checks")
        return include

    def _collect_kwargs(self) -> dict[str, Any]:
        """Gather plain inputs from the open project / services."""
        title = self.edit_title.text().strip()
        datasets: list = []
        parameters: dict[str, Any] = {}
        calculations: list = []
        scenarios: list = []
        project_warnings: list[str] = []

        if self._project_service is not None:
            if not title:
                title = self._project_service.project.name
            datasets = list(self._project_service.datasets)
            parameters = dict(self._project_service.parameters)
            calculations = list(self._project_service.calculations)
            scenarios = list(self._project_service.scenarios)
            project_warnings = list(self._project_service.warnings)

        scenario_comparison: list[dict[str, Any]] = []
        if self._scenario_service is not None:
            try:
                scenario_comparison = self._scenario_service.compare()
                # Prefer live scenario list from the scenario service when present.
                live = self._scenario_service.list()
                if live:
                    scenarios = live
            except (KeyError, ValueError, TypeError, AttributeError):
                scenario_comparison = []

        norms: list[str] = []
        for result in calculations:
            standard = result.metadata.methodology.standard
            if standard and standard not in norms:
                norms.append(standard)

        return {
            "title": title,
            "datasets": datasets,
            "parameters": parameters,
            "quality_report": None,  # filled in ReportBuildWorker (background)
            "calculations": calculations,
            "scenarios": scenarios,
            "scenario_comparison": scenario_comparison,
            "validation": None,
            "charts": [],  # GUI chart titles can be wired later
            "project_warnings": project_warnings,
            "norms": norms,
            "include": self._included_sections(),
            "_service_container": self._container,  # popped by the worker
        }

    def build_report(self) -> None:
        """Assemble the report in a background thread and show the preview."""
        if self._worker is not None and self._worker.isRunning():
            return  # already building
        self.btn_build.setEnabled(False)
        self.status_message.emit(t("report_building", "Формирование отчёта…"))
        kwargs = self._collect_kwargs()
        # build_report() must not see the private key; worker pops it first.
        self._worker = ReportBuildWorker(kwargs, parent=self)
        self._worker.report_ready.connect(self._on_report_ready)
        self._worker.failed.connect(self._on_report_failed)
        self._worker.start()

    def _on_report_ready(self, report: object) -> None:
        self._report = report  # type: ignore[assignment]
        assert isinstance(report, Report)
        text = ReportService.render_text(report)
        self.preview.setPlainText(text)
        self.btn_save.setEnabled(True)
        self.btn_build.setEnabled(True)
        self.status_message.emit(
            t("report_ready", f"Отчёт готов: {report.section_count} разделов")
        )
        self._worker = None

    def _on_report_failed(self, message: str) -> None:
        self.btn_build.setEnabled(True)
        self._worker = None
        self.error.emit(message)

    def save_report_as(self) -> None:
        """Save the last built report as a text file (default: project reports/)."""
        if self._report is None:
            return
        default_dir = self._default_reports_dir()
        default_dir.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("report_save_title", "Сохранить отчёт"),
            str(default_dir / "report.txt"),
            "Текстовые файлы (*.txt);;Все файлы (*)",
        )
        if not path:
            return
        try:
            target = ReportService.save_report(self._report, path)
        except OSError as exc:
            self.error.emit(f"Не удалось сохранить отчёт: {exc}")
            return
        if self._project_service is not None:
            with contextlib.suppress(KeyError, TypeError, ValueError, OSError):
                self._project_service.register_report(
                    {"type": "txt", "path": str(target)}
                )
        self.status_message.emit(
            t("report_saved", f"Отчёт сохранён: {target.name}")
        )

    def _default_reports_dir(self) -> Path:
        if self._project_service is not None and self._project_service.path is not None:
            return self._project_service.path.parent / "reports"
        return Path.cwd() / "reports"

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        """Stop the worker thread if the tab is closed mid-build."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(2000)
        super().closeEvent(event)


__all__ = ["ReportTab"]
