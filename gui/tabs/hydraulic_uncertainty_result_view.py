"""Rendering helpers for the P3.4 hydraulic uncertainty result view."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

from core.services.hydraulic_uncertainty_service import HydraulicUncertaintyResult


class HydraulicResultView:
    """Render hydraulic metric rows and normalized quantile curves."""

    def __init__(
        self,
        table: QTableWidget,
        figure: Figure,
        canvas: FigureCanvasQTAgg,
    ) -> None:
        self._table = table
        self._figure = figure
        self._canvas = canvas

    def clear(self) -> None:
        """Remove stale rows and plot content."""
        self._table.setRowCount(0)
        self._figure.clear()
        self._canvas.draw_idle()

    def show(self, result: HydraulicUncertaintyResult) -> None:
        """Render exact table values and a p5/p50/p95 comparison plot."""
        self._table.setRowCount(len(result.metrics))
        for row, (name, summary) in enumerate(result.metrics.items()):
            values = (
                name,
                f"{summary.p5:.6g}",
                f"{summary.p50:.6g}",
                f"{summary.p95:.6g}",
                f"{summary.mean:.6g}",
                f"{summary.std:.6g}",
            )
            for column, value in enumerate(values):
                self._table.setItem(row, column, QTableWidgetItem(value))

        self._figure.clear()
        axes = self._figure.add_subplot(111)
        names = list(result.metrics)
        x_values = list(range(len(names)))
        normalized = {
            quantile: [
                getattr(result.metrics[name], quantile)
                / max(abs(result.metrics[name].p95), 1e-12)
                for name in names
            ]
            for quantile in ("p5", "p50", "p95")
        }
        axes.plot(
            x_values,
            normalized["p5"],
            marker="o",
            color="#90A4AE",
            linestyle="--",
            label="p5",
        )
        axes.plot(
            x_values,
            normalized["p50"],
            marker="o",
            color="#00695C",
            linewidth=2.0,
            label="p50",
        )
        axes.plot(
            x_values,
            normalized["p95"],
            marker="o",
            color="#0D47A1",
            linestyle=":",
            label="p95",
        )
        axes.set_xticks(x_values, names, rotation=20, ha="right")
        axes.set_ylabel("Квантиль / p95 метрики")
        axes.set_title(f"Гидравлический Monte Carlo: {result.engine}, seed={result.seed}")
        axes.grid(True, alpha=0.25)
        axes.legend()
        self._canvas.draw_idle()


__all__ = ["HydraulicResultView"]
