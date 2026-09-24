"""Headless contract for Work9 reach-model export."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None
    return app


def test_work9_exports_reach_table_without_new_navigation(qt_app, tmp_path: Path) -> None:
    # Given: the existing Work9 widget with its default reach table.
    from gui.widget_work9 import Work9Widget

    widget = Work9Widget()
    target = tmp_path / "reaches.json"

    try:
        # When: the reach export action is invoked.
        result_path = widget.export_reach_model(target)

        # Then: the configured reaches are exported as a P3.5 model.
        assert result_path == target
        assert result_path.exists()
        assert result_path.with_suffix(".csv").exists()
        assert widget.btn_export_model.text()
    finally:
        widget.close()
        widget.deleteLater()
