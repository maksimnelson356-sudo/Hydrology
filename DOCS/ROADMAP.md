# HydroSphere — Roadmap и ТЗ (P0 → P3)

> **Источник концепции:** `DOCS/Привет.docx` — «HydroSphere — идея целиком» (27 разделов).
> **Назначение файла:** зафиксировать целевое видение продукта, текущее состояние кода, этапы P0
> с критериями приёмки и открытые решения. Расчётное ядро не переписывается — над ним
> надстраивается сервисный слой и рабочее место инженера.
>
> **Статус:** ТЗ, версия 1.2 · **Дата:** 21.09.2026 · **Ветка:** `global-implementation`

---

## 1. Что мы строим

HydroSphere — российский инженерный комплекс для гидрологических расчётов, статистического
анализа и принятия решений, объединяющий нормативную методику, исходные данные, контроль
качества, расчёт, проверку, сценарный анализ, визуализацию и автоматический инженерный отчёт
в одном рабочем процессе.

Главная идея: не «ввёл числа → получил число», а

```
данные → проверка → методика → расчёт → контроль → сценарии → результат → графики → отчёт
```

**ДНК продукта (конкурентное ядро):**

```
Data → Quality → Methodology → Calculation → Validation → Scenario → Decision → Report
```

**Три правила, которые нельзя нарушать:**

1. **Существующее расчётное ядро не переписывается.** `core/stats`, `core/hydrorash`,
   `core/hydraulics.py`, `core/profile.py`, `core/short_series.py`, `core/gts_reference.py` —
   это математический двигатель системы.
2. **Сервисный слой не содержит математики.** `core/services/*` отвечает только за организацию
   расчёта, валидацию, трассируемость и сериализацию; все формулы — в ядре.
3. **Программа не исправляет данные и не принимает решений молча.** Любое действие над данными
   или результатом — только после явного подтверждения пользователем, с объяснением
   «что обнаружено → почему это важно → что можно сделать».

**Позиционирование:** мы не клон HEC-RAS и не выигрываем количеством формул. HEC-RAS отвечает
на вопрос «как течёт вода»; HydroSphere отвечает на более широкий инженерный вопрос: «что
происходит с данными, какой нормативный метод применить, насколько можно доверять расчёту, что
произойдёт при изменении условий и как оформить результат».

---

## 2. Целевая архитектура (образ результата)

```
PROJECT (Проект)
├── Datasets        (наблюдения, ряды, морфометрия, параметры бассейна)
│     └── Data Quality (пропуски, выбросы, однородность, стационарность, полнота)
├── Methodologies   (реестр методик: СП/ГОСТ, версия, применимость, ограничения)
│     └── Calculation (CalculationService → существующее ядро)
│           └── Validation (ValidationService → PASS / PASS WITH WARNINGS / FAIL)
├── Scenarios       (Base → Scenario A → Scenario B …)
├── Results         (CalculationResult + Provenance)
└── Reports         (инженерный отчёт из 13 разделов)
```

Слои и правила зависимостей:

| Слой | Каталог | Разрешённые зависимости |
|------|---------|-------------------------|
| Domain | `core/domain/` | только стандартная библиотека |
| Services | `core/services/` | `core/domain`, расчётное ядро (`core/stats`, `core/hydrorash`, …) |
| Расчётное ядро | `core/stats/`, `core/hydrorash/`, `core/*.py` | numpy / scipy / pandas |
| UI | `gui/` | `core/services`, `core/domain`, `gui/*` |

Обратные зависимости (ядро → сервисы, сервисы → UI) запрещены.

---

## 3. Текущее состояние (на 21.09.2026)

### 3.1. Что уже готово (сохраняем)

**Расчётное ядро:**

- `core/stats/` — `frequency.py` (Пирсон III, Крицкий-Менкель, piecewise), `parameters.py`
  (Qср, Cv, Cs, ε), `homogeneity.py` (12 критериев), `trends.py` (Манн-Кендалл, Pettitt, Sen),
  `composite_curves.py`, `series_extension.py`, `advanced_frequency.py` (MLE, L-моменты, GEV,
  PDS), `confidence_bands.py`, `flow_duration.py`, `baseflow.py`, `spectral.py`, `drought.py`
  (SPI/SPEI), `kritsky_tables.py`, `critical_values.py`, `gts_integration.py`, `report_export.py`,
  `data_loader.py`, `sheet_reader.py`, `missing_data.py`.
- `core/hydrorash/` — `max_runoff`, `minimal_runoff`, `min_runoff_extended`, `intra_annual`,
  `ice_phenomena`, `water_balance`, `rational_method`, `flood_hydrograph`, `snowmelt`,
  `regional_regressions`, `spillway`, `backwater`, `reservoir_regulation`, `sedimentation`,
  `ecological_flow`, `hydrological_periods`, `utils`.
- Прочее ядро: `core/hydraulics.py`, `core/profile.py`, `core/short_series.py`,
  `core/gts_reference.py`.

