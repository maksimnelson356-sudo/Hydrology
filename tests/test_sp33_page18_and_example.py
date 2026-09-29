"""Формулы стр. 18 и числовой пример стр. 59, прибитые к снимкам печати.

История, чтобы ошибка не повторилась. Первое чтение стр. 18 мелким кеглем было
неверным в трёх местах: в (5.40) плюс вместо умножения, индекс C_s вместо C_v,
и C_s^2 вместо C_v^2 у гаммы. Затем я испортил ещё и букву функции, послушав
текстовый слой PDF, где «phi» отдалось как «theta», — то есть нарушил собственное
правило «снимок важнее слоя».

Тем не менее пример на стр. 59 подтверждает транскрипцию числом, напечатанным в
стандарте: phi(0,52) = 0,715 против 0,7146 по таблице Б.4.
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
EXAMPLE = json.loads(
    (FIXTURES / "sp33_worked_example_A7_v1.json").read_text(encoding="utf-8")
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
    assert "C_s" not in json.dumps(PHOTO["auxiliary_from_photo"])


def test_function_is_phi_not_theta() -> None:
    """Буква функции — phi. Текстовый слой ошибся, снимок прав."""
    assert "phi(C_v)" in TABLES["B4"]["title"]
    assert "varphi" in PHOTO["formulas"]["5.40"]["latex"]
    assert "varphi" in PHOTO["formulas"]["5.42"]["latex"]
    assert "theta" not in TABLES["B4"]["title"]
    assert "theta_was_ocr_error" in TABLES, "ошибка OCR зафиксирована явно"


def test_5_43_has_no_minus_as_printed() -> None:
    """(5.43) напечатана БЕЗ минуса. Это дефект стандарта, зафиксированный как есть."""
    latex = PHOTO["formulas"]["5.43"]["latex"]
    assert "-\\sum" not in latex
    assert latex.startswith("\\lambda_{2n/2} = \\frac{")
    assert "МИНУСА ПЕРЕД СУММОЙ НЕТ" in PHOTO["formulas"]["5.43"]["note"]


def test_standard_internal_contradiction_is_recorded() -> None:
    """Противоречие самого СП 33 зафиксировано, а не разрешено догадкой."""
    c = PHOTO["standard_internal_contradiction"]
    assert c["status"] == "метод НЕ реализован"
    joined = " ".join(c["evidence_for_negative"]).lower()
    against = " ".join(c["evidence_against"]).lower()
    assert "отрицательные" in joined
    assert "без минуса" in against
    assert "2,3026" in c["extra_defect"]


def test_b4_transcription_confirmed_by_printed_number() -> None:
    """phi(0,52) = 0,715 по печати; наша транскрипция даёт 0,7146."""
    v = EXAMPLE["chain_verified_against_our_fixture"]["B4"]
    assert v["printed"] == "phi(0,52) = 0,715"
    assert v["agrees"] is True
    assert v["interpolated"] == pytest.approx(0.7146, abs=1e-4)

    rows = TABLES["B4"]["rows"]
    phi_050 = rows["0.5"][0]
    phi_060 = rows["0.6"][0]
    interp = phi_050 + 0.2 * (phi_060 - phi_050)
    assert interp == pytest.approx(0.7146, abs=1e-4)
    assert abs(interp - 0.715) < 0.001, "расхождение с печатью должно быть в пределах 0,001"


def test_b5_columns_are_indices_not_lambda_values() -> None:
    """Колонки Б.5 — индексы. Соответствие колонка↔lambda из снимка не следует."""
    assert "ИНДЕКСЫ" in TABLES["B5_validation_by_example"]
    assert "остаётся неопределённым" in TABLES["B5_validation_by_example"]


def test_worked_example_numbers_are_pinned() -> None:
    """Контрольные значения примера стр. 59."""
    d = EXAMPLE["derived_values"]
    assert d["n_over_2"] == 43
    assert d["n_implied"] == 86
    assert d["x_bar_n_2"] == 8132
    assert d["lambda_2n_2"] == -0.0176
    assert d["Cv_from_B5"] == 0.52
    assert d["phi_from_B4"] == 0.715
    assert d["x0"] == 5814


@pytest.mark.parametrize(
    "printed, recomputed, tol",
    [
        ("349660 / 43 = 8132", 349660 / 43, 0.5),
        ("-0,75733 / 43 = -0,0176", -0.75733 / 43, 1e-4),
        ("8132 * 0,715 = 5814", 8132 * 0.715, 1.0),
    ],
)
def test_example_arithmetic_reproduces(printed: str, recomputed: float, tol: float) -> None:
    """Арифметика примера воспроизводится, значит чтение чисел верное."""
    assert round(recomputed, 4) == pytest.approx(
        float(printed.split("=")[-1].strip().replace(",", ".")), abs=tol
    )


def test_missing_source_for_full_reproduction() -> None:
    """Таблица А.4 отсутствует, поэтому сквозной расчёт невозможен — это заявлено."""
    assert "А.4" in EXAMPLE["missing_for_full_reproduction"]
    assert "невозможен" in EXAMPLE["use"]
