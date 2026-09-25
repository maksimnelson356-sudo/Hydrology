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
