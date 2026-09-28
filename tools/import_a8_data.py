"""Convert normalized A.8 observations into service-ready JSON artifacts.

Input is a long-form CSV/Excel table with columns ``series_id``, ``year``,
``value`` and ``unit``. ``series_id`` is ``seja_d_stan`` or ``q1``…``q7``;
units may be q (л/с·км²) or Q (м³/с). The importer converts everything to q
using the manifest catchment areas and never fills missing years with zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd  # noqa: F401  # noqa: PANDAS_OK

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.services.a8_import import (  # noqa: E402
    A8ImportError,
    build_import_artifacts,
    load_manifest,
    required_analog_coverage,
)
from core.services.a8_import_manifest import A8Manifest  # noqa: E402

TEMPLATE_COLUMNS = ("series_id", "year", "value", "unit", "analog_name", "fill")
DEFAULT_PUBLISHED_SERIES = (
    PROJECT_ROOT / "tests" / "fixtures" / "sp33_a8_published_series_v1.json"
)
Q_UNIT = "л/с·км²"


def read_observations(path: Path) -> pd.DataFrame:
    """Read long-form observations from CSV or Excel."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise A8ImportError("input", "поддерживаются только .csv, .xlsx и .xls")


def write_json(path: Path, payload: dict) -> None:
    """Write one UTF-8 JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def file_sha256(path: Path) -> str:
    """Return a stable SHA-256 digest for an input artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_provenance(
    input_path: Path,
    manifest_path: Path,
    strict: bool,
) -> dict[str, str | bool]:
    """Build deterministic file-level provenance for generated artifacts."""
    return {
        "input_file": str(input_path),
        "input_sha256": file_sha256(input_path),
        "manifest_file": str(manifest_path),
        "manifest_sha256": file_sha256(manifest_path),
        "importer": "tools/import_a8_data.py",
        "strict": strict,
    }


def load_published_subject(path: Path) -> dict[int, float]:
    """Load the published observed subject values from the A.8 target series.

    The subject series is published in table A.8, so it must not be requested
    from the user. Only analogs are left blank in the emitted template.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    subject = payload.get("subject")
    if not isinstance(subject, str):
        raise A8ImportError("published_series", "отсутствует поле subject")
    values: dict[int, float] = {}
    for record in payload.get("records", []):
        if record.get("status") != "observed":
            continue
        value = record.get("q_published_l_s_km2")
        if value is None:
            continue
        values[int(record["year"])] = float(value)
    if not values:
        raise A8ImportError("published_series", "не найдено наблюдённых значений")
    return values


def build_template_rows(
    manifest: A8Manifest,
    subject: dict[int, float],
) -> list[dict[str, object]]:
    """Build the blank analog template implied by the manifest equations."""
    rows: list[dict[str, object]] = []
    for year in sorted(subject):
        rows.append(
            {
                "series_id": manifest.subject_id,
                "year": year,
                "value": subject[year],
                "unit": Q_UNIT,
                "analog_name": manifest.subject_name,
                "fill": "из А.8, заполнено",
            }
        )
    for number, years in required_analog_coverage(manifest).items():
        for year in years:
            rows.append(
                {
                    "series_id": f"q{number}",
                    "year": year,
                    "value": "",
                    "unit": Q_UNIT,
                    "analog_name": manifest.analog_names.get(number, ""),
                    "fill": "ВПИШИТЕ q",
                }
            )
    return rows


def write_template(path: Path, rows: list[dict[str, object]]) -> None:
    """Write the template as CSV (utf-8-sig) or XLSX."""
    frame = pd.DataFrame(rows, columns=list(TEMPLATE_COLUMNS))
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        frame.to_excel(path, index=False)
        return
    if suffix == ".csv":
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        return
    raise A8ImportError("output_template", "поддерживаются только .csv, .xlsx и .xls")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Импорт наблюдений для СП 33-101-2003, приложение А.8"
    )
    parser.add_argument("--input", help="CSV/Excel с колонками series_id, year, value, unit")
    parser.add_argument("--manifest", required=True, help="JSON manifest A.8")
    parser.add_argument("--output-config", help="JSON staged-конфигурация")
    parser.add_argument("--output-primary", help="JSON основного ряда")
    parser.add_argument(
        "--emit-template",
        action="store_true",
        help="сгенерировать шаблон ввода analog-рядов из manifest; --input не нужен",
    )
    parser.add_argument(
        "--output-template",
        help="куда записать шаблон (.csv/.xlsx); по умолчанию DOCS/A8_analog_series_TEMPLATE.csv",
    )
    parser.add_argument(
        "--published-series",
        help=(
            "JSON с опубликованным рядом А.8 для предзаполнения основного ряда; "
            f"по умолчанию {DEFAULT_PUBLISHED_SERIES.name}"
        ),
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="разрешить неполные ряды; результат помечается strict=false",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="проверить данные и показать provenance, не записывая артефакты",
    )
    return parser


def emit_template(args: argparse.Namespace, manifest: A8Manifest) -> int:
    """Write the blank analog template derived from the manifest."""
    series_path = Path(args.published_series or DEFAULT_PUBLISHED_SERIES)
    subject = load_published_subject(series_path)
    rows = build_template_rows(manifest, subject)
    target = Path(
        args.output_template
        or PROJECT_ROOT / "DOCS" / "A8_analog_series_TEMPLATE.csv"
    )
    write_template(target, rows)
    blank = sum(1 for row in rows if row["value"] == "")
    print(f"Шаблон: {target}")
    print(f"Строк: {len(rows)}; предзаполнено основным рядом: {len(subject)}; ждут ввода: {blank}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the importer command."""
    args = build_parser().parse_args(argv)
    try:
        manifest_path = Path(args.manifest)
        manifest = load_manifest(manifest_path)
        if args.emit_template:
            return emit_template(args, manifest)
        missing = [
            name
            for name, value in (
                ("--input", args.input),
                ("--output-config", args.output_config),
                ("--output-primary", args.output_primary),
            )
            if not value
        ]
        if missing:
            raise A8ImportError("cli", f"требуются аргументы: {', '.join(missing)}")
        input_path = Path(args.input)
        observations = read_observations(input_path)
        strict = not args.allow_missing
        config, primary = build_import_artifacts(
            observations,
            manifest,
            strict=strict,
        )
        provenance = build_provenance(input_path, manifest_path, strict)
        config["metadata"]["provenance"] = provenance
        primary["provenance"] = provenance
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "provenance": provenance,
                        "observation_report": config["metadata"]["observation_report"],
                        "stages": len(config["stages"]),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        write_json(Path(args.output_config), config)
        write_json(Path(args.output_primary), primary)
    except (A8ImportError, OSError, ValueError, ImportError, pd.errors.ParserError) as error:
        print(f"ОШИБКА: {error}", file=sys.stderr)
        return 1

    print(f"Создан staged-конфиг: {args.output_config}")
    print(f"Создан основной ряд: {args.output_primary}")
    print(f"Этапов: {len(config['stages'])}; strict={strict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
