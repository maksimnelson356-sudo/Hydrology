"""
tools/run_methodology.py
Console run of a methodology through the service layer (stage 3 of DOCS/ROADMAP.md).

Examples:
    python tools/run_methodology.py --list
    python tools/run_methodology.py --method stats_parameters --file data.xlsx --post "Пост 1"
    python tools/run_methodology.py --method frequency_pearson3 --demo
    python tools/run_methodology.py --method series_extension_staged --file primary.xlsx --staged-config stages.json

Runs without GUI: builds the service container via build_container(), reads the
series with core.stats.sheet_reader and delegates to CalculationService.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - только для аннотаций
    import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows console defaults to a legacy codepage; force UTF-8 for Cyrillic output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.domain.models import Dataset, DatasetType  # noqa: E402
from core.services.bootstrap import build_container  # noqa: E402


def _load_json_dataset(path: Path) -> Dataset:
    """Read a normalized JSON dataset produced by the A.8 importer."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Не удалось прочитать JSON-файл {path}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise SystemExit(f"JSON-файл {path} должен содержать объект с полем data")

    data: dict[int, float] = {}
    for raw_year, raw_value in payload["data"].items():
        if raw_value is None:
            continue
        try:
            data[int(raw_year)] = float(raw_value)
        except (TypeError, ValueError) as error:
            raise SystemExit(f"Некорректные данные года {raw_year} в {path}") from error
    if not data:
        raise SystemExit(f"В JSON-файле {path} не найдено числовых данных")

    name = str(payload.get("name") or path.stem)
    unit = str(payload.get("unit") or "m³/s")
    area = payload.get("catchment_area_km2")
    return Dataset(
        name=name,
        data=data,
        dataset_type=DatasetType.OBSERVED,
        unit=unit,
        catchment_area_km2=float(area) if area is not None else None,
    )


def load_dataset(path: str | None, post: str | None) -> Dataset:
    """Read a yearly series from JSON/Excel (sheet_reader) or raise."""
    if not path:
        raise SystemExit("Не указан --file: путь к данным (.json/.xlsx/.xls)")
    path_object = Path(path)
    if path_object.suffix.lower() == ".json":
        return _load_json_dataset(path_object)

    # Импортируется лениво: sheet_reader тянет pandas/xlrd и нужен только здесь.
    # Раньше здесь стояло `from core.stats.sheet_reader import read_hydro_data` -
    # функции с таким именем в модуле нет, и путь --file падал с ImportError.
    import pandas as pd

    from core.stats.sheet_reader import numeric_column, read_work_sheet

    # Без --post берём первый лист: find_sheet с пустым списком ключей
    # возвращает None, и read_work_sheet отдаёт пустой DataFrame.
    sheet_keywords = [post] if post else []
    frame = read_work_sheet(path, sheet_keywords, use_columns=True)
    if frame is None or frame.empty:
        if post:
            # Перечисляем реальные листы, а не отсылаем к несуществующему флагу.
            try:
                available = ", ".join(pd.ExcelFile(path).sheet_names)
            except Exception:  # noqa: BLE001 - файл может быть не Excel
                available = "не удалось прочитать"
            raise SystemExit(
                f"В файле {path} не найден лист «{post}». "
                f"Доступные листы: {available}. "
                f"Либо запустите без --post, чтобы взять первый лист."
            )
        frame = read_work_sheet(path, [pd.ExcelFile(path).sheet_names[0]],
                                use_columns=True)
    if frame is None or frame.empty:
        raise SystemExit(f"В файле {path} не найдено данных")

    year_column = _find_year_column(frame)
    values = numeric_column(frame)

    if year_column is not None:
        years = pd.to_numeric(frame[year_column], errors="coerce")
    else:
        # Года может не быть отдельной колонкой: при чтении с skiprows он
        # становится индексом. Но индекс 0..N — это НЕ годы. Без проверки
        # диапазона молча получались бы годы 0,1,2,... и статистика по мусору,
        # поэтому год обязан выглядеть как год, иначе отказ.
        years = pd.to_numeric(pd.Series(frame.index), errors="coerce")
        plausible = years.dropna()
        looks_like_years = (
            len(plausible) > 0
            and bool(((plausible >= 1850) & (plausible <= 2100)).all())
        )
        if not looks_like_years:
            raise SystemExit(
                f"В файле {path} не найден год: нет ни колонки «год»/«year», ни "
                f"года в первой колонке (индекс выглядит как {list(years.head(3))}). "
                f"Добавьте столбец с годами или укажите --post с именем листа."
            )

    if values is None:
        raise SystemExit(f"В файле {path} не найден числовой столбец со значениями")

    # numeric_column в первом проходе возвращает dropna()-серию, то есть она
    # может быть короче years. Молчаливый zip тогда спарил бы 1990-й год со
    # вторым значением ряда. Проверяем длины и отказываем, а не подгоняем.
    if len(values) != len(years):
        raise SystemExit(
            f"В файле {path} столбец значений и столбец лет расходятся по длине "
            f"({len(values)} и {len(years)}) - вероятно, в значениях есть пропуски. "
            f"Уберите пропуски или укажите другой столбец значений."
        )

    data = {
        int(year): float(value)
        for year, value in zip(years, values, strict=True)
        if pd.notna(year) and pd.notna(value)
    }
    if not data:
        raise SystemExit(f"В файле {path} не удалось прочитать ни одного значения")
    name = post or path_object.stem
    return Dataset(name=name, data=data, dataset_type=DatasetType.OBSERVED)


