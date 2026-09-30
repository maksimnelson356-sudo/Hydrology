"""Регрессионные тесты core/hydrorash/regional_regressions.py.

Модуль реализует частные региональные зависимости Q = A x F^n на основе
зашитых коэффициентов. Нормативный статус (см. аудит по
DOCS/NORMATIVE/SP-529.1325800.2023.pdf): класс метода соответствует перечню
п. 7.1.2, но СП 529 (7.28), (7.41) и (7.42) НЕ реализованы, коэффициенты не
имеют подтверждённого источника (п. 4.11 не выполнен).

Эти тесты закрывают инженерную группу C и одновременно фиксируют границу
норм��тивной работы:

- неизвестный регион обязан давать ValueError, а не молчаливую подмену;
- площадь и период возврата защищены от неположительных значений, но никаких
  новых нормативных ограничений (T >= 2, T <= 100) не введено;
- искусственное плато при T > 100 устранено, логарифмическая конструкция
  продолжена за T = 100 в том же виде;
- коэффициенты всех 9 регионов, включая неиспользуемое поле 'exponent',
  зафиксированы числами, чтобы правка поведения их не сдвинула.

Модуль не меняет публичный API: 5 функций, их сигнатуры и REGIONAL_COEFFICIENTS
остаются прежними.
"""

from __future__ import annotations

import math

import pytest

from core.hydrorash import regional_regressions as rr

F = 1000.0
CENTRAL = "central_russia"

# Полный снимок коэффициентных наборов. Любое изменение чисел здесь означает
# изменение нормативно не подтверждённых данных и требует отдельного решения.
EXPECTED_COEFFICIENTS = {
    "central_russia": {
        "mean_runoff": (0.0025, 0.85), "peak_Q2": (0.08, 0.65),
        "peak_Q10": (0.12, 0.62), "peak_Q100": (0.18, 0.58),
        "min_winter": (0.0003, 0.90),
    },
    "volga_basin": {
        "mean_runoff": (0.0020, 0.88), "peak_Q2": (0.065, 0.68),
        "peak_Q10": (0.10, 0.64), "peak_Q100": (0.15, 0.60),
        "min_winter": (0.00025, 0.92),
    },
    "ob_irtysh": {
        "mean_runoff": (0.0030, 0.82), "peak_Q2": (0.09, 0.63),
        "peak_Q10": (0.13, 0.60), "peak_Q100": (0.20, 0.56),
        "min_winter": (0.00035, 0.88),
    },
    "yenisei": {
        "mean_runoff": (0.0035, 0.80), "peak_Q2": (0.10, 0.60),
        "peak_Q10": (0.15, 0.57), "peak_Q100": (0.22, 0.53),
        "min_winter": (0.0004, 0.85),
    },
    "lena": {
        "mean_runoff": (0.0032, 0.81), "peak_Q2": (0.095, 0.61),
        "peak_Q10": (0.14, 0.58), "peak_Q100": (0.21, 0.54),
        "min_winter": (0.00038, 0.86),
    },
    "kama": {
        "mean_runoff": (0.0022, 0.87), "peak_Q2": (0.07, 0.66),
        "peak_Q10": (0.105, 0.63), "peak_Q100": (0.16, 0.59),
        "min_winter": (0.00028, 0.91),
    },
    "don": {
        "mean_runoff": (0.0015, 0.90), "peak_Q2": (0.055, 0.70),
        "peak_Q10": (0.085, 0.66), "peak_Q100": (0.13, 0.62),
        "min_winter": (0.00015, 0.95),
    },
    "neva": {
        "mean_runoff": (0.0028, 0.84), "peak_Q2": (0.075, 0.67),
        "peak_Q10": (0.11, 0.63), "peak_Q100": (0.17, 0.59),
        "min_winter": (0.0003, 0.89),
    },
    "caucasus": {
        "mean_runoff": (0.0045, 0.75), "peak_Q2": (0.15, 0.55),
        "peak_Q10": (0.22, 0.50), "peak_Q100": (0.32, 0.45),
        "min_winter": (0.0005, 0.80),
    },
}

COEFF_SETS = ("mean_runoff", "peak_Q2", "peak_Q10", "peak_Q100", "min_winter")


# ---------------------------------------------------------------- региональные данные


def test_exactly_nine_regions_preserved() -> None:
    """Перечень регионов не менялся: ровно девять, те же ключи."""
    assert len(rr.REGIONAL_COEFFICIENTS) == 9
    assert set(rr.REGIONAL_COEFFICIENTS) == set(EXPECTED_COEFFICIENTS)


