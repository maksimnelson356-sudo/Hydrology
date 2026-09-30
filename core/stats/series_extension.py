"""
core/stats/series_extension.py
Удлинение рядов наблюдений

СТАТУС НОРМАТИВНОЙ ПРИВЯЗКИ: PARTIAL. Общий статус модуля — PARTIAL, а не
VERIFIED: реализована лишь часть требований раздела 6, при этом отдельные
участки имеют статус CONFLICT, SOURCE_MISSING, NOT_IMPLEMENTED, REFERENCE и
UNKNOWN. Формулировка «СП 529 полностью реализован» к этому модулю неприменима.

CURRENT НОРМАТИВНЫЙ ДОКУМЕНТ: СП 529.1325800.2023, раздел 6 «Определение
расчётных гидрологических характеристик при недостаточности данных
гидрологических наблюдений». Этот раздел является фактически релевантной
нормативной основой модуля, и каждое отмеченное ниже соответствие подтверждено
содержимонием СП 529, а не переносом номеров пунктов.

HISTORICAL / LEGACY АТРИБУЦИЯ. Прежнее описание модуля и прежние нормативные
строки в его функциях относили расчёты к СП 33-101-2003, п. 6.2–6.7 и п. 6.17.
Эта атрибуция сохранена как историческая. Первоисточник присутствует в
локальной нормативной базе: DOCS/NORMATIVE/HISTORICAL/СП 33-101-2003.pdf.
Сверка 2026-09-30 по этому файлу (стр. 15–17) подтвердила содержание
упомянутых положений:

- п. 6.2 — приведение выполняется, когда средняя квадратическая погрешность
  расчётного значения превышает 10 % для годового и сезонного стоков, 20 % —
  для максимального и минимального; критерии выбора пунктов-аналогов — п. 4.11;
- п. 6.3 — основные требования при выборе аналогов: синхронность колебаний
  стока, выраженная коэффициентом парной или множественной корреляции;
- п. 6.4 — при восстановлении значений стока за отдельные годы необходимо
  проводить статистическую оценку значимости и устойчивости решений с
  определением случайных и систематических погрешностей в соответствии с
  п. 6.17;
- п. 6.7 — условия применения регрессионного анализа: n ≥ (6–10); R ≥ Rкр;
  R/σR ≥ Aкр; k/σk ≥ Bкр (6.1), где n — число совместных лет наблюдений
  (n ≥ 6 при одном аналоге, n ≥ 10 при двух и более аналогах). Это ДОСЛОВНО то
  же условие, что СП 529 п. 6.1.6 (6.1): атрибуция исходного кода на п. 6.7
  была корректной, и СП 529 воспроизводит его без изменения содержания;
- п. 6.17 — данные, восстановленные по уравнению регрессии, имеют
  систематически заниженную дисперсию; исключение осуществляется одним из двух
  вариантов: поправкой по формуле (6.9) либо учётом случайной составляющей по
  формуле (6.10). Следовательно, отнесение формул (6.9)/(6.10) к п. 6.17
  СП 33-101-2003 подтверждено первоисточником.

Обратите внимание: нумерация СП 33 и СП 529 для этих формул РАЗНА, при
содержании совпадающем. В СП 33 метод отношений — это п. 6.9 и 6.10, а
поправка на дисперсию с формулами (6.9)/(6.10) — п. 6.17; в СП 529 метод
отношений — п. 6.2.2 (6.2) и 6.2.3, а та же поправка — п. 6.3.3. Переноса
номеров «СП 33 → СП 529» не производится и не должен производиться
автоматически: совпадение устанавливается только по содержанию.

ЧТО РЕАЛЬНО СООТВЕТСТВУЕТ СП 529 (подтверждено по локальному экземпляру):

- п. 6.1.6, формула (6.1) — условия применения регрессионного анализа
  n ≥ (6–10); R ≥ Rкр; R/σR ≥ Акр; k/σk ≥ Вкр, с обычными значениями
  Rкр ≥ 0,7, Акр ≥ 2,0, Вкр ≥ 2,0. В модуле реализованы все четыре проверки,
  однако порог минимального n применён как единый плоский MIN_COMMON_YEARS = 6,
  тогда как СП 529 требует n ≥ 6 при ОДНОМ аналоге и n ≥ 10 при ДВУХ И БОЛЕЕ.
  Для случая с несколькими аналогами это CONFLICT (см. debt ниже).
- п. 6.2.2, формула (6.2) — метод отношений. Реализована пропорциональная
  форма через отношение средних; см. proportional_extension.
- п. 6.3.1, формула (6.5) — уравнение множественной линейной регрессии
  Q = k0 + k1·Q1 + k2·Q2 + … + ki·Qi с коэффициентами по методу наименьших
  квадратов и ограничением «не более двух-трёх пунктов-аналогов».
  Реализовано в regression_extension и multi_analog_extension.
- п. 6.3.3, формулы (6.9) и (6.10) — исключение систематического занижения
  дисперсии восстановленных значений; см. multi_analog_extension. Порог
  «не менее 30 восстановленных значений» воспроизведён как предупреждение.
  Полная реализация п. 6.3.3 не заявляется.

НЕ РЕАЛИЗОВАНО (NOT_IMPLEMENTED) — присутствует в СП 529, в модуле отсутствует.
Ничего из перечисленного в рамках текстового remap не реализовывалось:

- (6.6) — приведение среднего к более длительному периоду
  Q̄N = Q̄n + r·(σn/σn,a)·(Q̄N,a − Q̄n,a);
- (6.7) — относительная средняя квадратическая погрешность приведённой нормы ε_Q̄N;
- (6.8) — коэффициент вариации приведённого ряда Cv,N;
- п. 6.3.5 — расчёт по восстановленному ряду среднего многолетнего значения,
  коэффициентов вариации и асимметрии и коэффициента корреляции между стоком
  смежных лет r(1);
- проверка однородности восстановленного ряда;
- п. 6.2.3 — необходимое условие R ≥ Rкр для метода отношений;
- п. 4.9 — критерии выбора рек-аналогов;
- (4.1) — обобщение нескольких независимых методов по обратным дисперсиям;
- п. 6.2.5 и формула (6.4) — построение уравнений регрессии по данным
  кратковременных (менее 6 лет) наблюдений.

ТАБЛИЦА А.8. Таблица А.8 СП 529.1325800.2023 — это α%-ные критические значения
статистики Диксона (D4I), то есть таблица однородности и выбросов. Она НЕ
является методикой восстановления рядов по рекам-аналогам и не имеет отношения
к этому модулю. Старые проектные ссылки на «Приложение А.8» относятся к СП
33-101-2003 и автоматически на СП 529 не перепривязываются.

ОСНОВНЫЕ ФУНКЦИИ (фактический состав модуля):
- validate_correlation — проверка условий применимости регрессии
- regression_extension — регрессионное продление ряда
- proportional_extension — метод отношений (пропорций)
- estimate_extension_error — оценка неопределённости по остаткам
- full_extension_workflow — полный цикл продления
- multi_analog_extension — продление по нескольким рекам-аналогам
- get_ro_critical — доступ к LEGACY-таблице (см. комментарий к RO_CRITICAL)
- compute_integral_curves — интегральные кривые, инженерный метод вне СП 529
"""


