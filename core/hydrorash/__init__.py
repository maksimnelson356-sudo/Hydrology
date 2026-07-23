"""
core/hydrorash/__init__.py
Пакет гидрологических расчётов

Содержит модули:
- utils — статистические характеристики, регрессия, продление рядов
- hydrological_periods — периоды водохозяйственного года
- intra_annual — внутригодовое распределение стока
- minimal_runoff — минимальный сток
- max_runoff — максимальный сток
- ice_phenomena — ледовые явления
- min_runoff_extended — расширенные расчёты минимальных стоков
- water_balance — водный баланс
- rational_method — метод рациона и IDF кривые
- flood_hydrograph — форма паводочной кривой
- snowmelt — прогноз таяния снега
- regional_regressions — регрессионные уравнения для нелогометрических рек
- spillway — пропускная способность ППУ
- backwater — кривые подпора (ГВП)
- reservoir_regulation — многолетнее регулирование стока
- sedimentation — накопление наносов
- ecological_flow — экологический сток (Тессман, ECOFRAME)
"""

from . import utils
from . import hydrological_periods
from . import intra_annual
from . import minimal_runoff
from . import max_runoff
from . import ice_phenomena
from . import min_runoff_extended
from . import water_balance
from . import rational_method
from . import flood_hydrograph
from . import snowmelt
from . import regional_regressions
from . import spillway
from . import backwater
from . import reservoir_regulation
from . import sedimentation
from . import ecological_flow

__all__ = [
    "utils",
    "hydrological_periods",
    "intra_annual",
    "minimal_runoff",
    "max_runoff",
    "ice_phenomena",
    "min_runoff_extended",
    "water_balance",
    "rational_method",
    "flood_hydrograph",
    "snowmelt",
    "regional_regressions",
    "spillway",
    "backwater",
    "reservoir_regulation",
    "sedimentation",
    "ecological_flow",
]
