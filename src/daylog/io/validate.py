"""Output validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List


def validate_processed_dir(processed_dir: Path) -> List[str]:
    errors: List[str] = []
    required = [
        "recording.json",
        "segments.json",
        "transcript.json",
        "transcript.txt",
        "events.jsonl",
        "events.csv",
    ]
    for name in required:
        if not (processed_dir / name).exists():
            errors.append(f"missing {name}")
    recording_path = processed_dir / "recording.json"
    duration_s = None
    if recording_path.exists():
        data = json.loads(recording_path.read_text(encoding="utf-8"))
        duration_s = data.get("input", {}).get("duration_s")
    events_path = processed_dir / "events.jsonl"
    if events_path.exists():
        last_t0 = -1.0
        for line in events_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                errors.append("events.jsonl has invalid JSON")
                break
            t0 = event.get("t0")
            t1 = event.get("t1")
            if t0 is None or t1 is None:
                errors.append("events.jsonl missing t0/t1")
                continue
            if t0 < last_t0:
                errors.append("events.jsonl not monotonic")
            last_t0 = t0
            if duration_s is not None and t1 > float(duration_s) + 1.0:
                errors.append("events.jsonl exceeds duration")
    return errors