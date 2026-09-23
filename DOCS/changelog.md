# Changelog — HydroSphere

## v2026.09.23 — P0, этапы 4–7: результаты, сценарии, отчёт, санитария GUI/сборки (этапы 0–7 закрыты)

### Добавлено
- **`core/services/result_store.py`** — хранилище результатов расчётов с provenance-цепочкой (`provenance_chain`), регистрация/список/поиск по id; используется вкладкой «Результаты».
- **`gui/tabs/tab_results.py`** — раздел «Результаты»: история расчётов, детали, провенанс (исходные данные → методика → параметры → версия движка), экспорт JSON, контекстное меню.
- **`gui/tabs/tab_scenarios.py`** — раздел «Сценарии»: CRUD сценариев через `ScenarioService`, клонирование, сравнение с базовым (таблица параметров/результатов), статусы.
- **`core/services/report_service.py`** — сборка инженерного отчёта по 13 разделам (исходные данные, качество, нормативная методика, параметры, формулы, расчёт, проверки, графики, таблицы, сценарии, итоги, предупреждения, вывод); `NO_DATA`/`EXCLUDED` для пустых опциональных секций; `render_text` / `save_report` (utf-8-sig, atomic). Штамп версии из `version.VERSION_FULL`; метка `Q_mean → Qср`.
- **`tests/test_report_service.py`** — 15 тестов: 13 секций и порядок, Qср/Cv/Cs, chart_count, пустой отчёт → «нет данных», include-фильтр сохраняет 13 слотов, warnings/conclusion, render/save.
- **`gui/tabs/tab_report.py`** — вкладка «Отчёт»: чекбоксы Сценарии/Графики/Проверки, «Сформировать» в фоне (`ReportBuildWorker` QThread), предпросмотр, «Сохранить как…» в `reports/` рядом с `.hsp`, регистрация через `project_service.register_report`.
- **`gui/tabs/tab_data.py`** — `TabData(QWidget)`: раздел «Данные и статистика» вынесен из `main_window.setup_data_tab` (виджеты-атрибуты, сигналы `load_requested`/`post_changed`/…); поведение не меняется.
- **`i18n/ru.json` + `i18n/en.json`** — ключи `report_*`, `menu_report_engineering`, `sidebar_report`.

### Изменено
- **`gui/main_window.py`** — вкладка «Отчёт» на позиции 6 (навигация 23/23/23); пункт меню «Сформировать инженерный отчёт...» → `_open_report_tab`; импорт `from i18n import t`; `setup_data_tab` → `_wire_tab_data()` (алиасы виджетов + connect сигналов `TabData`).
- **`core/services/__init__.py`** — экспортированы `Report`, `ReportSection`, `ReportService`.
- **`build.py`** — `HIDDEN_IMPORTS` дополнен `core.domain*`, `core.services*`, `core.services.handlers*`, `gui.tabs*` (включая `gui.tabs.tab_data`).
- **`build_nuitka.py`** — `--include-package` для `core.domain`, `core.services`, `core.services.handlers`, `gui.tabs`, `i18n`.
- **`INSTRUCTION.md`** — список разделов обновлён: 23 пункта (Проект → Качество данных → Методики → Результаты → Сценарии → Отчёт → …).
- **`gui/tabs/tab_report.py`** — новые `except Exception` заменены на конкретные типы (`KeyError`/`ValueError`/`TypeError`/`AttributeError`/`OSError` и т.д.); quality `analyze()` перенесён в воркер.
- **`gui/tabs/tab_data_quality.py`, `gui/tabs/tab_scenarios.py`** — ruff-санитария (I001, F401, F821 `ServiceContainer` через `TYPE_CHECKING`, F541, F841, W292).

### Исправлено
- **`gui/tabs/tab_results.py`** — IndentationError (метод вне класса), null-safe конструктор `result_store`/`service_container`, провенанс без `method_type`, warnings из `getattr`; **`QSortOrder` → `Qt.SortOrder`** (импорт из PyQt6 падал, `MainWindow` не собирался, падал `test_cr7_*`).
- **`gui/main_window.py`** — `results.add_result` → `results.register`.

### Проверки (DoD этапа 7)
- `python -m pytest tests -q` → **117 passed**.
- Все корневые `test_*.py` (7 файлов) → **135 passed** — не деградировали.
- ruff: тронутые файлы этапов 4–7 без новых замечаний (`main_window.py`/`build.py` delta=0 к HEAD).
- nav: names=pages=colors=23; offscreen GUI smoke — OK (23 pages).
- **Сборка**: `python build.py pyinstaller` → `dist/HydroSphere/HydroSphere.exe` (28.6 МБ) собран и **запускается**; `i18n/` и `gui/resources/` в `_internal`.
- Ручная генерация отчёта из GUI на реальном проекте — за приёмкой пользователя.

