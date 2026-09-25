# Матрица нормативной проверяемости HydroSphere

**Состояние на:** 2026-09-25
**Назначение:** отделить наличие формулы и regression-тестов от доказанной нормативной валидности.

## Как читать статусы

- **SOURCE_CHECKED** — пункт стандарта и реализация сопоставлены, есть автоматические тесты; независимый эталон ещё не подтверждён.
- **PARTIAL** — реализован только один из режимов/формул/областей методики.
- **ENGINEERING** — инженерная реализация без права заявлять нормативное соответствие.
- **UNVERIFIED** — формула, коэффициенты или применимость пока не подтверждены первичным/независимым источником.

Ни один метод в текущей версии не достиг уровня **GOLDEN_VALIDATED** (независимый официальный/сертифицированный пример) или **EXPERT_VALIDATED** (проверка специалистом и реальными данными). Статус `registry=true` означает, что методика зарегистрирована как нормативная, но не является доказательством корректности.

## Матрица

| ID | Registry | Источник / пункт | Реализация | Автоматические свидетельства | Статус | Следующее доказательство |
|---|---|---|---|---|---|---|
| `stats_parameters` | true | СП 33-101-2003, п. 5.1, 5.4–5.15 | `core/stats/parameters.py::calculate_statistical_parameters` | `test_normative_algorithms.py`, `test_normative_benchmarks.py`, `test_methodology_service.py` | PARTIAL | Hand-calculated benchmark добавлен; получить официальный/сертифицированный пример и проверить полный набор 5.4–5.15 |
| `frequency_pearson3` | true | СП 33-101-2003, п. 5.1–5.3 | `core/stats/frequency.py` | `test_all_functions.py`, `test_methodology_service.py` | SOURCE_CHECKED | Golden-примеры и сравнение с независимой реализацией |
| `frequency_kritsky_menkel` | true | СП 33-101-2003, п. 5.1–5.6 | `core/stats/frequency.py` | `test_all_functions.py`, `test_methodology_service.py` | SOURCE_CHECKED | Проверка таблиц/параметров и независимые ординаты |
| `homogeneity_full` | true | СП 33-101-2003, п. 4.7, прил. А.1–А.3 | `core/stats/homogeneity.py` | `test_all_functions.py`, `test_methodology_service.py` | SOURCE_CHECKED | Официальные примеры критериев и независимая проверка границ |
| `series_extension` | false | СП 33-101-2003, п. 6.2–6.7, 6.17 | `core/stats/series_extension.py`, `core/stats/sp33_variance_correction.py`, `core/stats/staged_series_extension.py::staged_multi_analog_extension` | `test_sp33_series_corrections.py`, `test_new_methodology_handlers.py`, `test_staged_series_extension.py` | PARTIAL | Получить raw analog series A.8 и добавить независимый golden-тест; проверить staged API на полном сценарии |
| `series_extension_staged` | false | СП 33-101-2003, п. 6.2–6.7, п. 6.17, Приложение А.8 | `core/services/handlers/staged_series_extension.py::handle_series_extension_staged`, `tools/run_methodology.py::load_staged_config` | `test_new_methodology_handlers.py`, `test_run_methodology_cli.py`, `test_staged_series_extension.py` | PARTIAL | Добавить raw analog series A.8 и полный golden-тест; проверить JSON-контракт в отдельном CLI-сценарии |
| `composite_curves` | true | СП 33-101-2003, п. 5.12, формулы 5.21–5.25 | `core/stats/composite_curves.py` | `test_normative_algorithms.py` | PARTIAL | Реализовать режимы 5.22/5.25 и получить официальный пример; отдельно подтвердить случай одного значения в год |
| `max_runoff` | true | СП 33-101-2003, п. 5.26–5.31 | `core/hydrorash/max_runoff.py` | `test_sp33_flow_limits.py`, `test_methodology_service.py` | PARTIAL | Проверить полную процедуру 5.26–5.31 на независимом максимальном ряду |
| `flood_hydrograph` | true | СП 33-101-2003, п. 5.32 | `core/hydrorash/flood_hydrograph.py` | `test_new_methodology_handlers.py`, `test_all_functions.py` | UNVERIFIED | Подтвердить форму/коэффициенты и сравнить с официальным примером |
| `ice_phenomena` | false | СП 33-101-2003, п. 5.44, 7.70–7.71; РД 52-26-2008 | `core/hydrorash/ice_phenomena.py` | `test_all_functions.py` | UNVERIFIED | Найти первичный источник формулы толщины и проверить коэффициенты |
| `flow_duration` | false | Инженерный метод FDC | `core/stats/flow_duration.py` | `test_methodology_service.py`, `test_all_functions.py` | ENGINEERING | Сравнить с независимой FDC-реализацией и определить область применения |
| `reservoir_regulation` | false | Метод Риппла | `core/hydrorash/reservoir_regulation.py` | `test_methodology_service.py`, `test_reservoir_scenario.py` | ENGINEERING | Проверить правило регулирования на проектном сценарии |
| `storage_yield` | false | Метод Риппла | `core/hydrorash/reservoir_regulation.py` | `test_methodology_service.py` | ENGINEERING | Сверить кривую «объём–отдача» с независимым расчётом |
| `trends_full` | false | Манн—Кендалл / Сен / Pettitt | `core/stats/trends.py` | `test_methodology_service.py`, `test_all_functions.py` | ENGINEERING | Проверить условия автокорреляции и границы методов |
| `min_runoff` | true | СП 33-101-2003, п. 5.41–5.43 | `core/hydrorash/min_runoff_extended.py` | `test_sp33_flow_limits.py`, `test_methodology_service.py` | PARTIAL | Подтвердить режимы 7/10/30 суток и независимые минимумы |
| `backwater` | true | СП 33-101-2003, п. 5.45, 7.69 | `core/hydrorash/backwater.py`, `core/services/backwater_profile_service.py` | `test_backwater_profile_service.py`, `test_new_methodology_handlers.py` | UNVERIFIED | Сравнить метод последовательных сечений с независимой гидравлической моделью |
| `spectral_hurst` | false | Метод R/S | `core/stats/spectral.py` | `test_extended_methodologies.py` | ENGINEERING | Сравнить с опубликованным R/S и проверить чувствительность к окну |
| `drought_spi` | false | McKee et al. / WMO SPI | `core/stats/drought.py` | `test_extended_methodologies.py` | PARTIAL | Реализовать/проверить полную WMO-нормировку и месячные испытательные ряды |
| `baseflow` | false | Boughton / Eckhardt / Lyne–Hollick | `core/stats/baseflow.py` | `test_extended_methodologies.py` | ENGINEERING | Сравнить с независимым разделением baseflow на суточном ряду |
| `confidence_bands` | false | Bootstrap-инженерная оценка | `core/stats/confidence_bands.py` | `test_extended_methodologies.py` | ENGINEERING | Зафиксировать seed/число выборок и сравнить с независимым bootstrap |
| `intra_annual` | false | HydroRash | `core/hydrorash/intra_annual.py` | `test_extended_methodologies.py` | ENGINEERING | Подтвердить границы водного года и сезонные суммы |
| `snowmelt` | false | РД 52-26-2008 | `core/hydrorash/snowmelt.py` | `test_extended_methodologies.py` | UNVERIFIED | Проверить коэффициенты и область применения РД |
| `spillway` | false | СП 290.1325800.2016 | `core/hydrorash/spillway.py` | `test_extended_methodologies.py` | UNVERIFIED | Проверить проектную схему и допущения по СП 290 |
| `ecological_flow` | false | Метод Тессмана | `core/hydrorash/ecological_flow.py` | `test_extended_methodologies.py` | UNVERIFIED | Подтвердить источник региональных α/β и независимый расчёт |

