# Состояние работы

## Текущий этап: P0 закрыт и запушен; открыт план P1 (ROADMAP §6.1) — код P1 не начат

### Выполненные этапы ROADMAP (P0)

| Этап | Статус | Тесты |
|------|--------|-------|
| 0 | готово | домен/сервисы |
| 1 | готово | `.hsp` persistence |
| 2 | готово | quality |
| 3 | готово | methodology + calculation |
| 4 | готово | results/provenance |
| 5 | готово | scenarios |
| 6 | готово | report_service (15) |
| 7 | **готово** | saniter/build/docs |

Итого: **117 passed** (`tests/`), все 7 корневых `test_*.py` → **135 passed** (не деградировали), ruff по тронутым файлам чист, `main_window.py` delta=0 к HEAD, nav 23/23/23, AST/импорты OK, GUI offscreen smoke OK (23 pages).

### Этап 7 — что сделано

1. **`gui/tabs/tab_data.py`** — `TabData(QWidget)`: UI «Данные и статистика» вынесен из `main_window.setup_data_tab`; виджеты как атрибуты (`combo_post`, `table`, `btn_*`), действия — сигналами (`load_requested`, `post_changed`, …).
2. **`gui/main_window.py`** — `setup_data_tab` → `_wire_tab_data()`: алиасы виджетов + `connect` сигналов к существующим методам (поведение не меняется).
3. **`gui/tabs/tab_report.py`** — `quality_service.analyze()` перенесён в `ReportBuildWorker._fill_quality_report()` (UI-поток не блокируется); `except Exception` → конкретные типы.
4. **Сборка** — `build.py` `HIDDEN_IMPORTS`: `core.domain*`, `core.services*`, `core.services.handlers*`, `gui.tabs*`; `build_nuitka.py` `--include-package` для `core.domain`, `core.services`, `core.services.handlers`, `gui.tabs`, `i18n`.
5. **Документация** — `INSTRUCTION.md` (23 раздела), `DOCS/changelog.md` (этапы 4–6 + работа этапа 7), `DOCS/ГидроСтатистика_2026_ТехническоеОписание.md` (дерево `core/domain` + `core/services` + `gui/tabs`, навигация 23).
6. **i18n** — ключи `report_*`, `menu_report_engineering`, `sidebar_report` в `ru.json`/`en.json`.
7. **Багфикс `tab_results.py`** — `QSortOrder` (нет в PyQt6) → `Qt.SortOrder`; иначе `MainWindow` не импортировался и падал `test_cr7_*`.
8. **ruff-санитария** — `tab_data_quality.py` (I001/F401/W292), `tab_scenarios.py` (I001/F821 `ServiceContainer` через `TYPE_CHECKING`, F541, F841, W292).
9. **Сборка PyInstaller** — `python build.py pyinstaller` → `dist/HydroSphere/HydroSphere.exe` собран (28.6 МБ), `i18n/` и `gui/resources/` в `_internal`; exe стартует (offscreen, PID живой, без падения), все вкладки включая `tab_data`/`tab_report` в PYZ (нет missing в `warn-HydroSphere.txt`). В `HIDDEN_IMPORTS` добавлен `gui.tabs.tab_data`.
10. **Документация синхронизирована с итогом P0** — `README.md` (таблица этапов 0–7, 117 passed, 23 раздела, сборка), `DOCS/changelog.md` (запись этапов 4–7), журнал ROADMAP v1.5–v1.8, раздел «3. Текущее состояние» (оба ROADMAP: `.planning/` и `DOCS/`), открытые решения 8.1–8.6 переведены в «закрыто» с фактическими ответами.

### Верификация DoD этапа 7 (2026-09-23)

- `python -m pytest tests -q` → **117 passed**.
- Все корневые: `test_all_functions` + `test_edge_cases` + `test_sp_compliance` + `test_regression_critical` + `test_backwater` + `test_q` + `test_real_data` → **135 passed**.
- ruff: тронутые файлы чисты; `main_window.py` и `build.py` без новых замечаний (delta=0 к HEAD).
- nav: names=pages=colors=23; offscreen `GUI_SMOKE_OK` (23 pages).
- AST + `IMPORT_OK` для `TabData`, `ReportTab`, `ScenarioTab`, `TabDataQuality`, `TabResults`, `ReportService`.
- Сборка: `python build.py pyinstaller` → **Build complete**, `dist/HydroSphere/HydroSphere.exe` (28.6 МБ) **запускается** (offscreen smoke, процесс жив); `i18n/ru.json` и `gui/resources` в `_internal`; `gui.tabs.tab_data` входит в сборку (добавлен в `HIDDEN_IMPORTS`).
- `HydroSphere.spec` в репо нет — путь сборки через `build.py`.
- Изменения **не закоммичены** (коммит — только по явной команде).

### Остатки (не блокируют этап; P0 закрыт)

- 2 предсуществующих `except Exception` в `main_window` (~3192, ~3208) — по мере рефакторинга.
- `charts: []` в `tab_report._collect_kwargs` — тайтлы графиков GUI дописать позже.
- Ручной GUI на чистой машине / полная приёмка отчёта — за пользователем.
- `icon.ico` в корне нет — сборка без иконки (есть `gui/resources/logo.png`).
- **Этапы 0–7 ROADMAP выполнены**, закоммичены (13 atomic + `6244444`) и запушены
  в `origin/global-implementation`.
- **Гигиена:** `DOCS/project-viz.html` восстановлен; в `.gitignore` добавлены
  `.opencode/`, `_file_inventory.json`, `generate_file_inventory.py`.
- **P1:** план в `DOCS/ROADMAP.md` §6.1 (P1.1 импорт CSV → P1.7 reservoir simulator);
  открытые решения 9.1–9.5; рекомендуемый порядок P1.1→P1.3→P1.2→P1.4→P1.7→P1.5→P1.6.
- Ожидается: ручная GUI-приёмка P0 (за пользователем) и/или команда стартовать P1.1.

### Примечания

- GSD-команды и фоновые субагенты недоступны (ProviderModelNotFoundError / shell encoding) — работаем напрямую.
- `core/stats/*` N803/N806 — предсуществующая гидрологическая нотация, не трогать.
- `i18n/__init__.py` имеет 3 предсуществующих замечания ruff (UP035/F401/W293) — файл не трогали в P0.

Обновлено: 2026-09-23
