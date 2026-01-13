"""Daylog GUI package."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .app import DaylogGUI


def main(config_path: Optional[Path] = None) -> int:
    """
    Launch Daylog GUI.

    Args:
        config_path: Optional path to config file

    Returns:
        Exit code (0 for success)
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        app = DaylogGUI(config_path)
        app.run()
        return 0
    except Exception as e:
        logging.error(f"GUI error: {e}")
        return 1


__all__ = ["DaylogGUI", "main"]