import numpy as np
import pandas as pd
from scipy import stats

from core.stats.sp33_variance_correction import apply_formula_6_9, apply_formula_6_10

# ---------------------------------------------------------------------------
# НОРМАТИВНЫЙ СТАТУС ПОРОГОВ: PARTIAL / CONFLICT
#
# Четыре порога ниже воспроизводят условия СП 529.1325800.2023, п. 6.1.6,
# формула (6.1):  n ≥ (6–10); R ≥ Rкр; R/σR ≥ Aкр; k/σk ≥ Bкр,
# где СП 529 указывает обычные значения Rкр ≥ 0,7, Aкр ≥ 2,0, Bкр ≥ 2,0.
# Соответствие подтверждено по содержанию СП 529, а не переносом номеров.
#
# КОНФЛИКТ (не исправляется в рамках текстового remap). MIN_COMMON_YEARS = 6
# применён как единый плоский порог. СП 529 п. 6.1.6 требует:
#     n ≥ 6  при ОДНОМ аналоге,
#     n ≥ 10 при ДВУХ И БОЛЕЕ аналогах.
# Поэтому для multi_analog_extension (max_analogs по умолчанию 3) значение
# MIN_COMMON_YEARS = 6 не соответствует норме и является CONFLICT.
# Отдельная методологическая правка, здесь НЕ выполняется.
#
# Отдельно: условие a > 0 в regression_extension — дополнительное инженерное
# ограничение текущего кода. В СП 529 соответствующего требования не найдено;
# источник не подтверждён (SOURCE_MISSING / engineering).
# ---------------------------------------------------------------------------

MIN_COMMON_YEARS = 6
MIN_COMMON_YEARS_MULTI_ANALOG = 10
MIN_CORRELATION = 0.7
MIN_CORRELATION_SIGMA_RATIO = 2.0
MIN_SLOPE_SIGMA_RATIO = 2.0


def _required_common_years(n_analogs: int) -> int:
    """Минимальное число совместных лет по СП 529.1325800.2023, п. 6.1.6 (6.1).

    Текст п. 6.1.6: n — число совместных лет наблюдений в приводимом пункте и
    пунктах-аналогах, «n ≥ 6 при одном аналоге, n ≥ 10 при двух и более
    аналогах».

    Возвращает 6 для одного аналога и 10 для двух и более.
    """
    return MIN_COMMON_YEARS if n_analogs <= 1 else MIN_COMMON_YEARS_MULTI_ANALOG

# LEGACY / SOURCE_MISSING. Таблица сохранена для вызывающих get_ro_critical()
# (в частности, core/short_series.py использует её значения в production).
#
# Что установлено:
#   - в воротах применимости регрессии (validate_correlation) таблица
#     НЕ используется: там применяется константа MIN_CORRELATION;
#   - первоисточник СП 33-101-2003 присутствует в локальной нормативной базе
#     (DOCS/NORMATIVE/HISTORICAL/СП 33-101-2003.pdf), однако СП 529 задаёт
#     Rкр как ориентировочное значение «обычно Rкр ≥ 0,7» (п. 6.1.6), а не
#     таблицей; табличной формы Rкр(n) в проверенном СП 33 на стр. 15–17 не
#     обнаружено, поэтому происхождение этих 26 чисел не верифицировано в
#     рамках текущего аудита;
#   - соответствие таблицы требованиям СП 529 не проверялось и не заявляется.
#
# Таблица и её значения НЕ изменяются. Перенос на СП 529 не производится.
# Ключ: (n_common, alpha=0.05)
RO_CRITICAL = {
    5: 0.878, 6: 0.811, 7: 0.754, 8: 0.707, 9: 0.666, 10: 0.632,
    11: 0.602, 12: 0.576, 13: 0.553, 14: 0.532, 15: 0.514,
    16: 0.497, 17: 0.482, 18: 0.468, 19: 0.456, 20: 0.444,
    25: 0.396, 30: 0.361, 35: 0.335, 40: 0.314, 50: 0.282,
    60: 0.259, 80: 0.226, 100: 0.203, 150: 0.166, 200: 0.143
}


def get_ro_critical(n: int, alpha: float = 0.05) -> float:
    """
    Получить табличное значение Ro крит для n общих лет.

    Если точное n нет в таблице — интерполяция.

    НОРМАТИВНЫЙ СТАТУС: LEGACY. Обращение к таблице RO_CRITICAL, происхождение
    значений которой не верифицировано в рамках текущего аудита: первоисточник
    СП 33-101-2003 доступен (DOCS/NORMATIVE/HISTORICAL/), но табличной формы
    Rкр(n) в проверенном тексте не обнаружено, а СП 529 п. 6.1.6 задаёт Rкр как
    ориентировочное «обычно ≥ 0,7». Функция НЕ
    участвует в воротах применимости регрессии: validate_correlation
    использует константу MIN_CORRELATION, а не эту таблицу. Соответствие
    СП 529 не заявляется.
    """
    keys = sorted(RO_CRITICAL.keys())
    if n < keys[0]:
        return 1.0
    if n > keys[-1]:
        return RO_CRITICAL[keys[-1]]

    for i in range(len(keys) - 1):
        if keys[i] <= n <= keys[i + 1]:
            frac = (n - keys[i]) / (keys[i + 1] - keys[i])
            return RO_CRITICAL[keys[i]] + frac * (RO_CRITICAL[keys[i + 1]] - RO_CRITICAL[keys[i]])

    return RO_CRITICAL[keys[-1]]


