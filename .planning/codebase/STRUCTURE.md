# Структура директорий и ключевые расположения

## Корневой уровень
```
Hydrolib/
├── .omo/                     # Данные планирования OpenCode и сессий
├── .planning/                # Артефакты GSD-планирования (созданы во время анализа)
│   └── codebase/             # Документы картирования кодовой базы (этот output)
├── core/                     # Ядро домена и прикладной логики
├── gui/                      # Графический пользовательский интерфейс (PyQt6)
├── tests/                    # Автоматизированный набор тестов
├── tools/                    # Утилиты командной строки и скрипты
├── DOCS/                     # Техническая документация
├── sample_data/              # Примеры данных (если есть)
├── requirements.txt          # Зависимости Python
├── pyproject.toml            # Конфигурация инструментов
├── README.md                 # Обзор проекта
├── version.py                # Информация о версии
└── build*.py                 # Различные скрипты сборки
```

## Модуль ядра (`core/`)
```
core/
├── __init__.py
├── domain/                   # Доменные модели и бизнес-сущности
│   ├── __init__.py
│   ├── models.py             # Базовые модели данных (Project, Dataset и т.д.)
│   └── serialization.py      # JSON-сериализация/десериализация
├── services/                 # Прикладные сервисы (оркестрация use case)
│   ├── __init__.py
│   ├── bootstrap.py          # Контейнер сервисов и внедрение зависимостей
│   ├── calculation_service.py # Главный оркестратор расчётов
│   ├── data_quality_service.py # Проверка и оценка качества данных
│   ├── methodology_registry.py # Регистрация и поиск обработчиков методик
│   ├── project_service.py    # Операции с файлами .hsp
│   ├── result_store.py       # Persistencia результатов расчётов
│   ├── scenario_service.py   # Управление сценариями
│   ├── validation_service.py # Валидация входных данных
│   └── handlers/             # Реализации отдельных методик
│       ├── __init__.py
│       ├── stats_parameters_handler.py
│       ├── frequency_pearson3_handler.py
│       ├── frequency_kritsky_menkel_handler.py
│       ├── homogeneity_full_handler.py
│       ├── trends_full_handler.py
│       ├── max_runoff_handler.py
│       ├── min_runoff_handler.py
│       ├── flow_duration_handler.py
│       └── reservoir_regulation_handler.py
├── stats/                    # Гидростатистические функции
│   ├── __init__.py
│   ├── frequency.py          # Анализ обеспеченности (Пирсон III и др.)
│   ├── parameters.py         # Расчёт статистических параметров
│   ├── homogeneity.py        # Проверка однородности
│   ├── trends.py             # Анализ трендов (Манн-Кендалл и др.)
│   ├── flow_duration.py      # Кривые длительностей стока
│   ├── baseflow.py           # Выделение базового стока
│   ├── drought.py            # Анализ засух
│   ├── spectral.py           # Спектральный анализ
│   ├── advanced_frequency.py # Продвинутые методы анализа обеспеченности
│   ├── composite_curves.py   # Анализ композитных кривых
│   ├── confidence_bands.py   # Расчёт доверительных интервалов
│   ├── critical_values.py    # Статистические критические значения
│   ├── data_loader.py        # Утилиты загрузки данных
│   ├── gts_integration.py    # Интеграция с ГТС
│   ├── kritsky_tables.py     # Таблицы Крицкого-Менкеля
│   ├── missing_data.py       # Обработка отсутствующих данных
│   ├── report.py             # Генерация отчётов
│   ├── report_export.py      # Экспорт отчётов
│   ├── series_extension.py   # Продолжение рядов
│   └── sheet_reader.py       # Чтение листов Excel/CSV
└── hydrorash/                # Гидравлические и русловые расчёты
    ├── __init__.py
    ├── backwater.py          # Расчёты кривых подпора
    ├── ecological_flow.py    # Расчёты экологических расходов
    ├── flood_hydrograph.py   # Анализ паводковых гидрографов
    ├── hydraulic_periods.py  # Анализ гидравлических периодов
    ├── ice_phenomena.py      # Расчёты ледостава и ледохода
    ├── intra_annual.py       # Внутригодское распределение
    ├── max_runoff.py         # Расчёты максимального стока/паводков
    ├── minimal_runoff.py     # Расчёты минимального стока
    ├── min_runoff_extended.py # Расширенный расчёт минимального стока
    ├── rational_method.py    # Метод рациональных формул для пиковых расходов
    ├── regional_regressions.py # Уравнения региональной регрессии
    ├── reservoir_regulation.py # Многолетнее регулирование стока водохранилищем
    ├── sedimentation.py      # Транспорт и отложение наносов
    ├── snowmelt.py           # Расчёты снегового стока
    ├── spillway.py           # Проектирование и анализ водосбросов
    ├── utils.py              # Гидравлические утилиты
    └── water_balance.py      # Расчёты водного баланса
```

