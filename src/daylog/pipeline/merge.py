"""Event log construction."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

from daylog.constants import PIPELINE_VERSION, SCHEMA_VERSION
from daylog.io.ffmpeg import extract_wav_segment
from daylog.io.time import seconds_to_iso
from daylog.pipeline.asr import TranscriptChunk
from daylog.pipeline.vad import VadSegment


def _stable_event_id(
    recording_id: uuid.UUID, event_type: str, t0: float, t1: float, speaker_id: Optional[str]
) -> str:
    namespace = recording_id
    basis = f"{event_type}:{t0:.3f}:{t1:.3f}:{speaker_id or ''}"
    return str(uuid.uuid5(namespace, basis))


def _timestamp_chunk_id(start_time: Optional[datetime], t0: float) -> str:
    """
    Generate chunk ID from timestamp: YYMMDD-HH_MM_SS

    Example: 250111-14_23_45
    """
    if start_time:
        chunk_time = start_time + timedelta(seconds=t0)
        return chunk_time.strftime("%y%m%d-%H_%M_%S")
    else:
        # Fallback if no timestamp
        return f"chunk_{int(t0):06d}"


def merge_transcript_chunks(chunks: List[TranscriptChunk], min_gap_s: float = 15.0) -> List[TranscriptChunk]:
    """
    Merge transcript chunks that are close together.

    Chunks separated by less than min_gap_s are merged into larger blocks.
    Chunks separated by more than min_gap_s remain separate.

    Args:
        chunks: List of transcript chunks sorted by time
        min_gap_s: Minimum gap in seconds to keep chunks separate (default 15s)

    Returns:
        List of merged chunks
    """
    if not chunks:
        return []

    # Sort by start time
    sorted_chunks = sorted(chunks, key=lambda c: c.t0)

    merged = []
    current_t0 = sorted_chunks[0].t0
    current_t1 = sorted_chunks[0].t1
    current_texts = [sorted_chunks[0].text] if sorted_chunks[0].text else []
    current_error = sorted_chunks[0].error

    for chunk in sorted_chunks[1:]:
        gap = chunk.t0 - current_t1

        if gap < min_gap_s:
            # Merge with current block
            current_t1 = chunk.t1
            if chunk.text:
                current_texts.append(chunk.text)
            if chunk.error and not current_error:
                current_error = chunk.error
        else:
            # Save current block and start new one
            merged_text = " ".join(current_texts).strip()
            merged.append(
                TranscriptChunk(
                    t0=current_t0,
                    t1=current_t1,
                    text=merged_text,
                    asr_confidence=None,
                    error=current_error,
                )
            )

            # Start new block
            current_t0 = chunk.t0
            current_t1 = chunk.t1
            current_texts = [chunk.text] if chunk.text else []
            current_error = chunk.error

    # Don't forget the last block
    merged_text = " ".join(current_texts).strip()
    merged.append(
        TranscriptChunk(
            t0=current_t0,
            t1=current_t1,
            text=merged_text,
            asr_confidence=None,
            error=current_error,
        )
    )

    return merged


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
        # Use timestamp-based chunk ID that matches audio filename
        chunk_id = _timestamp_chunk_id(start_time, chunk.t0)

        events.append(
            {
                "event_id": chunk_id,
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
        # Only include transcript_chunk events (skip speech_segment without text)
        if event["event_type"] == "speech_segment":
            continue
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


def export_audio_chunks(
    audio_wav: Path,
    transcript_chunks: List[TranscriptChunk],
    start_time: Optional[datetime],
    output_dir: Path,
    sample_rate: int,
    channels: int,
) -> None:
    """
    Export audio files for each merged transcript chunk.

    Each audio file is named with the chunk's timestamp-based ID (e.g., 250111-14_23_45.wav)
    matching the event_id in the CSV, so users can find the audio if transcription is unclear.

    Args:
        audio_wav: Path to the source audio WAV file
        transcript_chunks: List of merged transcript chunks
        start_time: Recording start time (for generating chunk IDs)
        output_dir: Directory to save audio chunks
        sample_rate: Audio sample rate
        channels: Number of audio channels
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for chunk in transcript_chunks:
        chunk_id = _timestamp_chunk_id(start_time, chunk.t0)
        chunk_filename = f"{chunk_id}.wav"
        chunk_path = output_dir / chunk_filename

        duration = chunk.t1 - chunk.t0

        extract_wav_segment(
            audio_wav,
            chunk_path,
            start_s=chunk.t0,
            duration_s=duration,
            sample_rate=sample_rate,
            channels=channels,
        )
