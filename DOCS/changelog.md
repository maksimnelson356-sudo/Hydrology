# Changelog — HydroSphere

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