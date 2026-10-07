"""Регрессии: ряды без изменений и закрытие файловых дескрипторов.

История файла. Полный прогон давал 41 warning, и 18 из них указывали не на
тестовые оговорки, а на три дефекта production-кода:

1. ``scipy.stats.skew`` вызывался на ряде без изменений (std == 0), где он делит
   на нулевую дисперсию. Возвращался NaN — и это правильный ответ, — но вместе
   с RuntimeWarning о потере точности, который к отношениям пользователя
   отношения не имеет.
2. ``np.corrcoef`` вызывался без проверки дисперсии лагов. У постоянного лага
   СКО = 0, то есть 0/0 -> NaN и RuntimeWarning о недопустимом делении. Ряд
   «30 спокойных лет и один выброс» — не экзотика, а обычный гидрологический
   случай, и передний лаг в нём постоянен.
3. ``pd.ExcelFile`` открывался и не закрывался: дескриптор освобождался только
   сборщиком мусора. На Windows это означает, что .xlsx нельзя удалить сразу
   после чтения, а pytest держит временные файлы до конца сессии.

Что здесь проверяется. Для (1) и (2) — что РЕЗУЛЬТАТ остался тем же (NaN, а не
0.0), потому что подмена «не определено» на ноль была бы утверждением о
независимости, которого никто не измерял. Для (3) — что книга, открытая внутри
функции, закрывается на всех путях, включая ранний return, а книга, переданная
вызывающим кодом, НЕ закрывается: её владелец — вызывающий.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.stats.homogeneity import check_homogeneity_full
from core.stats.parameters import (
    calculate_statistical_parameters,
    sp33_lag1_autocorrelation,
)

# Ряд, на котором воспроизводится дефект np.corrcoef: 30 одинаковых значений и
# один выброс. Взят из tests/test_quality_pipeline.py, где передний лаг
# оказывается постоянным, а задний — нет.
_SPIKE_VALUES = {1990 + i: 100.0 for i in range(30)}
_SPIKE_VALUES[2020] = 2000.0
SPIKE_SERIES = np.array([_SPIKE_VALUES[k] for k in sorted(_SPIKE_VALUES)], dtype=float)


def _messages(caught) -> list[str]:
    return [str(item.message) for item in caught]


# ----------------------------------------------------------------------
# Корень 1: scipy.stats.skew на ряде без изменений
# ----------------------------------------------------------------------
def test_constant_series_emits_no_precision_loss_warning() -> None:
    """Предупреждение о потере точности на постоянном ряде — ложное.

    Моменты вырожденного ряда не «неточны», они не определены, и говорить об
    этом должен флаг вырожденности, а не scipy. Проверяем именно отсутствие
    предупреждения, а не отсутствие NaN: NaN верен и остаётся.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        calculate_statistical_parameters(np.full(10, 5.0), show_warnings=False)
    assert not [m for m in _messages(caught) if "Precision loss" in m], _messages(caught)


def test_constant_series_keeps_nan_asymmetry_semantics() -> None:
    """Cs для ряда из одинаковых значений не определена, и это NaN, а не 0.0.

    Ноль был бы утверждением, что распределение симметрично. Подставить его —
    значит выдать догадку за измерение, а проект на этом сам настаивает в
    correction_note. Поэтому фиксируем именно NaN.
    """
    result = calculate_statistical_parameters(np.full(10, 5.0), show_warnings=False)
    assert np.isnan(result["cs"])
    assert np.isnan(result["corrected_cs"])
    assert np.isnan(result["cs_cv"])
    assert result["cv"] == 0.0
    # Отказ от поправок обязан остаться объяснённым, а не молчаливым.
    assert result["bias_corrections_applied"] is False
    assert "неприменимы" in result["correction_note"]


