"""
core/services/methodology_registry.py
Methodology registry for the HydroSphere P0 architecture.

The registry knows which calculation methodologies exist and what they require:
the normative document (SP / GOST) and its clause, the scope of application, data
requirements, parameters and applicability limits.

No mathematics lives here. Formulas stay in the calculation core
(`core.stats`, `core.hydrorash`) and are invoked through `core.services.handlers`.

Normative references in DEFAULT_METHODOLOGIES are copied verbatim from the
docstrings of the corresponding core modules - no references are invented.
See DOCS/ROADMAP.md, section 12 ("Нормативная база").
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from core.domain.models import Dataset, Methodology, ValidationResult, ValidationSeverity


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
# P0 catalogue
#
# References are quoted from the docstrings of the corresponding core modules
# (see the table in DOCS/ROADMAP.md, section 12). Data requirements that are not
# stated in the normative document are left at 0 / empty on purpose: the full
# catalogue (parameters schema, limitations, handlers) is filled in stage 3.
# ----------------------------------------------------------------------
DEFAULT_METHODOLOGIES: tuple[MethodologyDescriptor, ...] = (
    MethodologyDescriptor(
        id="stats_parameters",
        name="Статистические параметры ряда (Qср, Cv, Cs, ε)",
        category="statistics",
        standard="СП 33-101-2003",
        scope="Оценка среднего значения, коэффициентов вариации и асимметрии, ошибок ε",
        min_points=25,
        limitations=(
            "Ряд короче 25 лет — оценки ненадёжны (СП 482.1325800.2020, п. 8.2)",
            "Для обеспеченности P ≤ 1 % требуется не менее 50 лет наблюдений",
            "Cs ненадёжен при n < 20 лет",
        ),
        notes="СП 482.1325800.2020, п. 8.2: 25 лет — снеговое питание, 30 лет — дождевое",
    ),
    MethodologyDescriptor(
        id="frequency_pearson3",
        name="Кривая обеспеченности (Пирсон III)",
        category="statistics",
        standard="СП 33-101-2003",
        scope="Кривые обеспеченности среднегодовых, максимальных и минимальных расходов",
        limitations=("Форма кривой чувствительна к выбору Cs/Cv",),
        notes="Реализация: core/stats/frequency.py",
    ),
    MethodologyDescriptor(
        id="frequency_kritsky_menkel",
        name="Кривая обеспеченности (Крицкий-Менкель, ординаты)",
        category="statistics",
        standard="СП 33-101-2003",
        scope="Трёхпараметрическое гамма-распределение, табличные ординаты",
        notes="Реализация: core/stats/frequency.py, таблицы core/stats/kritsky_tables.py",
    ),
    MethodologyDescriptor(
        id="homogeneity_full",
        name="Проверка однородности ряда (12 критериев)",
        category="statistics",
        standard="СП 33-101-2003",
        clause="Приложение А",
        scope="5 критериев Диксона, 2 критерия Смирнова-Граббса, тесты стационарности",
        notes="Реализация: core/stats/homogeneity.py",
    ),
    MethodologyDescriptor(
        id="series_extension",
        name="Удлинение (восстановление) ряда по аналогу",
        category="statistics",
        standard="СП 33-101-2003",
        clause="раздел 6.2",
        scope="Регрессионное удлинение короткого ряда наблюдений по посту-аналогу",
        limitations=("Связь признаётся значимой при R > Ro(α, n)",),
        notes="Проверка остатков — п. 6.2.4; реализация: core/stats/series_extension.py",
    ),
    MethodologyDescriptor(
        id="composite_curves",
        name="Составная кривая обеспеченности (Рождественский)",
        category="statistics",
        standard="СП 33-101-2003",
        clause="п. 5.12",
        scope="Осреднение кривых обеспеченности при генетической неоднородности ряда",
        notes="Реализация: core/stats/composite_curves.py",
    ),
    MethodologyDescriptor(
        id="max_runoff",
        name="Максимальный сток (паводки)",
        category="runoff",
        standard="СП 33-101-2003",
        clause="раздел 8",
        scope=(
            "Расчёт максимальных расходов воды, кривые обеспеченности паводков, "
            "метод индексных годов, кривая Q = f(H)"
        ),
        notes="РД 52-26-2008; реализация: core/hydrorash/max_runoff.py",
    ),
    MethodologyDescriptor(
        id="flood_hydrograph",
        name="Гидрограф паводка (форма паводочной кривой)",
        category="runoff",
        standard="СП 33-101-2003",
        clause="п. 8.3",
        scope="Построение и трансформация гидрографа паводка",
        notes="Реализация: core/hydrorash/flood_hydrograph.py",
    ),
    MethodologyDescriptor(
        id="ice_phenomena",
        name="Ледовые явления (ледостав, толщина льда, заторы)",
        category="runoff",
        standard="СП 33-101-2003",
        clause="п. 8.5.2, п. 8.5.3",
        scope="Сроки ледостава и вскрытия, толщина льда, заторные явления",
        notes="ГОСТ 19179-73; Кондратьев В.Г. (1968); core/hydrorash/ice_phenomena.py",
    ),
    MethodologyDescriptor(
        id="flow_duration",
        name="Кривая длительностей (FDC)",
        category="statistics",
        standard="СП 32.13330.2018",
        scope="Перцентили Q10/Q50/Q90, показатели формы кривой, классификация режима",
        notes="Реализация: core/stats/flow_duration.py",
    ),
    MethodologyDescriptor(
        id="reservoir_regulation",
        name="Многолетнее регулирование стока",
        category="reservoir",
        standard="СП 58.13330.2019",
        scope="Полезный объём, гарантированная отдача, кривая «объём — отдача»",
        required_parameters=("demand",),
        limitations=("Расчёт зависит от выбранного правила регулирования и ряда притока",),
        notes="СП 33-101-2003 / СП 33.13330.2016; core/hydrorash/reservoir_regulation.py",
    ),
    MethodologyDescriptor(
        id="backwater",
        name="Кривые подпора (ГВП)",
        category="hydraulics",
        standard="СП 33-101-2003",
        scope="Расчёт кривой подпора и отметок воды при подпорном воздействии",
        limitations=("Точность зависит от детальности морфометрии русла (±5–10 %)",),
        notes="Реализация: core/hydrorash/backwater.py",
    ),
)


def build_default_registry() -> MethodologyRegistry:
    """Create a registry pre-filled with the P0 methodology catalogue."""
    return MethodologyRegistry(DEFAULT_METHODOLOGIES)




