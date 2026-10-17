"""Paths to read-only application resources in source and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path

RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