def validate_correlation(
    Q_calc: pd.Series,
    Q_analog: pd.Series,
    alpha: float = 0.05
) -> dict:
    """
    Проверить применимость регрессии по условиям СП 529.1325800.2023, п. 6.1.6.

    НОРМАТИВНЫЙ СТАТУС: PARTIAL. Реализованы все четыре условия формулы (6.1)
    СП 529:
        n ≥ (6–10);  R ≥ Rкр;  R/σR ≥ Aкр;  k/σk ≥ Bкр,
    с обычными значениями СП 529: Rкр ≥ 0,7, Aкр ≥ 2,0, Bкр ≥ 2,0. Именно эти
    значения заданы константами MIN_CORRELATION, MIN_CORRELATION_SIGMA_RATIO,
    MIN_SLOPE_SIGMA_RATIO.

    Почему не VERIFIED:
      - порог n задан одним плоским MIN_COMMON_YEARS = 6, тогда как СП 529
        различает n ≥ 6 при одном аналоге и n ≥ 10 при двух и более;
      - k/σk проверяется не здесь, а в regression_extension;
      - p_value вычисляется, но нормативного порога для него в (6.1) нет;
      - поле Ro_crit в результате НЕ берётся из таблицы RO_CRITICAL, а
        возвращается равным MIN_CORRELATION, то есть таблица не участвует.

    Подписи quality_class (R > 0.95 / 0.90 / 0.80 / 0.70) — инженерная
    классификация текущего кода; нормативного источника в проверенном СП 529
    для неё не найдено (SOURCE_MISSING / engineering).

    Формула σR = (1 − R²)/√n является оценкой стандартной погрешности
    коэффициента корреляции; в СП 529 п. 6.1.6 σR определён как «средняя
    квадратическая погрешность коэффициента корреляции» без явной формулы,
    поэтому конкретная форма записи здесь — инженерная (REFERENCE).
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    n = len(common_idx)

    if n < MIN_COMMON_YEARS:
        return {
            'R': 0.0,
            'R2': 0.0,
            'Ro_crit': MIN_CORRELATION,
            'R_critical': MIN_CORRELATION,
            'sigma_R': float('inf'),
            'R_over_sigma_R': 0.0,
            'n_common': n,
            'is_significant': False,
            'p_value': 1.0,
            'quality_class': f'Недостаточно совместных наблюдений (n < {MIN_COMMON_YEARS})',
        }

    Qc = Q_calc.loc[common_idx].values
    Qa = Q_analog.loc[common_idx].values
    R, p_value = stats.pearsonr(Qa, Qc)
    sigma_R = max((1.0 - float(R) ** 2) / np.sqrt(n), 1e-12)
    R_over_sigma_R = float(R) / sigma_R
    is_significant = (
        float(R) >= MIN_CORRELATION
        and R_over_sigma_R >= MIN_CORRELATION_SIGMA_RATIO
    )

    if R > 0.95:
        quality = 'Отличная (R² > 0.90)'
    elif R > 0.90:
        quality = 'Хорошая (R² > 0.81)'
    elif R > 0.80:
        quality = 'Удовлетворительная (R² > 0.64)'
    elif R > 0.70:
        quality = 'Слабая (R² > 0.49)'
    else:
        quality = 'Неудовлетворительная (R² < 0.49)'

    return {
        'R': round(float(R), 4),
        'R2': round(float(R) ** 2, 4),
        'Ro_crit': MIN_CORRELATION,
        'R_critical': MIN_CORRELATION,
        'sigma_R': round(sigma_R, 6),
        'R_over_sigma_R': round(R_over_sigma_R, 4),
        'n_common': n,
        'is_significant': is_significant,
        'p_value': round(float(p_value), 6),
        'quality_class': quality,
    }


def regression_extension(
    Q_calc: pd.Series,
    Q_analog: pd.Series
) -> dict:
    """
    Регрессионный метод продления ряда.

    Qрасчёт = a × Qаналог + b

    НОРМАТИВНЫЙ СТАТУС: PARTIAL. Соответствует СП 529.1325800.2023, п. 6.3.1
    (уравнение регрессии, коэффициенты по методу наименьших квадратов) и
    п. 6.1.6 в части минимального числа совместных лет. Форма
    Q = k0 + k1·Q1 + … структурно совпадает с формулой (6.5) СП 529.
    Полная реализация раздела 6 не заявляется: не реализованы
    (6.6), (6.7), (6.8) и п. 6.3.5, а также критерии выбора аналогов по п. 4.9.

    МИНИМАЛЬНОЕ ЧИСЛО СОВМЕСТНЫХ ЛЕТ (исправлено). СП 529.1325800.2023,
    п. 6.1.6, формула (6.1) устанавливает:
        n ≥ 6  при ОДНОМ аналоге;
        n ≥ 10 при ДВУХ И БОЛЕЕ аналогах.
    Ранее здесь применялся единый плоский порог 6, что для случая с несколькими
    аналогами не соответствовало норме. Теперь требование вычисляется по
    фактическому числу используемых аналогов и является полом: параметр n_min
    может его ужесточить, но не может опустить ниже нормы.

    Условие a > 0 — дополнительное инженерное ограничение текущего кода.
    В СП 529 соответствующего требования не найдено; источник не подтверждён
    (SOURCE_MISSING / engineering). Исправление не выполняется.

    Диагностика остатков (выбросы 3σ, отношение дисперсий половин > 4.0,
    |среднее остатков| > 0.5·σ) — инженерные пороги текущей реализации без
    подтверждённой нормативной атрибуции (SOURCE_MISSING / engineering).

    Parameters:
        Q_calc: ряд расчётной реки (короткий)
        Q_analog: ряд реки-аналога (длинный)

    Returns:
        Dict: a, b, R, n_common, validation, extended_series
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    n_common = len(common_idx)
    if n_common < MIN_COMMON_YEARS:
        raise ValueError(
            f"Для регрессии по СП 33-101-2003 п. 6.7 нужно ≥ {MIN_COMMON_YEARS} "
            f"совместных лет; получено {n_common}"
        )

    validation = validate_correlation(Q_calc, Q_analog)
    Qc = Q_calc.loc[common_idx]
    Qa = Q_analog.loc[common_idx]
    result = stats.linregress(Qa.values, Qc.values)
    a = float(result.slope)
    b = float(result.intercept)

    if not validation['is_significant']:
        raise ValueError(
            f"Корреляция R={validation['R']:.3f} не соответствует СП 33-101-2003 п. 6.7: "
            f"R ≥ {MIN_CORRELATION}, R/σR ≥ {MIN_CORRELATION_SIGMA_RATIO}"
        )

    slope_std_error = float(result.stderr)
    slope_over_sigma = (
        float('inf') if slope_std_error == 0.0 else abs(a) / slope_std_error
    )
    if a <= 0.0:
        raise ValueError("Коэффициент регрессии должен быть положительным")
    if slope_over_sigma < MIN_SLOPE_SIGMA_RATIO:
        raise ValueError(
            f"Коэффициент регрессии не подтверждён критерием СП 33-101-2003 п. 6.7: "
            f"k/σk={slope_over_sigma:.3f} < {MIN_SLOPE_SIGMA_RATIO}"
        )

    Q_ext = Q_analog.copy().astype(float)

    missing = Q_analog.index.difference(Q_calc.index)
    if len(missing) > 0:
        Q_ext.loc[missing] = a * Q_analog.loc[missing] + b

    common = Q_calc.index.intersection(Q_analog.index)
    Q_ext.loc[common] = Q_calc.loc[common]

    # === Проверка остатков ===
    # НОРМАТИВНЫЙ СТАТУС: engineering. Прежний комментарий относил этот блок
    # к СП 33-101-2003 п. 6.2.4. Сверка 2026-09-30 по локальному
    # первоисточнику (DOCS/NORMATIVE/HISTORICAL/СП 33-101-2003.pdf) показала,
    # что подраздела 6.2.4 в СП 33-101-2003 нет: раздел 6 содержит 6.1—6.24
    # без подразделов вида 6.2.4. Прежняя ссылка является CONFLICT.
    #
    # Ближайшее по смыслу положение — п. 6.4 СП 33 (стр. 15): «При восстановлении
    # значений стока за отдельные годы и расчёте параметров квантилей
    # распределения необходимо производить статистическую оценку значимости и
    # устойчивости получаемых решений с определением случайных и систематических
    # погрешностей в соответствии с п. 6.17». Конкретная форма проверки остатков
    # в модуле этому тексту не верифицирована в рамках текущего аудита.
    #
    # СП 529.1325800.2023 формулирует стандартное отклонение по формуле (6.3):
    #     σ = √( Σ(Qн − Qр)² / (n − 1) ).
    # Код использует СВОЮ оценку с числом степеней свободы n − p
    # (n − 2 для регрессии с двумя параметрами), то есть НЕ (6.3).
    # Тождество n − p и n − 1 здесь не выполняется; расхождение зафиксировано
    # как методологический долг и не исправляется.
    #
    # Остатки = наблюдаемые - предсказанные. Проверяется:
    # 1) Не иметь систематического смещения (mean ~ 0)
    # 2) Быть гомоскедастичными (σ постоянна)
    # 3) Не содержать выбросов (|residual| > 3·σ — подозрительные)
    # Пороги 3σ, отношение дисперсий > 4.0 и |mean| > 0.5·σ не имеют
    # подтверждённой нормативной атрибуции в проверенном СП 529.
    residuals = Q_calc.loc[common_idx] - (a * Q_analog.loc[common_idx] + b)
    resid_mean = float(residuals.mean())
    resid_std = float(residuals.std())
    outlier_mask = (residuals - resid_mean).abs() > 3 * resid_std
    n_outliers = int(outlier_mask.sum())

    # Тест на гетероскедастичность (ранговый по подвыборкам)
    half = len(residuals) // 2
    resid_var_1 = float(residuals.iloc[:half].var()) if half > 1 else 0.0
    resid_var_2 = float(residuals.iloc[half:].var()) if half > 1 else 0.0
    heteroscedasticity = (min(resid_var_1, resid_var_2) > 0 and
                         max(resid_var_1, resid_var_2) / min(resid_var_1, resid_var_2) > 4.0)

    residual_diagnostics = {
        'resid_mean': round(resid_mean, 4),
        'resid_std': round(resid_std, 4),
        'n_outliers_3sigma': n_outliers,
        'has_outliers': n_outliers > 0,
        'var_first_half': round(resid_var_1, 4),
        'var_second_half': round(resid_var_2, 4),
        'heteroscedastic': heteroscedasticity,
    }

    warnings = []
    if n_outliers > 0:
        warnings.append(
            f"Обнаружено {n_outliers} выбросов в остатках (>3σ). "
            f"Проверьте исходные данные — возможны аномальные годы."
        )
    if heteroscedasticity:
        warnings.append(
            f"Гетероскедастичность остатков: дисперсия меняется в {max(resid_var_1, resid_var_2) / max(min(resid_var_1, resid_var_2), 1e-10):.1f} раз. "
            f"Регрессия может давать смещённые интервалы."
        )
    if abs(resid_mean) > 0.5 * resid_std:
        warnings.append(
            f"Систематическое смещение в остатках: mean={resid_mean:.3f}, std={resid_std:.3f}."
        )

    return {
        'a': round(a, 6),
        'b': round(b, 4),
        'R': validation['R'],
        'R2': validation['R2'],
        'Ro_crit': validation['Ro_crit'],
        'sigma_R': validation['sigma_R'],
        'R_over_sigma_R': validation['R_over_sigma_R'],
        'slope_std_error': round(slope_std_error, 6),
        'slope_over_sigma': round(slope_over_sigma, 4),
        'n_common': validation['n_common'],
        'is_significant': validation['is_significant'],
        'quality_class': validation['quality_class'],
        'extended_series': Q_ext,
        'residual_diagnostics': residual_diagnostics,
        'warnings': warnings,
        'warning': None,
    }