## Что уже доказано автоматически

1. Наличие публично сопоставленного пункта и символа в реестре.
2. Наличие прямых regression-тестов на формулы и граничные случаи.
3. Отсутствие регрессий в текущем наборе тестов.
4. JSON-сериализацию и доступность методов через `CalculationService`/CLI.

Это доказывает корректность реализации **в пределах выбранных примеров**, но не подтверждает соответствие всем требованиям стандарта.

## Первый независимый benchmark

- Fixture: `tests/fixtures/sp33_stats_parameters_hand_calc_v1.json`.
- Метод: `tests/test_normative_benchmarks.py`.
- Проверяются среднее, `std`, `Cv`, `Cs`, `r₁`, `λ₂`, `λ₃` и погрешность по формулам СП 33 п. 5.26–5.27.
- Fixture рассчитан вручную по формулам и не вызывает production-функцию при подготовке ожидаемых значений.
- Это **hand-calculated benchmark**, а не официальный или сертифицированный эталон.

## Следующий протокол доказательства

Для каждого `PARTIAL`, `UNVERIFIED` или `ENGINEERING`-метода:

1. Зафиксировать точную редакцию источника и страницу/формулу.
2. Получить независимый эталонный расчёт.
3. Создать golden fixture с входными данными, ожидаемым результатом и единицами.
4. Сравнить с отдельной реализацией, не вызывающей тестируемый код.
5. Проверить минимум один штатный, один граничный и один ошибочный сценарий.
6. Зафиксировать результат и отметить статус `GOLDEN_VALIDATED`.
7. Передать проверенный набор независимому гидрологу для `EXPERT_VALIDATED`.

