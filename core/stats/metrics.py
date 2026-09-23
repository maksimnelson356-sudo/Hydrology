"""
core/stats/metrics.py
Fit metrics for calibration and model comparison (stage P1.5).

Conventions:
- ``mse`` — lower is better;
- ``nse`` — Nash–Sutcliffe efficiency, higher is better (1.0 = perfect).

No GUI and no scipy here — pure numeric helpers over numpy.
"""

from __future__ import annotations

import numpy as np

__all__ = ["AVAILABLE_METRICS", "mse", "nse"]

#: Default metric ids exposed to the user (decision 9.5).
AVAILABLE_METRICS: tuple[str, ...] = ("mse", "nse")


def mse(observed: np.ndarray | list[float], predicted: np.ndarray | list[float]) -> float:
    """Mean squared error: mean((obs - pred)^2). Lower is better."""
    obs = np.asarray(observed, dtype=float).ravel()
    pred = np.asarray(predicted, dtype=float).ravel()
    if obs.shape != pred.shape:
        raise ValueError(f"mse: shape mismatch {obs.shape} vs {pred.shape}")
    if obs.size == 0:
        raise ValueError("mse: empty series")
    return float(np.mean((obs - pred) ** 2))


def nse(observed: np.ndarray | list[float], predicted: np.ndarray | list[float]) -> float:
    """Nash–Sutcliffe efficiency: 1 - SS_res / SS_tot. Higher is better."""
    obs = np.asarray(observed, dtype=float).ravel()
    pred = np.asarray(predicted, dtype=float).ravel()
    if obs.shape != pred.shape:
        raise ValueError(f"nse: shape mismatch {obs.shape} vs {pred.shape}")
    if obs.size == 0:
        raise ValueError("nse: empty series")
    ss_res = float(np.sum((obs - pred) ** 2))
    ss_tot = float(np.sum((obs - np.mean(obs)) ** 2))
    if ss_tot == 0.0:
        # Constant observed series: define perfect fit as 1.0, otherwise 0.0.
        return 1.0 if ss_res == 0.0 else 0.0
    return 1.0 - ss_res / ss_tot
