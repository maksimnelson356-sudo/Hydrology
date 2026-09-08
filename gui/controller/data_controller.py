"""
gui/controller/data_controller.py
Контроллер загрузки/валидации/распределения данных.
Вынесен из main_window.py для разделения ответственности (SRP).
"""

from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

from core.stats.composite_curves import compute_composite_curve
from core.stats.data_loader import load_hydrological_data
from core.stats.gts_integration import build_gts_frequency_curve
from core.stats.homogeneity import check_homogeneity_full
from core.stats.report_export import generate_txt_report
from core.stats.series_extension import full_extension_workflow
from core.stats.sheet_reader import read_work_sheet
from core.stats.trends import full_trend_analysis


class DataController(QObject):
    """
    Управление данными: загрузка, парсинг, распределение по виджетам,
    статистические расчёты в фоновом потоке.
    
    Сигналы:
        data_loaded: исходный DataFrame, список постов
        post_changed: выбранный пост, его DataFrame
        calculation_done: тип расчёта, результат
        error: сообщение об ошибке
    """
    data_loaded = pyqtSignal(object, list)      # df_raw, available_posts
    post_changed = pyqtSignal(str, object)      # post_name, df
    calculation_done = pyqtSignal(str, dict)    # calc_type, result
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._df_raw: pd.DataFrame | None = None
        self._year_col: str | None = None
        self._available_posts: list[str] = []
        self._all_posts: dict[str, pd.DataFrame] = {}
        self._current_post: str | None = None

    # --- Properties ---
    @property
    def df_raw(self) -> pd.DataFrame | None:
        return self._df_raw

    @property
    def year_col(self) -> str | None:
        return self._year_col

    @property
    def available_posts(self) -> list[str]:
        return self._available_posts

    @property
    def current_post(self) -> str | None:
        return self._current_post

    @property
    def all_posts(self) -> dict[str, pd.DataFrame]:
        return self._all_posts

    # --- Public API ---
    def load_from_file(self, filepath: str) -> bool:
        """Загрузить данные из Excel-файла (единый шаблон или плоский)."""
        try:
            xls = pd.ExcelFile(filepath)
            self._df_raw, self._year_col, self._available_posts = load_hydrological_data(filepath)
            self._all_posts = {}
            found = self._parse_work_sheets(xls)
            if found or self._available_posts:
                self._populate_all_posts()
                self.data_loaded.emit(self._df_raw, self._available_posts)
                self.status.emit(f"Загружено постов: {len(self._available_posts)}")
                return True
            self.error.emit("Не удалось распознать формат файла")
            return False
        except (OSError, FileNotFoundError, ValueError, KeyError, TypeError) as e:
            self.error.emit(f"Ошибка загрузки: {e}")
            return False

    def set_post(self, post_name: str) -> bool:
        """Сменить текущий пост и уведомить подписчиков."""
        if post_name not in self._available_posts:
            return False
        self._current_post = post_name
        df = self._all_posts.get(post_name)
        if df is not None:
            self.post_changed.emit(post_name, df)
        return True

    def get_current_series(self) -> pd.DataFrame | None:
        """Вернуть DataFrame текущего поста (year, value)."""
        if self._current_post and self._current_post in self._all_posts:
            return self._all_posts[self._current_post]
        return None

    # --- Internal: parsing ---
    def _parse_work_sheets(self, xls: pd.ExcelFile) -> bool:
        """Парсить все рабочие листы единого шаблона."""
        found = False
        sheet_mapping = {
            "work1": ["Норма годового стока", "Норма стока"],
            "work2": ["Внутригодовое распределение", "Внутригодовое"],
            "work3": ["Минимальный сток", "Минимальный"],
            "work4": ["Максимальный сток", "Максимальный"],
            "work5": ["Кривая Q(H)", "Кривая QH", "Q(H)"],
            "work6": ["Ледовые явления", "Лёдовые", "Лед"],
            "work7": ["Водный баланс", "Баланс"],
            "work8": ["Рацион + IDF + Гидрографы", "Рацион", "IDF", "Гидрографы"],
            "work9": ["FDC + Регрессии + Статистика", "FDC", "Регрессии", "Статистика"],
            "work10": ["Экология + Базовый сток", "Экология", "Базовый"],
        }

        for widget_name, candidates in sheet_mapping.items():
            sheet = self._find_sheet(xls, candidates)
            if sheet:
                try:
                    df = read_work_sheet(xls, [sheet])
                    if not df.empty:
                        self._all_posts[widget_name] = df
                        found = True
                except (ValueError, TypeError, KeyError) as e:
                    print(f"[WARN] Ошибка загрузки '{candidates}': {e}")
        return found

    def _find_sheet(self, xls: pd.ExcelFile, candidates: list[str]) -> str | None:
        lower_names = [sn.strip().lower().replace(" ", "") for sn in xls.sheet_names]
        for kw in candidates:
            kw_clean = kw.strip().lower().replace(" ", "")
            for i, sn in enumerate(lower_names):
                if kw_clean in sn:
                    return xls.sheet_names[i]
        return None

    def _populate_all_posts(self):
        """Собрать все посты из загруженных листов."""
        # Посты уже в self._available_posts из load_hydrological_data
        # Если из work-листов пришли новые — объединить
        pass

    # --- Statistical calculations (delegated to core.stats) ---
    def check_homogeneity(self, series: pd.DataFrame) -> dict:
        return check_homogeneity_full(series['value'].values)

    def trend_analysis(self, series: pd.DataFrame) -> dict:
        return full_trend_analysis(series)

    def build_composite_curve(self, series: pd.DataFrame, break_year: int) -> dict:
        return compute_composite_curve(
            series['value'].values, series['year'].values, break_year
        )

    def extend_series(self, Q_calc: pd.Series, Q_analog: pd.Series) -> dict:
        return full_extension_workflow(Q_calc, Q_analog)

    def gts_integration(self, series: pd.DataFrame, F_km2: float, P_mm: float, H_m: float) -> dict:
        return build_gts_frequency_curve(series['value'].values, F_km2, P_mm, H_m)

    def generate_report(self, output_path: str, post_name: str, stats: dict, **kwargs) -> str:
        return generate_txt_report(output_path, post_name, stats, **kwargs)
