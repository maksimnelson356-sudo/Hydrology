"""
core/hydrorash/hydrological_periods.py
Класс для работы с периодами водохозяйственного года.

Перенесено из HydroRash с адаптацией под hydrolib.
"""

from typing import List, Optional
import re


class HydrologicalPeriods:
    """
    Класс для хранения и управления периодами водохозяйственного года.

    По умолчанию настроен на типичный режим рек с весенним половодьем
    (большинство рек России и СНГ).
    """

    DEFAULT_WATER_YEAR_START = 4                    # Апрель
    DEFAULT_NON_LIMITING = list(range(4, 11))       # IV–X
    DEFAULT_LIMITING = [11, 12, 1, 2, 3]            # XI–III
    DEFAULT_LIMITING_SEASON = [12, 1, 2]            # XII–II

    MONTH_NAMES_RU = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }

    def __init__(
        self,
        water_year_start_month: Optional[int] = None,
        non_limiting_months: Optional[List[int]] = None,
        limiting_months: Optional[List[int]] = None,
        limiting_season_months: Optional[List[int]] = None
    ):
        self.water_year_start_month = (
            water_year_start_month or self.DEFAULT_WATER_YEAR_START
        )
        self.non_limiting_months = (
            sorted(non_limiting_months) if non_limiting_months
            else self.DEFAULT_NON_LIMITING.copy()
        )
        self.limiting_months = (
            sorted(limiting_months) if limiting_months
            else self.DEFAULT_LIMITING.copy()
        )
        self.limiting_season_months = (
            sorted(limiting_season_months) if limiting_season_months
            else self.DEFAULT_LIMITING_SEASON.copy()
        )
        self._validate()

    def _validate(self):
        all_months = set(range(1, 13))
        if not (1 <= self.water_year_start_month <= 12):
            raise ValueError("Месяц начала водохозяйственного года должен быть от 1 до 12")
        if not set(self.non_limiting_months).issubset(all_months):
            raise ValueError("Некорректные месяцы в Нелимитирующем периоде")
        if not set(self.limiting_months).issubset(all_months):
            raise ValueError("Некорректные месяцы в Лимитирующем периоде")
        if self.limiting_season_months and not set(self.limiting_season_months).issubset(all_months):
            raise ValueError("Некорректные месяцы в Лимитирующем сезоне")

    @classmethod
    def from_text(
        cls,
        start_month_str: str,
        non_limiting_text: str = "4-10",
        limiting_text: str = "11-3"
    ):
        """Создание из текстового представления."""
        start = int(start_month_str) if not isinstance(start_month_str, int) else start_month_str

        def parse_range(text: str) -> List[int]:
            months = []
            for part in text.replace(",", " ").split():
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-")
                    a, b = int(a), int(b)
                    if a <= b:
                        months.extend(range(a, b + 1))
                    else:
                        months.extend(range(a, 13))
                        months.extend(range(1, b + 1))
                else:
                    months.append(int(part))
            return sorted(set(months))

        nlp = parse_range(non_limiting_text)
        lp = parse_range(limiting_text)
        return cls(water_year_start_month=start, non_limiting_months=nlp, limiting_months=lp)

    def __repr__(self):
        return (f"ВГ начинается: {self.MONTH_NAMES_RU[self.water_year_start_month]}, "
                f"НЛП: {self.months_to_str(self.non_limiting_months)}, "
                f"ЛП: {self.months_to_str(self.limiting_months)}")

    @staticmethod
    def months_to_str(months: List[int]) -> str:
        MONTHS_SHORT = {1:"I",2:"II",3:"III",4:"IV",5:"V",6:"VI",
                        7:"VII",8:"VIII",9:"IX",10:"X",11:"XI",12:"XII"}
        return "–".join(MONTHS_SHORT.get(m, str(m)) for m in months)