**Приложение:**

- `gui/main_window.py` — 17 разделов навигации (`QListWidget` + `QStackedWidget`), меню
  «Файл данных» и «Статистика».
- Виджеты расчётов: `gui/widget_work1..10.py`, `gui/widget_short.py`.
- Контроллеры: `gui/controller/data_controller.py`, `plot_controller.py`, `widget_factory.py`.
- Фоновые расчёты: `gui/workers/calculation_workers.py` (QThread-воркеры).
- Дизайн-система: `gui/plot_style.py`. Интерфейс: `i18n/ru.json`, `i18n/en.json`.
- Сборка: `build.py`, `HydroSphere.spec`, `build_nuitka.py`, `installer/`.
- Документация: `INSTRUCTION.md`, `DOCS/ГидроСтатистика_2026_*.md`, `DOCS/changelog.md`,
  `DOCS/hsp_schema.md`, `DOCS/project-viz.html`.
- Тесты в корне: `test_all_functions.py`, `test_backwater.py`, `test_edge_cases.py`,
  `test_q.py`, `test_real_data.py`, `test_regression_critical.py`, `test_sp_compliance.py`.

### 3.2. Что начато по новой архитектуре (P0-каркас, ещё не в git)

| Файл | Строк | Содержимое |
|------|-------|------------|
| `core/domain/models.py` | 350 | `Project`, `Dataset`, `Methodology`, `CalculationMetadata`, `CalculationResult`, `Scenario`, `ValidationIssue`, `ValidationResult`, `DataQualityReport` + enum'ы |
| `core/domain/__init__.py` | 36 | Реэкспорт моделей (enum'ы не экспортируются) |
| `core/services/calculation_service.py` | 208 | `CalculationService` (регистрация handler/validator, `execute`, `execute_async`), `CalculationContext`, `CalculationError` |
| `core/services/validation_service.py` | 470 | `ValidationService` (`validate_dataset`, `validate_calculation_result`, `validate_scenario`, custom validators) |
| `core/services/__init__.py` | 19 | Импортирует **отсутствующие** `scenario_service`, `methodology_registry` |
| `DOCS/hsp_schema.md` | — | Спецификация формата проекта `.hsp` (schema_version 1.0) |
| `sample_project.hsp` | — | Пример файла проекта (ничем не читается) |

### 3.3. Дефекты-блокеры (проверено запуском)

| # | Дефект | Доказательство | Приоритет |
|---|--------|----------------|-----------|
| B1 | `import core.domain` падает: `TypeError: 'NoneType' object is not callable` | `core/domain/models.py:304` — в классе `ValidationIssue` атрибут `field: Optional[str] = None` затеняет импортированный `dataclasses.field`, поэтому `details: dict = field(default_factory=dict)` вызывает `None` | Critical |
| B2 | `core/services` не импортируется | `core/services/__init__.py:14-15` импортирует `scenario_service` и `methodology_registry`, которых нет в каталоге | Critical |
| B3 | Enum'ы домена не экспортируются из `core/domain/__init__.py` | Модели используют `ProjectStatus`, `DatasetType`, `CalculationStatus`, `ValidationSeverity`, `ScenarioStatus` — снаружи доступны только через `core.domain.models` | Minor |
| B4 | В корне лежат отладочные логи, `.bak`, `old-session.json` | `allw.log`, `btns.log`, `combo*.log`, `diag.log`, `run_*.log`, `w4_*.log`, `frequency.py.bak`, `update_checker.py.bak` | Trivial |

### 3.4. Разрыв между концепцией и кодом (gap-анализ по разделам концепции)

| Концепция (раздел Привет.docx) | Состояние в коде | Этап P0 |
|--------------------------------|------------------|---------|
| Проект как контейнер (п.2) | Только dataclass `Project`; персистентности нет, GUI её не знает | Этап 1 |
| Dataset, импорт рядов (п.3) | `Dataset` (domain) + `DataController`/`data_loader`/`sheet_reader` (ядро), между собой не связаны | Этап 1 |
| Data Quality (п.4) | `ValidationService.validate_dataset` + `DataQualityReport` есть, но **не используются**; в GUI ad-hoc кнопки «Заполнить пропуски», «Однородность», «Выбросы» | Этап 2 |
| Нормативная методика как часть расчёта (п.5) | Норматив только в докстрингах и документации | Этап 3 |
| Methodology Registry (п.6) | **Отсутствует** | Этап 3 |
| CalculationService над ядром (п.7) | Каркас есть (208 строк), ни одного handler не зарегистрировано | Этап 3 |
| CalculationResult как объект (п.8) | Модель есть, в GUI живут «сырые» dict'ы | Этап 4 |
| ValidationService (п.9) | Сервис есть (470 строк), не вызывается из GUI | Этапы 2, 3 |
| Scenario / Scenario Manager / сравнение (п.10–12) | Только dataclass `Scenario`; сервиса и UI нет | Этап 5 |
| Визуализация как часть анализа (п.13) | Есть `plot_style.py`, графики в виджетах; «график как часть отчёта» не связан | Этапы 4, 6 |
| GIS / DEM (п.14) | Нет | P1 |
| Calibration / Optimization (п.15) | Нет | P1 |
| Uncertainty / Monte Carlo (п.16) | Частично: `confidence_bands.py` (bootstrap) | P2 |
| Климатические сценарии (п.17) | Нет | P2 |
| Reservoir Simulator (п.18) | Есть `reservoir_regulation.py` (метод Риппла) | P1 |
| Автоматический инженерный отчёт, 13 разделов (п.19) | Есть `report_export.generate_txt_report` + экспорт Excel; сборки отчёта из проекта нет | Этап 6 |
| Provenance (п.20) | **Отсутствует** (поиск по проекту: 0 совпадений) | Этап 4 |
| Версионность проекта (п.21) | Нет истории расчётов | Этап 4 |
| Regulatory Knowledge Base (п.22) | Нет реестра нормативных ссылок как данных | Этап 3 |
| Профессиональные предупреждения (п.23) | Предупреждения есть точечно в ядре (`normality_warning`), единой системы нет | Этапы 2–4 |
| Decision Support (п.24) | Нет | P1–P2 |
| Единая архитектура сервисов (п.25) | Каркас есть, не подключён | Этапы 0–6 |

---

## 4. Целевая структура каталогов (после P0)

```
core/
├── domain/
│   ├── models.py            (существует; починить ValidationIssue)
│   ├── serialization.py     НОВОЕ  to_dict/from_dict для всех сущностей (UUID, datetime, Enum)
│   └── __init__.py          (дополнить: экспорт enum'ов)
├── services/
│   ├── calculation_service.py  (существует)
│   ├── validation_service.py   (существует)
│   ├── methodology_registry.py НОВОЕ  реестр методик + нормативные ссылки + применимость
│   ├── scenario_service.py     НОВОЕ  CRUD сценариев, клонирование, сравнение
│   ├── project_service.py      НОВОЕ  .hsp: create/open/save/migrate (tolerant)
│   ├── data_quality_service.py НОВОЕ  проверки данных → DataQualityReport
│   ├── result_store.py         НОВОЕ  хранение CalculationResult + provenance-цепочка
│   ├── report_service.py       НОВОЕ  сборка инженерного отчёта (13 разделов)
│   ├── bootstrap.py            НОВОЕ  сборка контейнера: регистрация методик и валидаторов
│   ├── handlers/               НОВОЕ  тонкие адаптеры context → core.stats / core.hydrorash
│   └── __init__.py             (существует; после этапа 0 импортируется без ошибок)
├── stats/                   (без изменений — расчётное ядро)
└── hydrorash/               (без изменений — расчётное ядро)

gui/
├── tabs/
│   ├── tab_project.py       НОВОЕ  Проект: создать/открыть/сохранить .hsp, состав проекта
│   ├── tab_data_quality.py  НОВОЕ  Качество данных: PASS/WARNING/ERROR + «что можно сделать»
│   ├── tab_methodology.py   НОВОЕ  Реестр методик: СП, раздел, применимость к текущему ряду
│   ├── tab_scenarios.py     НОВОЕ  Сценарии: список, запуск, сравнение, график
│   ├── tab_results.py       НОВОЕ  Результаты + Provenance («Откуда это число?»)
│   └── tab_report.py        НОВОЕ  Инженерный отчёт: предпросмотр и экспорт
├── main_window.py           (постепенно уменьшается: вынести tab_data и тяжёлые расчёты)
└── ...                      (widget_work1..10, widget_short, controller, workers — сохраняются)

tests/                       НОВОЕ  pytest-тесты сервисного слоя (в корне остаются старые скрипты)
tools/
├── run_methodology.py       НОВОЕ  консольный прогон расчёта через CalculationService
└── ...                      (synthesize_series.py, verify_sheet_reader.py — сохраняются)
```

**Соглашения кода (по факту текущего проекта):**

- `core/` — docstring'и на английском, `from __future__ import annotations`, dataclasses,
  без циклов импортов; строка ≤ 100 символов (ruff, `pyproject.toml`).
- `gui/` — комментарии и тексты на русском, новые строки интерфейса — через
  `t(key, fallback)` из `i18n/__init__.py` (+ ключи в `ru.json` и `en.json`).
- Тяжёлые расчёты — только через `QThread`-воркеры (`gui/workers/calculation_workers.py`).
- Новые модули обязательно добавлять в `--hidden-import` (`HydroSphere.spec` / `build.py`),
  иначе они не попадут в сборку.

---

## 5. Версионирование продукта

| Версия | Приоритет | Содержание | Этапы этого ТЗ |
|--------|-----------|------------|----------------|
| **HydroSphere 1.0** | P0 | Project, Dataset, Data Quality, Methodology, Calculation, Validation, Scenario, Result, базовый Report, единая архитектура сервисов, сохранение существующего ядра | Этапы 0–6 |
| **HydroSphere 1.5** | P1 | Полноценный импорт временных рядов (CSV, API), автоконтроль качества, калибровка, оптимизация, GIS/DEM, расширенная статистика, Reservoir Scenario Simulator | — |
| **HydroSphere 2.0** | P2 | Monte Carlo, неопределённости, анализ чувствительности, климатические сценарии, расширенная визуализация, продвинутый decision support | — |
| **HydroSphere 3.0** | P3 | 1D/2D гидравлическое моделирование, пространственные расчёты, интеграция ГИС, крупные инженерные модели | — |

---

## 6. Этапы P0 с критериями приёмки

### Этап 0. Оживить P0-каркас (фундамент)

**Статус:** ✅ выполнен 21.09.2026 (коммиты `eb3b2b9`, `3790091`).

**Цель:** `import core.domain` и `import core.services` работают; домен и сервисы покрыты
smoke-тестами; каркас закоммичен.

**Задачи:**

1. `core/domain/models.py` — устранить затенение `field` в `ValidationIssue`
   (использовать `dataclasses.field(...)`; публичное имя атрибута `field` сохранить).
2. `core/domain/__init__.py` — экспортировать enum'ы (`ProjectStatus`, `DatasetType`,
   `CalculationStatus`, `ValidationSeverity`, `ScenarioStatus`).
