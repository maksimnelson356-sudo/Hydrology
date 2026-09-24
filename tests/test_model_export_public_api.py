"""Public API contract for P3.5 model exchange."""

from __future__ import annotations

import core.services as services
from core.services.model_export_types import ModelKind


def test_model_export_symbols_are_public() -> None:
    # Given: the public service package.
    # Then: the stable model kind and error type are available to consumers.
    assert services.ModelKind.REACHES.value == ModelKind.REACHES.value
    assert services.ModelExportError.__name__ == "ModelExportError"