def test_homogeneity_constant_series_emits_no_warnings() -> None:
    """Тот же вырожденный ряд в проверке однородности: без предупреждений."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = check_homogeneity_full(np.full(10, 5.0))
    assert not _messages(caught), _messages(caught)
    # Cs здесь тоже не определена, и по той же причине.
    assert np.isnan(result["cs"])


def test_regular_series_still_follows_scipy_exactly() -> None:
    """Для std > 0 Cs по-прежнему берётся из scipy, а не из другой формулы.

    Смысл проверки: правка касается ТОЛЬКО вырожденного ряда. Если бы Cs
    вычислялась иначе, число на обычных рядах тихо изменилось бы.
    """
    from scipy import stats as scipy_stats

    data = np.random.default_rng(7).gamma(3.0, 1.0, 40)
    result = calculate_statistical_parameters(data, show_warnings=False)
    assert result["cs"] == pytest.approx(scipy_stats.skew(data, bias=False), abs=5e-4)


# ----------------------------------------------------------------------
# Корень 2: np.corrcoef на постоянном лаге
# ----------------------------------------------------------------------
def test_spike_series_constant_lag_emits_no_divide_warning() -> None:
    """Передний лаг постоянен, задний — нет: 0/0 в обеих осях corrcoef.

    Именно этот ряд раньше давал два RuntimeWarning «invalid value encountered
    in divide» из numpy._function_base_impl. Теперь корреляция не вычисляется
    вовсе, потому что вычислить её не на чем.
    """
    assert np.std(SPIKE_SERIES[:-1], ddof=1) == 0.0, "фикстура должна сохранять свойство"
    assert np.std(SPIKE_SERIES[1:], ddof=1) > 0.0, "фикстура должна сохранять свойство"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sp33_lag1_autocorrelation(SPIKE_SERIES)
    assert not [m for m in _messages(caught) if "divide" in m], _messages(caught)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        check_homogeneity_full(SPIKE_SERIES)
    assert not [m for m in _messages(caught) if "divide" in m], _messages(caught)


def test_undefined_correlation_is_nan_not_zero() -> None:
    """Корреляция при постоянном лаге не определена — подставлять 0.0 нельзя.

    Ноль означал бы независимость лагов. Здесь она не измерена, а не доказана,
    и подмена одного утверждения другим повторила бы ровно тот дефект, который
    закрыт в (Б.1): молчаливая замена величины под её же формулировкой.
    """
    lag1 = sp33_lag1_autocorrelation(SPIKE_SERIES)
    assert np.isnan(lag1["pearson"])

    homogeneity = check_homogeneity_full(SPIKE_SERIES)
    assert np.isnan(homogeneity["r1"])


def test_constant_series_correlation_is_nan_and_falls_back_normatively() -> None:
    """На постоянном ряде (Б.2) не определена, и fallback на Пирсона честный.

    Прежний путь возвращал r(1) = pearson = NaN вместе с предупреждением о
    делении. Значение не меняется — исчезает только предупреждение.
    """
    lag1 = sp33_lag1_autocorrelation(np.full(10, 5.0))
    assert lag1["normative"] is False
    assert np.isnan(lag1["pearson"])
    assert lag1["r_tilde"] is None
    assert "Пирсон" in lag1["source"]

    result = calculate_statistical_parameters(np.full(10, 5.0), show_warnings=False)
    assert np.isnan(result["r1_pearson"])


def test_regular_series_correlation_unchanged() -> None:
    """Оба лага варьируют — корреляция по-прежнему равна np.corrcoef."""
    data = np.random.default_rng(11).gamma(2.5, 1.0, 40)
    lag1 = sp33_lag1_autocorrelation(data)
    assert lag1["pearson"] == pytest.approx(
        float(np.corrcoef(data[:-1], data[1:])[0, 1]), abs=1e-12
    )
    assert lag1["normative"] is True


# ----------------------------------------------------------------------
# Корень 3: закрытие pd.ExcelFile
# ----------------------------------------------------------------------
def _write_xlsx(path: Path, sheet: str = "Посты") -> Path:
    pd.DataFrame({"год": [1990, 1991, 1992], "Q": [1.0, 2.0, 3.0]}).to_excel(
        path, index=False, sheet_name=sheet
    )
    return path


def _spy_on_close(monkeypatch) -> list[pd.ExcelFile]:
    """Регистрирует книги, для которых вызвали close().

    Проверять надо именно вызов close(), а не «файл удалился»: под POSIX
    удаление открытого файла проходит, и unlink ничего не доказывал бы, а
    internals pandas между версиями меняются. Патчится метод класса, а не сам
    класс, поэтому isinstance-проверка внутри read_work_sheet продолжает
    работать и различает «свою» и «чужую» книгу.
    """
    closed: list[pd.ExcelFile] = []
    original = pd.ExcelFile.close

    def traced(self, *args, **kwargs):
        closed.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pd.ExcelFile, "close", traced)
    return closed


def test_read_work_sheet_closes_workbook_it_opened(tmp_path: Path, monkeypatch) -> None:
    """Книга, открытая внутри read_work_sheet, закрывается на успешном пути."""
    from core.stats import sheet_reader

    path = _write_xlsx(tmp_path / "ok.xlsx")
    closed = _spy_on_close(monkeypatch)

    frame = sheet_reader.read_work_sheet(path, ["Посты"], use_columns=True)
    assert not frame.empty, "фикстура перестала читаться — тест бессмысленен"
    assert len(closed) == 1, f"ожидалась ровно одна закрытая книга, закрыто {len(closed)}"


def test_read_work_sheet_closes_workbook_on_early_return(tmp_path: Path, monkeypatch) -> None:
    """Ранний return (лист не найден) тоже обязан закрывать книгу.

    Именно этот путь молчал: `return pd.DataFrame()` на не найденном листе
    выходил из функции, не закрыв книгу.
    """
    from core.stats import sheet_reader

    path = _write_xlsx(tmp_path / "missing.xlsx")
    closed = _spy_on_close(monkeypatch)

    frame = sheet_reader.read_work_sheet(path, ["НЕТ ТАКОГО ЛИСТА"], use_columns=True)
    assert frame.empty
    assert len(closed) == 1, f"на раннем return книга не закрыта, закрыто {len(closed)}"


def test_read_work_sheet_does_not_close_borrowed_workbook(tmp_path: Path, monkeypatch) -> None:
    """Чужая книга не закрывается: её владелец — вызывающий код.

    Если бы read_work_sheet закрывал переданный ему pd.ExcelFile, то вызывающий,
    который читает несколько листов подряд, получил бы закрытый дескриптор на
    втором листе.
    """
    from core.stats import sheet_reader

    path = _write_xlsx(tmp_path / "borrowed.xlsx")
    book = pd.ExcelFile(path)
    closed = _spy_on_close(monkeypatch)
    try:
        sheet_reader.read_work_sheet(book, ["Посты"], use_columns=True)
        assert closed == [], "функция закрыла книгу, принадлежащую вызывающему"
    finally:
        pd.ExcelFile.close(book)


@pytest.mark.skipif(os.name != "nt", reason="удержание файла специфично для Windows")
def test_workbook_file_is_deletable_right_after_read(tmp_path: Path) -> None:
    """На Windows .xlsx удаляется сразу после чтения — дескриптор не удерживается.

    Раньше файл оставался занятым до сборки мусора, и очистка временного каталога
    падала с PermissionError [WinError 32]. Это сквозная проверка правки: если
    закрытия нет, тест упадёт именно здесь.
    """
    from core.stats import sheet_reader

    path = _write_xlsx(tmp_path / "deletable.xlsx")
    sheet_reader.read_work_sheet(path, ["Посты"], use_columns=True)
    os.remove(path)
    assert not path.exists()


# ----------------------------------------------------------------------
# Корень 4: bootstrap-предупреждения в confidence_bands
# ----------------------------------------------------------------------
def test_bootstrap_emits_no_normative_warnings() -> None:
    """Ресемпл не должен приписывать свои нормативные оценки ряду пользователя.

    До правки бутстреп вызывал calculate_statistical_parameters с show_warnings
    по умолчанию, и на n_bootstrap = 25 это давало до 25 предупреждений вида
    «погрешность 13,1 % превышает предел 10 % для ряда n=40» — где n и состав
    ряда относятся к ресемплу, а не к данным, которые пользователь и так видит.
    """
    from core.stats.confidence_bands import pearson3_confidence_bands

    series = np.random.default_rng(4).gamma(3.0, 1.0, 40)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pearson3_confidence_bands(series, n_bootstrap=25, confidence=0.90)
    assert not [m for m in _messages(caught) if "погрешность" in m], _messages(caught)


def test_bootstrap_diagnostics_reported_as_count() -> None:
    """Вместо потока предупреждений в результате — один счётчик.

    Поле обязано называть, что оно измерять, и не выдавать себя за диагноз
    исходному ряду: непрошедших перевыборок может быть много, и это свойство
    бутстрепа, а не приговор данным.
    """
    from core.stats.confidence_bands import pearson3_confidence_bands

    series = np.random.default_rng(4).gamma(3.0, 1.0, 40)
    bands = pearson3_confidence_bands(series, n_bootstrap=25, confidence=0.90)

    assert "n_series_check_failed" in bands
    assert isinstance(bands["n_series_check_failed"], int)
    assert 0 <= bands["n_series_check_failed"] <= bands["n_bootstrap"]


def test_bootstrap_band_values_are_well_formed() -> None:
    """Полосы не должны измениться: подавление warning не есть изменение расчёта.

    rng = default_rng(42) в коде фиксирован, поэтому границы обязаны быть
    упорядочены и покрывать центральную кривую. Это предохранитель правки №4:
    если бы show_warnings=False повлиял на вычисления, полосы бы разъехались.
    """
    from core.stats.confidence_bands import pearson3_confidence_bands

    series = np.random.default_rng(4).gamma(3.0, 1.0, 40)
    bands = pearson3_confidence_bands(series, n_bootstrap=25, confidence=0.90)

    assert len(bands["Q_lower"]) == len(bands["P_values"])
    assert len(bands["Q_upper"]) == len(bands["P_values"])
    assert len(bands["Q_mean"]) == len(bands["P_values"])
    # Верхняя граница не может оказаться ниже нижней.
    assert all(lo <= up for lo, up in zip(bands["Q_lower"], bands["Q_upper"]))
    # Значения остаются конечными и полоса не вырождена.
    assert all(np.isfinite(v) for v in bands["Q_lower"] + bands["Q_upper"])
    assert max(bands["Q_upper"]) > min(bands["Q_lower"])


def test_bootstrap_ignores_warnings_but_not_errors(monkeypatch) -> None:
    """show_warnings=False не должен превращать ошибки в тишину.

    Ошибка внутри calculate_statistical_parameters обязана по-прежнему доходить
    до except-ветки, которая подставляет Q_mean, — иначе подавление
    предупреждений изменило бы устойчивость расчёта.
    """
    from core.stats import confidence_bands as cb

    def boom(*args, **kwargs):
        raise ValueError("искусственный сбой")

    monkeypatch.setattr(cb, "calculate_statistical_parameters", boom, raising=False)
    bands = cb.pearson3_confidence_bands(
        np.random.default_rng(4).gamma(3.0, 1.0, 40), n_bootstrap=5, confidence=0.90
    )
    assert bands["n_series_check_failed"] == 0
    assert all(np.isfinite(v) for v in bands["Q_lower"] + bands["Q_upper"])