3. `core/services/methodology_registry.py` — минимальный рабочий реестр (см. этап 3);
   `core/services/scenario_service.py` — минимальный рабочий сервис сценариев (см. этап 5).
4. `core/services/__init__.py` — привести экспорт в соответствие реальным файлам.
5. `tests/test_domain_services.py` — pytest-тесты: импорт обоих пакетов, `Methodology.qualified_name`
   и `__hash__`/`__eq__`, `Dataset.clone`, `Dataset.length/start_year/end_year`,
   `ValidationService.validate_dataset` на ряде с пропуском года и выбросом,
   `Scenario.with_parameters` (оригинал не изменяется), `CalculationService.execute` без handler
   → `CalculationError`.
6. `git add core/domain core/services tests` + коммит (каркас сейчас untracked — риск потери).

**Критерии приёмки:**

- `python -X utf8 -c "import core.domain, core.services"` → без ошибок (код возврата 0).
- `python -m pytest tests -q` → все тесты зелёные.
- `python -m ruff check core tests` → без новых замечаний.

**Как проверяем:** команды выше + повторный `git status` (файлы больше не untracked).

---

### Этап 1. Проект и персистентность `.hsp`

**Статус:** выполнен 21.09.2026.

**Цель:** пользователь создаёт Проект, сохраняет его в `.hsp`, открывает и продолжает работу;
состояние (данные, пост, параметры, результаты) восстанавливается.

