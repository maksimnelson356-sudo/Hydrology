"""Background worker for P3.4 hydraulic uncertainty runs."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget

from core.services.hydraulic_uncertainty_service import (
    HydraulicUncertaintyError,
    HydraulicUncertaintyRequest,
    HydraulicUncertaintyResult,
    HydraulicUncertaintyService,
)


class HydraulicUncertaintyWorker(QThread):
    """Run hydraulic uncertainty propagation outside the GUI thread."""

    result_ready = pyqtSignal(HydraulicUncertaintyResult)
    error = pyqtSignal(str)

    def __init__(
        self,
        request: HydraulicUncertaintyRequest,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._request = request

    def run(self) -> None:  # noqa: D102 — QThread entry point
        try:
            result = HydraulicUncertaintyService.run(self._request)
        except HydraulicUncertaintyError as error:
            self.error.emit(str(error))
        except Exception as error:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK — GUI boundary
            self.error.emit(f"{type(error).__name__}: {error}")
        else:
            self.result_ready.emit(result)


__all__ = ["HydraulicUncertaintyWorker"]
