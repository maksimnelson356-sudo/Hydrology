# HydroSphere Project File (.hsp) — Схема

Файл проекта HydroSphere — JSON-формат для сохранения/загрузки
состояния расчётов пользователя.

## Структура

```json
{
  "schema_version": "1.0",
  "title": "Название проекта",
  "created_at": "2026-08-30T12:00:00",
  "data_source": "имя_файла.xlsx",
  "data_path": "абсолютный/относительный/путь/к/файлу.xlsx",
  "selected_post": "Пост 10001",
  "region": "central_russia",
  "parameters": {
    "Q_mean": 150.2,
    "Cv": 0.25,
    "Cs": 0.12,
    "sigma": 37.5,
    "n": 30,
    "r1": 0.15
  },
  "calculations": {
    "frequency_curve": {
      "curve_type": "kritsky_menkel",
      "P_values": [0.01, 0.1, 1.0, 5.0, 50.0],
      "Q_values": [350.0, 280.0, 220.0, 180.0, 145.0]
    },
    "trend": {
      "slope": -0.5,
      "p_value": 0.12,
      "significant": false
    },
    "homogeneity": {
      "D1N_emp": 0.05,
      "D1N_crit": 0.30,
      "is_homogeneous": true
    }
  },
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

- `created_at` — ISO 8601 timestamp
- `data_path` — путь к файлу данных
- `selected_post` — выбранный пост
- `region` — регион (ключ из `core/hydrorash/regional_regressions.py:REGIONAL_COEFFICIENTS`)
- `parameters` — статистики ряда
- `calculations` — результаты расчётов
- `reports` — сгенерированные отчёты

## Версионирование

При несовпадении `schema_version` файл открывается с предупреждением.
Парсер максимально tolerant: отсутствующие поля заполняются значениями по умолчанию.
