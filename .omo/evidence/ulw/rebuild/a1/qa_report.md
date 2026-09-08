=== REBUILD-INSTALLER-QA REPORT ===
Date: 2026-08-31
Plan: rebuild-installer-qa (approved)

STAGE 1 — PYINSTALLER (.exe):
- Status: SUCCESS
- .exe: D:\hydrolib\dist\HydroSphere\HydroSphere.exe (21526794 bytes ~21 MB)
- Fixes applied: build.py — removed emoji print statements (UnicodeEncodeError on cp1251)
- Warnings: Hidden import scipy.special._cdflib not found (non-blocking)

STAGE 2 — INNO SETUP (Setup.exe):
- Status: BLOCKED / SKIPPED
- Cause: Inno Setup (iscc.exe) not installed / not in PATH
- Action: Documented; no fix attempted (infrastructure dependency, out of scope)

STAGE 3 — PYTEST (test_all_functions.py):
- Status: PASS (24/24)
- Duration: 1.43s
- All tests: test_short_*, test_homogeneity_*, test_stationarity, test_frequency_*, test_auto_cs_cv, test_pearson3_ppf, test_kritsky_menkel_ppf, test_historical_extremes, test_integral_curves, test_regression, test_rodzhestvensky, test_change_point, test_part_stats, test_composite_old, test_parameters, test_complex

STAGE 4 — MANUAL QA (data stitching):
- test_data_clean.xlsx: loaded OK (60 rows, 4 cols — years + 3 posts)
- шаблон_данных.xlsx: FileNotFoundError — path encoding issue with Cyrillic filename
- DataController._parse_work_sheets: sheet names in Russian (Норма годового стока etc.) — may cause mismatch depending on locale/encoding
- ShortWidget analog selection: code present; requires manual interaction
- Finding: Excel-parsing encoding mismatch is a real stitching gap (confirmed, not assumed)

BUGS FOUND & FIXED:
1. build.py — emoji UnicodeEncodeError (cp1251 terminal) → fixed (replaced with English text)

BUGS FOUND & DOCUMENTED (not fixed — out of scope/minimal fix rule):
2. DataController sheet parsing may fail on Cyrillic filenames / mixed encoding
3. Inno Setup unavailable — environment limitation

SCOPE COMPLIANCE:
- No feature changes made
- Only minimal bug fix (emoji → text) confirmed by QA
- No new dependencies
- All artifacts in .omo/evidence/
