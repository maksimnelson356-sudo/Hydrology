"""P3.4 GUI contract."""

from __future__ import annotations

import os

from core.services.hydraulic_uncertainty_service import HydraulicUncertaintyService
from gui.tabs.hydraulic_uncertainty_panel import HydraulicUncertaintyPanel


def test_hydraulic_panel_renders_quantiles_and_clears_on_engine_change():
    # Given: a headless hydraulic uncertainty panel.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None
    panel = HydraulicUncertaintyPanel()
    try:
        panel.hydraulic_n.setValue(20)
        request = panel.build_request()

        # When: a result is rendered and then the engine changes.
        result = HydraulicUncertaintyService.run(request)
        panel.show_result(result)
        assert panel.hydraulic_table.rowCount() == len(result.metrics)
        assert panel.hydraulic_figure.axes[0].lines
        panel.hydraulic_engine.setCurrentIndex(1)

        # Then: stale quantiles and plot are cleared.
        assert panel.hydraulic_table.rowCount() == 0
        assert not panel.hydraulic_figure.axes
    finally:
        panel.close()
        panel.deleteLater()
