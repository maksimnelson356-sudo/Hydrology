"""
gui/workers/__init__.py
Инициализация пакета воркеров.
"""

from .calculation_workers import (
    AutoCsCvWorker,
    CalculationWorker,
    CompositeCurveWorker,
    ConfidenceBandsWorker,
    ExtensionWorker,
    FrequencyCurveWorker,
    GTSIntegrationWorker,
    HistoricalExtremesWorker,
    HomogeneityWorker,
    KritskyWorker,
    TrendWorker,
)

__all__ = [
    'CalculationWorker',
    'FrequencyCurveWorker',
    'HomogeneityWorker',
    'TrendWorker',
    'CompositeCurveWorker',
    'ExtensionWorker',
    'KritskyWorker',
    'AutoCsCvWorker',
    'HistoricalExtremesWorker',
    'GTSIntegrationWorker',
    'ConfidenceBandsWorker',
]