**Задачи:**

1. `core/domain/serialization.py` — `to_dict`/`from_dict` для `Project`, `Dataset`,
   `Methodology`, `CalculationMetadata`, `CalculationResult`, `Scenario`, `ValidationResult`,
   `DataQualityReport`; корректная обработка `UUID`, `datetime`, `Enum`.
2. `core/services/project_service.py` — `create_project`, `open_project`, `save_project`,
   `add_dataset`, `set_selected_post`, tolerant-парсер: отсутствующие поля → значения по
   умолчанию (как в `DOCS/hsp_schema.md`), несовпадение `schema_version` → предупреждение,
   а не падение; поддержка `sample_project.hsp` (минимальный набор полей).
3. `gui/tabs/tab_project.py` — панель «Проект»: название, статус, список датасетов, выбранный
   пост, путь к файлу данных, кнопки «Создать/Открыть/Сохранить/Сохранить как».
4. `gui/main_window.py` — пункты меню «Файл данных → Создать проект… / Открыть проект… /
   Сохранить проект» + новый раздел навигации «Проект».
5. `tests/test_project_service.py` — round-trip (save → open → все поля совпадают),
   устойчивость к пустому/усечённому JSON, отсутствию файла (понятная ошибка), чтение
   `sample_project.hsp`.

**Критерии приёмки:**

- Созданный проект после сохранения/открытия содержит тот же набор датасетов и параметров
  (проверка тестом и вручную в GUI: 3 клика).
- `sample_project.hsp` открывается без ошибок (отсутствующие обязательные поля получают
  значения по умолчанию, выводится предупреждение).
- Файл `.hsp` — валидный JSON, читаемый текстовым редактором; `schema_version = "1.0"`.

**Как проверяем:** `python -m pytest tests/test_project_service.py -q` + запуск GUI
(`python gui/main_window.py`) и ручной прогон создания/сохранения/открытия проекта.

---

### Этап 2. Контроль качества данных (Data Quality)