def test_available_regions_reports_all_nine() -> None:
    listed = rr.available_regions()
    assert len(listed) == 9
    assert {r["key"] for r in listed} == set(EXPECTED_COEFFICIENTS)
    assert all(r["name"] for r in listed)


@pytest.mark.parametrize("region", sorted(EXPECTED_COEFFICIENTS))
def test_coefficients_unchanged(region: str) -> None:
    """Контрольные значения A и n каждого набора зафиксированы числами."""
    block = rr.REGIONAL_COEFFICIENTS[region]
    for name in COEFF_SETS:
        assert name in block, f"{region}: отсутствует набор {name}"
        assert block[name]["A"] == pytest.approx(EXPECTED_COEFFICIENTS[region][name][0])
        assert block[name]["n"] == pytest.approx(EXPECTED_COEFFICIENTS[region][name][1])


@pytest.mark.parametrize("region", sorted(EXPECTED_COEFFICIENTS))
def test_exponent_field_present_and_unchanged(region: str) -> None:
    """Поле 'exponent' остаётся неиспользуемым, но присутствует и не меняется.

    Удалять его или вводить в расчёт — отдельная задача; здесь только
    фиксируется текущее состояние: 1.0 во всех наборах всех регионов.
    """
    block = rr.REGIONAL_COEFFICIENTS[region]
    for name in COEFF_SETS:
        assert "exponent" in block[name], f"{region}/{name}: потеряно поле exponent"
        assert block[name]["exponent"] == 1.0


def test_get_regression_coefficients_returns_requested_region() -> None:
    got = rr.get_regression_coefficients("caucasus")
    assert got is rr.REGIONAL_COEFFICIENTS["caucasus"]
    assert got["mean_runoff"]["A"] == 0.0045


# ---------------------------------------------------------------- mean_annual_runoff


def test_mean_annual_runoff_control_value() -> None:
    """Существующий контроль: F=1000, central_russia -> около 0.887 м³/с."""
    result = rr.mean_annual_runoff(F, CENTRAL)
    assert result["Q_mean_m3_s"] == pytest.approx(0.887, abs=1e-3)
    assert result["Q_mean_m3_s"] == pytest.approx(0.0025 * F ** 0.85, rel=1e-3)
    assert result["region"] == CENTRAL
    assert result["F_km2"] == F


def test_mean_annual_runoff_module_and_volume() -> None:
    """Модуль в л/(с·км²) и объём в км³ — контроль перевода единиц."""
    result = rr.mean_annual_runoff(F, CENTRAL)
    q = 0.0025 * F ** 0.85
    assert result["module_l_s_km2"] == pytest.approx(q * 1000 / F, rel=1e-2)
    assert result["volume_km3"] == pytest.approx(q * 31.536, rel=1e-3)


def test_mean_scales_as_area_to_the_n() -> None:
    """Показатель степени извлекается из логарифма — форма Q = A·F^n."""
    q1 = rr.mean_annual_runoff(100.0, CENTRAL)["Q_mean_m3_s"]
    q2 = rr.mean_annual_runoff(400.0, CENTRAL)["Q_mean_m3_s"]
    assert q2 / q1 == pytest.approx(4.0 ** 0.85, rel=1e-2)


# ---------------------------------------------------------------- peak_discharge_regression


@pytest.mark.parametrize(
    "T, expected",
    [(2, 7.13), (5, 7.68), (10, 8.69), (100, 9.89)],
)
def test_peak_discharge_control_values(T: float, expected: float) -> None:
    """Существующие контроли на переходных точках 2/10/100 и внутри интервала."""
    result = rr.peak_discharge_regression(F, T, CENTRAL)
    assert result["Q_peak_m3_s"] == pytest.approx(expected, abs=1e-2)
    assert result["T_years"] == T
    assert result["region"] == CENTRAL


def test_peak_below_two_uses_q2_unchanged() -> None:
    """Ветка T <= 2 не тронута и совпадает с коэффициентами peak_Q2."""
    expected = 0.08 * F ** 0.65
    assert rr.peak_discharge_regression(F, 1.5, CENTRAL)["Q_peak_m3_s"] == pytest.approx(
        round(expected, 2), abs=1e-2
    )


def test_no_plateau_above_100_years() -> None:
    """T = 100 больше не равен T = 200 и T = 1000: плато устранено."""
    q100 = rr.peak_discharge_regression(F, 100, CENTRAL)["Q_peak_m3_s"]
    q200 = rr.peak_discharge_regression(F, 200, CENTRAL)["Q_peak_m3_s"]
    q1000 = rr.peak_discharge_regression(F, 1000, CENTRAL)["Q_peak_m3_s"]
    assert q200 != q100
    assert q1000 != q100
    assert q200 != q1000
    assert q100 < q200 < q1000