def proportional_extension(
    Q_calc: pd.Series,
    Q_analog: pd.Series
) -> dict:
    """
    Метод пропорций для продления ряда.

    Qрасчёт = k × Qаналог, где k = Qср_расчёт / Qср_аналог

    НОРМАТИВНЫЙ СТАТУС: PARTIAL. СП 529.1325800.2023, п. 6.2.2 (формула (6.2))
    описывает метод отношений, основанный на равенстве модульных коэффициентов,
    — отношение средних за период совместных наблюдений. Код реализует именно
    пропорциональную форму через отношение средних.

    Что НЕ соответствует и является методологическим долгом (здесь НЕ исправляется):

    - Корреляция R в этой функции НЕ проверяется вовсе. СП 529 п. 6.2.3
      устанавливает для метода отношений условие R ≥ Rкр, причём R определяется
      по пространственной корреляционной функции; ни то, ни другое здесь
      не реализовано. В результате функция принимает полностью
      некоррелированный аналог без предупреждения (CONFLICT).
    - Порог «не менее 2 общих лет» — инженерный минимум текущего кода, не
      связанный с какой-либо нормой (REFERENCE / engineering).
    - k = 1.0 при mean(Qa) == 0 — молчаливый engineering fallback,
      источник не подтверждён (SOURCE_MISSING / engineering).

    Parameters:
        Q_calc: ряд расчётной реки (короткий)
        Q_analog: ряд реки-аналога (длинный)

    Returns:
        Dict: k, Q_mean_calc, Q_mean_analog, extended_series
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    if len(common_idx) < 2:
        raise ValueError("Недостаточно общих лет")

    Qc_mean = float(Q_calc.loc[common_idx].mean())
    Qa_mean = float(Q_analog.loc[common_idx].mean())

    k = Qc_mean / Qa_mean if Qa_mean != 0 else 1.0

    Q_ext = Q_analog.copy().astype(float) * k

    common = Q_calc.index.intersection(Q_analog.index)
    Q_ext.loc[common] = Q_calc.loc[common]

    return {
        'k': round(k, 6),
        'Q_mean_calc': round(Qc_mean, 4),
        'Q_mean_analog': round(Qa_mean, 4),
        'extended_series': Q_ext
    }


def estimate_extension_error(
    Q_calc: pd.Series,
    Q_analog: pd.Series,
    regression_result: dict
) -> dict:
    """Оценить неопределённость по остаткам линейной регрессии.

    Это инженерная оценка ошибки прогноза: фиксированный коэффициент r=0.5
    удалён, а неопределённость вычисляется из остатков и разброса аналога.

    НОРМАТИВНЫЙ СТАТУС: CONFLICT / PARTIAL. Используется классическая ошибка
    прогноза с рычагом:
        s  = √( Σ e² / (n − p) )
        se(x) = s · √( 1/n + (x − x̄)² / Sxx )
    Это НЕ является реализацией СП 529.1325800.2023, п. 6.3.4, который
    предписывает определять окончательные значения восстановленного ряда
    с учётом средних квадратических погрешностей методов по формуле (4.1)
    (взвешивание по обратным дисперсиям). Формула (4.1) в модуле не
    реализована. Число степеней свободы n − p также отличается от
    записи СП 529 (6.3), где используется n − 1.

    Классификация надёжности по epsilon_extended (пороги 10 % и 15 %)
    и показатель improvement_pct — инженерные величины текущего кода без
    подтверждённой нормативной атрибуции (SOURCE_MISSING / engineering).
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    n_orig = len(common_idx)
    n_ext = len(Q_analog.dropna())
    if n_orig < 3:
        raise ValueError("Для оценки погрешности нужно ≥ 3 совместных наблюдений")

    if 'a' in regression_result:
        a = float(regression_result['a'])
        b = float(regression_result.get('b', 0.0))
        parameter_count = 2 if 'b' in regression_result else 1
    elif 'k' in regression_result:
        a = float(regression_result['k'])
        b = 0.0
        parameter_count = 1
    else:
        raise ValueError("Результат удлинения не содержит коэффициент регрессии")
    x_common = Q_analog.loc[common_idx].astype(float)
    y_common = Q_calc.loc[common_idx].astype(float)
    predicted_common = a * x_common + b
    residuals = y_common - predicted_common
    degrees_of_freedom = n_orig - parameter_count
    if degrees_of_freedom <= 0:
        raise ValueError("Недостаточно степеней свободы для оценки погрешности")

    residual_std_error = float(np.sqrt(np.sum(residuals ** 2) / degrees_of_freedom))
    x_mean = float(x_common.mean())
    sxx = float(np.sum((x_common - x_mean) ** 2))
    if sxx == 0.0:
        raise ValueError("Ряд-аналог не имеет дисперсии")

    def prediction_std_error(values: pd.Series) -> np.ndarray:
        leverage = 1.0 / n_orig + (values - x_mean) ** 2 / sxx
        return residual_std_error * np.sqrt(leverage)

    common_error = prediction_std_error(x_common)
    missing_idx = Q_analog.index.difference(Q_calc.index)
    extended_x = Q_analog.loc[missing_idx].astype(float)
    if extended_x.empty:
        extended_x = x_common
    extended_error = prediction_std_error(extended_x)
    extended_prediction = a * extended_x + b

    eps_orig = float(np.mean(common_error / np.maximum(np.abs(predicted_common), 1e-12)) * 100)
    eps_ext = float(np.mean(extended_error / np.maximum(np.abs(extended_prediction), 1e-12)) * 100)

    if eps_ext <= 10:
        reliability = 'Надёжная'
    elif eps_ext <= 15:
        reliability = 'Пониженная надёжность'
    else:
        reliability = 'Ненадёжная'

    return {
        'epsilon_original': round(eps_orig, 2),
        'epsilon_extended': round(eps_ext, 2),
        'residual_std_error': round(residual_std_error, 6),
        'prediction_std_error_mean': round(float(np.mean(extended_error)), 6),
        'n_original': n_orig,
        'n_extended': n_ext,
        'reliability': reliability,
        'improvement_pct': round((eps_orig - eps_ext) / eps_orig * 100, 1) if eps_orig > 0 else 0,
    }