### Известные ограничения
- `charts` в `_collect_kwargs` пока `[]` — можно дописать тайтлы активных графиков GUI.
- 2 предсуществующих `except Exception` в `main_window` (~3192, ~3208) — по мере рефакторинга.
- `icon.ico` в корне нет — сборка без иконки (есть `gui/resources/logo.png`).
- `HydroSphere.spec` в корне отсутствует (сборка идёт через `build.py`).

---

## v2026.09.21 — P0, этап 2: контроль качества данных

### Добавлено
- **`core/services/data_quality_service.py`** — сервис оценки качества данных (Этап 2 дорожной карты): единая точка входа `analyze()` поверх `ValidationService` + `MethodologyRegistry`; собственная математика отсутствует — только организация проверок. Принцип «не изменять данные молча»: сервис лишь оценивает ряд, для каждой проблемы формулирует «что обнаружено → почему важно → что можно сделать». Каталог рекомендаций `RECOMMENDATIONS` по кодам проблем (пропуски → интерполяция/аналог, выбросы → Диксон/Граббс, неоднородность → отчёт/составная кривая и т.д.); сортировка issues по серьёзности; проверка длины ряда по СП 482 п. 8.2 / СП 33-101-2003; применимость методики к ряду (`METHODOLOGY_MIN_POINTS`); сериализация отчёта (`to_json`, `recommendations()`, `register_report()`).
- **`gui/dialogs/data_quality_dialog.py`** — диалог «Качество данных»: сводка (оценка A–F, скор, полнота, однородность, стационарность, выбросы), таблица проблем с «почему важно», панель рекомендаций с кнопками-действиями, экспорт отчёта в JSON. Ничего не считает сам — расчёт в фоне через `DataQualityWorker`.
- **`gui/workers/calculation_workers.py`** — `DataQualityWorker`: фоновый анализ ряда через `DataQualityService` (прогресс, результат/ошибка через сигналы), GUI не блокируется.
- **`tests/test_data_quality_service.py`** — 15 тестов: чистый ряд → grade A без блокирующих issues; пропуски/нули/отрицательные/выбросы → отдельные issue с кодами и рекомендациями; короткий ряд n=5 → `INSUFFICIENT_DATA` (ERROR); `METHODOLOGY_MIN_POINTS` для n<25 против `stats_parameters`; сервис не изменяет датасет; сортировка по серьёзности, дедупликация рекомендаций, `to_json`/`register_report`.

### Изменено
- **`gui/main_window.py`** — кнопка «Качество данных» (панель инструментов + меню): открывает диалог для текущего ряда, результат доступен пользователю явным действием.

### 🐛 Исправлено
- **`core/domain/models.py`** — `ValidationResult.add_issue(details={...})` оборачивал переданный словарь в `{"details": {...}}` (kwargs-коллизия): все детали issue (`missing_years`, `outlier_count`, критерии однородности и т.д.) терялись во всём пайплайне, включая GUI. Сигнатура исправлена: явный параметр `details` + merge с произвольными kwargs.

### 🧪 Проверки
- `python -m pytest tests -q` → 60 passed (28 домен/сервисы + 17 проект + 15 качество данных).

### 📌 Известные ограничения
- Ручной прогон диалога в GUI на реальном ряде остаётся за пользователем (критерии приёмки Этапов 2 и 3); офлайн-логика и эквивалентность результатов покрыты тестами.

---

## v2026.09.21 — P0, этап 3: реестр методик и расчёт через сервис

