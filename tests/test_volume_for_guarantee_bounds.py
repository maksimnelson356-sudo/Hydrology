"""Границы бинарного поиска в mode='volume_for_guarantee': два исправленных дефекта.

ИСТОРИЯ. Оба дефекта найдены read-only-аудитом и воспроизведены на
production-коде инструментированием _calculate_regulation_year_metrics.

Дефект 1 — ЛОЖНОЕ ПРИНЯТИЕ ГРАНИЦЫ. best_V инициализировался значением
V_high, а условие выхода из цикла проверялось ДО тела. При V_upper < 1e6 м³
(порог max_drawdown < 0.0159 м³/с) тело не выполнялось ни разу, и наружу
уходила верхняя граница как «найденное решение»: состояние «решение не
найдено» было неотличимо от состояния «найдено ровно на границе».

Дефект 2 — АБСОЛЮТНЫЙ ДОПУСК. Критерий сходимости V_high - V_low < 1e6 м³
был чисто абсолютным, то есть для водохранилища объёмом менее 1 млн м³
допуск превышал сам объём. Это и порождало дефект 1, а также не позволяло
разрешить малые объёмы: истинный ответ 0 возвращался как ~0.9 млн м³.

ИСПРАВЛЕНИЕ. Критерий сходимости стал комбинированным —
max(1 м³, 1e-9 · max(|V_high|, |V_low|, 1)) — а решение дополнительно
проверяется фактическим достижением целевой гарантии в найденной точке.
Возврат границы без подтверждения теперь невозможен.

Значения допуска не введены заново: относительная 1e-9 уже применяется в
этом же модуле для допуска на сумму (Q−D), пол 1.0 — там же для защиты от
нулевого масштаба. Это численный критерий алгоритма, не нормативный параметр.

ЧТО НАМЕРЕННО НЕ ТРОГАЕТСЯ этим набором: множитель запаса верхней границы,
fallback, ветка `net < 0`, округление полей required_volume_*, Ripple и
методика массовой кривой.

НЕЗАВИСИМОСТЬ ОТ МНОЖИТЕЛЯ ГРАНИЦЫ. Тесты этого файла не имеют права
падать из-за конкретной величины запаса верхней границы. Read-only-аудит
установил, что `max_drawdown * T` — точная достаточная граница, а множитель
сверх неё — избыточный запас, не влияющий на ответ. Поэтому ожидания
сформулированы как «ответ равен НЕЗАВИСИМО вычисленному минимуму», а не как
«ответ равен такой-то доле границы». Ориентир для сверки —
_independent_min_capacity_m3 ниже; она переписывает модель баланса заново и
не обращается к production-хелперам.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.hydrorash import reservoir_regulation as rr

T_YEAR = 365 * 86400

# Ряд из production-кейса аудита: объём менее 1 млн м³.
SMALL_SERIES = np.array([0.1, 0.1, 0.1, 0.09])
SMALL_DEMAND = 0.096
SMALL_TRUE_MIN = 189_216.0  # 0.006 * T: минимум, при котором нет ни одного недобора

# Обычный случай из задания на аудит.
NORMAL_SERIES = np.array([30.0, 110.0, 130.0, 190.0])
NORMAL_DEMAND = 100.0
NORMAL_EXPECTED_MLN = 2207.5


def _independent_min_capacity_m3(series, demand, target_percent: float) -> float:
    """Минимальный V (м³), при котором достигается target_percent.

    НЕЗАВИСИМЫЙ ОРАКУЛ, а не слепок production. Модель баланса переписана
    заново по документированному виду (docstring multi_year_regulation,
    строка 460): S_{i+1} = min(V, max(0, S_i + (Q_i - D)·T)), а год без
    недобора считается годом, у которого raw < 0, где
    raw = S_i + (Q_i − D)·T.

    Верхняя граница собственной бисекции — суммарный АБСОЛЮТНЫЙ недобор
    sum(max(0, D − Q_i))·T. Он заведомо достаточен (весь накопленный дефицит
    закрывается запасом) и принципиально НЕ выводится из max_drawdown: иначе
    сверка была бы круговой и повторяла бы то же допущение, которое проверяет.
    """
    n = len(series)

    def guarantee_at(volume: float) -> float:
        storage = float(volume)
        deficit_years = 0
        for q in series:
            raw = storage + (float(q) - demand) * T_YEAR
            if raw < 0.0:
                deficit_years += 1
            storage = min(float(volume), max(0.0, raw))
        return 100.0 * (n - deficit_years) / n

    sufficient = sum(max(0.0, demand - float(q)) for q in series) * T_YEAR
    low, high = 0.0, max(sufficient, T_YEAR)
    assert guarantee_at(high) >= target_percent, (
        "независимая граница (суммарный абсолютный недобор) оказалась "
        "недостаточной — oracle сам непригоден"
    )
    for _ in range(200):
        mid = 0.5 * (low + high)
        if guarantee_at(mid) >= target_percent:
            high = mid
        else:
            low = mid
        if high - low <= max(1.0, 1e-9 * high):
            break
    return high


def _iterations(monkeypatch, series, demand, target=95.0, mode="volume_for_guarantee"):
    """Запустить production-функцию, посчитав итерации тела бинарного поиска.

    Инструментирование в памяти процесса: подменяется только helper, файлы
    не меняются. Число вызовов минус одна финальная проверка равно числу
    итераций тела цикла.

    Третьим элементом возвращается ТОЧНОЕ значение best_V, извлечённое из
    трассировки. Оно необходимо потому, что публичные поля округляются
    (required_volume_mln_m3 — с шагом 0.1 млн м³), и по ним нельзя судить о
    точности самого поиска. Округление публичных полей — отдельная задача и
    в этом наборе намеренно не проверяется.
    """
    real = rr._calculate_regulation_year_metrics
    seen: list[float] = []

    def traced(Q, d, cap, init, years=T_YEAR):
        seen.append(float(cap))
        return real(Q, d, cap, init, years)

    monkeypatch.setattr(rr, "_calculate_regulation_year_metrics", traced)
    result = rr.multi_year_regulation(series, demand, mode=mode, target_guarantee=target)
    return result, max(0, len(seen) - 1), seen[-1]


# ----------------------------------------------------------------------
# Test A — граница больше не выдаётся за найденное решение
# ----------------------------------------------------------------------
def test_small_reservoir_no_longer_returns_the_search_boundary(monkeypatch) -> None:
    """Production-кейс: функция возвращает истинный минимум, а не границу.

    До исправления: 0 итераций тела цикла и возврат верхней границы поиска
    как «найденного решения». Теперь поиск выполняется и сходится к
    независимо вычисленному минимуму.

    Свойство проверяется ПОЛОЖИТЕЛЬНО — ответ сверяется с oracle, а не
    отрицанием «не равно границе». Отрицательная форма была привязана к
    величине запаса границы: она знала только numerals и молчала бы, если
    бы production сменил множитель. Сверка с oracle переживает любой
    множитель и заодно сильнее: она ловит и границу вместо минимума, и
    любой другой промах по величине.
    """
    true_min = _independent_min_capacity_m3(SMALL_SERIES, SMALL_DEMAND, 95.0)
    assert true_min == pytest.approx(SMALL_TRUE_MIN, abs=1.0), (
        "oracle разошёлся с арифметикой минимума более чем на пол допуска — "
        "проверка непригодна"
    )

    result, iterations, best_v = _iterations(monkeypatch, SMALL_SERIES, SMALL_DEMAND)

    assert iterations > 0, (
        "бинарный поиск не выполнил ни одной итерации — наружу уйдёт граница"
    )
    assert best_v == pytest.approx(true_min, abs=1.0), (
        f"найдено {best_v:,.6f} м³ вместо минимума {true_min:,.6f} м³ — "
        "возвращена граница поиска, а не искомый объём"
    )
    assert result["required_volume_mln_m3"] == pytest.approx(0.2, abs=1e-9)
    assert result["guarantee_percent"] >= 95.0, "возвращённое значение обязано быть проверено"


def test_small_reservoir_search_actually_runs(monkeypatch) -> None:
    """Тело бинарного поиска выполняется ненулевое число раз.

    Это прямое измерение того, что раньше давало ноль итераций: условие выхода
    проверялось до тела, поэтому при V_upper < 1e6 м³ цикл не делал ничего.
    """
    _, iterations, _ = _iterations(monkeypatch, SMALL_SERIES, SMALL_DEMAND)

    assert iterations > 0, (
        "бинарный поиск не выполнил ни одной итерации — граница будет "
        "возвращена как найденное решение"
    )
    assert iterations < 50, "цикл должен сходиться, а не упираться в лимит итераций"


def test_insufficient_upper_bound_is_rejected_explicitly(monkeypatch) -> None:
    """Недостаточная верхняя граница даёт явный отказ, а не число.

    Граница искусственно занижается в 10^6 раз, после чего истинный минимум
    (189 216 м³) оказывается вне диапазона поиска. Функция обязана отказать,
    а не вернуть границу: возвращённое число не является подтверждённым
    минимальным требуемым объёмом.

    Проверка отказа построена на ФАКТИЧЕСКОМ достижении гарантии, а не на
    сравнении best_V == V_high, поэтому корректно отличает «решение найдено
    у границы» от «границы не хватило».
    """
    real_ripple = rr._ripple_mass_curve

    def crippled(q_d):
        result = dict(real_ripple(q_d))
        result["required_m3_s"] = result["required_m3_s"] * 1e-6
        return result

    monkeypatch.setattr(rr, "_ripple_mass_curve", crippled)

    with pytest.raises(ValueError, match="НЕ ПОДТВЕРЖДЕНА"):
        rr.multi_year_regulation(
            SMALL_SERIES, SMALL_DEMAND, mode="volume_for_guarantee",
            target_guarantee=95.0,
        )


def test_refusal_message_states_the_volume_is_not_confirmed() -> None:
    """Сообщение об отказе обязано говорить, что число не подтверждено.

    Иначе отказ неотличим от «ёмкость нулевая» или от обычного отказа по
    неверным входным данным, и пользователь не поймёт, что расчёт не выполнен.
    """
    real_ripple = rr._ripple_mass_curve

    def crippled(q_d):
        result = dict(real_ripple(q_d))
        result["required_m3_s"] = result["required_m3_s"] * 1e-6
        return result

    original = rr._ripple_mass_curve
    try:
        rr._ripple_mass_curve = crippled
        with pytest.raises(ValueError) as excinfo:
            rr.multi_year_regulation(
                SMALL_SERIES, SMALL_DEMAND, mode="volume_for_guarantee",
                target_guarantee=95.0,
            )
    finally:
        rr._ripple_mass_curve = original

    message = str(excinfo.value)
    assert "95" in message, "сообщение должно называть целевую гарантию"
    assert "недостаточной" in message or "не смог найти" in message
    assert "НЕ является подтверждённым" in message


# ----------------------------------------------------------------------
# Test B — обычный случай не сломан
# ----------------------------------------------------------------------
def test_normal_case_still_solves_and_matches_previous_value() -> None:
    """Штатный случай: результат методологически тот же, отказа нет.

    Ожидаемое значение 2 207.5 млн м³ получено ДО исправления при старом
    допуске 1e6. Расхождение означало бы, что изменён критерий сходимости
    самих вычислений, а не только граница поиска.
    """
    result = rr.multi_year_regulation(
        NORMAL_SERIES, NORMAL_DEMAND, mode="volume_for_guarantee",
        target_guarantee=95.0,
    )

    assert result["required_volume_mln_m3"] == pytest.approx(
        NORMAL_EXPECTED_MLN, abs=1e-9
    )
    assert result["guarantee_percent"] >= 95.0
    assert result["deficit_years"] == 0


def test_normal_case_search_really_executes(monkeypatch) -> None:
    """Поиск выполняется ненулевое число итераций и укладывается в лимит."""
    _, iterations, _ = _iterations(monkeypatch, NORMAL_SERIES, NORMAL_DEMAND)

    assert iterations > 0
    assert iterations <= 50


def test_normal_case_boundary_never_returned_verbatim(monkeypatch) -> None:
    """Возврат равен истинному минимуму, а не границе поиска.

    Раньше проверка выглядела как `returned < V_upper * 0.75`: она знала
    numerals запаса «2x» и потому падала бы при ЛЮБОЙ смене множителя, даже
    если production остался бы корректным. Это тест на историческую
    реализацию, а не на свойство.

    Свойство здесь одно: ответ — это искомый объём, а не точка, с которой
    начался поиск. Оно сформулировано через независимый oracle, поэтому
    верно при любом запасе границы и одновременно ловит возврат границы
    вместо минимума.
    """
    true_min = _independent_min_capacity_m3(NORMAL_SERIES, NORMAL_DEMAND, 95.0)

    _, iterations, best_v = _iterations(monkeypatch, NORMAL_SERIES, NORMAL_DEMAND)

    assert iterations > 0, "бинарный поиск обязан выполнять итерации"
    assert best_v == pytest.approx(true_min, rel=1e-9), (
        f"найдено {best_v:,.6f} м³ вместо минимума {true_min:,.6f} м³ — "
        "вернулась точка старта поиска, а не искомый объём"
    )


# ----------------------------------------------------------------------
# Test C — малый объём и абсолютный пол допуска
# ----------------------------------------------------------------------
def test_sub_million_volume_resolves_with_absolute_tolerance_floor(monkeypatch) -> None:
    """Малый объём разрешается до абсолютного пола 1 м³.

    ВАЖНО О МЕХАНИЗМЕ. При V_high <= 1e9 м³ выражение
    max(volume_abs_tol, volume_rel_tol * scale) выбирает АБСОЛЮТНЫЙ пол
    1 м³, а не относительный член. Относительная точность здесь не
    проверяется и не активна; имя теста отражает именно пол.

    При старом абсолютном допуске 1e6 м³ поиск на этом ряде не выполнялся ни
    одной итерации (V_upper = 189 216 м³ < 1e6), и ответ был ровно вдвое
    больше истинного. Теперь итерации выполняются, а найденное значение
    совпадает с истинным минимумом, что при допуске 1e6 недостижимо.
    """
    series = np.array([0.05, 0.05, 0.05, 0.045])
    demand = 0.048
    true_min = 0.003 * T_YEAR  # 94 608 м³

    assert true_min < 1e6, "объём должен быть заведомо меньше старого допуска"

    result, iterations, best_v = _iterations(monkeypatch, series, demand, target=100.0)

    assert iterations > 0, "поиск обязан выполняться при V_upper < 1e6 м³"
    # Сверка по ТОЧНОМУ best_V, а не по округлённому публичному полю:
    # required_volume_mln_m3 округляется с шагом 0.1 млн м³, что само по
    # себе даёт до 5.7 % погрешности на этом объёме и не характеризует поиск.
    assert best_v == pytest.approx(true_min, rel=1e-9), (
        f"найдено {best_v:,.6f} м³ вместо {true_min:,.6f} м³ — "
        "сходимость к минимуму не достигнута"
    )
    assert result["guarantee_percent"] == pytest.approx(100.0)


def test_zero_answer_case_converges_instead_of_stalling(monkeypatch) -> None:
    """Истинный ответ 0 сходится к нулю в пределах пола 1 м³.

    Ряд без единого дефицитного года: запас не убывает, поэтому минимальная
    ёмкость равна нулю. При старом допуске 1e6 м³ цикл останавливался с
    ответом порядка 10^6 м³, что для нулевого ответа является грубой ошибкой.

    ПРОВЕРКА ИДЁТ ПО ВНУТРЕННЕМУ best_V, а не по публичному полю.
    required_volume_mln_m3 округляется с шагом 0.1 млн м³, поэтому проверка
    публичного поля пропускала бы любой ответ меньше 50 000 м³ — включая
    40 000, что в 40 000 раз больше истинного нуля.

    Ровно ноль не требуется: бисекция останавливается по допуску, и при
    volume_abs_tol = 1.0 фактический результат составляет около 0.9 м³.
    Требуется лишь уложиться в пол.
    """
    series = np.array([60.0, 70.0, 80.0])
    demand = 50.0

    result, iterations, best_v = _iterations(monkeypatch, series, demand)

    assert iterations > 0, "бинарный поиск обязан выполняться"
    assert abs(best_v) <= 1.0, (
        f"при истинном ответе 0 внутренний best_V = {best_v:,.6f} м³ — "
        "это на порядки выше пола 1 м³, значит поиск не сошёлся"
    )
    # Публичные поля — дополнительная проверка, а не основная.
    assert result["required_volume_mln_m3"] == 0.0, (
        "минимальная ёмкость для ряда без дефицита равна 0, а не "
        f"{result['required_volume_mln_m3']} млн м³"
    )
    assert result["guarantee_percent"] == pytest.approx(100.0)


# ----------------------------------------------------------------------
# Test D — решение у верхней границы не считается ошибкой
# ----------------------------------------------------------------------
def test_answer_never_depends_on_where_the_search_started(monkeypatch) -> None:
    """Ответ не зависит от верхней границы: это и есть «решение ≠ граница».

    Исходный тест утверждал `returned ≈ V_upper / 2`, то есть проверял
    БУКВАЛЬНО текущий множитель запаса. Он проходил по построению, а не по
    существу: меняй production на любой множитель — и тест рассыпался, хотя
    методика оставалась бы корректной. Хуже того, равенство «ответ = половина
    границы» было бы истинным и для НЕВЕРНОГО ответа, случись тот равен
    половине границы: диагностической силы у такой проверки нет.

    Настоящее свойство: бинарный поиск возвращает искомый объём при ЛЮБОЙ
    верхней границе, какой бы достаточной она ни была, — граница влияет
    только на число итераций. Оно и проверяется лестницей масштабов
    границы, без предположения о множителе:

      * где production отвечает — ответ обязан совпасть с oracle;
      * где production отказывает — границы не хватило, и это штатно.

    Отдельное требование: лестница обязана содержать и отказ. Иначе при
    любой сколь угодно малой границе проверка была бы вакуумной, и
    достаточность границы вообще не проверялась бы — ровно та ловушка,
    о которой предупреждает задание.

    Попутно закрывается свойство «решение у верхней границы диапазона не
    отклоняется ложно»: чем меньше масштаб, тем ближе ответ к границе, и
    последний успешный шаг — это и есть решение ровно на границе.
    """
    real_ripple = rr._ripple_mass_curve
    true_min = _independent_min_capacity_m3(NORMAL_SERIES, NORMAL_DEMAND, 100.0)

    def solve_with_scale(scale: float) -> float | None:
        """ТОЧНЫЙ ответ production при масштабе границы scale, либо None при отказе.

        Берётся best_V из трассировки, а не публичное поле: required_volume_mln_m3
        округляется с шагом 0.1 млн м³, что на этом объёме само по себе даёт
        до 20 000 м³ расхождения и замаскировало бы проверку.
        """
        def scaled(q_d):
            result = dict(real_ripple(q_d))
            result["required_m3_s"] = result["required_m3_s"] * scale
            return result

        monkeypatch.setattr(rr, "_ripple_mass_curve", scaled)
        real_metrics = rr._calculate_regulation_year_metrics
        seen: list[float] = []

        def traced(Q, d, cap, init, years=T_YEAR):
            seen.append(float(cap))
            return real_metrics(Q, d, cap, init, years)

        monkeypatch.setattr(rr, "_calculate_regulation_year_metrics", traced)
        seen.clear()
        try:
            rr.multi_year_regulation(
                NORMAL_SERIES, NORMAL_DEMAND, mode="volume_for_guarantee",
                target_guarantee=100.0,
            )
        except ValueError:
            return None
        return seen[-1] if seen else None

    succeeded, refused = [], []
    scale = 1.0
    for _ in range(24):
        answer = solve_with_scale(scale)
        if answer is None:
            refused.append(scale)
        else:
            succeeded.append((scale, answer))
        scale *= 0.5

    assert succeeded, (
        "ни один масштаб границы не дал решения — проверка неинформативна"
    )
    assert refused, (
        "ни один масштаб границы не дал отказа: достаточность границы не "
        "проверяется, и лестница не может поймать слишком малую границу"
    )
    assert min(refused) < max(s for s, _ in succeeded), (
        "лестница должна пересекать порог: слишком малые границы обязаны "
        "отказывать, а достаточные — отвечать"
    )

    for scale, answer in succeeded:
        assert answer == pytest.approx(true_min, abs=1.0), (
            f"при масштабе границы {scale:g} ответ {answer:,.0f} м³ отличается "
            f"от минимума {true_min:,.0f} м³ более чем на пол допуска — "
            "величина границы просочилась в результат"
        )


def test_strict_target_still_accepted_when_attainable() -> None:
    """Строгая цель (100 %) принимается, когда она достижима.

    Проверка против «ложной строгости»: убеждается, что отказ не срабатывает
    просто из-за высокой целевой гарантии.
    """
    for target in (95.0, 100.0):
        result = rr.multi_year_regulation(
            NORMAL_SERIES, NORMAL_DEMAND, mode="volume_for_guarantee",
            target_guarantee=target,
        )
        assert result["guarantee_percent"] >= target - 1e-9


def test_existing_target_range_validation_is_preserved() -> None:
    """Прежняя проверка диапазона цели не ослаблена исправлением.

    Цель вне (0, 100] отсекается на входе, ДО бинарного поиска, собственным
    сообщением. Новая проверка достижимости не должна перехватывать этот случай
    и не должна позволить ему пройти дальше.
    """
    for bad_target in (0.0, -1.0, 100.0000001, 150.0):
        with pytest.raises(ValueError, match="target_guarantee"):
            rr.multi_year_regulation(
                NORMAL_SERIES, NORMAL_DEMAND, mode="volume_for_guarantee",
                target_guarantee=bad_target,
            )
