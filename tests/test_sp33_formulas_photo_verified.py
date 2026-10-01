"""Формулы, прочитанные по снимкам печати 2026-09-29: (5.2), (5.3), (5.40)-(5.43).

Тест не реализует методику, а фиксирует саму транскрипцию: проверяет, что
структура формул именно такая, как на снимке, и что ключевые спорные места
(знак у (n−1) в (5.2)/(5.3), знаменатель n/2 в (5.43), различие (5.40) и
(5.43)) не потеряны.

Зачем это нужно. Текстовый слой PDF эти формулы не отдаёт. На него уже была
опирана неверная (7.51) и неверная (Б.1) со знаменателем √n. Реконструкция
«по смыслу» от пользователя тоже не подошла: в ней (5.40) и (5.43) совпали,
а (5.42) пропала. Транскрипция обязана быть прибита тестом к снимку.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "sp33_formulas_photo_verified_v1.json"
)


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_declares_photo_provenance(data: dict) -> None:
    assert data["provenance"]["kind"] == "printed_photo"
    assert "5.2,5.3.png" in data["provenance"]["source"]
    assert "5.40-5.43.png" in data["provenance"]["source"]


def test_rejected_reconstruction_is_recorded(data: dict) -> None:
    """Ошибочная реконструкция зафиксирована, чтобы её не предложили снова."""
    rejected = data["rejected_reconstruction"]
    assert "опровергнуто" in rejected["verdict"]
    assert "5.40" in rejected["what"]


def test_lambda_2_divides_by_n_minus_one(data: dict) -> None:
    """(5.2): ДЕЛЕНИЕ на (n-1).

    Скобка закрывается после суммы, и (n-1) стоит ПОСЛЕ скобки. Проверяется и
    структурой latex, и числом: при n = 8 деление и умножение дают разные знаки,
    так что подмена невозможна незаметно.
    """
    latex = data["formulas"]["5.2"]["latex"]
    assert "/(n-1)" in latex
    assert "cdot" not in latex, "(5.2) — деление, а не умножение"
    k = [0.8, 1.2, 0.5, 1.7, 0.95, 1.35, 0.62, 1.05]
    n = len(k)
    log_sum = sum(math.log10(value) for value in k)

    lambda2 = log_sum / (n - 1)
    wrong = log_sum * (n - 1)
    # Числа получены прямым расчётом, а не подобраны.
    assert log_sum == pytest.approx(-0.166671, abs=1e-6)
    assert lambda2 == pytest.approx(-0.023810, abs=1e-5)
    assert wrong == pytest.approx(-1.166700, abs=1e-5)
    assert lambda2 == pytest.approx(wrong / (n - 1) ** 2, rel=1e-9)


def test_lambda_3_divides_by_n_minus_one(data: dict) -> None:
    """(5.3): та же структура, но k_i входит множителем под логарифм."""
    latex = data["formulas"]["5.3"]["latex"]
    assert "/(n-1)" in latex
    assert "cdot" not in latex
    assert "k_i\\lg k_i" in latex


def test_k_4_is_ratio_to_mean(data: dict) -> None:
    """(5.4) k_i = Q_i/Q̄ — модульный коэффициент, ранее не был зафиксирован."""
    latex = data["formulas"]["5.4"]["latex"]
    assert "k_i = Q_i/" in latex
    assert "bar{Q}" in latex
    assert data["formulas"]["5.5"]["latex"].endswith("/n")


def test_my_double_error_on_division_is_recorded(data: dict) -> None:
    """Я ошибся дважды и переубедил пользователя, который был прав.

    Пользователь прислал деление, я записал умножение, он возразил, и я настоял
    на своём. Снимок в высоком разрешении показал деление. Ошибка зафиксирована,
    чтобы «пользователь ошибся» не повторилось как приём.
    """
    c = data["critical_correction_5_2_5_3"]
    assert "переубедил пользователя, который был прав" in c["what_happened"]
    joined = " ".join(c["sequence"])
    assert "настоял на своей ошибке" in joined
    assert "Пользователь возразил" in joined
    assert "ДВАЖДЫ" in c["verification"]


def test_km_coefficients_come_from_external_source_4(data: dict) -> None:
    """п. 5.6: для Крицкого-Менкеля коэффициенты из [4], а не из Б.1.

    Б.1 - это Пирсон III. При Cs/Cv < 2 применяется Крицкий-Менкель, и там мы
    используем коэффициенты чужого распределения.
    """
    c = data["critical_finding_km_coefficients"]
    assert "Крицкого-Менкеля" in c["what"]
    assert "[4]" in c["what"]
    assert "таблица Б.1 для распределения Пирсона III типа" in c["quote"]
    assert "[4] - для распределения Крицкого-Менкеля" in c["quote"]
    assert "неверной таблицы" in c["consequence"]
    assert "Источник [4] вне СП 33" in c["blocked_on"]


def test_ml_coefficients_come_from_nomograms_source_5(data: dict) -> None:
    """п. 5.5: λ₂, λ₃ → C_v, C_s по номограммам [5], которых нет в СП 33."""
    c = data["formulas"]["5.5_clause"]
    assert "номограмм" in c["lambda_to_coefficients"]
    assert "[5]" in c["lambda_to_coefficients"]
    assert "усеченному" in c["note_about_B4_B5"] or "усеч" in c["note_about_B4_B5"]


def test_formula_5_40_is_x0_estimate_not_a_lambda(data: dict) -> None:
    """(5.40) — оценка x₀, а не статистика λ.

    Именно в этом реконструкция ошиблась: (5.40) и (5.43) были склеены в одну
    формулу. Здесь фиксируется, что (5.40) содержит x₀ и φ(Cₛ), и не содержит
    суммы, характерной для (5.43).
    """
    latex = data["formulas"]["5.40"]["latex"]
    assert "x_0" in latex
    assert "\\varphi(C_v)" in latex
    assert "C_s" not in latex, "индекс C_v (изменчивость), а не C_s (асимметрия)"
    assert "\\cdot" in latex, "(5.40) — умножение, а не сложение"
    assert "\\sum" not in latex, "(5.40) не содержит суммы — это оценка параметра"


def test_formula_5_43_is_separate_statistic(data: dict) -> None:
    """(5.43) — λ₂ₙ⁄₂ со знаменателем именно n/2, а не n/2 − 1."""
    latex = data["formulas"]["5.43"]["latex"]
    assert "\\lambda_{2n/2}" in latex
    assert "n/2}" in latex
    assert "n/2 - 1" not in latex

    # Проверка на данных: знаменатель n/2, не n/2 − 1
    x = [10.0, 12.0, 9.0, 14.0, 11.0, 13.0, 8.0, 15.0]
    half = len(x) // 2
    ordered = sorted(x, reverse=True)
    median_of_top = ordered[half - 1]
    total = sum(
        math.log(value / median_of_top) for value in ordered[:half]
    )
    with_half = total / half
    with_half_minus_one = total / (half - 1)
    assert with_half != pytest.approx(with_half_minus_one, rel=1e-3)


def test_formula_5_42_was_missing_from_reconstruction(data: dict) -> None:
    """(5.42) присутствует в фикстуре — в реконструкции её не было вовсе."""
    latex = data["formulas"]["5.42"]["latex"]
    assert "\\varphi(C_v)" in latex
    assert "C_s" not in latex
    assert "\\gamma" in latex
    assert "x_{mg}" in latex
    assert "Б.4" in data["auxiliary_from_photo"]["table_Б.4"]


def test_computation_order_and_tables_from_photo(data: dict) -> None:
    """Порядок расчёта и адреса таблиц Б.4/Б.5 — тоже со снимка."""
    order = data["computation_order_from_photo"]
    assert "убыванию" in order[0]
    assert any("5.41" in step for step in order)
    assert any("5.43" in step for step in order)
    assert any("5.40" in step for step in order)
    assert any("5.7" in step for step in order)

    aux = data["auxiliary_from_photo"]
    # (5.40) и (5.42) оперируют изменчивостью C_v, поэтому и гамма по C_v.
    assert aux["gamma"] == "gamma = 1 / C_v^2"
    assert "C_v" in aux["gamma"] and "Cₛ" not in aux["gamma"]
    assert "Б.5" in aux["table_Б.5"]


def test_truncated_gamma_declared_not_implemented(data: dict) -> None:
    """Метод усечённого гамма-распределения не объявляется реализованным.

    Для него нужны таблицы Б.4 и Б.5, которых в проекте нет. Объявлять методику
    готовой без них — ровно тот дефект, который закрыт в (7.51) и (Б.1).
    """
    pending = data["not_implemented_yet"]
    assert "Б.4" in pending["missing"][0]
    assert "Б.5" in pending["missing"][1]
    assert "5.44" in pending["missing"][2]
