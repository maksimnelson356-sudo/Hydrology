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
)


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


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Импорт наблюдений для СП 33-101-2003, приложение А.8"
    )
    parser.add_argument("--input", required=True, help="CSV/Excel с колонками series_id, year, value, unit")
    parser.add_argument("--manifest", required=True, help="JSON manifest A.8")
    parser.add_argument("--output-config", required=True, help="JSON staged-конфигурация")
    parser.add_argument("--output-primary", required=True, help="JSON основного ряда")
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


def main(argv: list[str] | None = None) -> int:
    """Run the importer command."""
    args = build_parser().parse_args(argv)
    try:
        input_path = Path(args.input)
        manifest_path = Path(args.manifest)
        manifest = load_manifest(manifest_path)
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
