"""Build-time asset preparation for HydroSphere."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer


def resolve_icon_path(project_root: Path | None = None) -> Path | None:
    """Return an existing ICO or generate one from the bundled SVG logo."""
    root = project_root or Path.cwd()
    direct_icon = root / "icon.ico"
    if direct_icon.exists():
        return direct_icon

    svg_path = root / "gui" / "resources" / "logo.svg"
    if not svg_path.exists():
        return None

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        return None

    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    asset_dir = root / "build" / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    png_path = asset_dir / "hydrosphere-icon.png"
    ico_path = asset_dir / "hydrosphere.ico"
    if not image.save(str(png_path), "PNG"):
        return None
    try:
        with Image.open(png_path) as icon_image:
            icon_image.save(
                ico_path,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
            )
    except OSError:
        return None
    finally:
        png_path.unlink(missing_ok=True)
    return ico_path


__all__ = ["resolve_icon_path"]