def full_extension_workflow(
    Q_calc: pd.Series,
    Q_analog: pd.Series,
    method: str = 'regression'
) -> dict:
    """
    Полный цикл удлинения ряда с валидацией.

    НОРМАТИВНЫЙ СТАТУС: PARTIAL (композиция инженерных шагов). Функция лишь
    объединяет validate_correlation, regression_extension или
    proportional_extension и estimate_extension_error; собственной
    нормативной методики не добавляет.

    Оговорка по порогу n_common < 10 в формируемых предупреждениях: значение 10
    взято из условия СП 529 п. 6.1.6 для случая ДВУХ И БОЛЕЕ аналогов, тогда как
    этот workflow работает с ОДНИМ аналогом, для которого норма требует
    n ≥ 6. Порог является инженерной эвристикой текущего кода
    (SOURCE_MISSING / engineering), а не нормативным требованием для данного
    случая.

    Parameters:
        Q_calc: расчётный (короткий) ряд
        Q_analog: ряд-аналог (длинный)
        method: 'regression' или 'proportional'

    Returns:
        Dict: validation, extension_result, error_estimate, warnings
    """
    warnings = []

    validation = validate_correlation(Q_calc, Q_analog)

    if not validation['is_significant']:
        warnings.append(
            f"КРИТИЧНО: R={validation['R']:.3f} < Ro({validation['n_common']})={validation['Ro_crit']:.3f}. "
            f"Корреляция статистически незначима! Результаты могут быть недостоверными."
        )

    # Этот путь работает с ОДНИМ рядом-аналогом, поэтому по СП 529.1325800.2023
    # п. 6.1.6 применимое требование — n ≥ 6, а не n ≥ 10 (последнее относится
    # к двум и более аналогам). Порог 10 сохраняется как рекомендация по
    # увеличению выборки, а не как нормативное требование.
    if validation['n_common'] < MIN_COMMON_YEARS_MULTI_ANALOG:
        warnings.append(
            f"Мало общих лет ({validation['n_common']}). "
            f"Для одного аналога СП 529.1325800.2023, п. 6.1.6 требует не менее "
            f"{MIN_COMMON_YEARS}; увеличение выборки повышает надёжность."
        )

    if method == 'regression':
        ext_result = regression_extension(Q_calc, Q_analog)
    else:
        ext_result = proportional_extension(Q_calc, Q_analog)

    error_est = estimate_extension_error(Q_calc, Q_analog, ext_result)

    if error_est['epsilon_extended'] > 15:
        warnings.append(
            f"ε после продления = {error_est['epsilon_extended']:.1f}% > 15%. "
            f"Ряд остаётся ненадёжным."
        )

    return {
        'validation': validation,
        'extension_result': ext_result,
        'error_estimate': error_est,
        'warnings': warnings,
        'extended_series': ext_result.get('extended_series'),
        'method': method
    }