### Добавлено
- **`core/services/handlers/`** — 9 адаптеров методик P0 (`stats_parameters`, `frequency_pearson3`, `frequency_kritsky_menkel`, `homogeneity_full`, `trends_full`, `max_runoff`, `min_runoff`, `flow_duration`, `reservoir_regulation`): делегируют в существующие функции ядра (`core.stats.*`, `core.hydrorash.*`), не содержат математики и сериализуют результаты в plain-Python dict / схему `{"columns": [...], "rows": [...]}` для хранения в `.hsp`.
- **`core/services/bootstrap.py`** — `build_container()`: единая точка сборки сервисного слоя; регистрирует дескрипторы, хендлеры и валидаторы применимости; возвращает `ServiceContainer` (`registry` + `calculation` + `quality`); есть `registered_methodology_ids()`.
- **`gui/tabs/tab_methodology.py`** — раздел «Методики»: список P0-методик с нормативной базой, требованиями к данным и статусом применимости к текущему ряду; кнопка «Выполнить расчёт» → `CalculationService.execute()`; вывод результата (плоское представление + исходный JSON); запросы параметров при запуске (например, `demand_m3_s` для `reservoir_regulation`).
- **`gui/main_window.py`** — вкладка «Методики» добавлена в навигацию на вторую позицию (теперь 19 разделов вместо 18); `service_container = build_container()`, соединение сигналов, синхронизация ряда из «Данные и статистика» при переключении раздела.
- **`tools/run_methodology.py`** — консольный прогон без GUI: `--list`, `--method`, `--file`, `--demo`, `--demand`.
- **`tests/test_methodology_service.py`** — 19 тестов: регистрация всех P0-методик, `COMPLETED` через сервис, эквивалентность результата сервису и прямому вызову ядра (ноль расхождений), отказ неприменимой методики с нормативной ссылкой, проверка каталога дескрипторов.

### 🧪 Проверки
- `python -m pytest tests -q` → 79 passed (28 домен/сервисы + 17 проект + 15 качество данных + 19 методики).
- `python tools/run_methodology.py --list` → 9 методик.
- `python tools/run_methodology.py --method stats_parameters --demo` → `COMPLETED`, детерминированный ряд.
- `python -m ruff check --quiet` для `gui/tabs/tab_methodology.py`, `core/services/bootstrap.py`, `core/services/handlers/__init__.py`, `tools/run_methodology.py` — без предупреждений по коду Этапа 3.
- Offscreen smoke: `main_window` загружается, вкладка «Методики» на позиции 2, в списке 9 записей.

---

## v2026.09.21 — P0, этап 1: проект и персистентность .hsp

### Добавлено
- **`core/domain/serialization.py`** — конвертеры `to_dict`/`from_dict` для всех сущностей домена (Project, Dataset, Methodology, CalculationMetadata, CalculationResult, Scenario, ValidationIssue/Result, DataQualityReport); tolerant-разбор.
- **`core/services/project_service.py`** — сервис проекта: create/open/save, tolerant-парсер `.hsp` (схема 1.0), атомарное сохранение, датасеты/параметры/пост/файл данных/сценарии/расчёты/отчёты, `summary()`.
- **`gui/tabs/tab_project.py`** — раздел «Проект»: создать/открыть/сохранить/сохранить как, таблицы наборов данных и параметров, панель предупреждений. Первый пункт боковой навигации (18 разделов).
- **`tests/test_project_service.py`** — 17 тестов персистентности (round-trip, атомарность JSON, tolerant-разбор, CRUD датасетов/параметров/сценариев, чтение `sample_project.hsp`).

### Изменено
- **`gui/main_window.py`** — меню «Файл данных» (Создать/Открыть/Сохранить/Сохранить как проект); `load_data()` разделён на `load_data()` + `load_data_from_path()`; заголовок окна показывает название проекта.
- **`DOCS/hsp_schema.md`** — схема расширена: `description`, `status`, `project_id`, `metadata`, `datasets`, `calculations`, `scenarios`.
- **`INSTRUCTION.md`** — список разделов: 18, «Проект» первым.

---

## v2026.09.21 — P0, этап 0: рабочий каркас домена и сервисов

### ✨ Добавлено
- **`DOCS/ROADMAP.md`** — ТЗ и roadmap P0→P3: концепция продукта (источник — `DOCS/Привет.docx`), gap-анализ кода, этапы с критериями приёмки, открытые решения.
- **`core/services/methodology_registry.py`** — реестр методик: `MethodologyDescriptor` (нормативный документ и пункт, область применения, требования к данным, ограничения, признак «нормативно предписано / инженерная реализация»), `MethodologyRegistry` (`register`/`get`/`list`/`by_standard`/`check_applicability`) и каталог `DEFAULT_METHODOLOGIES` из 12 методик со ссылками, дословно взятыми из docstring'ов ядра.
- **`core/services/scenario_service.py`** — сервис сценариев: CRUD, клонирование с сохранением происхождения (`parent_scenario_id`), переопределение датасета, `run()` через `CalculationService`, сравнение параметров и результатов.
- **`tests/`** — `conftest.py` + `test_domain_services.py`: 28 тестов домена и сервисов, запускаются без GUI.