## Журнал поиска официального эталона

Проверен публичный полный текст СП 33 и его Приложение А:

- `https://files.stroyinf.ru/Data2/1/4294815/4294815038.htm`
- `https://base.garant.ru/3924385/53f89421bbdaf741eb2d1ecc4ddb4c33/`

В Приложении А перечислены примеры A.1–A.15, но отдельного полного числового примера для базового расчёта `stats_parameters` с исходным рядом, `mean`, `Cv`, `Cs` и погрешностью ε не найдено. Примеры A.7–A.11 относятся к другим частям методики (максимальный сток, аналоги и восстановление рядов).

Найденный учебный пример на `studfile.net` (`n=31`, среднее `367`, `Cv≈0.26`) не принят: отсутствует полная исходная серия и не подтверждён официальный/сертифицированный статус. Он не используется как golden fixture.

**Вывод:** `stats_parameters` остаётся `PARTIAL`; hand-calculated benchmark подтверждает формулы, но не является нормативной сертификацией.

## Журнал проверки СП 33 Приложения А.8

Источник: `https://files.stroyinf.ru/Data2/1/4294815/4294815038.htm`, раздел А.8.

Опубликованный пример содержит:

- ряд р. Сьежа — д. Стан за 1971–1992 гг. (22 года);
- семь рек-аналогов и несколько последовательных уравнений регрессии;
- уравнения, коэффициенты корреляции, погрешности и объёмы эквивалентно-независимой информации;
- восстановленный ряд за 1882–1970 гг. и контрольные таблицы А.7–А.8.

Ограничения воспроизведения:

1. В тексте не приведены полные исходные погодовые ряды семи аналогов, поэтому восстановленные значения нельзя независимо воспроизвести только из стандарта.
2. A.8 использует последовательное применение нескольких уравнений на разных временных этапах. Базовый `multi_analog_extension` выполняет одно одновременное уравнение максимум для трёх аналогов; добавленный `staged_multi_analog_extension` поддерживает отдельные наборы аналогов, `fit_years`, `target_years`, пороги и коррекцию для каждого этапа.
3. A.8 задаёт для примера `Rкр = 0.60`, тогда как текущий обработчик использует базовый порог 0.70; staged API и CLI позволяют задать порог 0.60, но полный A.8 fixture ещё не выполнен.

**Вывод:** staged-workflow, service handler и CLI-конфигурация реализованы и покрыты синтетическими тестами, но A.8 всё ещё нельзя честно исполнить как golden-тест без исходных рядов аналогов и полного сценария A.8. Статус остаётся `PARTIAL`.

## Источники, с которыми уже сверялась реализация

- СП 33-101-2003: публичный текст `https://files.stroyinf.ru/Data2/1/4294815/4294815038.htm`
- СП 482.1325800.2020: публичный текст `https://meganorm.ru/Data2/1/4293720/4293720390.htm`

Публичная копия не заменяет официальный экземпляр стандарта и редакцию, действующую для конкретного проекта.
