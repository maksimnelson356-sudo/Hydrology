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

from . import (
    backwater,
    ecological_flow,
    flood_hydrograph,
    hydrological_periods,
    ice_phenomena,
    intra_annual,
    max_runoff,
    min_runoff_extended,
    minimal_runoff,
    rational_method,
    regional_regressions,
    reservoir_regulation,
    sedimentation,
    snowmelt,
    spillway,
    utils,
    water_balance,
)

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
