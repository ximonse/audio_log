"""Version discovery helpers."""

from __future__ import annotations

import platform
import subprocess
from typing import Optional


def _run_version(cmd: list[str]) -> Optional[str]:
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.splitlines()[0].strip()


def ffmpeg_version() -> Optional[str]:
    return _run_version(["ffmpeg", "-version"])


def ffprobe_version() -> Optional[str]:
    return _run_version(["ffprobe", "-version"])


def package_version(package_name: str) -> Optional[str]:
    try:
        import importlib.metadata as metadata

        return metadata.version(package_name)
    except Exception:
        return None


def python_version() -> str:
    return platform.python_version()