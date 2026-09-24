"""P3.4 public export and packaging contract."""

from __future__ import annotations

import build
import core.services as services
from core.services.hydraulic_uncertainty_service import (
    HYDRAULIC_UNCERTAINTY_PROVENANCE,
    HydraulicUncertaintyService,
)


def test_public_exports_and_build_hidden_imports():
    # Given: package and packaging configuration.
    # When/Then: P3.4 service and GUI modules are shipped publicly.
    assert services.HYDRAULIC_UNCERTAINTY_PROVENANCE == HYDRAULIC_UNCERTAINTY_PROVENANCE
    assert services.HydraulicUncertaintyService is HydraulicUncertaintyService
    assert "core.services.hydraulic_uncertainty_service" in build.HIDDEN_IMPORTS
    assert "gui.tabs.hydraulic_uncertainty_panel" in build.HIDDEN_IMPORTS
    assert "gui.tabs.hydraulic_uncertainty_support" in build.HIDDEN_IMPORTS
    assert "gui.tabs.hydraulic_uncertainty_result_view" in build.HIDDEN_IMPORTS
    assert "gui.workers.hydraulic_uncertainty_worker" in build.HIDDEN_IMPORTS