### 🐛 Исправлено
- **`core/domain/models.py`** — `import core.domain` падал с `TypeError: 'NoneType' object is not callable`: атрибут `ValidationIssue.field` затенял `dataclasses.field`; теперь используется `dataclasses.field(...)`.
- **`core/services/__init__.py`** — пакет не импортировался: ссылался на отсутствовавшие `scenario_service` и `methodology_registry`.
- **`core/domain/__init__.py`** — экспортированы enum'ы (`ProjectStatus`, `DatasetType`, `CalculationStatus`, `ValidationSeverity`, `ScenarioStatus`) и `ValidationIssue`.
- **Линт:** `ruff check core/domain core/services` — 0 замечаний (было 32), в `validation_service.py` убран вложенный `if` и неиспользуемый импорт.

### 🧪 Проверки
- `python -m pytest tests -q` → 28 passed.
- Регрессия: `test_all_functions.py` — 24/24 PASS, `test_edge_cases.py` — NO ISSUES, `test_sp_compliance.py` — OK, `import gui.main_window` — OK.

### 📌 Известные ограничения
- Каркас ещё не подключён к GUI: далее этапы 1–6 (проект `.hsp`, качество данных, методики в UI, результаты/provenance, сценарии, инженерный отчёт).

---

## v2026.08.30 — Audit & fixes: statistics corrections, build fixes, threading

### ✨ Исправления (audit-driven)
- **core/stats/frequency.py:** исправлен комментарий (формула К-М, не Каннана); Cv clamping заменён на явные checks; pearson3_ppf обрезает отрицательные значения явно
- **core/stats/parameters.py:** убрана некорректная поправка autocorr (autocorr_factor применялся к Cv, а не к SE)
- **core/stats/trends.py:** sens_slope векторизован (O(n²) → broadcasting)
- **core/stats/homogeneity.py:** таблица Диксона теперь с коэффициентами по n; добавлен Shapiro test; `normality_warning` в выводе
- **core/stats/advanced_frequency.py:** упрощена object-dtype конвертация в `mle_pearson3`
- **core/stats/critky_tables.py:** добавлен `bisect` для интерполяции; исправлен кэш-индекс (1.14→1.41); экстраполяция требует 2+ точек
- **core/stats/confidence_bands.py:** `quantile_ci_normal` добавляет `warning` для n<10
- **core/stats/composite_curves.py:** `find_change_point` векторизован
- **HydroSphere.spec:** абсолютные пути заменены на относительные (`gui/main_frozen.py`, `icon.ico`)
- **test_real_data.py:** хардкод `D:\!Учеба...` заменён на поиск в нескольких путях + graceful skip
- **version.py:** `UPDATE_SERVER_URL` заменён на рабочий домен (`api.hydrosphere.app`)
- **report_export.py:** `encoding='utf-8-sig'` для совместимости с Windows
- **DOCS/hsp_schema.md:** новая документация формата `.hsp`
- **core/hydrorash/regional_regressions.py:** добавлены ссылки на источники СП 33-101-2003, РД 52-26-2008
- **core/stats/series_extension.py:** добавлена диагностика остатков регрессии (outliers, heteroscedasticity, systematic bias)
- **gui/main_window.py:** `sys.path` переписан (insert вместо append), docstring обновлён
- **core/stats/sheet_reader.py:** добавлена обработка merged cells через `_fill_merged_headers`

### 🐛 Известные проблемы (не исправлены в этом релизе)
- `gui/main_window.py`: God class (2894 LOC) — требуется архитектурный рефакторинг
- `gui/main_window.py`: 22× `except Exception` — требуется замена на конкретные типы
- `gui/main_window.py`: расчёты в основном потоке — нужен `QThread` для всех операций
- `core/stats/confidence_bands.py`: нормальное приближение ненадёжно для малых n или высокой асимметрии — рекомендуется bootstrap

---

## v2026.08.07 — Переименование в HydroSphere, автопостроение кривой, диалог коротких рядов, составная кривая

### ✨ Изменения
- **Переименование программы:** «HydroSphere 2026» → «HydroSphere» — все документационные файлы, пути сборки и exe обновлены.
- **Автопостроение кривой обеспеченности:** кривая строится автоматически при выборе типа распределения (клик по радио-кнопке), кнопка «Построить» больше не требуется.
- **Составная кривая (авто):** перенесена из специальной секции в кнопку **«Составная кривая (авто)»** на панели инструментов главного окна.
- **Восстановление коротких рядов (Short):** диалог выбора аналогов теперь открывается по кнопке «Выбрать аналоги» — в правом столбце «Выбрать» отмечаются чекбоксами посты-аналоги; в диалоге также добавлено выпадающее поле для выбора расчётного поста.
- **Багфикс составных кривых:** исправлена методология расчёта (взвешенное среднее по числу лет вместо np.minimum).

