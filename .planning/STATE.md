# Состояние работы

## Текущий этап: P0 закрыт; P1.1 + P1.3 + P1.2 + P1.4 запушены; открыт P1.5+

### Выполненные этапы ROADMAP

| Этап | Статус | Тесты |
|------|--------|-------|
| 0–7 (P0) | готово | 117 → 184 в `tests/`, 135 root |
| P1.1 импорт CSV/TSV/Excel | **готово, запушен** (`9cf38b0`) | `test_import_service` (15) |
| P1.3 QualityPipeline | **готово, запушен** (`ed68de5`) | `test_quality_pipeline` (10) |
| P1.2 импорт через API | **готово, запушен** (`5383206`) | `test_api_source` (18) |
| P1.4 расширенная статистика N=10 | **готово, запушен** (`9247389`) | `test_extended_methodologies` (24) |
| P1.5+ (калибровка, GIS, …) | открыто | — |

Итого: **184 passed** (`tests/`), корневые `test_*.py` → **135 passed**, ruff по тронутым файлам чист (новые = 0; `main_window.py` 36/36 delta=0, `build.py` 7/7 delta=0), nav 23/23/23, GUI offscreen smoke OK (23 pages).

### P1.4 — что сделано (решение 9.4: N=10)

1. **handlers** — 10 тонких адаптеров: spectral_hurst, drought_spi, baseflow, confidence_bands, composite_curves, intra_annual, snowmelt, spillway, ecological_flow, ice_phenomena; только вызовы ядра + `_clean`/`_to_float_dict`.
2. **methodology_registry** — 8 новых descriptor'ов + `required_parameters` для ice_phenomena; нормативы из docstring'ов; composite_curves/ice_phenomena получили handlers (descriptor'ы уже были).
3. **GUI/tools** — реестр общий: `run_methodology --list` → 19 id; вкладка «Методики» подхватывает автоматически через `build_container()`.
4. **tests** — `tests/test_extended_methodologies.py` (24): регистрация, COMPLETED, equivalence == core, missing params, min_points=20 для Хёрста.
5. **ROADMAP** (DOCS + .planning) — N=10 зафиксирован; changelog обновлён.
6. **build.py** — HIDDEN_IMPORTS уже покрывают core.stats.* / core.hydrorash.* / handlers (delta=0).

### Верификация DoD P1.4 (2026-09-23)

- `python -m pytest tests -q` → **184 passed**.
- Корневые `test_*` → **135 passed** (`test_edge_cases`/`test_q` — no tests ran, `test_real_data` — warnings only, как раньше).
- ruff: handlers/registry/tests = 0; `main_window.py` 36/36 delta=0; `build.py` 7/7 delta=0.
- nav: 23/23/23; offscreen `GUI_SMOKE_OK` (23 pages).
- `run_methodology --list` → 19 методик; `--method spectral_hurst|drought_spi|baseflow --demo` → COMPLETED.
- Push: P1.1–P1.3 `9cf38b0..5383206` + STATE `4bfc3fa`; P1.4 `9247389` → `origin/global-implementation` (HEAD = origin = `9247389`).

### P1.3 — что сделано

1. **`core/services/quality_pipeline.py`** — `QualityPipeline.after_import` (только отчёт, не блокирует импорт, не мутирует данные) и `before_calculation` (CRITICAL/ERROR блок до явного `confirmed=True`; WARNING/INFO — предупреждения); reactive `DATA_SPIKE` (ratio max/min, default 8.0); `gate_payload` JSON-safe.
2. **`tests/test_quality_pipeline.py`** — 10 тестов: no-mutate, blocking→confirm, empty always blocked, spike threshold, gate_payload.
3. **`gui/main_window.py`** — `_quality_gate_before_calculation()` перед `calculate_and_plot` (QMessageBox Yes/No); `_on_import_series_ready` через `pipeline.after_import`.
4. **i18n** `quality_gate_*`; **build.py** hidden import `core.services.quality_pipeline`; **bootstrap** `ServiceContainer.quality_pipeline`.

### P1.2 — что сделано

1. **`core/services/api_source.py`** — `DataSource` protocol; `HttpApiSource` (requests, timeout=10s, retries=2 bounded; 4xx без ретраев; 5xx/timeout/connection — с ретраями; `ApiSourceError` человекочитаемо; `FieldMap`; list / nested series / parallel arrays; provenance в `Dataset.metadata`: `source`, `source_url`, `post_id`, `fetched_at`, `timeout_s`, `retries`, `field_map`).
2. **`tests/test_api_source.py`** — 18 мок-тестов: success+provenance, nested/parallel, timeout/conn/4xx/5xx, field-map, dups/year-range, roundtrip `.hsp` + quality, offline не ломает file import.
3. **`gui/dialogs/api_import_dialog.py`** — URL+пост → worker → `dataset_ready` (тот же path, что CSV: проект + QualityPipeline).
4. **меню** «Импорт из источника (API)…» → `import_from_api`; **i18n** `api_*`/`menu_import_api`; **build.py** `core.services.api_source`, `gui.dialogs.api_import_dialog`; экспорт из `core.services`.
5. **Новых runtime-зависимостей нет** (решение 9.2: только уже имеющийся `requests`); решение 9.1 закрыто адаптером + mock/fixture (открытые гидро-API — по желанию пользователя позже).

### Остатки (не блокируют; P0+P1.1–P1.4 закрыты)

- 2 предсуществующих `except Exception` в `main_window` — по мере рефакторинга.
- Ручной GUI / приёмка P1 — за пользователем.
- Следующий этап по порядку ROADMAP: **P1.5** (калибровка) — по команде; альтернатива P1.7 (порядок уточняется).
- `main` локально `d3967c7` [origin/main: ahead 2] — мёрдж `global-implementation` → `main` (решение 8.2) ждёт команды.

### Примечания

- GSD-команды и фоновые субагенты недоступны (ProviderModelNotFoundError) — работаем напрямую.
- `core/stats/*` N803/N806 — предсуществующая нотация, не трогать.
- `i18n/__init__.py` — предсуществующие ruff, файл не трогали.

Обновлено: 2026-09-23 (P1.4 запушен `9247389`)
