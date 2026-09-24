"""Packaging contract for P3.5 model exchange modules."""

from __future__ import annotations

import build


def test_build_includes_model_exchange_modules() -> None:
    # Given: the PyInstaller hidden-import configuration.
    # Then: service and reusable UI helper are present in the packaged app.
    assert "core.services.model_export_service" in build.HIDDEN_IMPORTS
    assert "gui.tabs.model_export_controls" in build.HIDDEN_IMPORTS