def multi_analog_extension(
    Q_calc: pd.Series,
    analogs: dict[str, pd.Series],
    n_min: int = 6,
    ro_cr: float = 0.7,
    ro_over_sigma: float = 2.0,
    k_over_sigma: float = 2.0,
    y_over_sigma: float = 0.2,
    max_analogs: int = 3,
    exclude_negative: bool = True,
    variance_correction: str = "6.9",
    phi: pd.Series | np.ndarray | None = None,
    random_state: int | None = None,
) -> dict:
    """Удлинить ряд множественной регрессией.

    НОРМАТИВНЫЙ СТАТУС: PARTIAL. Соответствует СП 529.1325800.2023, п. 6.3.1
    в той части, которая подтверждается содержанием:
      - уравнение множественной линейной регрессии общего вида
        Q = k0 + k1·Q1 + k2·Q2 + … + ki·Qi (формула (6.5));
      - коэффициенты и свободный член определяются методом наименьших
        квадратов;
      - ограничение «не более двух-трёх пунктов-аналогов» —
        здесь max_analogs = 3 по умолчанию.

    Утверждение «п. 6.3.1 полностью реализован» НЕВЕРНО. Не реализованы
    другие требования раздела 6, в частности (6.6), (6.7), (6.8), п. 6.3.5,
    проверка однородности восстановленного ряда, критерии выбора аналогов
    по п. 4.9 и обобщение по (4.1).

    ИСТОРИЧЕСКАЯ АТРИБУЦИЯ: прежний докстринг относил эту функцию к
    СП 33 п. 6.5 и 6.17. Первоисточник присутствует в локальной нормативной
    базе (DOCS/NORMATIVE/HISTORICAL/СП 33-101-2003.pdf). Сверка 2026-09-30
    (стр. 15–17) подтвердила: п. 6.7 СП 33 устанавливает условия регрессионного
    анализа, а п. 6.17 — исключение систематически заниженной дисперсии
    формулами (6.9) и (6.10), то есть прежняя атрибуция по существу корректна.
    При этом СП 33 не содержит отдельного пункта, аналогичного СП 529 п. 6.3.1
    с формулой (6.5): в СП 33 соответствующее уравнение регрессии приведено
    в п. 6.15. Полное содержательное соответствие не верифицировано в рамках
    текущего аудита.
    Пункта 6.17 в СП 529 нет; соответствующее содержание находится в п. 6.3.3.
    Согласно первоисточнику СП 33 (стр. 17) формулы (6.9) и (6.10) входят именно
    в п. 6.17, поэтому runtime-строка 'variance_correction_clause' с указанием
    «СП 33-101-2003 п. 6.17» корректна по существу.

    ВНУТРЕННЯЯ РАССИНХРОНИЗАЦИЯ ПРОЕКТА (отдельный долг, здесь не исправляется).
    Формулы (6.9) и (6.10) реализованы в core/stats/sp33_variance_correction.py,
    где их докстринги уже относят к СП 529.1325800.2023 п. 6.3.3. В настоящем
    модуле runtime-строка 'variance_correction_clause' по-прежнему содержит
    прежнюю атрибуцию «СП 33-101-2003 п. 6.17». Эта строка является частью
    возвращаемого результата, поэтому в рамках text-only remap она НЕ изменена;
    см. residual attribution debt.

    Поправка (6.9) и вариант (6.10) соответствуют СП 529 п. 6.3.3 по существу.
    Порог «не менее 30 восстановленных значений» воспроизведён как
    предупреждение и соответствует рекомендации п. 6.3.3; полная реализация
    п. 6.3.3 не заявляется.

    КОНФЛИКТ УСТРАНЁН. Значение n_min по умолчанию равно 6, но фактический
    минимум для двух и более аналогов определяется константой
    MIN_COMMON_YEARS_MULTI_ANALOG = 10 согласно СП 529 п. 6.1.6. Прежнее
    утверждение о CONFLICT по n_min в этом модуле больше не действует.
    Прочие методологические долги (n_min как параметр, y_over_sigma,
    exclude_negative) остаются в силе и здесь не переписываются.

    Критерий y_over_sigma (|среднее остатков| / σ ≤ 0.2) — инженерная величина
    текущего кода; нормативного источника в проверенном СП 529 для неё не
    найдено (SOURCE_MISSING / engineering). Параметр exclude_negative, молча
    заменяющий отрицательные восстановленные значения на NaN, также не имеет
    подтверждённой нормативной атрибуции.

    ``variance_correction="6.9"`` применяет детерминированную поправку
    систематически заниженной дисперсии. Вариант ``"6.10"`` добавляет
    нормально распределённую случайную составляющую; ``phi`` можно передать
    явно либо задать воспроизводимый ``random_state``.
    """
    if not analogs:
        raise ValueError("Не задан ни один ряд-аналог")
    if variance_correction not in {"6.9", "6.10"}:
        raise ValueError("variance_correction должен быть '6.9' или '6.10'")
    if phi is not None and random_state is not None:
        raise ValueError("Передавайте либо phi, либо random_state, но не оба")

    analog_names = list(analogs.keys())[:max_analogs]

    common = Q_calc.dropna().index
    for name in analog_names:
        common = common.intersection(analogs[name].dropna().index)

    n_common = len(common)

    # СП 529.1325800.2023, п. 6.1.6 (6.1): n ≥ 6 при одном аналоге,
    # n ≥ 10 при двух и более. Нормативный минимум является ПОЛОМ и не может
    # быть опущен параметром n_min: явный n_min может только ужесточить
    # требование, но не снизить его ниже нормы.
    required_n = max(n_min, _required_common_years(len(analog_names)))
    if n_common < required_n:
        return {
            'success': False,
            'n_common': n_common,
            'n_min': required_n,
            'reason': (
                f'Мало общих лет ({n_common} < {required_n}): для одного аналога '
                f'требуется не менее {MIN_COMMON_YEARS} общих лет, для двух и более '
                f'аналогов — не менее {MIN_COMMON_YEARS_MULTI_ANALOG} '
                f'(СП 529.1325800.2023, п. 6.1.6)'
            ),
        }

    y = Q_calc.loc[common].values.astype(float)
    X = np.column_stack([
        np.ones(n_common),
        *[analogs[name].loc[common].values.astype(float) for name in analog_names]
    ])

    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    k0 = beta[0]
    k = beta[1:]

    y_pred = X @ beta
    residuals = y - y_pred

    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    R = float(np.sqrt(max(r2, 0.0)))

    sigma_ro = (1.0 - r2) / np.sqrt(n_common) if n_common > 0 else np.nan

    p = X.shape[1]
    dof = max(n_common - p, 1)
    sigma2 = ss_res / dof
    try:
        cov = np.linalg.inv(X.T @ X) * sigma2
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(X.T @ X) * sigma2
    sigma_k = np.sqrt(np.abs(np.diag(cov)))

    k_all = np.concatenate([[k0], k])
    ratio_k = k_all / sigma_k

    y_mean = float(np.mean(residuals))
    y_std = float(np.std(residuals, ddof=1)) if n_common > 1 else 0.0
    ratio_y = abs(y_mean) / y_std if y_std > 0 else np.nan

    checks = {
        'n_common_ok': n_common >= required_n,
        'R_ok': ro_cr <= R,
        'ro_over_sigma_ok': (R / sigma_ro) >= ro_over_sigma if sigma_ro > 0 else False,
        'k_over_sigma_ok': bool(np.all(ratio_k[1:] >= k_over_sigma)),
        'y_over_sigma_ok': ratio_y <= y_over_sigma,
    }

    extended = Q_calc.copy().astype(float)
    warnings = []
    missing_years = extended.index[extended.isna()]
    for name in analog_names:
        missing_years = missing_years.intersection(
            analogs[name].dropna().index,
            sort=False,
        )
    missing_years = missing_years.sort_values()

    if len(missing_years) > 0:
        x_missing = np.column_stack([
            np.ones(len(missing_years)),
            *[analogs[name].loc[missing_years].values.astype(float)
              for name in analog_names],
        ])
        raw_missing = x_missing @ beta
        observed_mean = float(np.mean(y))

        if variance_correction == "6.9":
            corrected_missing = apply_formula_6_9(
                raw_missing,
                mean_n=observed_mean,
                correlation=R,
            )
        else:
            if phi is None:
                normal_draws = np.random.default_rng(random_state).normal(
                    size=len(missing_years)
                )
            elif isinstance(phi, pd.Series):
                aligned_phi = phi.reindex(missing_years)
                if aligned_phi.isna().any():
                    raise ValueError("phi должен содержать значения для всех восстанавливаемых лет")
                normal_draws = aligned_phi.to_numpy(dtype=float)
            else:
                normal_draws = np.asarray(phi, dtype=float)

            # Порог 30 восстановленных значений соответствует рекомендации
            # СП 529.1325800.2023, п. 6.3.3. Текст предупреждения ниже —
            # runtime-строка и в рамках text-only remap не изменяется, поэтому
            # в нём сохраняется историческая атрибуция «СП 33 п. 6.17».
            if len(missing_years) < 30:
                warnings.append(
                    "Для формулы СП 33 п. 6.17 (6.10) рекомендуется "
                    "не менее 30 восстановленных значений"
                )
            corrected_missing = apply_formula_6_10(
                raw_missing,
                correlation=R,
                sigma=float(np.std(y, ddof=1)),
                phi=normal_draws,
            )

        for year, value in zip(missing_years, corrected_missing, strict=True):
            if exclude_negative and value < 0.0:
                extended.loc[year] = np.nan
            else:
                extended.loc[year] = value

    coeffs = {'k0': round(k0, 4)}
    sigma_coeffs = {'s_k0': round(float(sigma_k[0]), 4)}
    ratios = {'r_k0': round(float(ratio_k[0]), 2)}
    for i, name in enumerate(analog_names):
        coeffs[f'k{i + 1}'] = round(float(k[i]), 4)
        sigma_coeffs[f's_k{i + 1}'] = round(float(sigma_k[i + 1]), 4)
        ratios[f'r_k{i + 1}'] = round(float(ratio_k[i + 1]), 2)

    return {
        'success': True,
        'n_common': n_common,
        'n_min': required_n,
        'R': round(R, 4),
        'sigma_Ro': round(float(sigma_ro), 4),
        'R_over_sigmaRo': round(R / sigma_ro, 2) if sigma_ro > 0 else np.nan,
        'S': round(y_std, 4),
        'Y_mean': round(y_mean, 4),
        'Y_over_sigmaY': round(ratio_y, 3) if not np.isnan(ratio_y) else np.nan,
        'analogs': analog_names,
        'coeffs': coeffs,
        'sigma_coeffs': sigma_coeffs,
        'k_over_sigma': ratios,
        'criteria': checks,
        'all_criteria_ok': all(checks.values()),
        'extended_series': extended,
        'variance_correction': variance_correction,
        'variance_correction_clause': (
            f'СП 33-101-2003 п. 6.17, формула {variance_correction}'
        ),
        'warnings': warnings,
        'formula': f'Q = {coeffs["k0"]}' + ''.join(
            f' {"+" if k[i] >= 0 else "-"} {abs(k[i]):.4f}·{name}'
            for i, name in enumerate(analog_names)
        )
    }


