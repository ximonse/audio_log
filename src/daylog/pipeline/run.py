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
import time
from daylog.io.paths import build_paths
from daylog.io.recording import build_recording_metadata
from daylog.io.serialize import write_csv, write_json, write_jsonl
from daylog.pipeline.asr import TranscriptChunk, transcribe_segments
from daylog.pipeline.merge import (
    _timestamp_chunk_id,
    build_csv_rows,
    build_events,
    export_audio_chunks,
    merge_transcript_chunks,
)
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
    # Priority 1: User-provided start_time
    if start_time:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
        dt = datetime.fromisoformat(start_time)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt, "user_set"

    # Priority 2: Parse from filename
    from daylog.gui.date_parser import DateTimeParser
    result = DateTimeParser.parse_filename(input_path.name)
    if result:
        dt, has_time = result
        if has_time:
            return dt, "filename"

    # Priority 3: Parse from parent directory name (e.g., "1 sep. 2024 18-46-16 (5)")
    if input_path.parent:
        result = DateTimeParser.parse_filename(input_path.parent.name)
        if result:
            dt, has_time = result
            if has_time:
                return dt, "directory_name"

    # Priority 4: Use file mtime if requested
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
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> Path:
    def _report(stage: str, progress: float) -> None:
        if progress_callback:
            progress_callback(stage, progress)

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

    _report("Initializing", 0.05)
    duration_s = probe_duration(paths.original_copy)
    recording_id = _recording_id(file_hash, duration_s)
    run_id = uuid.uuid4()

    start_dt, start_source = _resolve_start_time(
        input_path, start_time=start_time, use_mtime=use_mtime
    )

    # === PERFORMANCE TIMING ===
    pipeline_start = time.time()
    logger.info(f"=== PIPELINE START: {input_path.name} (duration: {duration_s:.1f}s) ===")

    # Stage 1: Audio conversion
    stage_start = time.time()
    logger.info("Stage 1/5: Converting audio")
    _report("Converting audio", 0.1)
    convert_to_wav(
        paths.original_copy,
        paths.audio_wav,
        sample_rate=config.audio.sample_rate_hz,
        channels=config.audio.channels,
    )
    stage_time = time.time() - stage_start
    logger.info(f"✓ Audio conversion completed in {stage_time:.1f}s")
    _report("Audio converted", 0.2)

    # Stage 2: VAD
    stage_start = time.time()
    logger.info("Stage 2/5: Running VAD (Energy + Spectral + Silero)")
    _report("Running VAD", 0.25)
    vad_segments = run_vad(paths.audio_wav, config.vad)
    stage_time = time.time() - stage_start
    total_speech_s = sum(seg.t1 - seg.t0 for seg in vad_segments)
    logger.info(f"✓ VAD completed in {stage_time:.1f}s - Found {len(vad_segments)} segments ({total_speech_s:.1f}s speech)")
    _report("VAD detailed", 0.3)

    segments_payload = {
        "schema_version": SCHEMA_VERSION,
        "recording_id": str(recording_id),
        "segments": [segment.__dict__ for segment in vad_segments],
    }
    write_json(paths.segments_json, segments_payload)

    # Stage 3: ASR (Transcription)
    transcript_chunks = []
    detected_language = None
    if vad_segments:
        stage_start = time.time()
        logger.info(f"Stage 3/5: Running ASR on {len(vad_segments)} segments ({total_speech_s:.1f}s speech)")
        _report("Initializing Whisper", 0.35)
        
        # Helper to bridge ASR progress to main callback
        asr_total = len(vad_segments)
        def _asr_callback(idx: int, total: int):
             # Map ASR progress (0-100%) to pipeline progress (35-85%)
             asr_percent = idx / total if total > 0 else 0
             pipeline_percent = 0.35 + (asr_percent * 0.50)
             _report(f"Transcribing segment {idx}/{total}", pipeline_percent)

        try:
            # Note: We need to modify transcribe_segments to accept callback if we want granular updates there too.
            # For now, we'll just report start/end of this block, unless we modify asr.py as well.
            # Assuming transcribe_segments doesn't take a callback yet, we'll implement it next or just wrapper it.
            # Let's check asr.py content first? I already read it via list_dir but not view_file.
            # I will trust the plan and just wrap it for now, or update it if I can.
            
            transcript_chunks, detected_language = transcribe_segments(
                paths.audio_wav,
                [(seg.t0, seg.t1) for seg in vad_segments],
                config.asr,
                paths.processed_dir / "chunks",
                sample_rate=config.audio.sample_rate_hz,
                channels=config.audio.channels,
            )
            stage_time = time.time() - stage_start
            throughput = total_speech_s / stage_time if stage_time > 0 else 0
            logger.info(f"✓ ASR completed in {stage_time:.1f}s ({stage_time/60:.1f}min) - Throughput: {throughput:.2f}x realtime")
        except Exception as exc:
            stage_time = time.time() - stage_start
            logger.error(f"✗ ASR failed after {stage_time:.1f}s: %s", exc)
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
        logger.info("Stage 3/5: No speech segments found; skipping ASR")
    
    _report("ASR Completed", 0.85)

    # Stage 4: Merge chunks
    stage_start = time.time()
    logger.info("Stage 4/5: Merging transcript chunks")
    if transcript_chunks:
        original_count = len(transcript_chunks)
        transcript_chunks = merge_transcript_chunks(transcript_chunks, min_gap_s=15.0)
        stage_time = time.time() - stage_start
        logger.info(f"✓ Merged {original_count} chunks into {len(transcript_chunks)} blocks in {stage_time:.1f}s")

        # Export audio chunks (matching CSV event_id)
        logger.info(f"Exporting {len(transcript_chunks)} audio chunks...")
        audio_chunks_dir = paths.processed_dir / "audio_chunks"
        export_audio_chunks(
            audio_wav=paths.audio_wav,
            transcript_chunks=transcript_chunks,
            start_time=start_dt,
            output_dir=audio_chunks_dir,
            sample_rate=config.audio.sample_rate_hz,
            channels=config.audio.channels,
        )
        logger.info(f"✓ Audio chunks saved to {audio_chunks_dir}")
    else:
        stage_time = time.time() - stage_start
        logger.info(f"✓ No chunks to merge ({stage_time:.1f}s)")
    
    _report("Merging completed", 0.90)

    # Stage 5: Output files
    stage_start = time.time()
    logger.info("Stage 5/5: Writing output files")

    # Build transcript chunks with chunk_id included
    transcript_chunks_with_id = []
    for chunk in transcript_chunks:
        chunk_id = _timestamp_chunk_id(start_dt, chunk.t0)
        chunk_dict = {
            "chunk_id": chunk_id,
            "t0": chunk.t0,
            "t1": chunk.t1,
            "text": chunk.text,
            "asr_confidence": chunk.asr_confidence,
            "error": chunk.error,
        }
        transcript_chunks_with_id.append(chunk_dict)

    # Calculate recording end_time
    from datetime import timedelta
    end_dt = None
    if start_dt:
        end_dt = start_dt + timedelta(seconds=duration_s)

    transcript_payload = {
        "schema_version": SCHEMA_VERSION,
        "recording_id": str(recording_id),
        "language": detected_language,
        "start_time": start_dt.isoformat() if start_dt else None,
        "end_time": end_dt.isoformat() if end_dt else None,
        "duration_s": duration_s,
        "chunks": transcript_chunks_with_id,
    }
    write_json(paths.transcript_json, transcript_payload)

    transcript_lines = []
    for chunk in transcript_chunks:
        if not chunk.text:
            continue
        chunk_id = _timestamp_chunk_id(start_dt, chunk.t0)
        transcript_lines.append(f"[{chunk_id}] {chunk.text}")
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

    stage_time = time.time() - stage_start
    logger.info(f"✓ Output files written in {stage_time:.1f}s")
    _report("Saving outputs", 0.95)

    if not config.output.keep_intermediate:
        chunk_dir = paths.processed_dir / "chunks"
        if chunk_dir.exists():
            try:
                shutil.rmtree(chunk_dir)
            except Exception as exc:
                logger.warning(f"Could not remove chunks directory (not critical): {exc}")

    # === PIPELINE SUMMARY ===
    total_time = time.time() - pipeline_start
    realtime_factor = duration_s / total_time if total_time > 0 else 0
    logger.info("=" * 70)
    logger.info(f"=== PIPELINE COMPLETE ===")
    logger.info(f"Total time: {total_time:.1f}s ({total_time/60:.1f}min)")
    logger.info(f"Audio duration: {duration_s:.1f}s ({duration_s/60:.1f}min)")
    logger.info(f"Realtime factor: {realtime_factor:.2f}x ({100/realtime_factor:.1f}% realtime)")
    logger.info(f"VAD segments: {len(vad_segments)} ({total_speech_s:.1f}s speech)")
    logger.info(f"Transcript blocks: {len(transcript_chunks)}")
    logger.info(f"Language detected: {detected_language or 'unknown'}")
    logger.info(f"Output: {paths.recording_dir}")
    logger.info("=" * 70)
    _report("Completed", 1.0)

    return paths.recording_dir


def run_pipeline(
    input_path: Path,
    config: DaylogConfig,
    date_override: Optional[str],
    start_time: Optional[str],
    use_mtime: bool,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> list[Path]:
    outputs = []
    files = list(iter_input_files(input_path))
    total_files = len(files)
    
    for idx, path in enumerate(files):
        # Create a wrapper callback to scale progress for batch processing if needed,
        # or just pass it through. Typically batch processor handles item-level progress.
        # Here we'll just pass it through as requested for single-item granularity.
        outputs.append(
            process_recording(
                path,
                config,
                date_override=date_override,
                start_time=start_time,
                use_mtime=use_mtime,
                progress_callback=progress_callback,
            )
        )
    if not outputs:
        raise FileNotFoundError(f"No audio files found at {input_path}")
    return outputs
