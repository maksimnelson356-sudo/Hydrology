"""Формулы стр. 18 и транскрипция таблиц Б.4/Б.5, прибитые к снимкам печати.

История, чтобы ошибка не повторилась. Первое чтение стр. 18 мелким кеглем было
неверным в трёх местах: в (5.40) плюс вместо умножения, индекс C_s вместо C_v,
и C_s^2 вместо C_v^2 у гаммы. Затем я испортил ещё и букву функции, послушав
текстовый слой PDF, где «phi» отдалось как «theta», — то есть нарушил собственное
правило «снимок важнее слоя».

Транскрипция Б.4 подтверждена числом примера А.7: phi(0,52) = 0,715 против 0,7146
по таблице. Полный численный разбор примера — в test_sp33_worked_example_A7.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
PHOTO = json.loads(
    (FIXTURES / "sp33_formulas_photo_verified_v1.json").read_text(encoding="utf-8")
)
TABLES = json.loads(
    (FIXTURES / "sp33_tables_b4_b5_v1.json").read_text(encoding="utf-8")
)


def test_5_40_is_multiplication_by_phi_of_cv() -> None:
    """(5.40) = x_0 = x_bar_{n/2} * phi(C_v). Не сложение, не C_s."""
    latex = PHOTO["formulas"]["5.40"]["latex"]
    assert latex == "x_0 = \\bar{x}_{n/2}\\cdot\\varphi(C_v)"
    assert "+" not in latex, "(5.40) — умножение, а не сложение"
    assert "C_s" not in latex
    assert "bar{x}" in latex, "во втором множителе есть черта над x"


def test_5_42_and_gamma_use_cv() -> None:
    """(5.42) — phi(C_v), гамма = 1/C_v^2."""
    assert "C_v" in PHOTO["formulas"]["5.42"]["latex"]
    assert PHOTO["auxiliary_from_photo"]["gamma"] == "gamma = 1 / C_v^2"
    assert "Cₛ" not in PHOTO["auxiliary_from_photo"]["gamma"]


def test_function_is_phi_not_theta() -> None:
    """Буква функции — phi. Текстовый слой ошибся, снимок прав."""
    assert "phi(C_v)" in TABLES["B4"]["title"]
    assert "varphi" in PHOTO["formulas"]["5.40"]["latex"]
    assert "varphi" in PHOTO["formulas"]["5.42"]["latex"]
    assert "theta" not in TABLES["B4"]["title"]
    assert "theta_was_ocr_error" in TABLES, "ошибка OCR зафиксирована явно"


def test_5_43_verified_form_uses_mean_in_denominator() -> None:
    """(5.43) проверена численно: в знаменателе СРЕДНЕЕ x̄(n/2), минус не нужен.

    Напечатанный вариант сохранён рядом, чтобы дефект не потерялся.
    """
    f = PHOTO["formulas"]["5.43"]
    assert f["status"] == "verified_by_numerical_example_A7"

    verified = f["latex_verified"]
    assert "\\bar{x}_{n/2}" in verified
    assert "-\\sum" not in verified
    assert "\\lg" in verified, "логарифм десятичный, не натуральный"

    printed = f["latex_printed"]
    assert "x_{n/2}" in printed
    assert "\\bar{x}" not in printed, "в печати черта над x потеряна"


def test_contradiction_resolved_not_deferred() -> None:
    """Противоречие снято численно, разъяснение издателя не требуется."""
    c = PHOTO["standard_internal_contradiction"]
    assert "РАЗРЕШЕНО ЧИСЛЕННО" in c["status"]
    assert "x̄(n/2)" in c["resolution"]
    assert len(c["two_printing_defects"]) == 2
    assert any("лишний минус" in d.lower() for d in c["two_printing_defects"])
    assert c["no_publisher_needed"]
    assert "Б.5" in c["residual_open_question"]


def test_b4_transcription_confirmed_by_printed_number() -> None:
    """phi(0,52) = 0,715 по печати; наша транскрипция даёт 0,7146."""
    rows = TABLES["B4"]["rows"]
    phi_050 = rows["0.5"][0]
    phi_060 = rows["0.6"][0]
    interp = phi_050 + 0.2 * (phi_060 - phi_050)
    assert interp == pytest.approx(0.7146, abs=1e-4)
    assert abs(interp - 0.715) < 0.001, "расхождение с печатью в пределах 0,001"


def test_b4_and_b5_are_keyed_by_cv() -> None:
    """Обе таблицы — по изменчивости C_v, а не по асимметрии C_s."""
    assert TABLES["B4"]["row_axis"] == "C_v"
    assert TABLES["B5"]["row_axis"] == "C_v"


def test_b5_columns_are_indices_not_lambda_values() -> None:
    """Колонки Б.5 — индексы. Соответствие колонка↔lambda из снимка не следует."""
    assert "ИНДЕКСЫ" in TABLES["B5_validation_by_example"]
    assert "остаётся неопределённым" in TABLES["B5_validation_by_example"]