**Цель:** после загрузки ряда программа сама показывает его качество и **не исправляет данные
молча**; пользователь видит «что обнаружено → почему это важно → что можно сделать».

**Задачи:**

1. `core/services/data_quality_service.py` — единая точка: `analyze(dataset) -> DataQualityReport`.
   Проверки (все — через существующее ядро):
   - пропуски внутри диапазона лет, дубликаты лет, разрывы;
   - отрицательные, нулевые и «невозможные» значения (например, расход > 1e6 м³/с при малой
     площади водосбора — порог из параметров);
   - выбросы: Диксон / Смирнов-Граббс через `core/stats/critical_values.py`;
   - однородность: `core/stats/homogeneity.check_homogeneity_full` (12 критериев);
   - стационарность и тренд: `core/stats/trends.full_trend_analysis`;
   - длина ряда против требований методики (минимум n лет для выбранного метода);
   - полнота наблюдений (`completeness_ratio`) и итоговый `quality_score` / `quality_grade`.
2. Рекомендации: для каждой проблемы — список допустимых действий (интерполяция, восстановление
   по аналогу `core/stats/series_extension.py`, исключение года, оставить как есть), но
   **без автоматического применения**.
3. `gui/tabs/tab_data_quality.py` — таблица проверок (Проверка / Результат / PASS-WARNING-ERROR /
   Пояснение) с итогом «PASS WITH WARNINGS», кнопки явного применения рекомендованных действий
   (переиспользуют уже существующие методы `main_window.py`: `fill_missing_data`,
   `fill_missing_with_correlation`, `check_homogeneity`, `detect_outliers`).
4. `tests/test_data_quality_service.py` — синтетические ряды: чистый ряд → нет ERROR;
   ряд с пропуском года, дубликатом, отрицательным значением и явным выбросом → ожидаемые коды
   issue; короткий ряд (n=5) → ERROR о недостаточной длине.

**Критерии приёмки:**

- На чистом ряду (`create_test_data.py` / `synthetic` из `tools/synthesize_series.py`) отчёт
  содержит только INFO/ничего, оценка ≥ 0.9 (grade A).
- На ряду с внесёнными дефектами каждый дефект даёт отдельный issue с кодом и пояснением.
- Панель «Качество данных» показывает отчёт и не меняет ряд без нажатия кнопки пользователем.

**Как проверяем:** `python -m pytest tests/test_data_quality_service.py -q` + ручной прогон в GUI
на файле `test_data_clean.xlsx`.

---

### Этап 3. Реестр методик и расчёт через сервис

**Цель:** пользователь выбирает не «формулу», а методику с нормативной базой, версией,
областью применения и ограничениями; расчёт идёт через `CalculationService`, ядро не меняется.

**Задачи:**

1. `core/services/methodology_registry.py` — реестр: `MethodologyDescriptor` (id, название,
   версия, стандарт + пункт, область применения, требования к данным: min_n/тип ряда/единицы,
   входные параметры, ограничения применимости, нормативные ссылки, примечание
   «нормативно предписано / инженерная реализация») и `MethodologyRegistry`:
   `register`, `get`, `list`, `by_standard`, `check_applicability(dataset) -> ValidationResult`.
2. `core/services/handlers/` — адаптеры `context -> dict` (без математики), минимум для P0:
   `frequency_pearson3`, `frequency_kritsky_menkel`, `stats_parameters`, `homogeneity_full`,
   `trends_full`, `max_runoff`, `min_runoff`, `flow_duration`, `reservoir_regulation`.
   Каждый handler делегирует в существующие функции `core.stats.*` / `core.hydrorash.*`.
3. `core/services/bootstrap.py` — `build_container()`: регистрирует методики, handlers и
   валидаторы применимости в `CalculationService` и `ValidationService` (единая точка сборки).
4. `gui/tabs/tab_methodology.py` — список методик с нормативными ссылками, требованиями к данным
   и статусом применимости к текущему ряду; кнопка «Выполнить» → расчёт через сервисный слой.
5. `tools/run_methodology.py` — консольный прогон: `python tools/run_methodology.py --method
   frequency_pearson3 --file data.xlsx --post "Пост 1"` (проверка без GUI).
6. `tests/test_methodology_service.py` — эквивалентность: результат через `CalculationService`
   совпадает с прямым вызовом ядра (те же числа); неприменимая методика (короткий ряд) →
   `ValidationResult.is_valid == False` и заполненный `CalculationResult.metadata.error_message`.

**Критерии приёмки:**

- Каждая методика P0 запускается через `CalculationService.execute()` и возвращает
  `CalculationResult` со статусом `COMPLETED`.
- Расхождение с прямым вызовом ядра — 0 (сравнение в тесте).
- Методика с недостаточной длиной ряда не выполняется, а возвращает понятную ошибку
  с нормативной ссылкой.
- У каждой методики в реестре заполнены: стандарт, пункт, требования к данным, ограничения.

**Как проверяем:** `python -m pytest tests/test_methodology_service.py -q`,
`python tools/run_methodology.py --list`.

