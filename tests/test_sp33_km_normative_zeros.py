"""Нормативные нули таблицы ординат КМ не должны подменяться положительными.

ДЕФЕКТ, КОТОРЫЙ ЗДЕСЬ ЗАКРЕПЛЯЕТСЯ.

В core.stats.frequency._log_interp отбор узлов для логарифмической интерполяции
выглядел как `valid = np.isfinite(tab_kp) & (tab_kp > 0)`. Условие `> 0`
отбрасывало и нормативные нули таблицы. Ноль в таблице — это напечатанное
значение «0,000» при трёх значащих цифрах, то есть «значение ниже разрешения
издания», а НЕ отсутствие данных. get_ordinates() эти нули возвращал верно;
терялись они последним шагом, в _log_interp.

Цена дефекта: 149 ячеек в 33 строках таблицы, ВСЕ 149 превращались в
положительные значения. Причём не в «хвостовую неточность», а в грубую порчу:

    Cs/Cv = 0,5, Cv = 0,7, P = 99,9 %   норматив 0,0   выдавалось 0,1775
    Cs/Cv = 1,5, Cv = 1,0, P = 99,9 %   норматив 0,0   выдавалось 0,01
    Cs/Cv = 1,   Cv = 2,0, P = 60,0 %   норматив 0,0   выдавалось 0,01

Плюс ломалась монотонность: для Cs/Cv = 1,5, Cv = 1,0 значения при
P = 95, 97, 99, 99,5, 99,7, 99,9 все равнялись 0,01 — плато вместо строго
убывающей кривой. Квантильная функция на таком участке невалидна.

ЧТО ЗДЕСЬ НЕ ПРОВЕРЯЕТСЯ.

Строка P = 0,001 % и восемь ранее исправленных хвостовых узлов блока
Cs/Cv = 1, Cv = 0,8...1,0 проверяются в tests/test_sp33_km_tail_constants.py и
намеренно не дублируются. Старый отдельный дефект блока Cs/Cv = 0 (давний
guard `abs(cs) < 0.001` превращает cs = 0 в отношение 0,001/Cv) здесь не
затрагивается и проверкой не закрывается.

ЧТО ОСТАЁТСЯ ПРЕДСТАВЛЯТЬ СОБОЙ 0,000. Проверяется по таблице: get_ordinates()
возвращает нули без единой потери, значит источник данных цел, и речь только
о presentation-слое интерполяции.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.stats.frequency import kritsky_menkel_ppf
from core.stats.kritsky_tables import PROBS, TABLES, get_ordinates

P_PCT = np.asarray(PROBS, dtype=float) * 100.0

# Относительный допуск. Значения проходят через log/exp, поэтому побитово
# табличному узлу не равны: 0,0003 приходит как 0,0003000000000000017.
REL = 1e-12


def _rows_with_zeros() -> list[tuple[float, float, np.ndarray, list[int]]]:
    """Все строки таблицы, где хотя бы один узел равен ровно 0.0."""
    out = []
    for cs_cv in sorted(TABLES, key=lambda k: (isinstance(k, str), k)):
        for cv in sorted(TABLES[cs_cv]):
            row = np.asarray(TABLES[cs_cv][cv], dtype=float)
            zeros = [int(j) for j in np.where(row == 0.0)[0]]
            if zeros:
                out.append((cs_cv, cv, row, zeros))
    return out


ZERO_ROWS = _rows_with_zeros()
ZERO_CASES = [(cs_cv, cv, zeros[0]) for cs_cv, cv, _, zeros in ZERO_ROWS]
ALL_ZERO_NODES = [(cs_cv, cv, j) for cs_cv, cv, _, zeros in ZERO_ROWS
                  for j in zeros]


def _kp(p_pct: float, cv: float, cs_cv: float) -> float:
    """Квантиль КМ при cs/cv == cs_cv. Вызов идёт как (mean, cv, cs)."""
    return float(kritsky_menkel_ppf(np.array([p_pct / 100.0]), 1.0, cv, cs_cv * cv)[0])


def _is_zero(cs_cv: float, cv: float, j: int) -> bool:
    return bool(np.asarray(TABLES[cs_cv][cv], dtype=float)[j] == 0.0)


def test_table_really_contains_these_zeros() -> None:
    """Число строк и узлов зафиксировано: 33 строки, 149 ячеек.

    Если правка задрогнула таблицу или менялся её разбор, тест обязан это
    показать, а не молча сократить перебор.
    """
    assert len(ZERO_ROWS) == 33
    assert len(ALL_ZERO_NODES) == 149
    for _, _, row, zeros in ZERO_ROWS:
        for j in zeros:
            assert row[j] == 0.0


def test_get_ordinates_preserves_the_zeros() -> None:
    """Источник цел: нули теряются не в get_ordinates, а в интерполяции."""
    for cs_cv, cv, row, zeros in ZERO_ROWS:
        got = np.asarray(get_ordinates(cs_cv, cv), dtype=float)
        for j in zeros:
            assert got[j] == 0.0, (
                f"get_ordinates({cs_cv}, {cv}) вернул {got[j]!r} на месте нуля "
                f"P = {P_PCT[j]} % — дефект теперь не в _log_interp."
            )


# --------------------------------------------------------------------------- #
# A. Все нормативные нули доходят до результата как 0.0
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(("cs_cv", "cv", "j0"), ZERO_CASES)
def test_first_zero_node_returns_exactly_zero(cs_cv: float, cv: float, j0: int) -> None:
    """Первый нулевой узел каждой из 33 строк даёт ровно 0.0."""
    assert _is_zero(cs_cv, cv, j0)
    got = _kp(float(P_PCT[j0]), cv, cs_cv)
    assert got == 0.0, (
        f"Cs/Cv = {cs_cv}, Cv = {cv}, P = {P_PCT[j0]} %: получено {got!r}, "
        "а норматив равен 0,000. Ноль снова подменён положительным узлом."
    )


@pytest.mark.parametrize(("cs_cv", "cv", "j"), ALL_ZERO_NODES)
def test_every_zero_node_returns_exactly_zero(cs_cv: float, cv: float, j: int) -> None:
    """Все 149 ячеек, а не только первые в каждой строке."""
    got = _kp(float(P_PCT[j]), cv, cs_cv)
    assert got == 0.0, (
        f"Cs/Cv = {cs_cv}, Cv = {cv}, P = {P_PCT[j]} %: {got!r} вместо 0,0"
    )


# --------------------------------------------------------------------------- #
# B. Соседний положительный узел перед нулём не тронут
# --------------------------------------------------------------------------- #

def test_positive_node_before_first_zero_is_intact() -> None:
    """Cs/Cv = 1, Cv = 1,1, P = 97 % возвращает табличные 0,0003."""
    assert _kp(97.0, 1.1, 1.0) == pytest.approx(0.0003, rel=REL)


@pytest.mark.parametrize(("cs_cv", "cv", "row", "zeros"),
                         ZERO_ROWS,
                         ids=[f"{c}-{v}" for c, v, _, _ in ZERO_ROWS])
def test_node_just_before_first_zero_is_preserved(
    cs_cv: float, cv: float, row: np.ndarray, zeros: list[int],
) -> None:
    """Последний положительный узел перед первым нулём не сдвинут правкой."""
    j0 = zeros[0]
    if j0 == 0:
        pytest.skip("нуль стоит в первом столбце, предшествующего узла нет")
    prev = j0 - 1
    exp = row[prev]
    assert exp > 0.0
    got = _kp(float(P_PCT[prev]), cv, cs_cv)
    assert got == pytest.approx(exp, rel=REL), (
        f"Cs/Cv = {cs_cv}, Cv = {cv}, P = {P_PCT[prev]} %: {got!r} вместо {exp!r}. "
        "Переход к нулю задел предшествующий узел."
    )


# --------------------------------------------------------------------------- #
# C. Переход через границу нуля
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(("cs_cv", "cv", "row", "zeros"),
                         ZERO_ROWS,
                         ids=[f"{c}-{v}" for c, v, _, _ in ZERO_ROWS])
def test_transition_across_the_zero_boundary(
    cs_cv: float, cv: float, row: np.ndarray, zeros: list[int],
) -> None:
    """До нуля — строго положительно и убывает, на нуле и после — ровно 0.

    Это и есть определение перехода: подстановка «ближайшего положительного»
    ломала его в двух местах сразу — значение на нуле становилось положительным,
    и последовательность вырождалась в плато.
    """
    idx = list(range(0, len(row)))
    p = P_PCT[idx] / 100.0
    kp = kritsky_menkel_ppf(p, 1.0, cv, cs_cv * cv)

    j0 = zeros[0]
    if j0 > 0:
        before = kp[j0 - 1]
        assert before > 0.0, (
            f"Cs/Cv = {cs_cv}, Cv = {cv}: перед первым нулём {before!r} — "
            "переход съел и предшествующий узел"
        )

    for j in zeros:
        assert kp[j] == 0.0, f"P = {P_PCT[j]} %: {kp[j]!r} вместо 0,0"

    # Нестрогое убывание до границы. Строгим его делать нельзя: в самой
    # таблице глубокий хвост печатается четырьмя значащими цифрами, и
    # соседние узлы округляются к одному числу. Пример - Cs/Cv = 3, Cv = 2,0:
    # P = 99,5 % и P = 99,7 % оба напечатаны как 0,0001. Это свойство
    # первоисточника, и «чинить» его здесь нельзя.
    positive = [float(kp[j]) for j in range(j0 + 1) if kp[j] > 0.0]
    for a, b in zip(positive, positive[1:]):
        assert a >= b, f"монотонность сломана до границы нуля: {positive}"


def test_transition_band_is_linear_and_stays_nonnegative() -> None:
    """Между последним положительным узлом и нулём — непрерывный спуск.

    Логарифмическая интерполяция туда не годится (ln 0 = -inf), поэтому
    участок заполняется линейно. Проверяется, что спуск есть, он конечен и
    нигде не уходит в минус.
    """
    cv, cs_cv = 1.1, 1.0
    row = np.asarray(TABLES[cs_cv][cv], dtype=float)
    j0 = int(np.where(row == 0.0)[0][0])
    p_zero = float(P_PCT[j0])
    p_last = float(P_PCT[j0 - 1])

    probe = np.array([p_last, (p_last + p_zero) / 2.0, p_zero]) / 100.0
    kp = kritsky_menkel_ppf(probe, 1.0, cv, cs_cv * cv)

    assert np.all(np.isfinite(kp))
    assert np.all(kp >= 0.0), f"спуск ушёл в минус: {kp}"
    assert kp[0] > kp[1] > kp[2], f"спуск не монотонен: {kp}"
    assert kp[0] == pytest.approx(0.0003, rel=REL)
    assert kp[2] == 0.0


# --------------------------------------------------------------------------- #
# D. Плато исчезло
# --------------------------------------------------------------------------- #

def test_plateau_of_001_is_gone() -> None:
    """Было шесть подряд P со значением 0,01 при Cs/Cv = 1,5, Cv = 1,0.

    Теперь на том же участке таблица и результат совпадают по каждому узлу,
    и повторяющихся значений нет.
    """
    cv, cs_cv = 1.0, 1.5
    row = np.asarray(TABLES[cs_cv][cv], dtype=float)
    idx = [j for j in range(len(row)) if P_PCT[j] >= 93.0]
    p = P_PCT[idx] / 100.0
    kp = kritsky_menkel_ppf(p, 1.0, cv, cs_cv * cv)

    assert int((kp == 0.01).sum()) == 0, (
        f"плато 0,01 вернулось: {[float(v) for v in kp]}"
    )
    assert len(set(float(v) for v in kp)) == len(kp), (
        f"в хвосте повторяются значения: {[float(v) for v in kp]}"
    )
    assert all(x >= y for x, y in zip(kp, kp[1:])), f"монотонность сломана: {kp}"
    for k, j in enumerate(idx):
        if row[j] > 0.0:
            assert kp[k] == pytest.approx(row[j], rel=REL)


def test_worst_offender_no_longer_fabricates_01775() -> None:
    """Cs/Cv = 0,5, Cv = 0,7, P = 99,9 %: было 0,1775 вместо нормативного нуля."""
    assert _kp(99.9, 0.7, 0.5) == 0.0


# --------------------------------------------------------------------------- #
# Блоки без нулей должны вести себя ровно как раньше
# --------------------------------------------------------------------------- #

def test_blocks_without_zeros_are_unaffected() -> None:
    """Правка не должна задеть строки, где нулей нет.

    Сравнение идёт с get_ordinates() — тем же источником, что и production, —
    и держится на 1e-12, то есть фактически на совпадении.

    Блок Cs/Cv = 0 ИСКЛЮЧЁН намеренно. Там своя давняя проблема: guard
    `abs(cs) < 0.001` в kritsky_menkel_ppf превращает cs = 0 в отношение
    0,001/Cv, и get_ordinates интерполирует между блоками Cs/Cv = 0 и 0,5 —
    расхождение доходит до 3,6e-3. Это отдельный старый дефект, который по
    условию задачи здесь не исправляется; включать его в проверку значило бы
    либо замаскировать его широким допуском, либо упасть на нём.
    """
    checked = 0
    for cs_cv in sorted(TABLES, key=lambda k: (isinstance(k, str), k)):
        if cs_cv == 0:
            continue
        for cv in sorted(TABLES[cs_cv]):
            row = np.asarray(TABLES[cs_cv][cv], dtype=float)
            if (row == 0.0).any():
                continue
            got = np.asarray(get_ordinates(cs_cv, cv), dtype=float)
            kp = kritsky_menkel_ppf(P_PCT / 100.0, 1.0, cv, cs_cv * cv)
            for j in range(len(got)):
                if got[j] > 0.0:
                    checked += 1
                    assert kp[j] == pytest.approx(got[j], rel=REL), (
                        f"Cs/Cv = {cs_cv}, Cv = {cv}, P = {P_PCT[j]} %: "
                        f"{kp[j]!r} против {got[j]!r} — блок без нулей изменился"
                    )
    assert checked > 5000
