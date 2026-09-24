"""
tests/test_routing_service.py
P3.2 — Muskingum routing: volume conservation, steady state, peak metrics,
validation errors, provenance, AST dependency guard.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from core.hydrorash.routing import MuskingumError, muskingum_coefficients, muskingum_route
from core.services.routing_service import (
    ROUTING_PROVENANCE,
    RoutingError,
    RoutingRequest,
    RoutingService,
)

# Stable demo parameters: K=6h, x=0.2, dt=3h.
# Non-negative coeffs require dt in [2Kx, 2K(1-x)] = [2.4, 9.6].
_K = 6.0
_X = 0.2
_DT = 3.0


def _triangular_inflow(n: int = 24, peak: float = 100.0, peak_at: int = 6) -> list[float]:
    """Simple triangular hydrograph rising to peak and receding to ~0."""
    out: list[float] = []
    for i in range(n):
        if i <= peak_at:
            out.append(peak * i / peak_at if peak_at else peak)
        else:
            # Linear recession over remaining steps, floor at 1 m³/s.
            span = n - 1 - peak_at
            out.append(max(1.0, peak * (1.0 - (i - peak_at) / span)))
    return out


def _request(inflow=None, dt=_DT, k=_K, x=_X, outflow0=None) -> RoutingRequest:
    return RoutingRequest(
        inflow=list(inflow) if inflow is not None else _triangular_inflow(),
        dt=dt,
        k=k,
        x=x,
        outflow0=outflow0,
    )


# ---------------------------------------------------------------------------
# Coefficients
# ---------------------------------------------------------------------------
def test_coefficients_sum_to_one():
    c0, c1, c2 = muskingum_coefficients(_K, _X, _DT)
    assert c0 + c1 + c2 == pytest.approx(1.0, abs=1e-12)
    for c in (c0, c1, c2):
        assert 0.0 <= c <= 1.0


def test_coefficients_validation_errors():
    with pytest.raises(MuskingumError, match="dt"):
        muskingum_coefficients(_K, _X, 0.0)
    with pytest.raises(MuskingumError, match="K"):
        muskingum_coefficients(0.5, _X, 1.0)  # K < dt
    with pytest.raises(MuskingumError, match="x"):
        muskingum_coefficients(_K, 0.6, _DT)  # x > 0.5
    with pytest.raises(MuskingumError, match="x"):
        muskingum_coefficients(_K, -0.1, _DT)


# ---------------------------------------------------------------------------
# Core equivalence / steady state
# ---------------------------------------------------------------------------
def test_constant_inflow_steady_outflow():
    """Constant Q in → constant Q out equal to input (steady state)."""
    const = [50.0] * 30
    result = muskingum_route(const, dt=_DT, k=_K, x=_X, outflow0=50.0)
    out = result["outflow"]
    assert out[0] == pytest.approx(50.0)
    # After a few steps of constant forcing, outflow settles at 50.
    assert out[-1] == pytest.approx(50.0, abs=1e-6)
    assert max(out) == pytest.approx(50.0, abs=1e-6)
    assert min(out) == pytest.approx(50.0, abs=1e-6)


def test_volume_conserved_within_one_percent():
    """ΣQ_out·dt ≈ ΣQ_in·dt within ±1% (open boundary steady start)."""
    inflow = _triangular_inflow(n=48, peak=200.0, peak_at=8)
    # Route with outflow0 = inflow[0] (steady initialisation).
    result = muskingum_route(inflow, dt=_DT, k=_K, x=_X, outflow0=inflow[0])
    vol_in = sum(inflow) * _DT
    vol_out = sum(result["outflow"]) * _DT
    assert vol_out == pytest.approx(vol_in, rel=0.01)


def test_peak_attenuation_non_negative_and_lag_non_negative():
    inflow = _triangular_inflow(n=36, peak=150.0, peak_at=6)
    result = muskingum_route(inflow, dt=_DT, k=_K, x=_X, outflow0=inflow[0])
    assert result["peak_attenuation_m3s"] >= -1e-9
    assert result["peak_lag_steps"] >= 0
    assert result["peak_out_m3s"] <= result["peak_in_m3s"] + 1e-9


def test_outflow_length_and_initial_condition():
    inflow = _triangular_inflow(n=20)
    explicit_o0 = 42.0
    result = muskingum_route(inflow, dt=_DT, k=_K, x=_X, outflow0=explicit_o0)
    assert len(result["outflow"]) == len(inflow)
    assert result["outflow"][0] == explicit_o0
    # Default outflow0 = inflow[0]
    result2 = muskingum_route(inflow, dt=_DT, k=_K, x=_X)
    assert result2["outflow"][0] == inflow[0]


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------
def test_service_provenance_and_dict():
    result = RoutingService.run(_request())
    assert result.provenance == ROUTING_PROVENANCE
    d = result.to_dict()
    assert d["provenance"] == ROUTING_PROVENANCE
    assert d["n_steps"] == len(_triangular_inflow())
    assert d["k"] == _K
    assert d["x"] == _X
    assert set(d["coefficients"]) == {"C0", "C1", "C2"}
    # JSON-safe floats.
    assert all(isinstance(v, float) for v in d["outflow"])


def test_service_matches_core_route():
    inflow = _triangular_inflow(n=24)
    core = muskingum_route(inflow, dt=_DT, k=_K, x=_X, outflow0=inflow[0])
    svc = RoutingService.run(_request(inflow, outflow0=inflow[0]))
    assert svc.outflow == pytest.approx(core["outflow"], abs=1e-12)
    assert svc.coefficients["C0"] == pytest.approx(core["coefficients"]["C0"])


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------
def test_empty_inflow_error():
    with pytest.raises(RoutingError, match="пуст"):
        RoutingService.run(_request(inflow=[]))


def test_single_point_inflow_error():
    with pytest.raises(RoutingError, match="2 точки"):
        RoutingService.run(_request(inflow=[10.0]))


def test_negative_inflow_error():
    with pytest.raises(RoutingError, match="inflow"):
        RoutingService.run(_request(inflow=[10.0, -1.0]))


def test_nan_inflow_error():
    with pytest.raises(RoutingError, match="конечным"):
        RoutingService.run(_request(inflow=[10.0, float("nan")]))


def test_k_less_than_dt_error():
    with pytest.raises(RoutingError, match="K"):
        RoutingService.run(_request(k=0.5, dt=3.0))


def test_x_out_of_range_error():
    with pytest.raises(RoutingError, match="x"):
        RoutingService.run(_request(x=0.7))


def test_bad_dt_error():
    with pytest.raises(RoutingError, match="dt"):
        RoutingService.run(_request(dt=0.0))


def test_unstable_coefficients_error():
    """dt < 2Kx makes C0 < 0 → core raises, service wraps as RoutingError."""
    with pytest.raises(RoutingError, match="unstable"):
        RoutingService.run(_request(k=6.0, x=0.2, dt=1.0))


def test_negative_outflow0_error():
    with pytest.raises(RoutingError, match="outflow0"):
        RoutingService.run(_request(outflow0=-5.0))


def _work7_widget():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from gui.widget_work7 import Work7Widget

    app = QApplication.instance() or QApplication([])
    assert app is not None
    return Work7Widget()


def test_work7_muskingum_plot_uses_requested_time_step():
    """The plotted inflow samples must match the routing interval."""
    # Given: a headless native widget with an explicit three-hour interval.
    widget = _work7_widget()
    widget.hg_method.setCurrentIndex(2)
    widget.hg_dt.setValue(3.0)

    try:
        # When: the Muskingum hydrograph is built.
        widget.build_hydrograph()

        # Then: both plotted series use the requested three-hour samples.
        lines = widget.hg_figure.axes[0].lines
        assert len(lines) == 2
        inflow_times = [float(value) for value in lines[0].get_xdata()]
        outflow_times = [float(value) for value in lines[1].get_xdata()]
        assert outflow_times == inflow_times
        assert all(
            current - previous == pytest.approx(_DT)
            for previous, current in zip(inflow_times, inflow_times[1:], strict=False)
        )
    finally:
        widget.close()
        widget.deleteLater()


def test_work7_muskingum_error_clears_previous_plot():
    """An invalid rerun must not leave a stale hydrograph visible."""
    # Given: a valid routing plot already rendered in the native widget.
    widget = _work7_widget()
    widget.hg_method.setCurrentIndex(2)
    widget.build_hydrograph()
    assert widget.hg_figure.axes

    try:
        # When: routing is rerun with K < dt.
        widget.hg_k.setValue(0.5)
        widget.build_hydrograph()

        # Then: the stale plot is removed and the error is reported.
        assert not widget.hg_figure.axes
        assert "Ошибка Мускингума" in widget.hg_result.toPlainText()
    finally:
        widget.close()
        widget.deleteLater()


def test_routing_service_public_export():
    import core.services as services

    assert services.ROUTING_PROVENANCE == ROUTING_PROVENANCE
    assert services.RoutingService is RoutingService


def test_build_includes_routing_modules():
    import build

    assert "core.hydrorash.routing" in build.HIDDEN_IMPORTS
    assert "core.services.routing_service" in build.HIDDEN_IMPORTS


# ---------------------------------------------------------------------------
# AST guard: service must not import banned heavy / non-core deps
# ---------------------------------------------------------------------------
def test_service_ast_no_banned_deps():
    service_path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "services"
        / "routing_service.py"
    )
    source = service_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = {"PyQt6", "pyqt", "matplotlib", "requests", "flask", "django"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)
    top_levels = {name.split(".")[0] for name in imported}
    assert not (top_levels & banned), f"banned imports: {top_levels & banned}"
    unexpected = top_levels - {"__future__", "dataclasses", "typing", "core"}
    assert not unexpected, f"unexpected import roots: {unexpected}"
    assert "core.hydrorash.routing" in imported or "core" in imported
