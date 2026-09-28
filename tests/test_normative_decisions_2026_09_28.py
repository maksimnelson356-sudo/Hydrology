"""The three normative forks resolved 2026-09-28, pinned so they cannot drift.

Each fork below was left open by the earlier audit. Resolving them in prose is
not enough: a later edit could quietly reopen any of them, so the reasoning is
asserted here against the artefacts it was decided from.

Fork 1 - is data_quality a methodology?
    No. The registry holds 24 calculation methodologies; data_quality is not
    among them. DataQualityService produces a DataQualityReport - an assessment
    of the input series - not a hydrological characteristic, and it carries no
    standard or clause. So the published count stays 24, and the scope of the
    list is now stated explicitly instead of being left for the next reader to
    re-raise.

Fork 2 - 2330 (МДС) or 2350 (А.6) for the Кобожа catchment?
    2330. The q conversion is Q*1000/A (core/services/a8_import.py:66), so Q
    and A must come from one edition. All 58 Кобожа rows in the filled CSV
    carry area_km2=2330 next to Q_m3_s from mdc103av23.xls. The RMSE-to-A.8
    argument that the question originally rested on is WITHDRAWN: the analogs
    are synthetic and test_sp33_a8_full_scenario.py forbids comparing restored
    values to table A.8.

Fork 3 - does СП 482 clause 8.2 support series-length validation?
    The clause exists but says something else: "Инженерно-гидрометеорологические
    изыскания при реконструкции зданий и сооружений". The standard contains no
    series-length rule at all - the only "лет" occurrences are "не менее двух
    недель" for field observation. The code already validates series length by
    the СП 33 clause 5.1 relative-error criterion; the false attribution is
    gone, and a guard now blocks it from returning.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.services.methodology_registry import build_default_registry

ROOT = Path(__file__).parents[1]
MATRIX = ROOT / "DOCS" / "normative_verification_matrix.md"
MANIFEST = ROOT / "tests" / "fixtures" / "sp33_a8_manifest_v1.json"
PROVENANCE = ROOT / "DOCS" / "A8_analog_series_filled.provenance.json"
FILLED_CSV = ROOT / "DOCS" / "A8_analog_series_filled.csv"
COMPLIANCE = ROOT / "test_sp_compliance.py"
A8_IMPORT = ROOT / "core" / "services" / "a8_import.py"


# ---------------------------------------------------------------- fork 1
def test_data_quality_is_not_a_registered_methodology() -> None:
    ids = {d.id for d in build_default_registry()}
    assert "data_quality" not in ids
    assert len(ids) == 24, f"в реестре {len(ids)} методик, опубликовано 24"


def test_data_quality_produces_an_assessment_not_a_characteristic() -> None:
    """Grounds fork 1 in what the service actually returns.

    The service does cite СП 33 Приложение А - correctly, because it delegates
    to check_homogeneity_full, which is a normative method. Delegating to a
    standard is not the same as being a registered methodology: the service
    returns a DataQualityReport about the input, not a hydrological
    characteristic, and that distinction is what keeps the count at 24.
    """
    service = (ROOT / "core" / "services" / "data_quality_service.py").read_text(
        encoding="utf-8"
    )
    assert "class DataQualityService" in service
    assert "DataQualityReport" in service
    # It *consumes* the registry when the caller names a methodology, and
    # reports that methodology's min_points and normative_reference. Being a
    # consumer is not being a member: the service contributes no methodology
    # of its own, which is why the published count stays at 24.
    assert "self.registry.get(" in service
    assert "descriptor.normative_reference" in service
    assert "MethodologyDescriptor" not in service, (
        "сервис начал определять собственные методики — тогда перечень должен быть пересмотрен"
    )


def test_published_scope_states_it_covers_calculation_methodologies() -> None:
    text = MATRIX.read_text(encoding="utf-8")
    assert "24" in text
    assert "расчётные методики" in text, (
        "в матрице не сказано, что перечень охватывает только расчётные методики — "
        "именно этим пробелом был вызван вопрос про data_quality"
    )
    assert "не является" in text, "причина исключения data_quality не названа"


# ---------------------------------------------------------------- fork 2
def _kobozha() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return data["area_decision"]["kobozha"]


def test_kobozha_area_question_is_closed() -> None:
    k = _kobozha()
    assert k["status"] == "resolved", f"вопрос по площади Кобожи снова открыт: {k['status']!r}"
    assert k["used_km2"] == k["mds_km2"] == 2330.0
    assert k["sp33_a6_km2"] == 2350.0
    assert k["delta_percent"] == pytest.approx(0.86, abs=0.01)


def test_kobozha_decision_cites_same_edition_not_rmse() -> None:
    k = _kobozha()
    basis = k["basis"]
    assert "одного издания" in basis
    assert "ИЗЪЯТО" in basis, (
        "основание должно явно фиксировать, что RMSE-аргумент изъят; "
        "иначе его легко воскресить"
    )
    assert "withdrawn_argument" in k
    assert "запрещает" in k["withdrawn_argument"]


def test_kobozha_rows_actually_use_the_mds_area() -> None:
    """The decision rests on this; if the CSV changes, the reasoning must be redone."""
    rows = list(csv.DictReader(FILLED_CSV.read_text(encoding="utf-8-sig").splitlines()))
    kob = [r for r in rows if "Кобож" in (r.get("analog_name") or "")]
    assert len(kob) == 58, f"ожидалось 58 строк Кобожи, найдено {len(kob)}"
    areas = {r["area_km2"] for r in kob}
    assert areas == {"2330"}, f"площади Кобожи в CSV разошлись: {areas}"
    # 54 of the 58 carry a measured Q; the remaining 4 are the uncovered years
    # 1989-1992, which is the known shortfall rather than a defect.
    with_q = [r for r in kob if (r.get("Q_m3_s") or "").strip()]
    assert len(with_q) == 54, f"ожидалось 54 строки с Q, найдено {len(with_q)}"
    without_q = sorted(int(r["year"]) for r in kob if not (r.get("Q_m3_s") or "").strip())
    assert without_q == [1989, 1990, 1991, 1992], (
        f"годы без Q должны быть ровно 1989-1992, а не {without_q}"
    )


def test_q_conversion_is_the_reason_area_must_match_its_source() -> None:
    text = A8_IMPORT.read_text(encoding="utf-8")
    assert "numeric * 1000.0 / area_km2" in text, (
        "q = Q*1000/A больше не используется — решение по площади нужно пересмотреть"
    )


def test_provenance_report_agrees_with_manifest() -> None:
    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    k = prov["area_decision"]["Кобожа"]
    assert k["status"] == "resolved"
    assert k["used_km2"] == _kobozha()["used_km2"]


# ---------------------------------------------------------------- fork 3
def test_sp482_clause_8_2_is_not_cited_for_series_length() -> None:
    text = COMPLIANCE.read_text(encoding="utf-8")
    live = [
        line
        for line in text.splitlines()
        if "482" in line and "8.2" in line and "не" not in line.lower()
    ]
    assert live == [], f"живая ссылка на СП 482 п. 8.2 как на основание — запрещена: {live}"


def test_series_length_validation_uses_sp33_not_sp482() -> None:
    params = (ROOT / "core" / "stats" / "parameters.py").read_text(encoding="utf-8")
    body = params[params.index("def validate_series_length"):]
    body = body[: body.index("\ndef ")]
    assert "СП 33-101-2003 п. 5.1" in body
    assert "482" not in body, "в validate_series_length просочилась ссылка на СП 482"


def test_compliance_script_no_longer_claims_blanket_compliance() -> None:
    text = COMPLIANCE.read_text(encoding="utf-8")
    assert "Проект соответствует требованиям строительных норм и правил." not in text, (
        "безусловное заявление о соответствии возвращено, хотя подтверждено 6 из 24 методик"
    )