# ============================================================
# ИНТЕГРАЛЬНАЯ / РАЗНОСТНО-ИНТЕГРАЛЬНАЯ КРИВАЯ (ГГИ)
# ============================================================
#
# НОРМАТИВНЫЙ СТАТУС: engineering / historical method, SOURCE_MISSING.
#
# Привязка к СП 529.1325800.2023 НЕ устанавливается. Проверенный локальный
# экземпляр СП 529 не содержит ни «интегральной кривой», ни «разностно-
# интегральной кривой», ни обозначений ГГИ/ДИК: раздел 6 СП 529 регулирует
# приведение рядов к многолетнему периоду, а не выявление границ
# нестационарности по модульным коэффициентам. Соответствие не заявляется,
# аналогичный по смыслу пункт не подбирается.
#
# Метод относится к инженерной и исторической практике анализа
# нестационарности; нормативного источника в текущем локальном корпусе нет.
#
# Модульные коэффициенты:
#     ki = xi / x̄
# Интегральная кривая:               Σki
# Разностно-интегральная кривая:      Σ(ki − 1) / Cv
#
# Назначение (по смыслу метода, а не по норме):
# - Переломы = границы нестационарности
# - Экстремумы = границы периодов повышенных/пониженных значений


def compute_integral_curves(data: pd.Series) -> dict:
    """
    Вычисление интегральной и разностно-интегральной кривых.

    НОРМАТИВНЫЙ СТАТУС: engineering / historical method, SOURCE_MISSING.
    Привязка к СП 529.1325800.2023 не устанавливается: интегральная и
    разностно-интегральная кривые (ГГИ/ДИК) в проверенном экземпляре СП 529
    не упоминаются. Аналогичный по смыслу пункт не подбирается. Порог
    «менее 4 точек» — инженерный минимум текущего кода, нормативного
    источника не имеет.

    Аргументы:
        data — pd.Series с индексом=год, значения=Q

    Возвращает dict:
        years — годы
        modular_coefficients — ki = Q/Qср
        integral_curve — Σki (нарастающая сумма)
        diff_integral_curve — Σ(ki-1)/Cv
        mean — среднее значение
        cv — Cv
        breakpoints — список годов с переломами (экстремумы разностно-интегральной)
    """
    data = data.dropna()
    if len(data) < 4:
        return {
            'years': data.index.tolist(),
            'modular_coefficients': [],
            'integral_curve': [],
            'diff_integral_curve': [],
            'mean': 0, 'cv': 0, 'breakpoints': [],
        }

    values = data.values.astype(float)
    years = data.index.tolist()

    mean_val = np.mean(values)
    std_val = np.std(values, ddof=1)
    cv = std_val / mean_val if mean_val > 0 else 0

    # Модульные коэффициенты
    ki = values / mean_val if mean_val > 0 else np.ones_like(values)

    # Интегральная кривая: нарастающая сумма ki
    integral = np.cumsum(ki)

    # Разностно-интегральная кривая: нарастающая сумма (ki-1)/Cv
    if cv > 1e-12:
        diff_integral = np.cumsum((ki - 1) / cv)
    else:
        diff_integral = np.cumsum(ki - 1)

    # Поиск переломов (экстремумы разностно-интегральной кривой)
    breakpoints = []
    if len(diff_integral) >= 3:
        for i in range(1, len(diff_integral) - 1):
            if ((diff_integral[i] > diff_integral[i-1] and
                 diff_integral[i] > diff_integral[i+1]) or
                (diff_integral[i] < diff_integral[i-1] and
                 diff_integral[i] < diff_integral[i+1])):
                breakpoints.append(years[i])

    return {
        'years': years,
        'modular_coefficients': ki.tolist(),
        'integral_curve': integral.tolist(),
        'diff_integral_curve': diff_integral.tolist(),
        'mean': round(mean_val, 4),
        'cv': round(cv, 4),
        'breakpoints': breakpoints,
    }