def test_peak_above_100_follows_same_logarithmic_dependence() -> None:
    """За T = 100 продолжается та же логарифмическая конструкция.

    Форма не придумывается и не проверяется по СП 529: тест лишь убеждается,
    что зависимость осталась log-линейной по T с теми же точками q10 и q100,
    то есть ограничение min(..., 1.0) действительно снято, а не заменено
    новой нормой.
    """
    c = rr.REGIONAL_COEFFICIENTS[CENTRAL]
    q10 = 0.12 * F ** 0.62
    q100 = 0.18 * F ** 0.58
    for T in (100.0, 150.0, 200.0, 400.0, 1000.0):
        expected = round(q10 * (q100 / q10) ** ((T - 10) / 90), 2)
        got = rr.peak_discharge_regression(F, T, CENTRAL)["Q_peak_m3_s"]
        assert got == pytest.approx(expected, abs=1e-2), f"T={T}"


def test_peak_is_monotonic_in_return_period() -> None:
    """Монотонность по периоду возврата не нарушена продолжением за 100 лет."""
    values = [
        rr.peak_discharge_regression(F, T, CENTRAL)["Q_peak_m3_s"]
        for T in (1, 2, 5, 10, 50, 100, 200, 1000)
    ]
    assert values == sorted(values)


def test_peak_uses_region_specific_coefficients() -> None:
    """Кавказ и Центральная Россия дают разные расходы при одной площади."""
    assert (
        rr.peak_discharge_regression(F, 10, "caucasus")["Q_peak_m3_s"]
        != rr.peak_discharge_regression(F, 10, CENTRAL)["Q_peak_m3_s"]
    )


# ---------------------------------------------------------------- min_winter_runoff_regression


def test_min_winter_runoff_control_value() -> None:
    """Существующий контроль: F=1000, central_russia -> около 0.15 м³/с."""
    result = rr.min_winter_runoff_regression(F, CENTRAL)
    assert result["Q_min_m3_s"] == pytest.approx(0.15, abs=1e-3)
    # функция округляет до 3 знаков, поэтому сверяем с округлённым значением
    assert result["Q_min_m3_s"] == pytest.approx(round(0.0003 * F ** 0.90, 3), abs=1e-9)
    assert result["region"] == CENTRAL


def test_min_winter_is_below_mean_runoff_everywhere() -> None:
    """Зимний минимум должен быть меньше среднегодового во всех регионах."""
    for region in EXPECTED_COEFFICIENTS:
        assert (
            rr.min_winter_runoff_regression(F, region)["Q_min_m3_s"]
            < rr.mean_annual_runoff(F, region)["Q_mean_m3_s"]
        )


# ---------------------------------------------------------------- неизвестный регион


REGION_TAKING = (
    (rr.mean_annual_runoff, {"F_km2": F}),
    (rr.peak_discharge_regression, {"F_km2": F, "T": 5}),
    (rr.min_winter_runoff_regression, {"F_km2": F}),
    (rr.get_regression_coefficients, {}),
)


@pytest.mark.parametrize(
    "func, kwargs", REGION_TAKING, ids=[f.__name__ for f, _ in REGION_TAKING]
)
def test_unknown_region_raises(func, kwargs) -> None:
    """Неизвестный регион больше не подменяется молча на central_russia."""
    with pytest.raises(ValueError) as exc:
        func(region="atlantis", **kwargs)
    message = str(exc.value)
    assert "atlantis" in message, f"сообщение должно называть регион: {message}"
    assert "Неизвестный регион" in message


@pytest.mark.parametrize(
    "func, kwargs", REGION_TAKING, ids=[f.__name__ for f, _ in REGION_TAKING]
)
def test_every_existing_region_still_works(func, kwargs) -> None:
    """Поведение для всех девяти существующих регионов не изменилось."""
    for region in EXPECTED_COEFFICIENTS:
        func(region=region, **kwargs)


def test_known_region_is_not_rewritten() -> None:
    """Валидный регион возвращается как есть, без подмены на значение по умолчанию."""
    assert rr.mean_annual_runoff(F, "don")["region"] == "don"
    assert rr.peak_discharge_regression(F, 5, "neva")["region"] == "neva"
    assert rr.min_winter_runoff_regression(F, "lena")["region"] == "lena"


