# Состояние работы

## Текущий этап: P0–P2.5 и P3.1–P3.3 выполнены и запушены; P3.4 реализован локально; P3.5 не начат

### Выполненные этапы ROADMAP

| Этап | Статус | Тесты |
|------|--------|-------|
| 0–7 (P0) | готово | 117 → в `tests/`, 135 root |
| P1.1 импорт CSV/TSV/Excel | **готово, запушен** (`9cf38b0`) | `test_import_service` (15) |
| P1.3 QualityPipeline | **готово, запушен** (`ed68de5`) | `test_quality_pipeline` (10) |
| P1.2 импорт через API | **готово, запушен** (`5383206`) | `test_api_source` (18) |
| P1.4 расширенная статистика N=10 | **готово, запушен** (`9247389`) | `test_extended_methodologies` (24) |
| P1.5 калибровка MSE/NSE | **готово, запушен** (`b022ef7`+`f815305`) | `test_calibration_service` (18) |
| P1.7 Reservoir Scenario Simulator | **готово, запушен** (`6860165`, 6 atomic commits `3f01684`..`6860165`) | `test_reservoir_scenario` (15) |
| P1.6 GIS/DEM морфометрия (9.3=(б)) | **готово, запушен** (`58f63b8` feat + `424f238` docs) | `test_geo_service` (18) |
| ROADMAP §6.2 P2.1–P2.5 | **готово, запушен** (`f9e48c2` docs) | — |
| P2.1 Monte Carlo (10.1/10.2) | **готово, запушен** (`6ae65a0` feat + `a5c0096` docs) | `test_monte_carlo` (20) |
| P2.2 чувствительность (tornado) | **готово, запушен** (`55bde3a` feat + `bdb9d81` docs) | `test_sensitivity_service` (18) |
| ROADMAP §6.3 P3.1–P3.5 | **расписано** (`c6506e3` docs) | — |
| P2.3 климат (delta-change) | **готово, запушен** (`2c44287` feat + `8b4bf4a` docs) | `test_climate_service` (17) |
| P2.4 визуализация (fan/hist/tornado) | **готово, запушен** (`2c44287` + `8b4bf4a`) | helpers + GUI |
| P2.5 Decision Support (10.3=а) | **готово, запушен** (`2c44287` + `8b4bf4a`) | `test_decision_support_service` (23) |
| **P3.1 многопролётная ГВП** | **готово, запушен** (`bf2feb4` feat + `5c93459` docs) | `test_backwater_profile_service` (13) |
| **P3.2 Muskingum-маршрутизация (11.1=а)** | **готово, запушен** (`d108ef7`/`ce33f55`/`5dc3f9f` feat + `96e08b9`/`953fd60` docs) | `test_routing_service` (22) |
| **P3.3 Затопление H→S,V (11.2=а)** | **готово, запушен** (`98a8664`/`5b55f17`/`f2c1458` feat + `27ddf36`/`a3a0940` docs) | `test_inundation_service` (19) |
| **P3.4 MC × гидравлика** | **готово локально, ожидает commit/push** (`hydraulic_uncertainty@1.0`) | `test_hydraulic_uncertainty_service` (11) |
| мёрдж в main | **выполнен** (решение 8.2) | — |

Итого: **378 passed** (`tests/`), корневые **135 passed** (полный набор **513 passed**), новые P3.4-файлы ruff/LSP чистые (build.py содержит существующие baseline N806/F841), nav **25/25/25**; native P3.4 initial/backwater/routing/clear-state/launch captures и QThread worker smoke проверены.

### P1.6 — что сделано (решение 9.3 = (б) GeoJSON)

1. **решение 9.3** — зафиксировано в обоих ROADMAP: только GeoJSON-контуры, stdlib + `core.stats.geometry`, без rasterio/QtGIS; DEM-растры — вне P1.6.
2. **`core/stats/geometry.py`** — planar shoelace + spherical lonlat area, haversine perimeter, vertex-average centroid; pure `math`.
3. **`core/services/geo_service.py`** — Feature/FC/Polygon|MultiPolygon → `BasinMorphometry` + `to_metadata()`; `GeoServiceError` на ошибки формата.
4. **GUI** — вкладка «Морфометрия» (`tab_geo.py`): диалог GeoJSON, сводка, таблица metadata, matplotlib-превью; меню «Загрузить контур…»; nav 24.
5. **tests** — 18: analytical area/perimeter/centroid, spherical sanity, happy paths, errors, AST no-banned-deps guard.
6. **build.py** — hidden imports geo_service / geometry / tab_geo; i18n `menu_load_contour`, `sidebar_geo`.