def _find_year_column(frame: pd.DataFrame) -> str | None:
    """Найти столбец с годом по его имени."""
    for col in frame.columns:
        cleaned = str(col).strip().lower()
        if "год" in cleaned or "year" in cleaned:
            return col
    return None


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
    print("Зарегистрированные методики:\n")
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


def load_staged_config(path: str) -> dict:
    """Load and validate the JSON stage configuration for the staged method."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise SystemExit(f"Не удалось прочитать staged-конфигурацию: {path}") from error
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SystemExit(f"Некорректный JSON staged-конфигурации: {path}") from error
    if not isinstance(config, dict) or not isinstance(config.get("stages"), list):
        raise SystemExit("staged-конфигурация должна содержать непустой список stages")
    if not config["stages"]:
        raise SystemExit("staged-конфигурация должна содержать непустой список stages")
    return config


def _build_parameters(args, dataset: Dataset) -> dict:
    """Map CLI options to the selected methodology's parameter names."""
    parameters: dict = {}
    if args.demand is not None:
        parameters["demand_m3_s"] = args.demand

    if args.method == "series_extension_staged":
        if args.staged_config is None:
            raise SystemExit("Для series_extension_staged требуется --staged-config")
        config = load_staged_config(args.staged_config)
        parameters["stages"] = config["stages"]
        parameters["exclude_negative"] = config.get("exclude_negative", True)
        # Статус доказательности из манифеста источника: без него потребитель не
        # отличит частично подтверждённый ряд от проверенного.
        metadata = config.get("metadata")
        if isinstance(metadata, dict):
            status = metadata.get("evidence_status")
            if isinstance(status, str) and status.strip():
                parameters["evidence_status"] = status.strip()

    if args.method == "series_extension":
        if args.analog_file:
            analog = load_dataset(args.analog_file, args.analog_post)
            parameters["analog_df"] = dict(analog.data)
        elif args.demo:
            parameters["analog_df"] = dict(dataset.data)
        if args.extension_method is not None:
            parameters["method"] = args.extension_method

    if args.method == "flood_hydrograph":
        flood_values = {
            "Q_peak": args.q_peak,
            "T_peak": args.t_peak,
            "T_base": args.t_base,
            "shape": args.flood_shape,
            "dt": args.flood_dt,
            "asymmetry": args.flood_asymmetry,
        }
        parameters.update({key: value for key, value in flood_values.items() if value is not None})
        if args.flood_method is not None:
            parameters["method"] = args.flood_method

    if args.method == "backwater":
        backwater_values = {
            "Q": args.q,
            "B": args.channel_width,
            "m": args.channel_side_slope,
            "n": args.manning_n,
            "I": args.channel_slope,
            "H_reservoir": args.reservoir_head,
            "L_max": args.backwater_length,
            "dx": args.backwater_dx,
        }
        parameters.update({key: value for key, value in backwater_values.items() if value is not None})

    return parameters


def main() -> int:
    parser = argparse.ArgumentParser(description="Прогон методики через сервисный слой HydroSphere")
    parser.add_argument("--method", help="id методики (см. --list)")
    parser.add_argument("--file", help="файл данных (.xlsx/.xls)")
    parser.add_argument("--post", help="имя поста в файле (опционально)")
    parser.add_argument("--demand", type=float, default=None, help="demand_m3_s для reservoir_regulation")
    parser.add_argument("--analog-file", help="файл ряда-аналога для series_extension")
    parser.add_argument("--analog-post", help="имя поста-аналога")
    parser.add_argument("--extension-method", choices=["regression", "proportional"], help="метод series_extension")
    parser.add_argument("--staged-config", help="JSON-конфигурация этапов для series_extension_staged")
    parser.add_argument("--q-peak", type=float, help="пиковый расход flood_hydrograph")
    parser.add_argument("--t-peak", type=float, help="время нарастания flood_hydrograph, ч")
    parser.add_argument("--t-base", type=float, help="длительность паводка flood_hydrograph, ч")
    parser.add_argument("--flood-method", choices=["gamma", "triangle"], help="форма flood_hydrograph")
    parser.add_argument("--flood-shape", type=float, help="параметр формы гамма-гидрографа")
    parser.add_argument("--flood-dt", type=float, help="шаг времени flood_hydrograph, ч")
    parser.add_argument("--flood-asymmetry", type=float, help="асимметрия треугольного гидрографа")
    parser.add_argument("--q", type=float, help="расход backwater, м3/с")
    parser.add_argument("--channel-width", type=float, help="ширина дна backwater, м")
    parser.add_argument("--channel-side-slope", type=float, help="откос бортов backwater")
    parser.add_argument("--manning-n", type=float, help="коэффициент Маннинга backwater")
    parser.add_argument("--channel-slope", type=float, help="уклон русла backwater")
    parser.add_argument("--reservoir-head", type=float, help="уровень водохранилища backwater, м")
    parser.add_argument("--backwater-length", type=float, help="максимальная длина расчёта backwater, м")
    parser.add_argument("--backwater-dx", type=float, help="шаг длины backwater, м")
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
    parameters = _build_parameters(args, dataset)
    return run_methodology(container, args.method, dataset, parameters)


if __name__ == "__main__":
    raise SystemExit(main())
