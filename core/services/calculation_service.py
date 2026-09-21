"""
core/services/calculation_service.py
Thin orchestration layer for calculations.

This service does NOT implement mathematical calculations.
It delegates to existing core modules (core.stats, core.hydrorash, etc.)
and provides a unified interface for executing and tracking calculations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from core.domain.models import (
    CalculationMetadata,
    CalculationResult,
    Dataset,
    Methodology,
    ValidationResult,
)


@dataclass
class CalculationContext:
    """Context passed to calculation functions."""
    dataset: Dataset
    parameters: dict[str, Any]
    methodology: Methodology


class CalculationError(Exception):
    """Raised when calculation fails."""
    def __init__(self, message: str, methodology: str, original_error: Exception | None = None):
        super().__init__(message)
        self.methodology = methodology
        self.original_error = original_error


class CalculationService:
    """
    Thin orchestration layer for calculations.

    Responsibilities:
    - Register calculation handlers for methodologies
    - Execute calculations with proper metadata tracking
    - Delegate to existing core modules (no math here)
    - Return structured CalculationResult

    Does NOT:
    - Implement mathematical formulas
    - Duplicate existing core.stats or core.hydrorash functions
    """

    def __init__(self):
        self._handlers: dict[str, Callable[[CalculationContext], dict[str, Any]]] = {}
        self._validators: dict[str, Callable[[CalculationContext], ValidationResult]] = {}

    def register_handler(
        self,
        methodology_name: str,
        handler: Callable[[CalculationContext], dict[str, Any]],
    ) -> None:
        """
        Register a calculation handler for a methodology.

        Args:
            methodology_name: Qualified name (e.g., "frequency_pearson3@1.0")
            handler: Function that takes CalculationContext and returns output dict
        """
        self._handlers[methodology_name] = handler

    def register_validator(
        self,
        methodology_name: str,
        validator: Callable[[CalculationContext], ValidationResult],
    ) -> None:
        """
        Register a pre-calculation validator for a methodology.

        Args:
            methodology_name: Qualified name
            validator: Function that validates context and returns ValidationResult
        """
        self._validators[methodology_name] = validator

    def execute(
        self,
        methodology: Methodology,
        dataset: Dataset,
        parameters: dict[str, Any] | None = None,
        input_dataset_ids: list[UUID] | None = None,
    ) -> CalculationResult:
        """
        Execute a calculation with the given methodology.

        Args:
            methodology: The methodology to use
            dataset: Primary input dataset
            parameters: Calculation parameters
            input_dataset_ids: IDs of all input datasets

        Returns:
            CalculationResult with output data or error information
        """
        metadata = CalculationMetadata(
            methodology=methodology,
            input_dataset_ids=input_dataset_ids or [dataset.id],
            input_parameters=parameters or {},
        )

        metadata.mark_running()

        try:
            # Run pre-calculation validation if registered
            validator = self._validators.get(methodology.qualified_name)
            if validator:
                context = CalculationContext(
                    dataset=dataset,
                    parameters=parameters or {},
                    methodology=methodology,
                )
                validation = validator(context)
                if not validation.is_valid:
                    error_msgs = [i.message for i in validation.errors]
                    raise CalculationError(
                        f"Validation failed: {'; '.join(error_msgs)}",
                        methodology.qualified_name,
                    )

            # Execute the calculation handler
            handler = self._handlers.get(methodology.qualified_name)
            if not handler:
                raise CalculationError(
                    f"No handler registered for methodology: {methodology.qualified_name}",
                    methodology.qualified_name,
                )

            context = CalculationContext(
                dataset=dataset,
                parameters=parameters or {},
                methodology=methodology,
            )
            output_data = handler(context)

            metadata.mark_completed()

            return CalculationResult(
                metadata=metadata,
                output_data=output_data,
            )

        except CalculationError:
            metadata.mark_failed(str(metadata.error_message))
            raise
        except Exception as e:
            metadata.mark_failed(f"{type(e).__name__}: {e}")
            raise CalculationError(
                f"Calculation failed: {e}",
                methodology.qualified_name,
                original_error=e,
            ) from e

    def execute_async(
        self,
        methodology: Methodology,
        dataset: Dataset,
        parameters: dict[str, Any] | None = None,
        input_dataset_ids: list[UUID] | None = None,
        callback: Callable[[CalculationResult], None] | None = None,
    ) -> None:
        """
        Execute calculation asynchronously (fire and forget with callback).

        Note: This is a simple implementation. For production, use proper
        thread pool or async framework.
        """
        import threading

        def run():
            try:
                result = self.execute(methodology, dataset, parameters, input_dataset_ids)
                if callback:
                    callback(result)
            except CalculationError as e:
                # Create failed result
                metadata = CalculationMetadata(
                    methodology=methodology,
                    input_dataset_ids=input_dataset_ids or [dataset.id],
                    input_parameters=parameters or {},
                )
                metadata.mark_failed(str(e))
                result = CalculationResult(metadata=metadata)
                if callback:
                    callback(result)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def get_registered_methodologies(self) -> list[str]:
        """Get list of registered methodology qualified names."""
        return list(self._handlers.keys())

    def has_handler(self, methodology_name: str) -> bool:
        """Check if a handler is registered for the methodology."""
        return methodology_name in self._handlers
