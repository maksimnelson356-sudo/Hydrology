"""Headless contracts for the Russian Data Quality UI."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QGroupBox, QLabel, QPushButton

from core.domain import Dataset, DatasetType
from core.services.data_quality_service import DataQualityService
from gui.tabs.tab_data_quality import TabDataQuality


def _app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    assert app is not None
    return app


def _dataset_with_issue() -> Dataset:
    values = {1990 + index: 100.0 + index for index in range(12)}
    del values[1998]
    values[2005] = -1.0
    return Dataset(name="Тестовый пост", data=values, dataset_type=DatasetType.OBSERVED)


def test_data_quality_tab_is_russian_and_action_buttons_are_stacked():
    # Given: a report with gaps and an invalid negative value.
    app = _app()
    tab = TabDataQuality()
    report = DataQualityService().analyze(_dataset_with_issue())
    tab.update_report(report)
    tab.resize(1200, 700)
    tab.show()
    app.processEvents()

    # When: the user-visible tab is inspected.
    group_titles = [group.title() for group in tab.findChildren(QGroupBox)]
    labels = [label.text() for label in tab.findChildren(QLabel)]
    buttons = [button.text() for button in tab.findChildren(QPushButton)]

    # Then: the screen is Russian and the report is populated.
    assert "Как пользоваться" in group_titles
    assert "Качество данных" in labels
    assert all("Dataset" not in text for text in labels)
    assert all("Fill Missing" not in text for text in buttons)
    assert "Заполнить пропуски (интерполяция)" in buttons
    assert "Ряд" in tab.issues_edit.toPlainText() or "пропуск" in tab.issues_edit.toPlainText()

    visible_actions = [
        button
        for button in (
            tab.btn_fill_missing,
            tab.btn_fill_missing_corr,
            tab.btn_check_homogeneity,
            tab.btn_detect_outliers,
        )
        if button.isVisible()
    ]
    assert len(visible_actions) >= 2
    for upper, lower in zip(visible_actions, visible_actions[1:], strict=False):
        assert upper.geometry().bottom() <= lower.geometry().top()
    tab.close()
    tab.deleteLater()
