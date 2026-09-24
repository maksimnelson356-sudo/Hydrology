"""Headless contract for Work7 routing-model export."""

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


def test_work7_exposes_routing_export_after_muskingum(qt_app, tmp_path: Path) -> None:
    # Given: a Muskingum result already rendered in Work7.
    from gui.widget_work7 import Work7Widget

    widget = Work7Widget()
    widget.hg_method.setCurrentIndex(2)
    widget.build_hydrograph()
    target = tmp_path / "routing.json"

    try:
        # When: the export action is invoked with an explicit target.
        result_path = widget.export_hydrograph_model(target)

        # Then: the action is discoverable and writes the paired exchange files.
        assert widget.btn_export_model.isEnabled()
        assert result_path == target
        assert target.exists()
        assert target.with_suffix(".csv").exists()
    finally:
        widget.close()
        widget.deleteLater()