### Верификация DoD P1.6 (2026-09-23)

- `pytest tests -q` → **235**; root → **135**; nav **24/24/24**; GUI smoke OK (`pages=24`, `has_open_geo=True`, `menu_has_contour=True`).
- ruff тронутые = 0; build/main_window delta=0.
- Квадрат 1 км² — площадь точно 1e6 м² (rel 1e-9); без новых runtime-зависимостей.

### P2.1 — что сделано (решения 10.1, 10.2)

1. **ROADMAP §6.2** — этапы P2.1–P2.5 расписаны (коммит docs `f9e48c2`); открытые решения 10.1–10.3.
2. **`core/services/monte_carlo_service.py`** — `ParameterSpec` / `MonteCarloRequest` / `MonteCarloService.run/sample_parameters/summarize` / `SummaryStats`; seedable `np.random.default_rng`; распределения uniform/normal/triangular (10.1a); N default 1000 (10.2a); `CalculationResult` + provenance.
3. **`tests/test_monte_carlo.py`** — 20: детерминизм, p50/p5/p95 аналитика, границы, ошибки, provenance, AST no-banned-deps.
4. **GUI `tab_monte_carlo.py`** — таблица параметров, N/seed, демо-модель y=a·x+b, `MonteCarloWorker` QThread, сводка + гистограмма с квантилями; меню «Запуск Monte Carlo…»; nav 25.
5. **build.py / i18n** — hidden imports `monte_carlo_service`, `tab_monte_carlo`; ключи `menu_run_monte_carlo`, `sidebar_monte_carlo`.

### Верификация DoD P2.1 (2026-09-23)

- `pytest tests -q` → **255**; root → **135**; nav **25/25/25**; GUI smoke OK (`pages=25`, `has_monte_carlo=True`, `menu_has_mc=True`).
- ruff тронутые = 0; build/main_window delta=0.
- Детерминизм seed=42 бит-в-бит; p50 нормали ≈ μ; без новых runtime-зависимостей.

### P2.2 — что сделано (tornado sensitivity)

1. **`core/services/sensitivity_service.py`** — OAT `analyze`/`run`: baseline ± Δ (абсолютный из `deltas` или `relative_delta × |baseline|`, нулевой baseline → scale 1.0), swing = |f(high) − f(low)|, ранг по убыванию swing с tie-break по имени; provenance `sensitivity_oat@1.0`; stdlib + `core.domain` only.
2. **`tests/test_sensitivity_service.py`** — 18: acceptance rank `[x1, x2]` на `y = 3·x1 + 1·x2`, swing = 2·coef·delta, монотонная `x³`, tie-break, relative delta, ошибки, provenance, AST-guard.
3. **GUI `tab_monte_carlo.py`** — блок «Чувствительность — Tornado»: спинбокс ±Δ, кнопка, `build_sensitivity_request()` (baseline = центр колонки распределения), horizontal bar matplotlib, метка порядка.
4. **`core/services/__init__.py` / `build.py`** — экспорт `Sensitivity*` + hidden import `core.services.sensitivity_service`.

### Верификация DoD P2.2 (2026-09-23)

- `pytest tests -q` → **273** (+18); root → **135**; nav **25/25/25**; GUI smoke OK; tornado UI → `TORNADO_UI_OK` (order `a, b, c`).
- ruff тронутые = 0; build/main_window delta=0.
- Критерий ROADMAP: `y = a·x1 + b·x2`, a > b → ранг `[x1, x2]` — закрыт pytest.
- Без новых runtime-зависимостей; математика в сервисе, GUI только рисует.

### P2.3–P2.5 — что сделано (решение 10.3 = (а))

