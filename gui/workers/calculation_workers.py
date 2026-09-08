"""
gui/workers/calculation_workers.py
QThread-воркеры для тяжелых расчётов (не блокируют UI).
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal


class CalculationWorker(QThread):
    """Базовый класс для расчётных воркеров."""
    finished = pyqtSignal(dict)  # result dict
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)  # percent, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            result = self._do_work()
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")

    def _do_work(self) -> dict:
        raise NotImplementedError


class FrequencyCurveWorker(CalculationWorker):
    """Расчёт кривой обеспеченности в фоне."""

    def __init__(self, values: np.ndarray, curve_type: str = "pearson3",
                 probabilities: np.ndarray | None = None,
                 use_corrected: bool = True,
                 parent=None):
        super().__init__(parent)
        self.values = values
        self.curve_type = curve_type
        self.probabilities = probabilities
        self.use_corrected = use_corrected

    def _do_work(self) -> dict:
        from core.stats.frequency import calculate_frequency_curve
        from core.stats.parameters import calculate_statistical_parameters

        self.progress.emit(10, "Вычисление статистических параметров...")
        params = calculate_statistical_parameters(self.values)

        self.progress.emit(30, f"Построение кривой ({self.curve_type})...")
        curve_df = calculate_frequency_curve(
            self.values,
            probabilities=self.probabilities,
            curve_type=self.curve_type,
            use_corrected=self.use_corrected
        )

        self.progress.emit(90, "Формирование результата...")
        return {
            'curve_df': curve_df,
            'params': params,
            'curve_type': self.curve_type,
            'status': 'ok'
        }


class HomogeneityWorker(CalculationWorker):
    """Проверка однородности в фоне."""

    def __init__(self, values: np.ndarray, alpha: float = 0.05, parent=None):
        super().__init__(parent)
        self.values = values
        self.alpha = alpha

    def _do_work(self) -> dict:
        from core.stats.homogeneity import check_homogeneity_full
        self.progress.emit(50, "Выполнение 12 критериев...")
        result = check_homogeneity_full(self.values, alpha=self.alpha)
        return {'homogeneity': result, 'status': 'ok'}


class TrendWorker(CalculationWorker):
    """Анализ тренда в фоне."""

    def __init__(self, years: np.ndarray, values: np.ndarray, parent=None):
        super().__init__(parent)
        self.years = years
        self.values = values

    def _do_work(self) -> dict:
        import pandas as pd

        from core.stats.trends import full_trend_analysis
        self.progress.emit(30, "Линейный тренд...")
        self.progress.emit(60, "Манна-Кендалл...")
        self.progress.emit(90, "Pettitt test...")
        df = pd.DataFrame({'year': self.years, 'value': self.values})
        result = full_trend_analysis(df)
        return {'trend': result, 'status': 'ok'}


class CompositeCurveWorker(CalculationWorker):
    """Составная кривая в фоне."""

    def __init__(self, values: np.ndarray, years: np.ndarray, break_year: int, parent=None):
        super().__init__(parent)
        self.values = values
        self.years = years
        self.break_year = break_year

    def _do_work(self) -> dict:
        from core.stats.composite_curves import compute_composite_curve
        self.progress.emit(50, "Вычисление составной кривой...")
        result = compute_composite_curve(
            self.values, self.years, self.break_year
        )
        return {'composite': result, 'status': 'ok'}


class ExtensionWorker(CalculationWorker):
    """Удлинение ряда в фоне."""

    def __init__(self, Q_calc, Q_analog, method: str = 'regression', parent=None):
        super().__init__(parent)
        self.Q_calc = Q_calc
        self.Q_analog = Q_analog
        self.method = method

    def _do_work(self) -> dict:
        from core.stats.series_extension import full_extension_workflow
        self.progress.emit(30, "Валидация корреляции...")
        self.progress.emit(60, f"Расчёт методом ({self.method})...")
        self.progress.emit(90, "Оценка погрешности...")
        result = full_extension_workflow(self.Q_calc, self.Q_analog, self.method)
        return {'extension': result, 'status': 'ok'}


class KritskyWorker(CalculationWorker):
    """Ординаты Крицкого-Менкеля в фоне."""

    def __init__(self, cs_cv: float, cv: float, parent=None):
        super().__init__(parent)
        self.cs_cv = cs_cv
        self.cv = cv

    def _do_work(self) -> dict:
        from core.stats.kritsky_tables import get_ordinates
        self.progress.emit(50, "Интерполяция таблиц...")
        ordinates = get_ordinates(self.cs_cv, self.cv)
        return {'ordinates': ordinates, 'cs_cv': self.cs_cv, 'cv': self.cv, 'status': 'ok'}


class AutoCsCvWorker(CalculationWorker):
    """Автоподбор Cs/Cv в фоне."""

    def __init__(self, values: np.ndarray, curve_type: str = 'pearson3',
                 p_range: tuple | None = None, precision: float = 0.05,
                 cs_cv_min: float = -2.0, cs_cv_max: float = 6.0, parent=None):
        super().__init__(parent)
        self.values = values
        self.curve_type = curve_type
        self.p_range = p_range
        self.precision = precision
        self.cs_cv_min = cs_cv_min
        self.cs_cv_max = cs_cv_max

    def _do_work(self) -> dict:
        from core.stats.frequency import auto_select_cs_cv
        self.progress.emit(20, "Перебор Cs/Cv значений...")
        result = auto_select_cs_cv(
            self.values, self.curve_type, self.p_range,
            self.precision, self.cs_cv_min, self.cs_cv_max
        )
        self.progress.emit(90, "Формирование результата...")
        return {'auto_cs_cv': result, 'status': 'ok'}


class HistoricalExtremesWorker(CalculationWorker):
    """Расчёт с историческими экстремумами в фоне."""

    def __init__(self, values: np.ndarray, extremes: list[dict], is_max: bool = True, parent=None):
        super().__init__(parent)
        self.values = values
        self.extremes = extremes
        self.is_max = is_max

    def _do_work(self) -> dict:
        from core.stats.frequency import HistoricalExtreme as HE
        from core.stats.frequency import compute_params_with_extremes
        he_list = [HE(e['year'], e['value'], e['period']) for e in self.extremes]
        self.progress.emit(50, "Обработка экстремумов...")
        result = compute_params_with_extremes(self.values, he_list, self.is_max)
        return {'extremes_result': result, 'status': 'ok'}


class GTSIntegrationWorker(CalculationWorker):
    """GTS интеграция в фоне."""

    def __init__(self, values: np.ndarray, F_km2: float, P_mm: float, H_m: float, parent=None):
        super().__init__(parent)
        self.values = values
        self.F_km2 = F_km2
        self.P_mm = P_mm
        self.H_m = H_m

    def _do_work(self) -> dict:
        from core.stats.gts_integration import build_gts_frequency_curve, gts_summary_table
        self.progress.emit(30, "Классификация ГТС...")
        self.progress.emit(70, "Построение кривой...")
        curve = build_gts_frequency_curve(self.values, self.F_km2, self.P_mm, self.H_m)
        summary = gts_summary_table(curve)
        return {'gts_curve': curve, 'gts_summary': summary, 'status': 'ok'}


class ConfidenceBandsWorker(CalculationWorker):
    """Доверительные полосы в фоне."""

    def __init__(self, values: np.ndarray, P_values: list | None = None,
                 confidence: float = 0.95, n_bootstrap: int = 1000, parent=None):
        super().__init__(parent)
        self.values = values
        self.P_values = P_values
        self.confidence = confidence
        self.n_bootstrap = n_bootstrap

    def _do_work(self) -> dict:
        from core.stats.confidence_bands import pearson3_confidence_bands
        self.progress.emit(10, f"Bootstrap ({self.n_bootstrap} итераций)...")
        result = pearson3_confidence_bands(
            self.values, self.P_values, self.confidence, self.n_bootstrap
        )
        return {'confidence_bands': result, 'status': 'ok'}
