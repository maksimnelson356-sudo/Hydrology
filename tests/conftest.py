"""
tests/conftest.py
Ensures the project root is importable when pytest is started from any directory
(e.g. `pytest tests` or `python -m pytest tests`).

The root-level `test_*.py` scripts are legacy standalone runners and are not part
of this directory; see DOCS/ROADMAP.md, section 7.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
