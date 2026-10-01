"""Таблица Б.10 транскрибирована, дефекты тиража зафиксированы, а не исправлены.

Три замечания к методу, потому что они на будущее.

Первое: Б.10 бралась из текстового слоя, а не со снимка. За сессию чтение снимков
провалилось пять раз подряд, все - на подстрочных индексах в мелком кегле:
(5.40) плюс вместо умножения, C_s вместо C_v, theta вместо phi, 1878 = 3930
вместо 5930, V_p за K_m в (5.46). Снимок годится для текста и структуры, но не
для различения похожих индексов.

Второе: выравнивание сделано по монотонности, а не на глаз. В печати каждая строка
невозрастающая по lambda, а в текстовом слое хвостовые нули выпадают, поэтому ряд
дополняется нулями до 21 колонки. Проверка невозрастания по каждой строке одновременно
служит контролем: она нашла три аномалии, которые иначе ушли бы в данные.

Третье, и это главное: дефекты НЕ исправлены. В строках ks = 0,7 и 1,3 в печати
стоят 0,04 и 0,47 в первой ячейке, хотя по соседним строкам ожидается около 0,94
и 0,97. В строке ks = 1,2 значение 0,46 стоит на месте 0,51 и ячейка разъехалась
из-за разрыва "0,9 1". Это дефекты тиража СП 33, а не ошибки извлечения. Молча
чинить их по правдоподобию нельзя: ровно так была получена неверная (7.51) и
неверная (Б.1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sp33_table_b10_values_v1.json"


@pytest.fixture(scope="module")
def table() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_grid_is_29_by_21(table: dict) -> None:
    assert table["row_axis"]["count"] == 29
    assert table["column_axis"]["count"] == 21
    assert len(table["values"]) == 29
    assert all(len(row) == 21 for row in table["values"].values())
    assert sum(len(row) for row in table["values"].values()) == 609


def test_row_axis_ks_from_0_1_to_6_0(table: dict) -> None:
    axis = table["row_axis"]["values"]
    assert axis[0] == 0.1
    assert axis[-1] == 6.0
    # в фикстуре ось хранится числами, а значения - строковыми ключами
    assert {f"{k}" for k in axis} == set(table["values"])


def test_column_axis_lambda_and_its_print_numbering(table: dict) -> None:
    """Колонок 21, и они пронумерованы в печати 2...22, а не 1...21."""
    assert table["column_axis"]["values"] == [
        0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3,
        1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.2, 2.4, 2.6,
    ]
    assert table["column_axis"]["column_numbering_in_print"].startswith("2, 3")


def test_all_values_are_ordinates_in_zero_one(table: dict) -> None:
    """y = Qi/Qp% - доля, значит лежит в [0; 1]. Исключение - дефекты тиража."""
    for ks, row in table["values"].items():
        for value in row:
            assert 0.0 <= value <= 1.0, f"ks={ks}: значение {value} вне [0; 1]"


def test_ks_1_0_row_is_all_ones(table: dict) -> None:
    """При ks = 1,0 нормированный ординат равен единице по всей строке.

    Контроль на выравнивание: если бы нули в хвосте были расставлены неверно,
    строка потеряла бы вид.
    """
    assert table["values"]["1.0"] == [1.0] * 21


def test_ks_0_9_and_1_1_stay_close_about_ks_1_0(table: dict) -> None:
    """Соседние с ks = 1,0 строки близки - признак верной разметки колонок.

    Совпадение не точное: ks = 0,9 и ks = 1,1 - разные строки, и расхождение
    достигает 0,03. Точное совпадение было бы подозрительно, а вот разброс больше
    0,05 означал бы сдвиг колонок.
    """
    r09 = table["values"]["0.9"]
    r11 = table["values"]["1.1"]
    spread = max(abs(a - b) for a, b in zip(r09, r11, strict=True))
    assert spread == pytest.approx(0.03, abs=0.005)
    assert spread < 0.05, "разброс 0,03 у соседних строк: сдвига колонок нет"


def test_clean_rows_are_non_increasing(table: dict) -> None:
    """26 строк из 29 обязаны быть невозрастающими."""
    clean = [ks for ks in table["values"] if ks not in {"0.7", "1.2", "1.3"}]
    assert len(clean) == 26
    for ks in clean:
        row = table["values"][ks]
        assert all(row[j] >= row[j + 1] for j in range(20)), f"ks={ks} не убывает"


def test_printing_defects_are_recorded_not_repaired(table: dict) -> None:
    """Три дефекта тиража зафиксированы; значения оставлены как напечатано."""
    defects = {s["ks"]: s for s in table["suspect_cells"]}
    assert "0.7" in defects
    assert "1.2" in defects
    assert "1.3" in defects

    assert table["values"]["0.7"][0] == 0.04, "ks=0,7: напечатано 0,04, не «исправлено»"
    assert table["values"]["1.3"][0] == 0.47, "ks=1,3: напечатано 0,47"
    assert table["values"]["1.2"][2] == 0.46, "ks=1,2: напечатано 0,46 на месте 0,51"


def test_policy_forbids_silent_repair(table: dict) -> None:
    assert "КАК НАПЕЧАТАНО" in table["suspect_cells_policy"]
    assert "молча" in table["suspect_cells_policy"]


def test_method_is_documented(table: dict) -> None:
    assert "монотонност" in table["transcription_method"]
    assert "нулями" in table["alignment_rule"]
    assert "промахов" in table["transcription_method"]


def test_table_b10_is_not_claimed_as_implemented() -> None:
    """Таблица перенесена, но методика расчёта гидрографа не реализована."""
    text = FIXTURE.read_text(encoding="utf-8")
    assert "не реализована" in text or "not_claimed" in text
