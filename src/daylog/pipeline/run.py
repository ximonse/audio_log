"""Pipeline runner."""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from daylog.config import DaylogConfig
from daylog.constants import DEFAULT_TIMEZONE, SCHEMA_VERSION
from daylog.io.ffmpeg import convert_to_wav, probe_duration
from daylog.io.hash import sha256_file
from daylog.io.paths import build_paths
from daylog.io.recording import build_recording_metadata
from daylog.io.serialize import write_csv, write_json, write_jsonl
from daylog.pipeline.asr import TranscriptChunk, transcribe_segments
from daylog.pipeline.merge import build_csv_rows, build_events
from daylog.pipeline.vad import run_vad

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg", ".opus"}


logger = logging.getLogger("daylog")


def iter_input_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for path in sorted(input_path.rglob("*")):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
            yield path


def _resolve_date(input_path: Path, override: Optional[str]) -> str:
    if override:
        return override
    mtime = datetime.fromtimestamp(input_path.stat().st_mtime)
    return mtime.date().isoformat()


def _resolve_start_time(
    input_path: Path, start_time: Optional[str], use_mtime: bool
) -> tuple[Optional[datetime], str]:
    if start_time:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
        dt = datetime.fromisoformat(start_time)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt, "user_set"
    if use_mtime:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
        dt = datetime.fromtimestamp(input_path.stat().st_mtime, tz)
        return dt, "file_mtime"
    return None, "unknown"


def _recording_id(file_hash: str, duration_s: float) -> uuid.UUID:
    basis = f"{file_hash}:{duration_s:.3f}"
    return uuid.uuid5(uuid.NAMESPACE_URL, basis)


def process_recording(
    input_path: Path,
    config: DaylogConfig,
    date_override: Optional[str],
    start_time: Optional[str],
    use_mtime: bool,
) -> Path:
    date_str = _resolve_date(input_path, date_override)
    file_hash = sha256_file(input_path)
    recording_name = f"{input_path.stem}_{file_hash[:8]}"
    paths = build_paths(
        Path(config.output.root_dir), date_str, recording_name, input_path.suffix
    )
    paths.recording_dir.mkdir(parents=True, exist_ok=True)
    paths.processed_dir.mkdir(parents=True, exist_ok=True)

    if not paths.original_copy.exists():
        shutil.copy2(input_path, paths.original_copy)

    duration_s = probe_duration(paths.original_copy)
    recording_id = _recording_id(file_hash, duration_s)
    run_id = uuid.uuid4()

    start_dt, start_source = _resolve_start_time(
        input_path, start_time=start_time, use_mtime=use_mtime
    )

    logger.info("Converting audio")
    convert_to_wav(
        paths.original_copy,
        paths.audio_wav,
        sample_rate=config.audio.sample_rate_hz,
        channels=config.audio.channels,
    )

    logger.info("Running VAD")
    vad_segments = run_vad(paths.audio_wav, config.vad)

    segments_payload = {
        "schema_version": SCHEMA_VERSION,
        "recording_id": str(recording_id),
        "segments": [segment.__dict__ for segment in vad_segments],
    }
    write_json(paths.segments_json, segments_payload)

    transcript_chunks = []
    detected_language = None
    if vad_segments:
        logger.info("Running ASR")
        try:
            transcript_chunks, detected_language = transcribe_segments(
                paths.audio_wav,
                [(seg.t0, seg.t1) for seg in vad_segments],
                config.asr,
                paths.processed_dir / "chunks",
                sample_rate=config.audio.sample_rate_hz,
                channels=config.audio.channels,
            )
        except Exception as exc:
            logger.error("ASR failed: %s", exc)
            transcript_chunks = [
                TranscriptChunk(
                    t0=seg.t0,
                    t1=seg.t1,
                    text="",
                    asr_confidence=None,
                    error=str(exc),
                )
                for seg in vad_segments
            ]
    else:
        logger.info("No speech segments found; skipping ASR")

    transcript_payload = {
        "schema_version": SCHEMA_VERSION,
        "recording_id": str(recording_id),
        "language": detected_language,
        "chunks": [chunk.__dict__ for chunk in transcript_chunks],
    }
    write_json(paths.transcript_json, transcript_payload)

    transcript_lines = []
    for chunk in transcript_chunks:
        if not chunk.text:
            continue
        transcript_lines.append(f"[{chunk.t0:.3f}-{chunk.t1:.3f}] {chunk.text}")
    paths.transcript_txt.write_text("\n".join(transcript_lines), encoding="utf-8")

    events = build_events(
        recording_id=recording_id,
        run_id=run_id,
        start_time=start_dt,
        vad_segments=vad_segments,
        transcript_chunks=transcript_chunks,
    )
    write_jsonl(paths.events_jsonl, events)
    write_csv(paths.events_csv, build_csv_rows(events))

    recording_payload = build_recording_metadata(
        recording_id=str(recording_id),
        run_id=str(run_id),
        input_path=paths.original_copy,
        duration_s=duration_s,
        start_time=start_dt,
        start_time_source=start_source,
        file_hash=file_hash,
        config=config,
    )
    write_json(paths.recording_json, recording_payload)

    if not config.output.keep_intermediate:
        chunk_dir = paths.processed_dir / "chunks"
        if chunk_dir.exists():
            shutil.rmtree(chunk_dir)

    return paths.recording_dir


def run_pipeline(
    input_path: Path,
    config: DaylogConfig,
    date_override: Optional[str],
    start_time: Optional[str],
    use_mtime: bool,
) -> list[Path]:
    outputs = []
    for path in iter_input_files(input_path):
        outputs.append(
            process_recording(
                path,
                config,
                date_override=date_override,
                start_time=start_time,
                use_mtime=use_mtime,
            )
        )
    if not outputs:
        raise FileNotFoundError(f"No audio files found at {input_path}")
    return outputs
