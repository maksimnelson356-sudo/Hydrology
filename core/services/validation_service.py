"""
core/services/validation_service.py
Unified validation interface for HydroSphere.

Provides a single entry point for validating:
- Datasets (completeness, outliers, homogeneity, stationarity)
- Calculation results (consistency, bounds, quality)
- Scenarios (parameter validity)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from core.domain.models import (
    CalculationResult,
    DataQualityReport,
    Dataset,
    Scenario,
    ValidationResult,
    ValidationSeverity,
)


class ValidationService:
    """
    Unified validation service.

    Consolidates all validation logic in one place.
    Uses existing core.stats functions for statistical validation.
    """

    def __init__(self):
        self._custom_validators: dict[str, callable] = {}

    # ============================================================
    # Dataset Validation
    # ============================================================

    def validate_dataset(
        self,
        dataset: Dataset,
        min_points: int = 10,
        check_homogeneity: bool = True,
        check_stationarity: bool = True,
        check_outliers: bool = True,
    ) -> ValidationResult:
        """
        Comprehensive dataset validation.

        Args:
            dataset: Dataset to validate
            min_points: Minimum required data points
            check_homogeneity: Run homogeneity tests
            check_stationarity: Run stationarity tests
            check_outliers: Check for outliers

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult(is_valid=True)

        # Basic checks
        if dataset.length < min_points:
            result.add_issue(
                code="INSUFFICIENT_DATA",
                message=f"Dataset has {dataset.length} points, minimum is {min_points}",
                severity=ValidationSeverity.ERROR,
                field="data",
            )

        if dataset.length == 0:
            result.add_issue(
                code="EMPTY_DATASET",
                message="Dataset contains no data points",
                severity=ValidationSeverity.CRITICAL,
                field="data",
            )
            return result

        # Check for missing years (gaps)
        years = dataset.years
        if len(years) > 1:
            expected_years = set(range(min(years), max(years) + 1))
            missing_years = expected_years - set(years)
            if missing_years:
                result.add_issue(
                    code="DATA_GAPS",
                    message=f"Missing years in series: {sorted(missing_years)}",
                    severity=ValidationSeverity.WARNING,
                    field="data",
                    details={"missing_years": sorted(missing_years)},
                )

        # Check for duplicate years
        if len(years) != len(set(years)):
            result.add_issue(
                code="DUPLICATE_YEARS",
                message="Dataset contains duplicate years",
                severity=ValidationSeverity.ERROR,
                field="data",
            )

        # Check for zero/negative values if inappropriate
        values = np.array(dataset.values)
        zero_count = np.sum(values == 0)
        negative_count = np.sum(values < 0)
        if zero_count > 0:
            result.add_issue(
                code="ZERO_VALUES",
                message=f"Dataset contains {zero_count} zero values",
                severity=ValidationSeverity.WARNING,
                field="data",
            )
        if negative_count > 0:
            result.add_issue(
                code="NEGATIVE_VALUES",
                message=f"Dataset contains {negative_count} negative values",
                severity=ValidationSeverity.WARNING,
                field="data",
            )

        # Statistical validation (delegates to core.stats)
        if check_homogeneity or check_stationarity or check_outliers:
            self._validate_statistical(dataset, result, check_homogeneity, check_stationarity, check_outliers)

        return result

    def _validate_statistical(
        self,
        dataset: Dataset,
        result: ValidationResult,
        check_homogeneity: bool,
        check_stationarity: bool,
        check_outliers: bool,
    ) -> None:
        """Run statistical validations using core.stats."""
        values = np.array(dataset.values, dtype=float)
        values = values[~np.isnan(values)]

        if len(values) < 3:
            return

        # Homogeneity check
        if check_homogeneity:
            try:
                from core.stats.homogeneity import check_homogeneity_full
                homo_result = check_homogeneity_full(values)
                if not homo_result.get('is_homogeneous', True):
                    n_het = homo_result.get('n_heterogeneous', 0)
                    result.add_issue(
                        code="HOMOGENEITY_FAILED",
                        message=f"Homogeneity check failed: {n_het} criteria indicate heterogeneity",
                        severity=ValidationSeverity.WARNING,
                        field="data",
                        details={"n_heterogeneous": n_het, "criteria": homo_result.get('criteria', {})},
                    )
            except Exception as e:
                result.add_issue(
                    code="HOMOGENEITY_ERROR",
                    message=f"Homogeneity check error: {e}",
                    severity=ValidationSeverity.INFO,
                    field="data",
                )

        # Stationarity check
        if check_stationarity:
            try:
                from core.stats.homogeneity import stationarity_test
                years = np.array(dataset.years, dtype=float)
                stat_result = stationarity_test(values, years=years)
                if not stat_result.get('is_stationary', True):
                    result.add_issue(
                        code="STATIONARITY_FAILED",
                        message="Stationarity check failed: significant trend or variance change detected",
                        severity=ValidationSeverity.WARNING,
                        field="data",
                        details={
                            "t_test": stat_result.get('t_test', {}),
                            "f_test": stat_result.get('f_test', {}),
                        },
                    )
            except Exception as e:
                result.add_issue(
                    code="STATIONARITY_ERROR",
                    message=f"Stationarity check error: {e}",
                    severity=ValidationSeverity.INFO,
                    field="data",
                )

        # Outlier check (simple IQR method)
        if check_outliers and len(values) >= 4:
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = values[(values < lower) | (values > upper)]
                if len(outliers) > 0:
                    result.add_issue(
                        code="OUTLIERS_DETECTED",
                        message=f"Detected {len(outliers)} potential outliers (IQR method)",
                        severity=ValidationSeverity.INFO,
                        field="data",
                        details={"outlier_count": len(outliers), "lower_bound": lower, "upper_bound": upper},
                    )

    def generate_quality_report(self, dataset: Dataset) -> DataQualityReport:
        """
        Generate a comprehensive data quality report.

        Args:
            dataset: Dataset to assess

        Returns:
            DataQualityReport with quality metrics
        """
        validation = self.validate_dataset(dataset)

        # Calculate completeness
        years = dataset.years
        if len(years) > 1:
            expected = max(years) - min(years) + 1
            completeness = len(years) / expected
        else:
            completeness = 1.0 if dataset.length > 0 else 0.0

        # Homogeneity
        homo_passed = True
        try:
            from core.stats.homogeneity import check_homogeneity_full
            values = np.array(dataset.values, dtype=float)
            values = values[~np.isnan(values)]
            if len(values) >= 3:
                homo_result = check_homogeneity_full(values)
                homo_passed = homo_result.get('is_homogeneous', True)
        except Exception:
            homo_passed = True

        # Stationarity
        stat_passed = True
        try:
            from core.stats.homogeneity import stationarity_test
            values = np.array(dataset.values, dtype=float)
            values = values[~np.isnan(values)]
            years = np.array(dataset.years, dtype=float)
            if len(values) >= 4:
                stat_result = stationarity_test(values, years=years)
                stat_passed = stat_result.get('is_stationary', True)
        except Exception:
            stat_passed = True

        # Outliers (IQR)
        n_outliers = 0
        values = np.array(dataset.values, dtype=float)
        values = values[~np.isnan(values)]
        if len(values) >= 4:
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                n_outliers = int(np.sum((values < lower) | (values > upper)))

        # Quality score (0-1)
        quality_score = 1.0
        if dataset.length == 0:
            quality_score = 0.0
        else:
            # Penalize for issues
            quality_score -= len(validation.errors) * 0.2
            quality_score -= len(validation.warnings) * 0.1
            quality_score -= len(validation.critical_issues) * 0.3
            quality_score *= completeness
            quality_score = max(0.0, min(1.0, quality_score))

        # Statistics
        stats_dict = {}
        if len(values) > 0:
            stats_dict = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1)),
                "cv": float(np.std(values, ddof=1) / np.mean(values)) if np.mean(values) != 0 else 0,
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "skewness": float(pd.Series(values).skew()),
            }

        return DataQualityReport(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            n_points=dataset.length,
            n_missing=max(0, (max(years) - min(years) + 1) - len(years)) if len(years) > 1 else 0,
            n_outliers=n_outliers,
            homogeneity_passed=homo_passed,
            stationarity_passed=stat_passed,
            completeness_ratio=completeness,
            quality_score=quality_score,
            issues=validation.issues,
            statistics=stats_dict,
        )

    # ============================================================
    # Calculation Result Validation
    # ============================================================

    def validate_calculation_result(
        self,
        calc_result: CalculationResult,
        expected_keys: list[str] | None = None,
        value_bounds: dict[str, tuple[float, float]] | None = None,
    ) -> ValidationResult:
        """
        Validate a calculation result.

        Args:
            calc_result: CalculationResult to validate
            expected_keys: Required keys in output_data
            value_bounds: Dict of key -> (min, max) for numeric values

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)

        if not calc_result.is_successful:
            result.add_issue(
                code="CALCULATION_FAILED",
                message=f"Calculation failed: {calc_result.metadata.error_message}",
                severity=ValidationSeverity.ERROR,
                field="metadata",
            )
            return result

        # Check expected keys
        if expected_keys:
            for key in expected_keys:
                if key not in calc_result.output_data:
                    result.add_issue(
                        code="MISSING_OUTPUT_KEY",
                        message=f"Expected output key '{key}' not found",
                        severity=ValidationSeverity.ERROR,
                        field=f"output_data.{key}",
                    )

        # Check value bounds
        if value_bounds:
            for key, (min_val, max_val) in value_bounds.items():
                if key in calc_result.output_data:
                    value = calc_result.output_data[key]
                    if isinstance(value, (int, float)) and (value < min_val or value > max_val):
                        result.add_issue(
                            code="VALUE_OUT_OF_BOUNDS",
                            message=f"Value {value} for '{key}' outside bounds [{min_val}, {max_val}]",
                            severity=ValidationSeverity.WARNING,
                            field=f"output_data.{key}",
                            details={"value": value, "min": min_val, "max": max_val},
                        )

        # Check for NaN/Inf in numeric outputs
        for key, value in calc_result.output_data.items():
            if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                result.add_issue(
                    code="INVALID_NUMERIC_VALUE",
                    message=f"Output '{key}' contains NaN or Inf",
                    severity=ValidationSeverity.ERROR,
                    field=f"output_data.{key}",
                )
            elif isinstance(value, (list, np.ndarray)):
                arr = np.array(value, dtype=float)
                if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
                    result.add_issue(
                        code="INVALID_ARRAY_VALUES",
                        message=f"Output array '{key}' contains NaN or Inf",
                        severity=ValidationSeverity.WARNING,
                        field=f"output_data.{key}",
                    )

        return result

    # ============================================================
    # Scenario Validation
    # ============================================================

    def validate_scenario(
        self,
        scenario: Scenario,
        required_params: list[str] | None = None,
        param_bounds: dict[str, tuple[Any, Any]] | None = None,
    ) -> ValidationResult:
        """
        Validate scenario parameters.

        Args:
            scenario: Scenario to validate
            required_params: List of required parameter keys
            param_bounds: Dict of param -> (min, max) for validation

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)

        # Check required parameters
        if required_params:
            for param in required_params:
                if param not in scenario.parameters:
                    result.add_issue(
                        code="MISSING_PARAMETER",
                        message=f"Required parameter '{param}' not set",
                        severity=ValidationSeverity.ERROR,
                        field=f"parameters.{param}",
                    )

        # Check parameter bounds
        if param_bounds:
            for param, (min_val, max_val) in param_bounds.items():
                if param in scenario.parameters:
                    value = scenario.parameters[param]
                    try:
                        if value < min_val or value > max_val:
                            result.add_issue(
                                code="PARAMETER_OUT_OF_BOUNDS",
                                message=f"Parameter '{param}' = {value} outside bounds [{min_val}, {max_val}]",
                                severity=ValidationSeverity.WARNING,
                                field=f"parameters.{param}",
                                details={"value": value, "min": min_val, "max": max_val},
                            )
                    except TypeError:
                        # Non-comparable types, skip
                        pass

        return result

    # ============================================================
    # Custom Validators
    # ============================================================

    def register_custom_validator(
        self,
        name: str,
        validator: callable,
    ) -> None:
        """Register a custom validator function."""
        self._custom_validators[name] = validator

    def run_custom_validator(
        self,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> ValidationResult:
        """Run a registered custom validator."""
        if name not in self._custom_validators:
            result = ValidationResult(is_valid=False)
            result.add_issue(
                code="VALIDATOR_NOT_FOUND",
                message=f"Custom validator '{name}' not registered",
                severity=ValidationSeverity.ERROR,
            )
            return result
        return self._custom_validators[name](*args, **kwargs)