1. **`climate_service.py`** — multiplicative/additive delta-change, clone Dataset без мутации, metadata `climate` для `.hsp`; 17 тестов (identity, ×1.1, empty, NaN, round-trip).
2. **P2.4 `gui/plot_style.py`** — `draw_fan_chart`, `draw_histogram_quantiles`, `draw_tornado_hbars`; histogram/tornado в `tab_monte_carlo` переключены на хелперы; fan — для климатического до/после.
3. **`decision_support_service.py`** — P(exceed) от **пользовательского** Q_крит (10.3а), класс риска low/med/high (0.05/0.20), recommendation; 23 теста с аналитической выборкой; provenance `decision_support@1.0`.
4. **GUI `tab_monte_carlo`** — блоки «Климат» (δ, режим, mean до/после + fan) и «Решения» (Q_крит, P(exceed), класс).
5. **Отчёт** — 13 секций не тронуты (опциональная секция DS не добавлялась, чтобы не ломать `section_count == 13`).

### Верификация DoD P2.3–P2.5 (2026-09-23)

- `pytest tests -q` → **313** (+17+23); root → **135**; `test_report_service` → **15** (13 секций); nav **25/25/25**; smoke OK; `P2345_UI_OK`.
- ruff тронутые = 0; build/main_window delta=0; plot_style N802/N814 — baseline.
- Без новых runtime-зависимостей; решение **10.3 (а)** закрыто.

### P3.1 — что сделано (многопролётная ГВП)

1. **`core/hydraulics_profile.py`** — `Reach` (validate: B/n/slope/L > 0, m ≥ 0, имя) + `route_backwater_profile`: цепочка `backwater_curve_step` от понижающего конца, control = exit depth предыдущего reach; глобальные series без дубля стыка; per-reach block (normal_depth, junction_depth); core `backwater.py` **не изменялся** (только вызов).
2. **`core/services/backwater_profile_service.py`** — `ReachSpec` / `BackwaterProfileRequest` / `BackwaterProfileResult` / `BackwaterProfileService` / `BackwaterProfileError`; provenance `backwater_profile@1.0`; JSON-safe `to_dict()`; без математики.
3. **`tests/test_backwater_profile_service.py`** — 13: 1 пролёт бит-в-бит ≡ core, provenance, стыковка, 3 reach, 7 типов ошибок, AST no-banned-deps.
4. **GUI `widget_work9.py`** — таблица пролётов (добавить/удалить) + кнопка многопролётной ГВП в **существующей** вкладке «Кривые подпора» (nav = 25); текст + WSE-график со стыками.
5. **exports** — `core/services/__init__.py`, `build.py` hidden-imports `core.hydraulics_profile` + `backwater_profile_service`.

### Верификация DoD P3.1 (2026-09-23)

- `pytest tests -q` → **326** (+13); root → **135**; nav **25/25/25**; GUI smoke OK (`pages=25`).
- ruff: новые = 0; build 7/7, main_window 36/36 delta=0; widget_work9 — без новых (бейзлайн N806/N802 сохранён).
- 1 пролёт: числа бит-в-бит == `backwater_curve_step`; без новых runtime-зависимостей; решение 11.x не закрывалось (11.2/11.3 — P3.3/P3.5).

### P3.2 — что сделано (решение 11.1 = (а) Muskingum)

1. **`core/hydrorash/routing.py`** — `MuskingumError`, C0/C1/C2, проверки dt/K/x и коэффициентов, входного ряда и O0; выход `outflow`, пики входа/выхода, аттенюация и lag.
2. **`core/services/routing_service.py`** — `RoutingRequest` / `RoutingResult` / `RoutingService` / `RoutingError`, JSON-safe `to_dict()`, provenance `muskingum@1.0`; математика только в core.
3. **`tests/test_routing_service.py`** — 22: коэффициенты, constant→steady, объём ±1%, метрики, validation, provenance, AST, public export/build hidden-imports; GUI-контракты `dt` и очистки stale plot.
4. **GUI `widget_work7.py`** — Muskingum в существующей вкладке гидрографов: K/x/dt, вход→выход на одном временном шаге, коэффициенты/пики/ослабление/lag/provenance; nav = 25.
5. **exports/build** — `core.services` публикует `Routing*`; PyInstaller hidden imports включают routing core/service.

