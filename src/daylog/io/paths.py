"""Output path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecordingPaths:
    recording_dir: Path
    processed_dir: Path
    original_copy: Path
    audio_wav: Path
    segments_json: Path
    transcript_json: Path
    transcript_txt: Path
    events_jsonl: Path
    events_csv: Path
    recording_json: Path


def build_paths(
    output_root: Path, date_str: str, recording_name: str, original_suffix: str
) -> RecordingPaths:
    recording_dir = output_root / date_str / recording_name
    processed_dir = recording_dir / "processed"
    original_name = f"original{original_suffix}"
    return RecordingPaths(
        recording_dir=recording_dir,
        processed_dir=processed_dir,
        original_copy=recording_dir / original_name,
        audio_wav=processed_dir / "audio_16k_mono.wav",
        segments_json=processed_dir / "segments.json",
        transcript_json=processed_dir / "transcript.json",
        transcript_txt=processed_dir / "transcript.txt",
        events_jsonl=processed_dir / "events.jsonl",
        events_csv=processed_dir / "events.csv",
        recording_json=processed_dir / "recording.json",
    )
