# HydroSphere Project File (.hsp) — Схема

Файл проекта HydroSphere — JSON-формат для сохранения/загрузки
состояния инженерной работы пользователя. Реализация:
`core/services/project_service.py`, `core/domain/serialization.py`.

Файл пишется атомарно (временный файл + замена) в кодировке UTF-8.

## Структура

```json
{
  "schema_version": "1.0",
  "title": "Название проекта",
  "description": "Описание проекта",
  "status": "draft",
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "created_at": "2026-08-30T12:00:00",
  "updated_at": "2026-09-21T10:15:00",
  "data_source": "имя_файла.xlsx",
  "data_path": "абсолютный/относительный/путь/к/файлу.xlsx",
  "selected_post": "Пост 10001",
  "region": "central_russia",
  "parameters": {
    "Q_mean": 150.2,
    "Cv": 0.25,
    "Cs": 0.12
  },
  "metadata": {},
  "datasets": [
    {
      "id": "...",
      "name": "Пост 10001",
      "dataset_type": "observed",
      "unit": "м³/с",
      "location": "",
      "catchment_area_km2": null,
      "data": {"1990": 120.5, "1991": 115.2}
    }
  ],
  "calculations": [
    {
      "id": "...",
      "metadata": {
        "methodology": {"name": "frequency_pearson3", "version": "1.0"},
        "input_dataset_ids": ["..."],
        "input_parameters": {},
        "status": "completed"
      },
      "output_data": {"Q": 1240.0},
      "warnings": []
    }
  ],
  "scenarios": [
    {
      "id": "...",
      "name": "Маловодный год",
      "project_id": "...",
      "parameters": {"demand": 350.0},
      "description": "",
      "status": "draft"
    }
  ],
  "reports": [
    {
      "type": "txt",
      "path": "output/report_post_10001.txt"
    }
  ]
}
```

## Обязательные поля

- `schema_version` — версия формата (текущая: "1.0")
- `title` — название проекта
- `data_source` — имя файла данных (xlsx)

## Опциональные поля

- `description` — описание проекта
- `status` — статус жизненного цикла (`draft` / `active` / `archived` / `completed`)
- `project_id` — идентификатор проекта (UUID)
- `created_at`, `updated_at` — ISO 8601 timestamp
- `data_path` — путь к файлу данных
- `selected_post` — выбранный пост
- `region` — регион (ключ из `core/hydrorash/regional_regressions.py:REGIONAL_COEFFICIENTS`)
- `parameters` — параметры проекта (Qср, Cv, Cs, ...)
- `metadata` — произвольные метаданные проекта
- `datasets` — наборы данных: год (строка) → значение; тип (`observed` / `calculated` / `synthetic` / `extended` / `composite` / `historical`)
- `calculations` — сохранённые результаты расчётов
- `scenarios` — сценарии (раздел «Сценарии», этап 5) со связью `parent_scenario_id`
- `reports` — сгенерированные отчёты

## Версионирование

При несовпадении `schema_version` файл открывается с предупреждением.
Парсер максимально tolerant: отсутствующие поля заполняются значениями по умолчанию,
неизвестные разделы игнорируются, нечитаемые записи пропускаются с предупреждением.

## Совместимость

Файл `sample_project.hsp` в корне репозитория — минимальный пример
(`title`, `data_source`, `parameters`); открывается корректно.