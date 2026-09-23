"""
gui/tabs/tab_data_quality.py
Data quality tab for HydroSphere GUI.
"""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout as FormLayout,
)
from PyQt6.QtWidgets import (
    QGroupBox as GroupBox,
)
from PyQt6.QtWidgets import (
    QHBoxLayout as HBox,
)
from PyQt6.QtWidgets import (
    QLabel as Label,
)
from PyQt6.QtWidgets import (
    QPushButton as PushButton,
)
from PyQt6.QtWidgets import (
    QTextEdit as TextEdit,
)
from PyQt6.QtWidgets import (
    QVBoxLayout as VBox,
)
from PyQt6.QtWidgets import (
    QWidget as Widget,
)

from core.domain.models import DataQualityReport


class TabDataQuality(Widget):
    """Tab showing data quality assessment for the selected dataset."""

    # Signals for requesting actions based on recommendations
    fill_missing_requested = pyqtSignal()
    fill_missing_with_correlation_requested = pyqtSignal()
    check_homogeneity_requested = pyqtSignal()
    detect_outliers_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._report: DataQualityReport | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = VBox()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Dataset info group
        info_group = GroupBox("Dataset Information")
        info_layout = FormLayout()
        self.dataset_name_label = Label("-")
        self.dataset_id_label = Label("-")
        self.n_points_label = Label("-")
        info_layout.addRow("Name:", self.dataset_name_label)
        info_layout.addRow("ID:", self.dataset_id_label)
        info_layout.addRow("Data Points:", self.n_points_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Quality metrics group
        metrics_group = GroupBox("Quality Metrics")
        metrics_layout = FormLayout()
        self.completeness_label = Label("-")
        self.quality_score_label = Label("-")
        self.quality_grade_label = Label("-")
        self.homogeneity_label = Label("-")
        self.stationarity_label = Label("-")
        self.n_missing_label = Label("-")
        self.n_outliers_label = Label("-")
        metrics_layout.addRow("Completeness:", self.completeness_label)
        metrics_layout.addRow("Quality Score:", self.quality_score_label)
        metrics_layout.addRow("Quality Grade:", self.quality_grade_label)
        metrics_layout.addRow("Homogeneity Passed:", self.homogeneity_label)
        metrics_layout.addRow("Stationarity Passed:", self.stationarity_label)
        metrics_layout.addRow("Missing Years:", self.n_missing_label)
        metrics_layout.addRow("Outliers Detected:", self.n_outliers_label)
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        # Issues group
        issues_group = GroupBox("Issues and Recommendations")
        self.issues_edit = TextEdit()
        self.issues_edit.setReadOnly(True)
        issues_layout = VBox()
        issues_layout.addWidget(self.issues_edit)
        issues_group.setLayout(issues_layout)
        layout.addWidget(issues_group)

        # Actions group
        actions_group = GroupBox("Recommended Actions")
        actions_layout = HBox()
        self.btn_fill_missing = PushButton("Fill Missing (Interpolation)")
        self.btn_fill_missing.clicked.connect(self.fill_missing_requested.emit)
        self.btn_fill_missing.setVisible(False)
        self.btn_fill_missing_corr = PushButton("Fill Missing (Correlation)")
        self.btn_fill_missing_corr.clicked.connect(self.fill_missing_with_correlation_requested.emit)
        self.btn_fill_missing_corr.setVisible(False)
        self.btn_check_homogeneity = PushButton("Check Homogeneity")
        self.btn_check_homogeneity.clicked.connect(self.check_homogeneity_requested.emit)
        self.btn_check_homogeneity.setVisible(False)
        self.btn_detect_outliers = PushButton("Detect Outliers")
        self.btn_detect_outliers.clicked.connect(self.detect_outliers_requested.emit)
        self.btn_detect_outliers.setVisible(False)
        actions_layout.addWidget(self.btn_fill_missing)
        actions_layout.addWidget(self.btn_fill_missing_corr)
        actions_layout.addWidget(self.btn_check_homogeneity)
        actions_layout.addWidget(self.btn_detect_outliers)
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        layout.addStretch(1)
        self.setLayout(layout)

    def update_report(self, report: DataQualityReport | None) -> None:
        """Update the tab with a new data quality report."""
        self._report = report
        if report is None:
            self._clear()
            return

        # Dataset info
        self.dataset_name_label.setText(report.dataset_name)
        self.dataset_id_label.setText(str(report.dataset_id))
        self.n_points_label.setText(str(report.n_points))

        # Metrics
        self.completeness_label.setText(f"{report.completeness_ratio:.2%}")
        self.quality_score_label.setText(f"{report.quality_score:.3f}")
        self.quality_grade_label.setText(report.quality_grade)
        self.homogeneity_label.setText("Yes" if report.homogeneity_passed else "No")
        self.stationarity_label.setText("Yes" if report.stationarity_passed else "No")
        self.n_missing_label.setText(str(report.n_missing))
        self.n_outliers_label.setText(str(report.n_outliers))

        # Issues and recommendations
        lines: list[str] = []
        if report.issues:
            lines.append(f"Found {len(report.issues)} issue(s):\\n")
            for i, issue in enumerate(report.issues, 1):
                lines.append(f"{i}. [{issue.severity.value.upper()}] {issue.message}")
                if issue.details:
                    # Show why it matters and recommended actions if present
                    why = issue.details.get("why_it_matters")
                    if why:
                        lines.append(f"   Why it matters: {why}")
                    actions = issue.details.get("recommended_actions")
                    if actions:
                        lines.append("   Recommended actions:")
                        for act in actions:
                            lines.append(f"     - {act.get('title', '')}: {act.get('description', '')}")
                lines.append("")  # blank line between issues
        else:
            lines.append("No issues found. Data quality is good!")

        self.issues_edit.setPlainText("\\n".join(lines))

    def _clear(self) -> None:
        """Clear the tab display."""
        self.dataset_name_label.setText("-")
        self.dataset_id_label.setText("-")
        self.n_points_label.setText("-")
        self.completeness_label.setText("-")
        self.quality_score_label.setText("-")
        self.quality_grade_label.setText("-")
        self.homogeneity_label.setText("-")
        self.stationarity_label.setText("-")
        self.n_missing_label.setText("-")
        self.n_outliers_label.setText("-")
        self.issues_edit.clear()