## Модуль GUI (`gui/`)
```
gui/
├── __init__.py
├── main_frozen.py          # Точка входа PyInstaller
├── main_window.py          # Главное окно приложения и навигация
├── plot_style.py           # Единый стиль построения графиков
├── update_dialog.py        # Диалог проверки обновлений ПО
├── controller/             # MVC-контроллеры, опосредующие GUI и сервисы
│   ├── __init__.py
│   ├── data_controller.py  # Обработка взаимодействия, связанного с данными
│   ├── plot_controller.py  # Управление построением и визуализацией
│   └── widget_factory.py   # Создание и конфигурация GUI-виджетов
├── dialogs/                # Модальные диалоги
│   ├── __init__.py
│   └── data_quality_dialog.py # Оценка и отчётность по качеству данных
├── tabs/                   # Панели вкладочного интерфейса
│   ├── __init__.py
│   ├── tab_project.py      # Вкладка управления проектом
│   └── tab_methodology.py  # Вкладка выбора и выполнения методик
└── workers/                # Фоновые worker-потоки для долговременных операций
    ├── __init__.py
    ├── calculation_workers.py # Worker-потоки для расчётов
    └── thread_example.py   # Пример реализации потока
```

## Модуль тестов (`tests/`)
```
tests/
├── conftest.py             # Конфигурация и фикстуры pytest
├── test_data_quality_service.py # Тесты сервиса качества данных
├── test_domain_services.py   # Тесты доменных сервисов
├── test_methodology_service.py # Тесты сервиса методик
├── test_project_service.py   # Тесты сервиса проектов
└── test_result_store.py      # Тесты хранилища результатов
```

## Модуль утилит (`tools/`)
```
tools/
├── run_methodology.py      # Консольный запуск методик
├── build.py                # Основной скрипт сборки
├── build_installer.py      # Создание установщика
├── build_nuitka.py         # Компиляция Nuitka
├── build_visualization.py  # Сборка визуализации
├── create_template.py      # Утилита создания шаблонов
├── create_test_data.py     # Генерация тестовых данных
├── debug_startup.py        # Утилита отладки запуска
├── diploma_assessment.py   # Инструмент оценки дипломной работы
├── generate_file_inventory.py # Генератор инвентаря файлов
├── update_checker.py       # Утилита проверки обновлений
└── run_from_excel.py       # Утилита запуска из Excel
```

## Документация (`DOCS/`)
```
DOCS/
├── ROADMAP.md              # Дорожная карта разработки и критерии приёмки
├── changelog.md            # История изменений
├── hsp_schema.md           # Спецификация формата файлов .hsp
├── Анализ_соответствия_СП.md # Анализ соответствия СП (русский)
├── Анализ_соответствия_СП.pdf # PDF-версия анализа соответствия
├── ИТОГОВЫЙ_ОТЧЁТ_СП.md    # Итоговый отчёт (русский)
├── Итоговый_отчёт_СП.md    # Заглушка пустого итогового отчёта
└── Руководство пользователя.pdf # Руководство пользователя (русский)
```

## Ключевые соглашения об именовании
- **Модули Python**: snake_case (например, `data_quality_service.py`)
- **Классы**: PascalCase (например, `CalculationService`, `Project`)
- **Методы/Переменные**: snake_case (например, `calculate_statistics`, `data_loader`)
- **Константы**: UPPER_SNAKE_CASE (например, `DEFAULT_PRECISION`)
- **Файлы**: описательные имена, указывающие на назначение
- **Тесты**: `test_<имя_модуля>.py` или `test_<функциональность>.py`

## Важные файлы
- `gui/main_window.py` — Точка входа приложения (GUI)
- `tools/run_methodology.py` — Точка входа приложения (консоль)
- `core/services/bootstrap.py` — Инициализация контейнера сервисов
- `core/services/calculation_service.py` — Главный оркестратор расчётов
- `core/domain/models.py` — Базовые доменные модели
- `requirements.txt` — Спецификации зависимостей
- `pyproject.toml` — Конфигурация инструментов разработки

Обновлено: 2026-09-21