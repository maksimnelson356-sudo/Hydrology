# Состояние работы

## Текущий этап: P0 закрыт; P1.1 + P1.3 + P1.2 закоммичены и запушены; открыт P1.4+

### Выполненные этапы ROADMAP

| Этап | Статус | Тесты |
|------|--------|-------|
| 0–7 (P0) | готово | 117 → 160 в `tests/`, 135 root |
| P1.1 импорт CSV/TSV/Excel | **готово, запушен** (`9cf38b0`) | `test_import_service` (15) |
| P1.3 QualityPipeline | **готово, запушен** (`ed68de5`) | `test_quality_pipeline` (10) |
| P1.2 импорт через API | **готово, запушен** (`5383206`) | `test_api_source` (18) |
| P1.4+ (калибровка, GIS, …) | открыто | — |

Итого: **160 passed** (`tests/`), корневые `test_*.py` → **135 passed**, ruff по тронутым файлам чист (новые = 0; `main_window.py` 36/36 delta=0, `build.py` 7/7 delta=0), nav 23/23/23, GUI offscreen smoke OK (23 pages, menu API есть).

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

### Верификация DoD P1.3+P1.2 (2026-09-23)

- `python -m pytest tests -q` → **160 passed**.
- Корневые `test_*` → **135 passed** (`test_edge_cases`/`test_q` — no tests ran, `test_real_data` — warnings only, как раньше).
- ruff: новые файлы чисты; `main_window.py` 36/36 delta=0; `build.py` 7/7 delta=0.
- nav: 23/23/23; offscreen `GUI_SMOKE_OK` (23 pages) + `API_MENU_OK`.
- Push: `9cf38b0..5383206` → `origin/global-implementation` (P1.1 `9cf38b0` уже был; P1.3 `ed68de5`, P1.2 `5383206` запушены).

### Остатки (не блокируют; P0+P1.1–1.3 закрыты)

- 2 предсуществующих `except Exception` в `main_window` — по мере рефакторинга.
- Ручной GUI / приёмка P1 — за пользователем.
- Следующий этап по порядку: **P1.4** (калибровка/оптимизация) — по команде.
- `main` локально `d3967c7` [origin/main: ahead 2] — мёрдж `global-implementation` → `main` (решение 8.2) ждёт команды.

### Примечания

- GSD-команды и фоновые субагенты недоступны (ProviderModelNotFoundError) — работаем напрямую.
- `core/stats/*` N803/N806 — предсуществующая нотация, не трогать.
- `i18n/__init__.py` — предсуществующие ruff, файл не трогали.

Обновлено: 2026-09-23
