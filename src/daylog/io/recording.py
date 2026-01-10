"""Recording metadata generation."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, Optional

from daylog.constants import DEFAULT_TIMEZONE, PIPELINE_VERSION, SCHEMA_VERSION
from daylog.config import DaylogConfig
from daylog.io.versions import ffmpeg_version, ffprobe_version, package_version, python_version


def build_recording_metadata(
    recording_id: str,
    run_id: str,
    input_path: Path,
    duration_s: float,
    start_time: Optional[datetime],
    start_time_source: str,
    file_hash: str,
    config: DaylogConfig,
) -> Dict[str, Any]:
    stat = input_path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=ZoneInfo(DEFAULT_TIMEZONE))
    return {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "recording_id": recording_id,
        "run_id": run_id,
        "input": {
            "path": str(input_path),
            "size_bytes": stat.st_size,
            "mtime": mtime.isoformat(),
            "sha256": file_hash,
            "duration_s": duration_s,
        },
        "start_time": start_time.isoformat() if start_time else None,
        "start_time_source": start_time_source,
        "tool_versions": {
            "python": python_version(),
            "ffmpeg": ffmpeg_version(),
            "ffprobe": ffprobe_version(),
            "webrtcvad": package_version("webrtcvad"),
            "faster_whisper": package_version("faster-whisper"),
        },
        "config": {
            "vad": config.vad.__dict__,
            "asr": config.asr.__dict__,
            "diarize": config.diarize.__dict__,
            "audio": config.audio.__dict__,
            "output": config.output.__dict__,
        },
    }
