"""
core/stats/__init__.py
Пакет статистической обработки гидрологических данных

Содержит модули:
- data_loader — загрузка данных
- frequency — частотный анализ
- advanced_frequency — продвинутый частотный анализ (GEV, Вейбулл, etc)
- parameters — параметры распределения
- missing_data — обработка пропусков
- trends — анализ трендов
- homogeneity — контроль однородности
- spectral — спектральный анализ
- flow_duration — кривая продолжительности расходов (FDC)
- baseflow — отделение базового стока
- composite_curves — составные кривые
- confidence_bands — доверительные полосы
- drought — анализ засух
- series_extension — продление ряда
- kritsky_tables — таблицы Критского
- gts_integration — интеграция с ГТС
- report — формирование отчётов
- report_export — экспорт отчётов
- critical_values — критические значения
"""

__all__ = [
    "data_loader",
    "frequency",
    "advanced_frequency",
    "parameters",
    "missing_data",
    "trends",
    "homogeneity",
    "spectral",
    "flow_duration",
    "baseflow",
    "composite_curves",
    "confidence_bands",
    "drought",
    "series_extension",
    "kritsky_tables",
    "gts_integration",
    "report",
    "report_export",
    "critical_values",
]
