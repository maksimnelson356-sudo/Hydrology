"""
core/services/methodology_registry.py
Methodology registry for the HydroSphere P0 architecture.

The registry knows which calculation methodologies exist and what they require:
the normative document (SP / GOST) and its clause, the scope of application, data
requirements, parameters and applicability limits.

No mathematics lives here. Formulas stay in the calculation core
(`core.stats`, `core.hydrorash`) and are invoked through `core.services.handlers`.

Normative references in DEFAULT_METHODOLOGIES were NOT all taken from the core
module docstrings, and several were invented outright. A 2026-09-28 audit
against the printed texts refuted eight of them: СП 33 has no section 8,
its chapter 7 has 74 clauses, not 53; СП 290 (not СП 58) prescribes the
spillway formula; СП 32 is "Канализация" and does not cover ecological flow;
СП 58 has no table 6.1; and РД 52-26-2008 could not be found in any of the
thirteen catalogue collections. Those references were corrected.

The `evidence_status` field records what was verified, per method, and is the
machine-readable counterpart of DOCS/normative_verification_matrix.md. Read it
rather than `is_normative` when the question is "how solid is this?".
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from core.domain.models import Dataset, Methodology, ValidationResult, ValidationSeverity

# What was actually verified against a primary source. Deliberately orthogonal
# to is_normative: that flag says "a standard prescribes this", these say
# "we went and looked at the text".
#
#   source_checked - calculation checked against the printed source
#   partial        - source confirmed, only part of the formula checked
#   engineering    - works, but no standard backs it
#   unverified     - claimed source is absent or refuted
EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {"source_checked", "partial", "engineering", "unverified"}
)


@dataclass(frozen=True)
class MethodologyDescriptor:
    """
    Full description of a single calculation methodology.

    Attributes:
        id: Stable identifier, e.g. "frequency_pearson3".
        name: Human-readable name (Russian by default).
        version: Methodology version, e.g. "1.0".
        category: Grouping key: "statistics", "runoff", "hydraulics", "reservoir".
        standard: Normative document, e.g. "СП 33-101-2003".
        clause: Section or clause of the document, e.g. "Приложение А".
        scope: Field of application (область применения).
        min_points: Minimum number of observations; 0 means "not specified".
        required_parameters: Names of parameters the calculation cannot run without.
        limitations: Known applicability limits.
        is_normative: True when the method is prescribed by a normative document,
            False when it is an engineering implementation or recommendation.
        evidence_status: What was actually verified against a primary source.
            One of EVIDENCE_STATUSES. This is deliberately separate from
            is_normative: that flag answers "does a standard prescribe this?",
            while this one answers "did we check?". A method can have a verified
            source and still not be normative (spillway: СП 290 п. 6.3, checked
            against the printed text, but not a mandatory design basis), and a
            method can be non-normative with a refuted source (ecological_flow:
            СП 32 turned out to be "Канализация").
        notes: Free-form notes (additional documents, caveats).
    """

    id: str
    name: str
    version: str = "1.0"
    category: str = "statistics"
    standard: str | None = None
    clause: str | None = None
    scope: str = ""
    min_points: int = 0
    required_parameters: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    is_normative: bool = True
    evidence_status: str = "unverified"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("Methodology id cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("Methodology name cannot be empty")
        if not self.version or not self.version.strip():
            raise ValueError("Methodology version cannot be empty")
        if self.min_points < 0:
            raise ValueError("Methodology min_points cannot be negative")
        if self.evidence_status not in EVIDENCE_STATUSES:
            raise ValueError(
                f"Methodology '{self.id}' has evidence_status "
                f"'{self.evidence_status}'; allowed: {sorted(EVIDENCE_STATUSES)}"
            )
        # A refuted source cannot be advertised as normative. This is the one
        # hard invariant between the two flags, and it is enforced here so a
        # descriptor can never be built in a self-contradictory state.
        if self.evidence_status == "unverified" and self.is_normative:
            raise ValueError(
                f"Methodology '{self.id}' is is_normative=True while its source is "
                f"unverified. A refuted or absent source must set is_normative=False."
            )

    @property
    def qualified_name(self) -> str:
        """Unique identifier combining id and version, e.g. "frequency_pearson3@1.0"."""
        return f"{self.id}@{self.version}"

    @property
    def normative_reference(self) -> str:
        """Human-readable normative reference, e.g. "СП 33-101-2003, Приложение А"."""
        parts = [part for part in (self.standard, self.clause) if part]
        return ", ".join(parts) if parts else "не указана"

    def to_methodology(self) -> Methodology:
        """Convert the descriptor into a domain `Methodology` entity."""
        return Methodology(
            name=self.id,
            version=self.version,
            standard=self.standard,
            description=self.name,
            parameters={
                "category": self.category,
                "clause": self.clause,
                "scope": self.scope,
                "limitations": list(self.limitations),
                "is_normative": self.is_normative,
                "evidence_status": self.evidence_status,
            },
        )


class MethodologyRegistry:
    """In-memory catalogue of calculation methodologies."""

    def __init__(self, descriptors: Iterable[MethodologyDescriptor] | None = None) -> None:
        self._items: dict[str, MethodologyDescriptor] = {}
        for descriptor in descriptors or ():
            self.register(descriptor)

    # ------------------------------------------------------------------
    # Registration and lookup
    # ------------------------------------------------------------------
    def register(self, descriptor: MethodologyDescriptor) -> MethodologyDescriptor:
        """Register a descriptor. Raises ValueError when the id is already registered."""
        if descriptor.id in self._items:
            raise ValueError(f"Methodology '{descriptor.id}' is already registered")
        self._items[descriptor.id] = descriptor
        return descriptor

    def unregister(self, methodology_id: str) -> None:
        """Remove a descriptor. Raises KeyError for an unknown id."""
        self.get(methodology_id)
        del self._items[methodology_id]

    def has(self, methodology_id: str) -> bool:
        """Check whether a methodology id is registered."""
        return methodology_id in self._items

    def get(self, methodology_id: str) -> MethodologyDescriptor:
        """Return a descriptor by id. Raises KeyError for an unknown id."""
        try:
            return self._items[methodology_id]
        except KeyError:
            known = ", ".join(sorted(self._items)) or "нет зарегистрированных методик"
            raise KeyError(
                f"Unknown methodology '{methodology_id}'. Known: {known}"
            ) from None

    def get_optional(self, methodology_id: str) -> MethodologyDescriptor | None:
        """Return a descriptor by id or None when it is not registered."""
        return self._items.get(methodology_id)

    def list(
        self,
        category: str | None = None,
        standard: str | None = None,
    ) -> list[MethodologyDescriptor]:
        """List descriptors, optionally filtered by category and/or standard."""
        items = list(self._items.values())
        if category is not None:
            items = [item for item in items if item.category == category]
        if standard is not None:
            needle = standard.strip().lower()
            items = [item for item in items if needle in item.normative_reference.lower()]
        return sorted(items, key=lambda item: (item.category, item.id))

    def by_standard(self, standard: str) -> list[MethodologyDescriptor]:
        """List descriptors whose normative reference contains the given text."""
        return self.list(standard=standard)

    def ids(self) -> list[str]:
        """Return sorted list of registered methodology ids."""
        return sorted(self._items)

    def categories(self) -> list[str]:
        """Return sorted list of registered categories."""
        return sorted({item.category for item in self._items.values()})

    # ------------------------------------------------------------------
    # Applicability
    # ------------------------------------------------------------------
    def check_applicability(
        self,
        methodology_id: str,
        dataset: Dataset,
        parameters: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """
        Check whether a methodology may be applied to the given dataset.

        Raises:
            KeyError: when the methodology id is not registered.
        """
        descriptor = self.get(methodology_id)
        result = ValidationResult(is_valid=True)

        if dataset.length == 0:
            result.add_issue(
                code="EMPTY_DATASET",
                message="Датасет не содержит данных",
                severity=ValidationSeverity.CRITICAL,
                field="data",
                methodology=descriptor.qualified_name,
            )
            return result

        if descriptor.min_points and dataset.length < descriptor.min_points:
            result.add_issue(
                code="INSUFFICIENT_DATA",
                message=(
                    f"Методика «{descriptor.name}» требует не менее {descriptor.min_points} "
                    f"лет наблюдений, в ряду {dataset.length}. "
                    f"Нормативная ссылка: {descriptor.normative_reference}"
                ),
                severity=ValidationSeverity.ERROR,
                field="data",
                methodology=descriptor.qualified_name,
                details={"required": descriptor.min_points, "actual": dataset.length},
            )

        if descriptor.required_parameters:
            provided = parameters or {}
            missing = [name for name in descriptor.required_parameters if name not in provided]
            if missing:
                result.add_issue(
                    code="MISSING_PARAMETER",
                    message=(
                        f"Не заданы обязательные параметры: {', '.join(missing)} "
                        f"(методика «{descriptor.name}»)"
                    ),
                    severity=ValidationSeverity.ERROR,
                    field="parameters",
                    methodology=descriptor.qualified_name,
                    details={"missing": missing},
                )

        return result

    # ------------------------------------------------------------------
    # Container protocol
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[MethodologyDescriptor]:
        return iter(self.list())

    def __contains__(self, methodology_id: object) -> bool:
        return isinstance(methodology_id, str) and methodology_id in self._items


# ----------------------------------------------------------------------
# Methodology catalogue
#
# Normative references were checked against the current texts available on
# 2026-09-24. Methods without a verified prescriptive source are explicitly
# marked is_normative=False; engineering implementations remain available but
# must not be advertised as compliant with СП/ГОСТ.
# ----------------------------------------------------------------------
DEFAULT_METHODOLOGIES: tuple[MethodologyDescriptor, ...] = (
    MethodologyDescriptor(
        id="stats_parameters",
        evidence_status="partial",
        name="Статистические параметры ряда (Qср, Cv, Cs, ε)",
        category="statistics",
        standard="СП 33-101-2003",
        clause="п. 5.1, п. 5.4–5.15",
        scope="Оценка среднего значения, коэффициентов вариации и асимметрии, ошибок ε",
        limitations=(
            "Достаточность ряда определяется относительной среднеквадратической погрешностью, а не фиксированным числом лет",
        ),
        notes="Для годового и сезонного стока предельная относительная погрешность — 10%",
    ),
    MethodologyDescriptor(
        id="frequency_pearson3",
        evidence_status="source_checked",
        name="Кривая обеспеченности (Пирсон III)",
        category="statistics",
        standard="СП 33-101-2003",
        clause="п. 5.1–5.3",
        scope="Кривые обеспеченности среднегодовых, максимальных и минимальных расходов",
        limitations=("Форма кривой чувствительна к выбору Cs/Cv",),
        notes="Реализация: core/stats/frequency.py",
    ),
    MethodologyDescriptor(
        id="frequency_kritsky_menkel",
        evidence_status="source_checked",
        name="Кривая обеспеченности (Крицкий-Менкель, ординаты)",
        category="statistics",
        standard="СП 33-101-2003",
        clause="п. 5.1–5.6",
        scope="Трёхпараметрическое гамма-распределение, табличные ординаты",
        notes="Реализация: core/stats/frequency.py, таблицы core/stats/kritsky_tables.py",
    ),
    MethodologyDescriptor(
        id="homogeneity_full",
        evidence_status="source_checked",
        name="Проверка однородности ряда (12 критериев)",
        category="statistics",
        standard="СП 33-101-2003",
        clause="п. 4.7, прил. А.1–А.3",
        scope="5 критериев Диксона, 2 критерия Смирнова-Граббса, тесты стационарности",
        notes="Реализация: core/stats/homogeneity.py",
    ),
    MethodologyDescriptor(
        id="series_extension",
        evidence_status="partial",
        name="Удлинение (восстановление) ряда по аналогу",
        category="statistics",
        standard="СП 33-101-2003",
        clause="п. 6.2–6.7, п. 6.17",
         scope="Регрессионное удлинение короткого ряда наблюдений по посту-аналогу",
         required_parameters=("analog_df",),
         limitations=(
             "Поддержаны критерии п. 6.7 и поправки дисперсии по п. 6.17; для коротких рядов требуется проверка репрезентативности",
         ),
         is_normative=False,
         notes="Сервисный handler; core/stats/series_extension.py",

    ),
    MethodologyDescriptor(
        id="series_extension_staged",
        evidence_status="partial",
        name="Ступенчатое восстановление ряда по этапам",
        category="statistics",
        standard="СП 33-101-2003",
        clause="п. 6.2–6.7, п. 6.17, Приложение А.8",
        scope="Последовательное регрессионное восстановление короткого ряда по этапам",
        min_points=6,
        required_parameters=("stages",),
        limitations=(
            "Для каждого этапа нужны собственные аналоги, период обучения и годы восстановления",
            "A.8 не воспроизводится без исходных рядов аналогов",
        ),
        is_normative=False,
        notes="Сервисный handler; core/stats/staged_series_extension.py",
    ),
    MethodologyDescriptor(
        id="composite_curves",
        evidence_status="partial",
        name="Составная кривая обеспеченности (Рождественский)",
        category="statistics",
        standard="СП 33-101-2003",
        clause="п. 5.12, формулы 5.21–5.25",
        scope="Осреднение кривых обеспеченности при генетической неоднородности ряда",
        notes="Реализация: core/stats/composite_curves.py",
    ),
    MethodologyDescriptor(
        id="max_runoff",
        evidence_status="partial",
        name="Максимальный сток (паводки)",
        category="runoff",
        standard="СП 33-101-2003",
        clause="п. 5.26–5.31",
        scope=(
            "Расчёт максимальных расходов воды, кривые обеспеченности паводков, "
            "метод индексных годов, кривая Q = f(H)"
        ),
        required_parameters=("daily_df",),
        notes="Реализация: core/hydrorash/max_runoff.py. Ранее в notes значился «РД 52-26-2008» — документ не найден ни в одной из 13 доступных коллекций, номер не соответствует шаблону РД 52.XX.XXX-YYYY каталога; атрибуция удалена как недоказуемая.",
    ),
    MethodologyDescriptor(
        id="flood_hydrograph",
        evidence_status="source_checked",
        name="Гидрограф паводка (форма паводочной кривой)",
        category="runoff",
        standard="СП 33-101-2003",
         clause="п. 5.32",
         scope="Построение и трансформация гидрографа паводка",
         required_parameters=("Q_peak", "T_peak", "T_base"),
         notes="Сервисный handler; core/hydrorash/flood_hydrograph.py",

    ),
    MethodologyDescriptor(
        id="ice_phenomena",
        evidence_status="engineering",
        name="Ледовые явления (ледостав, толщина льда, заторы)",
        category="runoff",
        standard="СП 33-101-2003",
        clause="п. 7.70, п. 7.71 (п. 7.72 / формула 7.51 в коде НЕ реализована)",
        scope="Сроки ледостава и вскрытия, заторные явления",
        required_parameters=("latitude", "mean_jan_temp"),
        is_normative=False,
        notes=(
            "Проверено 2026-09-28 по публичному тексту СП 33-101-2003. Прежняя ссылка на "
            "п. 5.44 ошибочна: этот пункт о наивысших уровнях воды, не о ледовых явлениях. "
            "Формул толщины льда стандарт не содержит; предписанная формула (7.51) из п. 7.72 "
            "в core/hydrorash/ice_phenomena.py не реализована. "
            "РД 52-26-2008 и СП 58.13330.2019 не проверены."
        ),
    ),
    MethodologyDescriptor(
        id="flow_duration",
        evidence_status="engineering",
        name="Кривая длительностей (FDC)",
        category="statistics",
        standard="Инженерный метод FDC",
        scope="Перцентили Q10/Q50/Q90, показатели формы кривой, классификация режима",
        is_normative=False,
        notes="Реализация: core/stats/flow_duration.py",
    ),
    MethodologyDescriptor(
        id="reservoir_regulation",
        evidence_status="engineering",
        name="Многолетнее регулирование стока",
        category="reservoir",
        standard="Метод Риппла (инженерный метод)",
        scope="Полезный объём, гарантированная отдача, кривая «объём — отдача»",
        required_parameters=("demand_m3_s",),
        limitations=("Расчёт зависит от выбранного правила регулирования и ряда притока",),
        is_normative=False,
        notes="Требуется проектное обоснование режима; core/hydrorash/reservoir_regulation.py",
    ),
    MethodologyDescriptor(
        id="storage_yield",
        evidence_status="engineering",
        name="Кривая «объём — гарантированная отдача»",
        category="reservoir",
        standard="Метод Риппла (инженерный метод)",
        scope="Максимальная отдача D при заданном полезном объёме и целевой гарантии",
        limitations=("Для каждой V_max отдача ищется бинарным поиском по правилу Риппла",),
        is_normative=False,
        notes="Требуется проектное обоснование режима; core/hydrorash/reservoir_regulation.py",
    ),
    MethodologyDescriptor(
        id="trends_full",
        evidence_status="engineering",
        name="Анализ тренда (линейный, Манн-Кендалл, Сен, Pettitt)",
        category="statistics",
        standard="Манн—Кендалл / Сен / Pettitt",
        scope="Выявление направленных изменений многолетнего ряда (тренд, точка смены режима)",
        min_points=10,
        limitations=(
            "Манн-Кендалл/Сен предполагают отсутствие сильной автокорреляции ряда",
        ),
        is_normative=False,
        notes="Методы не регламентированы СП 33-101-2003; core/stats/trends.py",
    ),
    MethodologyDescriptor(
        id="min_runoff",
        evidence_status="partial",
        name="Минимальный сток (30-суточные зимние минимумы)",
        category="runoff",
        standard="СП 33-101-2003",
        clause="п. 5.41–5.43",
        scope=(
            "Расчёт минимальных расходов воды: 7/10/30-суточные минимумы, "
            "экосистемный минимум. Прежняя ссылка на СП 32.13330.2018 ошибочна: "
            "по официальным метаданным это «Канализация. Наружные сети и "
            "сооружения», предмет не совпадает; источник для экосистемного "
            "минимума не установлен"
        ),
        required_parameters=("daily_df",),
        notes="Реализация: core/hydrorash/min_runoff_extended.py",
    ),
    MethodologyDescriptor(
        id="backwater",
        evidence_status="source_checked",
        name="Кривые подпора (ГВП)",
        category="hydraulics",
        standard="СП 33-101-2003",
         clause="п. 5.45, п. 7.69",
         scope="Расчёт кривой подпора и отметок воды при подпорном воздействии",
         required_parameters=("Q", "B", "m", "n", "I", "H_reservoir"),
         limitations=("Точность зависит от детальности морфометрии русла (±5–10 %)",),
         notes="Сервисный handler; core/hydrorash/backwater.py",

    ),
    # ----------------------------------------------------------------------
    # P1.4 — расширенная статистика (N=10; решение 9.4)
    # References are taken from the docstrings of the corresponding core modules.
    # ----------------------------------------------------------------------
    MethodologyDescriptor(
        id="spectral_hurst",
        evidence_status="engineering",
        name="Экспонента Хёрста (метод R/S)",
        category="statistics",
        standard="Метод R/S (экспонента Хёрста)",
        is_normative=False,
        scope="Оценка долгосрочной памяти и стационарности ряда (H > 0.5 — персистентный)",
        min_points=20,
        limitations=("H ненадёжен при n < 20; оконный R/S чувствителен к выбору max_window",),
        notes="Реализация: core/stats/spectral.py",
    ),
    MethodologyDescriptor(
        id="drought_spi",
        evidence_status="partial",
        name="Стандартный индекс осадков (SPI)",
        category="statistics",
        standard="McKee et al. (1993) / WMO SPI",
        scope="Классификация засух по накопленным месячным осадкам (McKee et al., 1993)",
        min_points=12,
        limitations=(
            "Ряд должен быть месячными осадками, мм (не годовыми расходами)",
            "Масштаб scale: 1, 3, 6 или 12 месяцев",
        ),
        is_normative=False,
        notes="Упрощённая z-нормировка; полная методика WMO требует отдельной реализации",
    ),
    MethodologyDescriptor(
        id="baseflow",
        evidence_status="engineering",
        name="Разделение базового стока (baseflow separation)",
        category="statistics",
        standard="Boughton (1968), Eckhardt (2005), Lyne & Hollick (1979)",
        is_normative=False,
        scope="Выделение подземной составляющей стока: прямолинейный, цифровой фильтр, Лайн-Холлик",
        min_points=10,
        limitations=("Методы настроены на суточные расходы; на годовом ряде дают грубую оценку",),
        notes="Реализация: core/stats/baseflow.py",
    ),
    MethodologyDescriptor(
        id="confidence_bands",
        evidence_status="engineering",
        name="Доверительные полосы кривой обеспеченности",
        category="statistics",
        standard="Bootstrap-метод (инженерная оценка)",
        scope="Бутстреп-интервалы для кривой Пирсона III (уровень доверия 90/95/99 %)",
        min_points=25,
        limitations=("Число бутстреп-выборок n_bootstrap влияет на время расчёта",),
        is_normative=False,
        notes="Метод не предписан СП 482; core/stats/confidence_bands.py",
    ),

    MethodologyDescriptor(
        id="intra_annual",
        evidence_status="engineering",
        name="Внутригодовое распределение стока",
        category="runoff",
        standard="HydroRash",
        is_normative=False,
        scope="Суммы стока по периодам водного года (НЛП, ЛП, ЛС) и их статистика",
        required_parameters=("monthly_df",),
        limitations=("Требуется месячный DataFrame (столбцы 1–12 или I–XII)",),
        notes="Перенесено из HydroRash; реализация: core/hydrorash/intra_annual.py",
    ),
    MethodologyDescriptor(
        id="snowmelt",
        evidence_status="engineering",
        name="Снеговой баланс за период таяния",
        category="runoff",
        standard="Градусно-суточный метод (инженерный расчёт, источник не подтверждён)",
        scope="Объём талых вод и сток с бассейна: W_end = W_init + P − M",
        required_parameters=("W_initial", "precipitation_mm", "T_air"),
        is_normative=False,
        notes=(
            "Проверено 2026-09-28 по публичному тексту СП 33-101-2003: градусно-суточного "
            "метода стандарт не содержит (слово встречается 0 раз), п. 8.1 не существует. "
            "Ранее модуль core/hydrorash/snowmelt.py ошибочно ссылался на «СП 33 п. 8.1». "
            "Ранее полем standard значился «РД 52-26-2008»: документ не найден, номер не соответствует шаблону каталога, существование не опровергнуто. Подтверждённого источника для градусно-суточного метода нет — поле standard переведено на честную формулировку."
        ),
    ),
    MethodologyDescriptor(
        id="spillway",
        evidence_status="source_checked",
        name="Пропускная способность ППУ (водосброс)",
        category="reservoir",
        standard="СП 290.1325800.2016",
        scope="Сравнение расчётного расхода паводка с пропускной способностью водосброса",
        required_parameters=("Q_design", "H_max", "L"),
        is_normative=False,
        notes="Проверено по полному тексту СП 290.1325800.2016 (раздел 6 «Поверхностные "
        "водосбросы»): п. 6.3, формула (4) — расход Q через водосливную стенку при полном "
        "напоре и напоре на гребне H, ширине водослива b, коэффициенте расхода m, "
        "коэффициенте бокового сжатия и коэффициенте подтопления. Структура формулы "
        "совпадает с реализацией. Численные значения Cd (1.84/1.50/2.20/0.62) из текста "
        "стандарта НЕ следуют: СП 290 отсылает за ними к [3]. Прежняя ссылка кода "
        "«СП 58.13330.2019 п.6» ошибочна — там общие требования безопасности "
        "при эксплуатации, расчётные положения в разделе 8.",
    ),
    MethodologyDescriptor(
        id="ecological_flow",
        evidence_status="unverified",
        name="Экологический сток (сезонный Тессман)",
        category="runoff",
        standard="Метод Тессмана (инженерный метод)",
        scope="Сезонные величины экологического стока по месяцам (α, β по типу региона)",
        required_parameters=("Q_annual_mean",),
        limitations=("Q_monthly_mean (12 значений) опционален; без него месяцы равны годовому среднему",),
        is_normative=False,
        notes="Требуется подтверждение источника региональных коэффициентов",
    ),
)


def build_default_registry() -> MethodologyRegistry:
    """Create a registry pre-filled with the P0 methodology catalogue."""
    return MethodologyRegistry(DEFAULT_METHODOLOGIES)