---

## v2026.08.06b — Переименование листов шаблона в соответствии с вкладками GUI

### ✨ Переименование листов unified_template.xlsx
Все листы шаблона получили имена, совпадающие с названиями вкладок GUI. Любое упоминание «Работа N» удалено:

| Было | Стало |
|------|-------|
| Гидропост | Данные и статистика |
| Работа1 | Норма годового стока |
| Работа2 | Внутригодовое распределение |
| Работа3 | Минимальный сток |
| Работа4 | Максимальный сток |
| КриваяQH | Кривая Q(H) |
| Работа5 | Ледовые явления |
| Работа6 | Водный баланс |
| Работа7 | Рацион + IDF + Гидрографы |
| Работа8 | FDC + Регрессии + Статистика |
| Работа9 | ППУ + ГВП + Регулирование |
| Работа10 | Экология + Базовый сток |
| ГТС | ГТС (без изменений) |

### 🔧 Сопутствующие правки
- **`gui/main_window.py`** — все `_find_sheet()` и `read_work_sheet()` ключевые списки обновлены с новыми именами листов; исключительный список `_parse_main_posts` обновлён (добавлены «Рацион», «ГВП» вместо «Работа»).
- **`gui/widget_work2.py`, `widget_work4.py`, `widget_work8.py`, `widget_work10.py`** — загрузчики файлов обновлены с новыми ключевыми словами.
- **`tools/verify_sheet_reader.py`** — все 12 секций используют новые имена листов; A1-заголовки шаблона не содержат «Работа N».
- **`core/stats/sheet_reader.py`** — docstring-примеры обновлены.
- **`INSTRUCTION.md`** — таблица листов шаблона обновлена.
- **`DOCS/HydroSphere_2026_Руководство.md`** — описание структуры шаблона обновлено.

### 🧪 Тесты
- `verify_sheet_reader.py`: 12/12 секций OK, 0 упоминаний «Работа» в ячейках шаблона.
- `test_all_functions.py`: 24/24 PASS.
- `test_edge_cases.py`: 0 ISSUES.
- styles.xml: 5 шрифтов, 8 cellXfs — валидно, PatternFill не протекла в шрифты.

---

## v2026.08.06 — Исправление styles.xml + доделан шаблон (ГТС, Работа7, Работа9)

### 🐛 Критический баг: Excel ругался на unified_template.xlsx
- **`create_unified_template.py`** — в `write_header_row()` заливка `header_fill` (объект `PatternFill`) по ошибке передавалась в параметр `font=` → openpyxl регистрировал объект-заливку как шрифт, и в `styles.xml` попадал элемент `<font><name val="<openpyxl.styles.fills.PatternFill object>…">`.
- Excel считал `styles.xml` повреждённым, удалял компонент `/xl/styles.xml` и «чинил» сведения о ячейках всех 12 листов.
- Исправлено: `font=header_font`, лишний повторный блок стилей убран.

### ✨ Единый шаблон для всех функций (закрыты 3 пробела)
- **ГТС** — лист читается в `_parse_work_sheets()`, параметры (высота плотины / объём водохр.) классифицируются через `classify_gts_by_parameters()` → `self._gts_class`/`self._gts_params`; `build_curve_with_gts()` предвыбирает класс из шаблона в диалоге.
- **Работа7** — парсер и `set_data()` читают T / t / α помимо F и зоны.
- **Работа9** — исправлен баг потери `slope` (`bw_I` теперь применяется), шаблон расширен параметрами водосброса/подпора/регулирования (L, H, тип, m, n, Hres, Lbackwater, Qmean, demand).

### 🧪 Тесты
- `tools/verify_sheet_reader.py` — добавлены секции 9–12: ГТС, Работа7 (5 параметров), Работа9 (все 12, slope не теряется), интеграция «шаблон → парсер → классификация».

---

## v2026.08.05 — Реализация функционала ГГИ (Short, однородность, Cs/Cv)

### ✨ Новое
- **`core/short_series.py`** — восстановление коротких рядов (<6 лет) по методике ГГИ:
  - `fit_analog_relationship()` — линейная связь calc↔analog (единое решение: k1=σy/σx)
  - `restore_year()` — восстановление за один год (осреднение с весом 1/σ²)
  - `restore_short_series()` — полный цикл восстановления
  - `build_protocol()` — текстовый протокол (аналог Продление.txt)
  - `convert_to/from_module_flow()` — Q↔q преобразование
