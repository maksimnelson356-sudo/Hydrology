"""CLI tests for the newly wired methodologies."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from core.domain import Dataset
from tools import run_methodology as cli


class _Descriptor:
    name = "Test"
    qualified_name = "test@1.0"
    normative_reference = "Test standard"

    def to_methodology(self):
        return SimpleNamespace(qualified_name=self.qualified_name)


class _Registry:
    def get(self, _methodology_id: str) -> _Descriptor:
        return _Descriptor()


class _Calculation:
    def __init__(self) -> None:
        self.parameters = None

    def has_handler(self, _methodology_name: str) -> bool:
        return True

    def execute(self, _methodology, _dataset, parameters=None):
        self.parameters = parameters
        return SimpleNamespace(output_data={"ok": True})


class _Container:
    def __init__(self) -> None:
        self.registry = _Registry()
        self.calculation = _Calculation()

    def registered_methodology_ids(self):
        return []


def _run_main(monkeypatch, argv: list[str], container: _Container) -> int:
    monkeypatch.setattr(cli, "build_container", lambda: container)
    monkeypatch.setattr(sys, "argv", ["run_methodology.py", *argv])
    return cli.main()


def test_flood_hydrograph_cli_maps_parameters(monkeypatch) -> None:
    container = _Container()

    exit_code = _run_main(
        monkeypatch,
        [
            "--method", "flood_hydrograph",
            "--demo",
            "--q-peak", "100",
            "--t-peak", "5",
            "--t-base", "20",
            "--flood-method", "triangle",
            "--flood-dt", "2",
        ],
        container,
    )

    assert exit_code == 0
    assert container.calculation.parameters == {
        "Q_peak": 100.0,
        "T_peak": 5.0,
        "T_base": 20.0,
        "method": "triangle",
        "dt": 2.0,
    }


def test_backwater_cli_maps_parameters(monkeypatch) -> None:
    container = _Container()

    exit_code = _run_main(
        monkeypatch,
        [
            "--method", "backwater",
            "--demo",
            "--q", "50",
            "--channel-width", "10",
            "--channel-side-slope", "1",
            "--manning-n", "0.03",
            "--channel-slope", "0.001",
            "--reservoir-head", "2",
            "--backwater-length", "1000",
        ],
        container,
    )

    assert exit_code == 0
    assert container.calculation.parameters == {
        "Q": 50.0,
        "B": 10.0,
        "m": 1.0,
        "n": 0.03,
        "I": 0.001,
        "H_reservoir": 2.0,
        "L_max": 1000.0,
    }


def test_series_extension_cli_loads_analog_file(monkeypatch) -> None:
    container = _Container()
    primary = Dataset(name="primary", data={2000: 10.0, 2001: 12.0})
    analog = Dataset(name="analog", data={2000: 20.0, 2001: 24.0, 2002: 28.0})

    def fake_load_dataset(path: str, _post: str | None) -> Dataset:
        return analog if path == "analog.xlsx" else primary

    monkeypatch.setattr(cli, "load_dataset", fake_load_dataset)
    exit_code = _run_main(
        monkeypatch,
        [
            "--method", "series_extension",
            "--file", "primary.xlsx",
            "--analog-file", "analog.xlsx",
            "--analog-post", "A",
        ],
        container,
    )

    assert exit_code == 0
    assert container.calculation.parameters == {"analog_df": analog.data}


def test_staged_series_extension_cli_loads_stage_config(monkeypatch, tmp_path) -> None:
    container = _Container()
    years = range(1990, 2026)
    config = {
        "stages": [
            {
                "name": "recent",
                "analogs": {
                    "a1": {str(year): float(i + 1) for i, year in enumerate(years)},
                    "a2": {
                        str(year): float((i % 5) + 1)
                        for i, year in enumerate(years)
                    },
                },
                "fit_years": list(range(1990, 2020)),
                "target_years": [2020, 2021, 2022],
                "ro_cr": 0.6,
            }
        ]
    }
    config_path = tmp_path / "staged.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = _run_main(
        monkeypatch,
        [
            "--method", "series_extension_staged",
            "--demo",
            "--staged-config", str(config_path),
        ],
        container,
    )

    assert exit_code == 0
    assert container.calculation.parameters == {
        "stages": config["stages"],
        "exclude_negative": True,
    }


def test_staged_series_extension_cli_requires_config(monkeypatch) -> None:
    container = _Container()

    with pytest.raises(SystemExit, match="--staged-config"):
        _run_main(
            monkeypatch,
            ["--method", "series_extension_staged", "--demo"],
            container,
        )


def test_load_staged_config_rejects_invalid_json(tmp_path) -> None:
    config_path = tmp_path / "broken.json"
    config_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(SystemExit, match="Некорректный JSON"):
        cli.load_staged_config(str(config_path))


def test_load_dataset_reads_normalized_a8_json(tmp_path) -> None:
    primary_path = tmp_path / "primary.json"
    primary_path.write_text(
        json.dumps(
            {
                "name": "р. Сьежа – д. Стан",
                "unit": "л/с·км²",
                "catchment_area_km2": 407,
                "data": {"1971": 3.77},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    dataset = cli.load_dataset(str(primary_path), None)

    assert dataset.name == "р. Сьежа – д. Стан"
    assert dataset.data == {1971: 3.77}
    assert dataset.unit == "л/с·км²"
    assert dataset.catchment_area_km2 == 407


def test_staged_series_extension_cli_forwards_the_evidence_status(monkeypatch, tmp_path) -> None:
    """metadata.evidence_status обязан доехать до параметров расчёта.

    Регрессия: _build_parameters брал из конфига только stages и exclude_negative,
    поэтому статус доказательности оставался в файле и никуда не попадал.
    """
    container = _Container()
    years = range(1990, 2026)
    config = {
        "stages": [
            {
                "name": "recent",
                "analogs": {
                    "a1": {str(year): float(i + 1) for i, year in enumerate(years)},
                    "a2": {
                        str(year): float((i % 5) + 1)
                        for i, year in enumerate(years)
                    },
                },
                "fit_years": list(range(1990, 2020)),
                "target_years": [2020, 2021, 2022],
                "ro_cr": 0.6,
            }
        ],
        "metadata": {"evidence_status": "partial"},
    }
    config_path = tmp_path / "staged.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = _run_main(
        monkeypatch,
        [
            "--method", "series_extension_staged",
            "--demo",
            "--staged-config", str(config_path),
        ],
        container,
    )

    assert exit_code == 0
    assert container.calculation.parameters["evidence_status"] == "partial", (
        "статус доказательности не дошёл до параметров расчёта"
    )


# ─────────────────────────────────────────────────────────────────────────
# Регрессия: путь --file для Excel был сломан
#
# load_dataset импортировал read_hydro_data из core.stats.sheet_reader, а
# функции с таким именем в модуле нет. Импорт ленивый, поэтому --list и
# --demo работали, а --file падал с ImportError. README документирует
# именно этот путь. Тесты покрывали только JSON, поэтому баг дожил до main.
# ─────────────────────────────────────────────────────────────────────────

_VALUES = [110.5, 117.8, 74.5, 98.6, 110.1, 113.5, 106.5, 115.0, 102.9, 105.5,
           101.8, 89.3, 91.5, 103.8, 94.2, 112.7, 112.9, 118.0, 99.7, 113.8]
_YEARS = list(range(1990, 1990 + len(_VALUES)))


def _xlsx(path, sheets: dict[str, object]) -> str:
    import pandas as pd

    with pd.ExcelWriter(path) as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    return str(path)


def test_excel_with_year_column_loads(tmp_path):
    """Основной случай: год отдельной колонкой."""
    import pandas as pd

    path = _xlsx(tmp_path / "plain.xlsx",
                 {"Sheet1": pd.DataFrame({"Год": _YEARS, "Расход": _VALUES})})

    dataset = cli.load_dataset(path, None)

    assert len(dataset.data) == len(_VALUES)
    assert min(dataset.data) == _YEARS[0]
    assert max(dataset.data) == _YEARS[-1]


def test_excel_without_year_is_refused_not_faked(tmp_path):
    """Индекс 0..N - это не годы.

    Без проверки диапазона молча получались бы годы 0,1,2,..., и статистика
    считалась бы по мусору. Проверка диапазона добавлена именно поэтому.
    """
    import pandas as pd

    path = _xlsx(tmp_path / "no_year.xlsx",
                 {"Пост 1": pd.DataFrame({"Пост 1": _VALUES})})

    with pytest.raises(SystemExit) as excinfo:
        cli.load_dataset(path, "Пост 1")

    assert "не найден год" in str(excinfo.value)


def test_excel_sheet_named_by_post_still_needs_a_year(tmp_path):
    """Лист по --post находится, но без года чтение всё равно отказывает.

    Имя намеренно не «loads»: проверяет отказ, а не успешное чтение.
    """
    import pandas as pd

    path = _xlsx(tmp_path / "named.xlsx",
                 {"Пост 1": pd.DataFrame({"Расход": _VALUES})})

    with pytest.raises(SystemExit) as excinfo:
        cli.load_dataset(path, "Пост 1")
    assert "не найден год" in str(excinfo.value)


def test_excel_unknown_post_names_available_sheets(tmp_path):
    import pandas as pd

    path = _xlsx(tmp_path / "sheets.xlsx",
                 {"Данные": pd.DataFrame({"Год": _YEARS, "Расход": _VALUES})})

    with pytest.raises(SystemExit) as excinfo:
        cli.load_dataset(path, "НетТакогоЛиста")

    message = str(excinfo.value)
    assert "НетТакогоЛиста" in message
    # Перечисляются реальные листы. Раньше здесь предлагалась команда
    # --list-sheets, которой в CLI нет, - то есть сообщение уводило в никуда.
    assert "Данные" in message
    assert "--list-sheets" not in message


def test_excel_with_title_rows_before_header(tmp_path):
    """Книги МДС начинаются с титульных строк; заголовок ищется под ними."""
    import pandas as pd

    path = tmp_path / "with_title.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([
            ["ФЕДЕРАЛЬНАЯ СЛУЖБА ГИДРОМЕТЕОРОЛОГИИ"],
            [],
            ["Таблица 1 - расходы воды, м3/с"],
            [],
            ["Пост 1 - д. Горелуха"],
            [],
        ]).to_excel(writer, sheet_name="Данные", index=False, header=False)
        pd.DataFrame({"Год": _YEARS, "Расход": _VALUES}).to_excel(
            writer, sheet_name="Данные", index=False, startrow=6)

    dataset = cli.load_dataset(str(path), None)

    assert len(dataset.data) == len(_VALUES)
    assert min(dataset.data) == _YEARS[0]