### Верификация DoD P3.2 (2026-09-24)

- `pytest tests -q` → **348** (+22); root → **135**; nav **25/25/25**, Work7 index 19; GUI smoke OK.
- Targeted routing → **22 passed**; новые routing-файлы ruff = 0; Work7/build.py — только существующие baseline; LSP clean.
- Volume ±1%; constant→steady; C0/C1/C2∈[0,1]; native valid/error states при 1200×700 и 1600×900; без новых runtime-зависимостей.
- Решение **11.1=(а) закрыто**; 11.2/11.3 остаются P3.3/P3.5. Два независимых visual-review не запустились из-за provider-model конфигурации; локальная native-screen проверка и regression-тесты зелёные.
- Push: feature/docs tip `953fd60` отправлен в `origin/global-implementation` и `origin/main`; divergence **0/0**.

### P3.3 — что сделано (решение 11.2 = (а) S(H))

1. **`core/hydrorash/inundation.py`** — `StageAreaPoint` / `InundationEstimate`; строгая монотонная S(H), линейная интерполяция, trapezoidal volume, clamp+warning выше максимума, аналитический trapezoid.
2. **`core/services/inundation_service.py`** — `StageAreaSource` / `TrapezoidSource` / `GeoJsonSource`, request/result/service, GeoJSON через существующий `GeoService`, provenance `inundation@1.0`, JSON-safe `to_dict()`.
3. **`tests/test_inundation_service.py`** — 19: интерполяция/интеграл, монотонность, clamp, analytic trapezoid, GeoJSON elevation, ошибки, JSON, exports/build и GUI.
4. **GUI `gui/tabs/tab_inundation.py` + Work9** — внутренняя вкладка «Затопление H → S,V», три источника, редактируемая S(H), график/result, dynamic m²/km², очистка stale output; nav = 25.
5. **exports/build** — `Inundation*` в `core.services`; hidden imports core/service/GUI.

### Верификация DoD P3.3 (2026-09-24)

- `pytest tests -q` → **367** (+19); root → **135**; nav **25/25/25**; Work9 tabs = 4; GUI smoke OK.
- Targeted P3.3 → **19 passed**; новые файлы ruff/no-excuse/LSP чистые; Work9/build.py baseline без новых ошибок.
- Native Windows: `S(H)` 1200×700/1600×900, trapezoid, пустой GeoJSON и empty-table error; small-area plot использует м² без `1e-5`; смена источника очищает старый output.
- Без новых runtime-зависимостей и DEM; решение **11.2=(а) закрыто**, GeoJSON — второй источник; 11.3 остаётся P3.5.
- Push: feature/docs tip `a3a0940` отправлен в `origin/global-implementation` и `origin/main`; divergence **0/0**.

### P3.4 — что сделано (MC × гидравлика)

1. **`core/services/hydraulic_uncertainty_service.py`** — `HydraulicUncertaintyService` использует
   `MonteCarloService.sample_parameters()` и прогоняет каждый draw через P3.1/P3.3 или P3.2;
   allowed parameters, typed errors, JSON-safe result и `hydraulic_uncertainty@1.0`.
2. **Backwater output** — `max_depth_m`, `flooded_area_m2`, `flooded_volume_m3`; **routing output** —
   `peak_in_m3s`, `peak_out_m3s`, `peak_attenuation_m3s`, `peak_lag_steps`; p5/p50/p95/mean/std.
3. **`gui/tabs/hydraulic_uncertainty_panel.py`** — engine, N, seed, uniform parameter table,
   quantile table/chart; request parsing, result rendering и `QThread` worker вынесены в
   `hydraulic_uncertainty_support.py`, `hydraulic_uncertainty_result_view.py` и
   `gui/workers/hydraulic_uncertainty_worker.py`; stale output очищается при смене engine.
4. **`gui/tabs/tab_monte_carlo.py`** — launch button без новой navigation page; сигналы панели
   перенаправляются в существующий tab status/error.
5. **`core/services/__init__.py` / `build.py`** — public exports и hidden imports.