- **`gui/widget_short.py`** — виджет Short: таблицы, scatter plots, протокол
- **`core/stats/homogeneity.py`** — полная проверка однородности:
  - 5 критериев Диксона (D1N–D5N) по СП 33-101-2003
  - 2 критерия Смирнова-Граббса (Gn, G1)
  - `stationarity_test()` — t-тест Стьюдента и F-тест Фишера
  - `batch_homogeneity_check()` — сплошная проверка всех столбцов
- **`core/stats/frequency.py`** — дополнения:
  - `auto_select_cs_cv()` — автоматический подбор Cs/Cv (минимизация Σ(Yэмп-Yтеор)²)
  - `piecewise` — интерполяция ломаной линией
  - `HistoricalExtreme` — класс исторических экстремумов
  - `compute_params_with_extremes()` — расчёт параметров с учётом экстремумов
- **`core/stats/series_extension.py`** — `compute_integral_curves()` — интегральная/разностно-интегральная кривая
- **`core/stats/composite_curves.py`** — метод Рождественского (осреднение P(Q), не Q)

### 🔧 GUI
- **Short в навигации** — «Короткие ряды (Short)» (оранжевый #F57C00)
- **Меню** — «Восстановить короткий ряд (Short)...»
- **Кривая обеспеченности** — кнопки «Подбор Cs/Cv», «Добавить экстремум», «Все варианты»
- **Анализ трендов** — кнопка «Проверка стационарности»
- **QSplitter** — масштабирование панелей во вкладках

### 📚 Документация
- `INSTRUCTION.md` — разделы по Short, Cs/Cv, экстремумам, стационарности
- `DOCS/HydroSphere_2026_ТехническоеОписание.md` — обновлена архитектура

---

## v2026.08.02 — Полная таблица Крицкого–Менкеля, Пирсон III через scipy

### ✨ Новое
- **`core/stats/kritsky_tables.py` полностью перегенерирован** — полная таблица ординат Крицкого–Менкеля (Прил. Б «Методических рекомендаций…» ГГИ, 2005): 15 листов Cs/Cv (−1…6, шаг 0.5), 27 уровней P (0.001–99.9 %), Cv 0.1–2.0. Значения загружены из `OFFICE\KritkMenc.bin` эталонной программы HydroStatCalc (float32). `get_ordinates()` — билинейная интерполяция по Cv/Cs + лог-интерполяция пропусков по P.
- **`core/stats/frequency.py`** — Пирсон III через точную функцию `scipy.stats.pearson3.ppf` вместо приближения Корниша–Фишера; эмпирические точки по формуле Каннана (`empirical_plotting_positions`, P = (m−0.3)/(n+0.4)).
- **`core/hydrorash/utils.py`** — эмпирическая обеспеченность по формуле Каннана (была `m/n`).

### 🔧 Изменено
- **`core/stats/parameters.py`** — удалена поправка на автокорреляцию к Cv (сверено с эталоном: Cv_расч ≡ Cv_выб).
- **`core/stats/series_extension.py`** — добавлена `multi_analog_extension` (множественная регрессия по рекам-аналогам, до 3 аналогов, критерии Ro/σRo, ki/σki, Y/σY).
- **GUI** — «Параметры» перенесены в конец навигации; текст результатов и графики в рабочих вкладках разнесены разделителями QSplitter (widget_work1–10, trend); эмпирические точки — формула Каннана.

### 📚 Документация
- `INSTRUCTION.md` — обновлён список навигации, дополнен раздел о таблице Крицкого–Менкеля.
- `DOCS/HydroSphere_2026_ТехническоеОписание.md` — §4.1–4.3 (Пирсон III, К-М, параметры), новый §5.5 (таблица К-М).

---

## v2026.07.28 — Code review: исправление ошибок и улучшение качества

### Исправлено

#### Критические ошибки
- **4 bare `except:` заменены** на конкретные типы исключений:
  - `create_unified_template.py:81` — `(FileNotFoundError, ValueError, KeyError, TypeError)`
  - `core/profile.py:82` — `(ValueError, TypeError, KeyError)`
  - `core/stats/data_loader.py:35` — `(ValueError, TypeError)`
  - `core/stats/data_loader.py:98` — `(ValueError, TypeError, AttributeError)`
- **ZeroDivisionError в `run_stats_demo.py:39`** — добавлена проверка `if len(df) > 0` перед делением

#### Обработка ошибок
- **`gui/main_window.py`** — 12 `except Exception: pass` заменены на конкретные исключения + print warning
- **`core/stats/advanced_frequency.py`** — 6 `except Exception:` заменены на `(ValueError, FloatingPointError, ZeroDivisionError, TypeError, RuntimeError)`
- **`core/stats/frequency.py`** — 6 `except Exception:` заменены на `(ImportError, ValueError, TypeError, RuntimeError)`
- **`core/stats/confidence_bands.py`** — `(ValueError, TypeError, ZeroDivisionError)`
- **`core/hydrorash/utils.py`** — `(ValueError, TypeError)`

#### Структура и документация
- **`core/stats/__init__.py`** — добавлен `__all__` со списком 19 модулей
- **`build.py`** — кроссплатформенные пути: `os.path.join()`, `sys.platform` для разделителя `--add-data`

## v2026.07.27 — Текущая версия

### 🐛 Исправленные ошибки

#### Критические баги
- **`np.trapz` → `np.trapezoid`** (`core/hydrorash/flood_hydrograph.py`)
  Удалённый в NumPy 2.0 метод `np.trapz` заменён на `np.trapezoid`. Также исправлен вызов `flood_volume()` с неверными аргументами (`dt * ones_like` → `dx=dt`).

- **Ключ `'depths'` → `'depths_m'`** (`core/hydrorash/backwater.py:218`)
  `backwater_from_reservoir()` обращалась к несуществующему ключу в возвращаемом словаре — ошибка `KeyError` при расчёте кривой подпора ГВП.

- **`q7_10()` возвращал dict, а вызывающий код использовал как число** (`core/hydrorash/ecological_flow.py:231`)
  `round(q710, 2)` → `round(q710['Q7_10_value'], 2)`. Ошибка `TypeError` при расчёте методом 7Q10.

- **`fft_analysis()` — разные ключи `'periods'` vs `'periods_years'`** (`core/stats/spectral.py:36`)
  Ранний возврат при < 4 точках возвращал `'periods'`, основной путь — `'periods_years'`. Несовпадение вызвало `KeyError`.

- **`draw()` вместо `plt.figure()`** (`gui/main_window.py` lines 528, 549, 578)
  Утечка памяти: создание нескольких `plt.figure()` одновременно. Заменено на существующие `Figure()` объекты canvas'ов.

- **Отсутствовал `AutoResizeTableFilter`** (`gui/plot_style.py`)
  Класс `AutoResizeTableFilter` был вызван в `main_window.py` но не был определён → `ImportError` при запуске.

- **Отсутствовал `import pandas as pd`** (`gui/widget_work10.py`)
  `NameError: name 'pd' is not defined`.

#### Валидация и числовые ошибки
- **`rational_method.py:238`** — добавлена валидация `I > 0` (ZeroDivisionError при интенсивности 0)
- **`backwater.py`** (`normal_depth`, `critical_depth`) — добавлена валидация `Q, B, n, I > 0`
- **`advanced_frequency.py:181`** — исправлена формула Cs: `tau3 * np.pi` → `tau3 / cv`
- **`max_runoff.py:189`** — добавлена проверка `gauged_mean_annual <= 0`
- **`parameters.py:105`** — добавлена проверка `r1 < 1.0` (ZeroDivisionError при `r1=1.0`)

#### Составные кривые
- **`composite_curves.py:212`** — исправлена методология: вместо `np.minimum(Q1, Q2)` теперь взвешенное среднее по числу лет: `(Q1*n1 + Q2*n2) / (n1+n2)`

### 🎨 UI улучшения

#### Цветовая схема
- Добавлены единые стили для всех виджетов (`gui/plot_style.py` — `apply_global_style`, `setup_axes_style`, `COLORS`, `auto_resize_table`)
- Удалён белый фон (`background: white`) с `QTabWidget::pane` во всех Work-вкладках
- Добавлен глобальный QSS в `main_window.py` для `QGroupBox`, `QLineEdit`, `QDoubleSpinBox`, `QTextEdit`, `QTableWidget`, `QComboBox`

#### Кнопки
- Добавлен глобальный стиль `QPushButton` (тёмно-серый фон `#37474F`, белый текст, жирный шрифт) — все нестилизованные кнопки теперь читаемые
- Цветные кнопки (зелёные «РАССЧИТАТЬ», синие «Сохранить», оранжевые «Ввести вручную») сохраняют свои цвета

#### Автоматизация
- **Автоматическая передача Qsr**: после расчёта в Работе 1, Qsr автоматически подставляется в Работы 4, 6, 7, 10
- **Автоматическое построение FDC**: в Работе 8 при наличии ≥5 точек
- **Автоматическая раздача данных**: `_distribute_data_to_widgets()` загружает данные в Work4/6/8/10 при загрузке файла

#### Шаблоны и загрузка
- **`load_unified_template()`** — переписана с поддержкой понятных русских названий листов (см. ниже)
- **Добавлена кнопка «➕ Добавить пост»** — объединение данных второго файла с первым по году
- **Простановка `blockSignals`** для `combo_post` при загрузке/добавлении постов (устранены ложные срабатывания)

### 📊 Шаблон данных
- Новое: `create_template.py` — генератор шаблона Excel
- Новый файл: **`шаблон_данных.xlsx`** с 10 листами:
  - `Данные` — год + 4 поста (40 лет реалистичных данных)
  - `Норма годового стока` — расчётная река + аналог + площади
  - `Внутригодовое распределение` — помесячные суммы I–XII
  - `Минимальный сток` — зимний и летний стоки
  - `Максимальный сток` — Qmax по годам
  - `Кривая Q(H)` — 25 пар уровень–расход
  - `Ледовые явления` — даты ледостава/вскрытия
  - `Водный баланс` — 13 870 суточных значений
  - `FDC` — 13 870 суточных значений
  - `Экология и базовый сток` — 13 870 суточных значений

### 🇷🇺 Локализация (русский язык)
Исправлено 21 вхождение английского текста в интерфейсе:

| Файл | Было | Стало |
|------|------|-------|
| `main_window.py` (x4) | `"Excel Files (*.xlsx)"` | `"Файлы Excel (*.xlsx)"` |
| `main_window.py` | `"PNG Files...; JPEG Files...; PDF Files..."` | `"Изображения PNG...; Изображения JPEG...; Документы PDF..."` |
| `main_window.py:1624` | `'Regression: Q=...'` | `'Регрессия: Q=...'` |
| `widget_work9.py` | `"Тrapeция (Cd=1.50)"` | `"Трапеция (Cd=1.50)"` |
| `widget_work9.py` | `"Ogee (Cd=2.20)"` | `"Оgee-профиль (Cd=2.20)"` |
| `widget_work8.py` (x2) | `"mean="` | `"среднее="` |
| `widget_work5.py` | `"N/A"` | `"Н/Д"` |
| `widget_work6.py` (x9) | `"N/A"` | `"Н/Д"` |

### 📚 Документация
- **`INSTRUCTION.md`** — полное руководство пользователя для начинающих
  - Описание интерфейса при первом запуске
  - Пошаговая инструкция от загрузки до расчётов
  - Описание всех 16 разделов навигации
  - Описание меню и типичных workflow'ов
  - Таблица решения проблем
  - Добавлена глава о едином шаблоне

### 🛠 Очистка кода
- Удалён мёртвый метод `apply_parameters()` (был `pass`)
- Удалена мёртвая переменная `self._all_posts` в инициализации (не использовалась)
- `bare except:` → `except (ValueError, TypeError):` в статистических тестах

---

## Файлы

| Файл | Статус |
|------|--------|
| `build.py` | Обновлён — добавлены hidden imports |
| `create_template.py` | **Новый** — генератор шаблона |
| `шаблон_данных.xlsx` | **Новый** — шаблон с реалистичными данными |
| `gui/main_window.py` | UI стили, load_unified_template, load_dates, save_report, English→Russian |
| `gui/plot_style.py` | **Новый** — единая тема стилей для графиков |
| `gui/widget_work1–10.py` | Стили, auto_resize_table, set_data/set_qsr |
| `core/hydrorash/backwater.py` | KeyError fix, валидация Q,B,n,I |
| `core/hydrorash/ecological_flow.py` | `round(dict)` → `round(dict['key'])` |
| `core/hydrorash/flood_hydrograph.py` | `np.trapz` → `np.trapezoid`, `dx` исправление |
| `core/hydrorash/ice_phenomena.py` | Исправлена ошибка 永久→постоянным |
| `core/hydrorash/max_runoff.py` | Валидация `gauged_mean_annual > 0` |
| `core/hydrorash/rational_method.py` | Валидация `I > 0` |
| `core/stats/advanced_frequency.py` | Исправлена формула Cs |
| `core/stats/composite_curves.py` | Взвешенное среднее вместо np.minimum |
| `core/stats/parameters.py` | Защита от `r1=1.0` |
| `core/stats/spectral.py` | Единый ключ `'periods_years'` |
| `INSTRUCTION.md` | **Новый** — руководство пользователя |