# ---------------------------------------------------------------- валидация входов


@pytest.mark.parametrize("F_bad", [0.0, -0.0, -1.0, -1000.0])
def test_nonpositive_area_rejected(F_bad: float) -> None:
    """Неположительная площадь отвергается всеми функциями, где F есть."""
    for func, kwargs in (
        (rr.mean_annual_runoff, {}),
        (rr.min_winter_runoff_regression, {}),
        (rr.peak_discharge_regression, {"T": 5}),
    ):
        with pytest.raises(ValueError) as exc:
            func(F_km2=F_bad, region=CENTRAL, **kwargs)
        assert "F_km2" in str(exc.value)


@pytest.mark.parametrize("T_bad", [0.0, -0.0, -1.0, -50.0])
def test_nonpositive_return_period_rejected(T_bad: float) -> None:
    """Неположительный период возврата отвергается."""
    with pytest.raises(ValueError) as exc:
        rr.peak_discharge_regression(F, T_bad, CENTRAL)
    assert "T" in str(exc.value)


def test_no_extra_normative_limits_introduced() -> None:
    """Ни T >= 2, ни T <= 100 не вводились — это техточки модели, а не норма."""
    # T меньше 2 допускается: ветка T <= 2 существовала и раньше
    assert rr.peak_discharge_regression(F, 0.5, CENTRAL)["Q_peak_m3_s"] > 0
    assert rr.peak_discharge_regression(F, 1.0, CENTRAL)["Q_peak_m3_s"] > 0
    # T больше 100 допускается и даёт иной результат
    assert rr.peak_discharge_regression(F, 5000.0, CENTRAL)["Q_peak_m3_s"] > 0
    # малая, но положительная площадь допускается (0.01 округлилась бы до 0.0,
    # поэтому берётся значение, различимое после округления до 3 знаков)
    assert rr.mean_annual_runoff(0.5, CENTRAL)["Q_mean_m3_s"] > 0


def test_area_validation_runs_before_region_lookup() -> None:
    """Неположительная площадь отвергается независимо от валидности региона."""
    with pytest.raises(ValueError) as exc:
        rr.mean_annual_runoff(0.0, "atlantis")
    assert "F_km2" in str(exc.value)


# ---------------------------------------------------------------- граница нормативной работы


def test_module_still_declares_sp529_formulas_not_implemented() -> None:
    """Правки поведения не должны были превратить модуль в реализацию СП 529.

    TEXT-ONLY remap зафиксирован как выполненный; инженерная группа C его не
    отменяет. Проверяем, что нормативные оговорки на месте.
    """
    doc = rr.__doc__ or ""
    assert "НЕ УСТАНОВЛЕНО" in doc
    assert "7.1.2" in doc
    assert "4.11" in doc
    assert "7.8.2" in doc
    peak_doc = rr.peak_discharge_regression.__doc__ or ""
    assert "NOT_IMPLEMENTED" in peak_doc
    assert "7.4.2" in peak_doc
    assert "(7.28)" in peak_doc
    min_doc = rr.min_winter_runoff_regression.__doc__ or ""
    assert "(7.41)" in min_doc
    assert "A1" in min_doc


def test_flood_frequency_regression_was_not_created() -> None:
    """Функция, которой не было, не появилась: это отдельное решение."""
    assert not hasattr(rr, "flood_frequency_regression")


def test_public_api_surface_unchanged() -> None:
    """Пять публичных функций плюс словарь коэффициентов — и ничего лишнего."""
    public = {n for n in dir(rr) if not n.startswith("_")}
    assert public == {
        "REGIONAL_COEFFICIENTS",
        "available_regions",
        "get_regression_coefficients",
        "mean_annual_runoff",
        "min_winter_runoff_regression",
        "peak_discharge_regression",
    }
    assert not any(n.startswith("math") and n != "math" for n in public)


def test_log_dependence_stays_self_consistent() -> None:
    """ln Q линеен по T в верхней ветке — подтверждение неизменности формы."""
    c = rr.REGIONAL_COEFFICIENTS[CENTRAL]
    q10 = 0.12 * F ** 0.62
    q100 = 0.18 * F ** 0.58
    slope = (math.log(q100) - math.log(q10)) / 90
    for T in (50.0, 200.0, 1000.0):
        expected = math.exp(math.log(q10) + slope * (T - 10))
        got = rr.peak_discharge_regression(F, T, CENTRAL)["Q_peak_m3_s"]
        assert got == pytest.approx(expected, rel=1e-3), f"T={T}"