---

### Этап 4. Результаты, история и Provenance

**Цель:** результат — объект, а не число; через год можно открыть проект и понять, откуда взялось
конкретное значение.

**Задачи:**

1. `core/services/result_store.py` — хранение `CalculationResult` в рамках проекта, нумерация
   расчётов (`Calculation #1, #2, …`), поиск по id, выборка по методике/датасету/сценарию,
   `compare(result_a, result_b) -> diff` (для сообщения «результат изменился с 1180 до 1240 м³/с
   на +5.1 %» с указанием изменившегося входа).
2. Provenance: `provenance_chain(result) -> list[ProvenanceStep]` — цепочка «расчёт ← методика
   (версия) ← датасет (число лет) ← качество данных (оценка) ← параметры (Cv, Cs, …) ← сценарий ←
   версия движка (`version.VERSION_FULL`)». Шаги сериализуются в `.hsp`.
3. `gui/tabs/tab_results.py` — таблица результатов (методика, дата, ключевые значения, статус
   валидации) + кнопка/клик «Откуда это число?» → диалог с цепочкой provenance.
4. `tests/test_result_store.py` — сохранение/выборка результатов, корректная нумерация,
   provenance-цепочка содержит версию движка и оценку качества, `compare` на изменённом
   параметре даёт ожидаемую разницу.

**Критерии приёмки:**

- Любой результат в GUI можно «раскрыть» до полной цепочки получения.
- История расчётов сохраняется в `.hsp` и восстанавливается после перезапуска приложения.
- Тест на `compare` показывает изменение значения и причину (изменённый вход).

**Как проверяем:** `python -m pytest tests/test_result_store.py -q` + в GUI: расчёт → изменение
параметра → повторный расчёт → отображение «было/стало».

---

### Этап 5. Сценарии и их сравнение

**Цель:** «а что будет, если условия изменятся?» — без ручного пересчёта всего.

**Задачи:**

1. `core/services/scenario_service.py` — CRUD сценариев в проекте: `create`, `clone`, `update`,
   `archive`, `list`; наследование от базового (`parent_scenario_id`); переопределение
   параметров (`DatasetType.EXTENDED/SYNTHETIC` — например, маловодный год) и входных параметров;
   `run(scenario, methodology) -> CalculationResult` через `CalculationService`;
   `compare(scenarios) -> DataFrame` (Параметр / Базовый / Сценарий A / Сценарий B …).
2. `gui/tabs/tab_scenarios.py` — список сценариев, редактор параметров, кнопка «Рассчитать»,
   таблица сравнения и график изменения результата (стиль — `gui/plot_style.py`).
3. `tests/test_scenario_service.py` — клонирование не меняет оригинал; изменение параметра даёт
   иной результат; таблица сравнения содержит все сценарии и совпадает с результатами расчётов.

**Критерии приёмки:**

- Сценарий можно создать, рассчитать и сравнить с базовым (таблица + график).
- Клонирование сценария не изменяет исходный (проверяется тестом).
- Сценарии сохраняются в `.hsp` и восстанавливаются.

**Как проверяем:** `python -m pytest tests/test_scenario_service.py -q` + ручной сценарий в GUI
(Базовый → «Маловодный год» → сравнение).

---

### Этап 6. Инженерный отчёт из проекта

**Цель:** «Сформировать отчёт» — и на выходе готовый инженерный документ, а не набор цифр.

**Задачи:**

1. `core/services/report_service.py` — сборка отчёта из проекта по 13 разделам концепции:
   1) исходные данные; 2) качество данных; 3) нормативная методика; 4) исходные параметры;
   5) формулы/алгоритм; 6) расчёт; 7) проверки; 8) графики; 9) таблицы; 10) сценарии;
   11) итоговые значения; 12) предупреждения; 13) вывод.
2. Источники разделов: `DataQualityReport`, `MethodologyDescriptor` (нормативные ссылки),
   `CalculationResult` + provenance, `ValidationResult`, фигуры matplotlib,
   таблицы сравнения сценариев, `update_checker`/`version` для штампа версии.
3. Экспорт (формат — см. «Открытые решения», п. 8.1): предпросмотр в GUI +
   сохранение файла отчёта в папку проекта (`reports/` в `.hsp`).
4. `gui/tabs/tab_report.py` — параметры отчёта (что включать: сценарии/графики/проверки),
   кнопка «Сформировать», предпросмотр, «Сохранить как…».
5. `tests/test_report_service.py` — отчёт содержит все 13 разделов и ключевые значения
   (Qср, Cv, Cs, расчётные расходы), число графиков = числу выбранных, отсутствие данных не ломает
   сборку (раздел помечается «нет данных»).

**Критерии приёмки:**

- На проекте с одним расчётом отчёт содержит 13 разделов, все числа совпадают с результатами
  в GUI.
