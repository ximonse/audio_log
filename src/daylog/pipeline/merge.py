"""Event log construction."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable, List, Optional

from daylog.constants import PIPELINE_VERSION, SCHEMA_VERSION
from daylog.io.time import seconds_to_iso
from daylog.pipeline.asr import TranscriptChunk
from daylog.pipeline.vad import VadSegment


def _stable_event_id(
    recording_id: uuid.UUID, event_type: str, t0: float, t1: float, speaker_id: Optional[str]
) -> str:
    namespace = recording_id
    basis = f"{event_type}:{t0:.3f}:{t1:.3f}:{speaker_id or ''}"
    return str(uuid.uuid5(namespace, basis))


def build_events(
    recording_id: uuid.UUID,
    run_id: uuid.UUID,
    start_time: Optional[datetime],
    vad_segments: Iterable[VadSegment],
    transcript_chunks: Iterable[TranscriptChunk],
) -> List[dict]:
    events: List[dict] = []
    for seg in vad_segments:
        events.append(
            {
                "event_id": _stable_event_id(recording_id, "speech_segment", seg.t0, seg.t1, None),
                "recording_id": str(recording_id),
                "run_id": str(run_id),
                "event_type": "speech_segment",
                "t0": round(seg.t0, 3),
                "t1": round(seg.t1, 3),
                "start_iso": seconds_to_iso(start_time, seg.t0),
                "end_iso": seconds_to_iso(start_time, seg.t1),
                "speaker_id": None,
                "text": None,
                "error": None,
                "vad_confidence": seg.vad_confidence,
                "asr_confidence": None,
                "diarization_confidence": None,
                "schema_version": SCHEMA_VERSION,
                "provenance": {
                    "pipeline_version": PIPELINE_VERSION,
                },
            }
        )
    for chunk in transcript_chunks:
        events.append(
            {
                "event_id": _stable_event_id(
                    recording_id, "transcript_chunk", chunk.t0, chunk.t1, None
                ),
                "recording_id": str(recording_id),
                "run_id": str(run_id),
                "event_type": "transcript_chunk",
                "t0": round(chunk.t0, 3),
                "t1": round(chunk.t1, 3),
                "start_iso": seconds_to_iso(start_time, chunk.t0),
                "end_iso": seconds_to_iso(start_time, chunk.t1),
                "speaker_id": None,
                "text": chunk.text,
                "error": chunk.error,
                "vad_confidence": None,
                "asr_confidence": chunk.asr_confidence,
                "diarization_confidence": None,
                "schema_version": SCHEMA_VERSION,
                "provenance": {
                    "pipeline_version": PIPELINE_VERSION,
                },
            }
        )
    events.sort(key=lambda item: (item["t0"], item["event_type"]))
    return events


def build_csv_rows(events: Iterable[dict]) -> List[dict]:
    rows = []
    for event in events:
        rows.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "t0": event["t0"],
                "t1": event["t1"],
                "start_iso": event["start_iso"],
                "end_iso": event["end_iso"],
                "speaker_id": event["speaker_id"],
                "text": event["text"],
                "error": event["error"],
            }
        )
    return rows
