# Changelog — ГидроСтатика 2026

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