- Отчёт формируется < 5 с на ряде 50 лет (без учёта времени на графики — вне UI-потока).
- Формирование отчёта идёт в фоновом потоке (UI не подвисает).

**Как проверяем:** `python -m pytest tests/test_report_service.py -q` + ручная генерация отчёта
из GUI и проверка содержимого.

---

### Этап 7. Санитария GUI и сборки (выполняется параллельно этапам 1–6)

**Цель:** новые модули не превращают God class в неподдерживаемый монолит; сборка включает всё новое.

**Задачи:**

1. Вынести раздел «Данные и статистика» из `gui/main_window.py` в `gui/tabs/tab_data.py`
   (по образцу `gui/controller/data_controller.py`) — без изменения поведения.
2. Все новые тяжёлые расчёты (качество данных, методики, сценарии, отчёт) — через
   `gui/workers/calculation_workers.py` (`CalculationWorker`-наследники).
3. Заменить новые `except Exception` на конкретные типы; существующие 22 случая — по мере
   рефакторинга соответствующих методов (не «одним заходом»).
4. Новые строки интерфейса — через `t(key, fallback)` + ключи в `i18n/ru.json` и `i18n/en.json`.
5. Обновить сборку: `HydroSphere.spec`, `build.py`, `build_nuitka.py` — добавить
   `--hidden-import` для `core.services.*`, `core.domain.serialization`, `core.services.handlers.*`,
   `gui.tabs.*`.
6. Обновить документацию: `DOCS/changelog.md`, `DOCS/hsp_schema.md` (если схема расширяется),
   `DOCS/ГидроСтатистика_2026_ТехническоеОписание.md` (новая архитектура), `INSTRUCTION.md`
   (новые разделы навигации).

**Критерии приёмки:**

- `python build.py` собирает приложение, `dist/HydroSphere/HydroSphere.exe` запускается
  и содержит новые разделы (проверка на чистой машине/в новом каталоге).
- `python -m pytest tests -q` — зелёно; старые скрипты `test_*.py` в корне не деградировали.
- `python -m ruff check .` — без новых замечаний.

---

### Сводка этапов

| Этап | Содержание | Ключевые артефакты | Оценка |
|------|------------|--------------------|--------|
| 0 | Оживить каркас, тесты, коммит | `models.py` (fix), `methodology_registry.py`, `scenario_service.py`, `tests/test_domain_services.py` | ~0.5 дня |
| 1 | Проект и `.hsp` | `serialization.py`, `project_service.py`, `gui/tabs/tab_project.py`, `tests/test_project_service.py` | ~1–2 дня |
| 2 | Контроль качества данных | `data_quality_service.py`, `gui/tabs/tab_data_quality.py`, `tests/test_data_quality_service.py` | ~1–2 дня |
| 3 | Реестр методик + расчёт через сервис | `methodology_registry.py` (полный), `handlers/`, `bootstrap.py`, `tools/run_methodology.py`, `tests/test_methodology_service.py` | ~2–3 дня |
| 4 | Результаты + Provenance | `result_store.py`, `gui/tabs/tab_results.py`, `tests/test_result_store.py` | ~1–2 дня |
| 5 | Сценарии | `scenario_service.py` (полный), `gui/tabs/tab_scenarios.py`, `tests/test_scenario_service.py` | ~2 дня |
| 6 | Инженерный отчёт | `report_service.py`, `gui/tabs/tab_report.py`, `tests/test_report_service.py` | ~2–3 дня |
| 7 | Санитария GUI и сборки | `gui/tabs/tab_data.py`, воркеры, spec/build, документация | параллельно |

---

## 7. Definition of Done (общие правила для всех этапов)

