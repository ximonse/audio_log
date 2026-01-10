"""FFmpeg helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _run_capture(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def run_ffprobe_json(input_path: Path) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(input_path),
    ]
    output = _run_capture(cmd)
    return json.loads(output)


def probe_duration(input_path: Path) -> float:
    info = run_ffprobe_json(input_path)
    fmt = info.get("format", {})
    duration = fmt.get("duration")
    if duration is None:
        raise ValueError("ffprobe returned no duration")
    return float(duration)


def convert_to_wav(
    input_path: Path, output_path: Path, sample_rate: int, channels: int
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-vn",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    _run(cmd)


def extract_wav_segment(
    input_path: Path,
    output_path: Path,
    start_s: float,
    duration_s: float,
    sample_rate: int,
    channels: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ss",
        f"{start_s:.3f}",
        "-t",
        f"{duration_s:.3f}",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-vn",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    _run(cmd)