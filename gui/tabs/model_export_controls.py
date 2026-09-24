"""Reusable file-action control for P3.5 engineering-model exchange."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from core.services.model_export_types import ModelExportError
from i18n import t


class ModelExportButton(QPushButton):
    """A push button that chooses a JSON destination and runs one exporter."""

    def __init__(
        self,
        label: str,
        dialog_title: str,
        default_name: str,
        exporter: Callable[[Path], None],
        parent=None,
    ) -> None:
        super().__init__(label, parent)
        self._dialog_title = dialog_title
        self._default_name = default_name
        self._exporter = exporter
        self.clicked.connect(self._export_from_dialog)

    def export_to(self, target: Path) -> bool:
        """Export to an explicit target and report whether it succeeded."""
        try:
            self._exporter(target)
        except ModelExportError as error:
            QMessageBox.critical(
                self,
                t("model_export_error_title", "Ошибка экспорта модели"),
                str(error),
            )
            return False
        return True

    def _export_from_dialog(self) -> None:
        target = self.choose_target()
        if target is not None:
            self.export_to(target)

    def choose_target(self) -> Path | None:
        """Ask for a JSON path; return None when the user cancels."""
        selected, _ = QFileDialog.getSaveFileName(
            self,
            self._dialog_title,
            str(Path.cwd() / self._default_name),
            "JSON model (*.json)",
        )
        return Path(selected) if selected else None