1. Код соответствует соглашениям репозитория (ruff, line-length 100, типизация, docstring'и).
2. Математика не дублируется: сервисы вызывают существующие функции ядра.
3. Для каждого этапа есть pytest-тест(ы) в `tests/`, запускаемые без GUI.
4. Все ранее существовавшие тесты (`test_all_functions.py`, `test_sp_compliance.py`,
   `test_regression_critical.py`, `test_backwater.py`, `test_edge_cases.py`, `test_q.py`,
   `test_real_data.py`) не деградировали.
5. Новая функциональность доступна из GUI и не блокирует интерфейс (фоновые воркеры).
6. `DOCS/changelog.md` обновлён; при изменении формата — `DOCS/hsp_schema.md`.
7. Изменения закоммичены в ветку `global-implementation` (и, при готовности, в `main`).

---

## 8. Открытые решения (нужны ответы перед соответствующим этапом)

| # | Вопрос | Варианты | Влияет на |
|---|--------|----------|-----------|
| 8.1 | Формат инженерного отчёта | (а) `python-docx` → настоящий Word (новая зависимость в `requirements.txt`); (б) HTML с расширением `.doc` (без новых зависимостей); (в) `xlsx` + `txt` как сейчас | Этап 6 |
| 8.2 | Ветка и стратегия коммитов | (а) продолжать в `global-implementation`, затем мёрдж в `main`; (б) сразу в `main` | Этапы 0–6 |
| 8.3 | Каталог тестов | (а) новые тесты в `tests/` (старые скрипты в корне не трогаем); (б) перенести всё в `tests/` | Этапы 0–6 |
| 8.4 | Язык новых строк интерфейса | (а) русский + ключи i18n; (б) русский без i18n до реализации переключения языка | Этапы 1–6 |
| 8.5 | Кнопка «Сохранить проект» и автосохранение | (а) только явное сохранение; (б) + автосохранение в `%APPDATA%` | Этап 1 |
| 8.6 | Нужен ли `CalculationResult` для всех 17 существующих разделов сразу | (а) только для методик P0 (частоты, параметры, однородность, тренды, макс./мин. сток, FDC, регулирование); (б) для всех | Этапы 3–4 |

---

## 9. Риски и их снижение

| Риск | Следствие | Снижение |
|------|-----------|----------|
| P0-каркас untracked | Потеря работы при сбое/очистке | Этап 0 — коммит в первую очередь |
| `main_window.py` — God class (2897 строк) | Каждое новое окно увеличивает связанность | Новые экраны — только в `gui/tabs/`; вынос `tab_data` (этап 7) |
| Дублирование математики в сервисах | Расхождение результатов ядра и сервисов | Тесты эквивалентности (этап 3): сервис обязан давать те же числа |
| Расширение `.hsp` ломает старые файлы | Невозможно открыть проект | Tolerant-парсер + `schema_version` + предупреждение (этап 1) |
| Отсутствие GUI-тестов (`pytest-qt` не подключён) | Регрессии интерфейса | Разделять логику (сервисы) и UI: всё проверяемое — в `core/services`; UI — ручной чек-лист |
| Забыли `--hidden-import` для новых модулей | Падение собранного exe | Пункт 7.5 DoD + проверка сборки на этапе 7 |
| Расчёты в главном потоке | «Зависание» интерфейса | Воркеры для всех новых тяжёлых операций |

---

## 10. Что НЕ делаем в P0 (non-goals)

- Не переписываем `core/stats` и `core/hydrorash`.
- Не делаем GIS/DEM, калибровку, Monte Carlo, климатические сценарии (P1/P2).
- Не делаем 1D/2D гидравлическое моделирование (P3).
- Не придумываем нормативные ссылки: у каждой методики — только проверяемые документ/раздел/пункт,
  с явным разделением «нормативно предписано» и «инженерная реализация».
- Не внедряем обязательную телеметрию/облако.

---

## 11. Регрессионная защита

- Перед этапом 0: зафиксировать текущее состояние тестов (сколько PASS) как baseline.
- После каждого этапа: `python -m pytest tests -q` + прогон существующих скриптов
  (`python test_all_functions.py`, `python test_sp_compliance.py`,
  `python test_regression_critical.py`).
- Расчётные значения ядра (Qср, Cv, Cs, ординаты Крицкого-Менкеля, максимальные/минимальные
  расходы) считать «замороженными»: сервисный слой не имеет права их менять.

---

## 12. Нормативная база (для реестра методик)

| Стандарт | Содержание | Где используется |
|----------|-----------|------------------|
| СП 33-101-2003 | Определение основных гидрологических параметров (п. 5–8) | `stats/parameters.py`, `stats/frequency.py`, `hydrorash/max_runoff.py`, `hydrorash/minimal_runoff.py` |
| СП 482.1325800.2020 | Инженерные изыскания для строительства | `stats/report.py`, `stats/report_export.py` |
| СП 58.13330.2019 | Водохранилища, каналы и водоёмы | `hydrorash/reservoir_regulation.py`, `hydrorash/spillway.py` |
| СП 32.13330.2018 | Канализация. Наружные сети и сооружения | `hydrorash/rational_method.py` |
| СП 219.1325800.2020 | Системы водоотведения | `hydrorash/rational_method.py` |
| РД 52-26-2008 | Гидрометеорологические прогнозы | `hydrorash/regional_regressions.py` |

Реестр методик (этап 3) заполняется по этой таблице; для каждой методики указываются документ,
раздел/пункт, что именно регулирует, используемая формула, ограничения применимости.

---

## 13. Журнал изменений документа

| Дата | Версия | Изменение |
|------|--------|-----------|
| 21.09.2026 | 1.0 | Первая редакция ТЗ: концепция из `DOCS/Привет.docx`, gap-анализ кода, этапы P0 с критериями приёмки, открытые решения |
| 21.09.2026 | 1.2 | Этап 1 выполнен: проект (.hsp) с сохранением/открытием, раздел «Проект» в GUI (18 разделов)
| 21.09.2026 | 1.1 | Этап 0 выполнен: каркас домена и сервисов работает (коммиты `eb3b2b9`, `3790091`); добавлены реестр методик (12 методик), сервис сценариев и 28 тестов в `tests/` |

