"""
tools/run_methodology.py
Console run of a methodology through the service layer (stage 3 of DOCS/ROADMAP.md).

Examples:
    python tools/run_methodology.py --list
    python tools/run_methodology.py --method stats_parameters --file data.xlsx --post "Пост 1"
    python tools/run_methodology.py --method frequency_pearson3 --demo

Runs without GUI: builds the service container via build_container(), reads the
series with core.stats.sheet_reader and delegates to CalculationService.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows console defaults to a legacy codepage; force UTF-8 for Cyrillic output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.domain.models import Dataset, DatasetType
from core.services.bootstrap import build_container


def load_dataset(path: str | None, post: str | None) -> Dataset:
    """Read a yearly series from an Excel file (sheet_reader) or raise."""
    from core.stats.sheet_reader import read_hydro_data

    if not path:
        raise SystemExit("Не указан --file: путь к файлу данных (.xlsx/.xls)")
    data, _ = read_hydro_data(path, post or None)
    if not data:
        raise SystemExit(f"В файле {path} не найдено данных для поста «{post or '(первый)'}»")
    name = post or Path(path).stem
    return Dataset(name=name, data=data, dataset_type=DatasetType.OBSERVED)


def demo_dataset() -> Dataset:
    """Deterministic demo series (30 years, same as in tests)."""
    values = [
        110.5, 117.8, 74.5, 98.6, 110.1, 113.5, 106.5, 115.0, 102.9, 105.5,
        101.8, 89.3, 91.5, 103.8, 94.2, 112.7, 112.9, 118.0, 99.7, 113.8,
        90.9, 91.8, 100.8, 102.8, 84.0, 82.7, 103.6, 91.4, 112.1, 103.9,
    ]
    return Dataset(
        name="Демо-пост",
        data={1990 + i: v for i, v in enumerate(values)},
        dataset_type=DatasetType.OBSERVED,
    )


def print_list(container) -> None:
    print("Зарегистрированные методики (P0):\n")
    for methodology_id in container.registered_methodology_ids():
        descriptor = container.registry.get(methodology_id)
        print(f"  {methodology_id}")
        print(f"    Название:   {descriptor.name}")
        print(f"    Норматив:   {descriptor.normative_reference}")
        if descriptor.min_points:
            print(f"    Мин. ряд:   {descriptor.min_points} лет")
        print(f"    Применение: {descriptor.scope}")
        print()


def run_methodology(container, methodology_id: str, dataset: Dataset, parameters: dict) -> int:
    descriptor = container.registry.get(methodology_id)

    print(f"Методика:  {descriptor.name} ({descriptor.qualified_name})")
    print(f"Норматив:  {descriptor.normative_reference}")
    print(f"Ряд:       {dataset.name}, {dataset.length} лет ({dataset.start_year}–{dataset.end_year})")
    print()

    try:
        result = container.calculation.execute(
            descriptor.to_methodology(), dataset, parameters=parameters
        )
    except Exception as error:  # noqa: BLE001 - console boundary
        print(f"ОШИБКА: {error}")
        return 1

    print("Результат (COMPLETED):")
    print(json.dumps(result.output_data, ensure_ascii=False, indent=2, default=str)[:4000])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Прогон методики через сервисный слой HydroSphere")
    parser.add_argument("--method", help="id методики (см. --list)")
    parser.add_argument("--file", help="файл данных (.xlsx/.xls)")
    parser.add_argument("--post", help="имя поста в файле (опционально)")
    parser.add_argument("--demand", type=float, default=None, help="demand_m3_s для reservoir_regulation")
    parser.add_argument("--list", action="store_true", help="показать список методик")
    parser.add_argument("--demo", action="store_true", help="использовать встроенный демо-ряд")
    args = parser.parse_args()

    container = build_container()

    if args.list:
        print_list(container)
        return 0

    if not args.method:
        parser.print_help()
        return 2

    if not container.calculation.has_handler(
        container.registry.get(args.method).qualified_name
    ):
        print(f"Методика «{args.method}» зарегистрирована, но не имеет обработчика (см. --list)")
        return 2

    dataset = demo_dataset() if args.demo else load_dataset(args.file, args.post)
    parameters: dict = {}
    if args.demand is not None:
        parameters["demand_m3_s"] = args.demand

    return run_methodology(container, args.method, dataset, parameters)


if __name__ == "__main__":
    raise SystemExit(main())
