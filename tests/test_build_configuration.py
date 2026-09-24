"""Regression tests for packaged-build configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import build

_PROJECT_MODULE_ROOTS = (
    "core",
    "gui",
    "i18n",
    "version",
    "update_checker",
    "create_unified_template",
)


def test_hidden_imports_reference_existing_project_modules() -> None:
    # Given: the repository's declared PyInstaller project imports.
    project_imports = [
        module_name
        for module_name in build.HIDDEN_IMPORTS
        if module_name.split(".")[0] in _PROJECT_MODULE_ROOTS
    ]

    # When: each import is resolved by Python's import system.
    missing: list[str] = []
    for module_name in project_imports:
        import_name = module_name.removesuffix(".__init__")
        try:
            module_spec = importlib.util.find_spec(import_name)
        except ModuleNotFoundError:
            module_spec = None
        if module_spec is None:
            missing.append(module_name)

    # Then: PyInstaller never receives a stale project-module warning.
    assert missing == []


def test_pyinstaller_uses_logo_when_icon_is_absent(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    # Given: a checkout without icon.ico but with the bundled PNG logo.
    monkeypatch.chdir(tmp_path)
    logo_path = tmp_path / "gui" / "resources" / "logo.png"
    logo_path.parent.mkdir(parents=True)
    logo_path.write_bytes(b"test-logo")

    # When: PyInstaller arguments are assembled.
    args = build.get_pyinstaller_args()
    output = capsys.readouterr().out

    # Then: the existing asset is used and no missing-icon warning is emitted.
    assert "--icon=gui/resources/logo.png" in args
    assert "Warning: icon.ico not found" not in output
