"""п. 5.6 СП 33-101-2003: поправки на смещение обязательны вне Cv < 0,6 и Cs < 1,0.

Находка 2026-09-28. Функция `calculate_statistical_parameters` отдавала ключи
`corrected_cv` и `corrected_cs`, которые тождественно равны `cv` и `cs`: поправок
не было никогда, но имена обещали, что они есть. СП 33 п. 5.6 разрешает отказ
от поправок только при Cv < 0,6 и Cs < 1,0 — то есть как исключение с
проверяемым условием. Условие не проверялось, и на реке с Cv = 0,9 код молча
выдавал неверный Cv под именем `corrected_cv`.

Ключи `corrected_*` сохранены: их читают шесть production-потребителей
(`frequency.py`, `gts_integration.py`, `confidence_bands.py`, `run_stats_demo.py`,
тест бенчмарков и фикстур). Удаление сломало бы их API. Поэтому ложь убрана
другим способом — явными ключами `bias_corrections_applied` и
`corrections_required` плюс предупреждением, когда поправки обязательны, но не
применены.

Настоящие поправки (коэффициенты a1..a6 и b1..b6 из Приложения Б, табл. Б.1) в
проекте не реализованы, и эти тесты фиксируют именно факт их отсутствия, а не
правильность вычисления поправок.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from core.stats.parameters import calculate_statistical_parameters


def low_variability(n: int = 40) -> np.ndarray:
    """Ряд с малым Cv и малой асимметрией: поправки по п. 5.6 не нужны."""
    rng = np.random.default_rng(20260928)
    return 10.0 + rng.normal(0.0, 0.1, size=n)


def high_variability(n: int = 40) -> np.ndarray:
    """Экспоненциальный ряд: Cv ≈ 1, Cs ≈ 2, поправки обязательны."""
    rng = np.random.default_rng(20260928)
    return rng.exponential(1.0, size=n)


def test_low_variability_needs_no_corrections_and_warns_not() -> None:
    data = low_variability()
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        result = calculate_statistical_parameters(data, show_warnings=False)
    assert result["corrections_required"] is False
    assert result["bias_corrections_applied"] is False


def test_high_variability_marks_corrections_as_required() -> None:
    result = calculate_statistical_parameters(high_variability(), show_warnings=False)
    assert result["corrections_required"] is True, (
        "при Cv около 1 поправки по п. 5.6 обязательны, а флаг этого не отметил"
    )


def test_high_variability_warns_about_missing_corrections() -> None:
    """Главное: нарушение условия п. 5.6 обязано быть видно пользователю."""
    with pytest.warns(UserWarning, match="5\\.6"):
        calculate_statistical_parameters(high_variability(), show_warnings=True)


def test_warning_names_the_missing_source() -> None:
    """Предупреждение должно называть, чего именно не хватает.

    Ищем нужное среди всех предупреждений, а не по индексу: функция сначала
    предупреждает о длине ряда (п. 5.1) и лишь затем о поправках, так что
    порядок выдачи не задан условиями теста.
    """
    with pytest.warns(UserWarning) as caught:
        calculate_statistical_parameters(high_variability(), show_warnings=True)
    texts = [str(w.message) for w in caught]
    matching = [t for t in texts if "5.6" in t]
    assert matching, f"нет предупреждения о поправках среди: {texts}"
    text = matching[0]
    assert "Приложения Б" in text, "не названы коэффициенты поправок"
    assert "a1..a6" in text and "b1..b6" in text, "не названы сами коэффициенты"


def test_corrected_keys_stay_identical_to_raw() -> None:
    """Документируемый факт: поправок нет, corrected_* тождественны cv/cs.

    Это осознанно оставлено как поведение — потребители читают эти ключи, и
    менять их значение без реализации поправок (5.6)-(5.9) было бы подменой
    одного несоответствия другим.
    """
    result = calculate_statistical_parameters(high_variability(), show_warnings=False)
    assert result["corrected_cv"] == result["cv"]
    assert result["corrected_cs"] == result["cs"]
    assert result["bias_corrections_applied"] is False


def test_ratio_cs_cv_is_exposed() -> None:
    """П. 5.4 задаёт набор параметров как {среднее, Cv, Cs/Cv}, а не {Cs}.

    Отношения в выводе не было вовсе — только сырая асимметрия, тогда как
    формула (5.7) заканчивается именно на Cs/Cv, и расчётные кривые
    используют отношение, а не Cs.
    """
    result = calculate_statistical_parameters(high_variability(), show_warnings=False)
    assert result["cs_cv"] == pytest.approx(result["cs"] / result["cv"], abs=5e-4)
    assert "cs_cv" in result


def test_guard_is_not_vacuous() -> None:
    """Флаг обязан различать два режима, а не всегда возвращать одно и то же."""
    low = calculate_statistical_parameters(low_variability(), show_warnings=False)
    high = calculate_statistical_parameters(high_variability(), show_warnings=False)
    assert low["corrections_required"] is False
    assert high["corrections_required"] is True
    # и он выключаемым, как и прочие предупреждения
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        calculate_statistical_parameters(high_variability(), show_warnings=False)