### Верификация DoD P3.4 (2026-09-24)

- `python -m pytest tests -q` → **378 passed**; полный `python -m pytest -q` → **513 passed**;
  корневые regression-тесты → **135 passed**; targeted P3.4 → **11 passed**.
- P3.4 service/panel/export/test modules: Ruff, no-excuse и LSP чистые; `tab_monte_carlo.py`
  сохраняет pre-existing oversized-module/broad-except baseline; `build.py` сообщает только
  существующие baseline N806/F841; новых runtime-зависимостей нет.
- Native offscreen captures: initial, backwater result, routing result, engine-change clear,
  Monte Carlo launch; QThread worker smoke прошёл. Offscreen QPA не содержит кириллических шрифтов,
  поэтому capture показывает square placeholders только вместо русских glyphs.
- P3.4 пока не коммитится и не пушится; P3.5 остаётся следующим этапом.

### P1.7 — что сделано

1. **domain** — `Scenario.scenario_type` (`generic`/`reservoir`), сериализация в `.hsp`.
2. **`ReservoirScenarioService`** — create/run/compare_delta/series_for поверх ScenarioService; валидация параметров; только вызовы `multi_year_regulation` / handler.
3. **handlers** — `storage_yield` (descriptor + handler); реестр 20 id.
4. **`ScenarioService.compare_numeric_results`** — Δ-таблица scalar-метрик vs baseline.
5. **GUI** — блок водохранилища + баланс-график + Δ-таблица в `tab_scenarios`.
6. **tests** — 15: валидация, equivalence core, distinguishable+Δ, series, .hsp roundtrip.

### Верификация DoD P1.7 (2026-09-23)

- `pytest tests -q` → **217**; root → **135**; nav 23/23/23; GUI smoke OK.
- ruff тронутые = 0; build/main_window delta=0.
- Push P1.7 feat: `3f01684`..`6860165`; docs: `54a7257`, `0d00003`.
- `origin/main` и `origin/global-implementation` **синхронизированы** (0/0 divergence); рабочая ветка — `global-implementation`.

### Мёрдж в main (решение 8.2, 2026-09-23)

- `main` был предком `global-implementation` → **fast-forward** `d3967c7` → `54a7257` → tip (без конфликтов); затем docs `0d00003` продлён в обе ветки.
- Тесты на main после merge: 217 / 135 / nav / GUI smoke — зелёные.
- `git push origin main` — выполнен; **origin/main == origin/global-implementation** (проверено `rev-list --left-right` = 0 0).

### Остатки (не блокируют; P0+P1.1–P1.5+P1.7 + мёрдж готовы)

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

### Остатки (не блокируют; P0+P1.1–P1.7 + P1.6 + P2.1–P2.5 + мёрдж закрыты)

- 2 предсуществующих `except Exception` в `main_window` — по мере рефакторинга.
- Ручной GUI / приёмка — за пользователем.
- **§6.2 P2, P3.1–P3.4 закрыты; P3.4 пока локально, без commit/push.** Дальше — **P3.5** (решения 11.1=(а)/11.2=(а) закрыты; 11.3 — P3.5).

### Примечания

- GSD-команды и фоновые субагенты недоступны (ProviderModelNotFoundError) — работаем напрямую.
- `core/stats/*` N803/N806 — предсуществующая нотация, не трогать.
- `i18n/__init__.py` — предсуществующие ruff, файл не трогали.
- i18n для reservoir GUI не добавлялся: `tab_scenarios` historically uses hardcoded ru strings (как весь файл); меню/калибровка/контур/Monte Carlo — через i18n.
- P1.6: DEM-растры (rasterio) — осознанно вне объёма (решение 9.3 = (б)); при необходимости — reopen 9.3 позже.
- P2.1: demo model y=a·x+b — для smoke/знакомства; подключение к калиброванным моделям/P2.2 — позже.

Обновлено: 2026-09-24 (P3.4 реализован локально: `hydraulic_uncertainty@1.0`, QThread panel, 378+135=513 tests, native offscreen QA; P3.3 остаётся запушенным, P3.4 ожидает отдельного commit/push; решение 11.2=(а) закрыто)
