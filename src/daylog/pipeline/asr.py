"""ASR transcription using faster-whisper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from daylog.config import AsrConfig
from daylog.io.ffmpeg import extract_wav_segment


@dataclass(frozen=True)
class TranscriptChunk:
    t0: float
    t1: float
    text: str
    asr_confidence: Optional[float]
    error: Optional[str]


def _load_model(model_name: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("faster-whisper is not installed") from exc
    return WhisperModel(model_name)


def transcribe_segments(
    wav_path: Path,
    segments: Iterable[Tuple[float, float]],
    config: AsrConfig,
    work_dir: Path,
    sample_rate: int,
    channels: int,
) -> Tuple[List[TranscriptChunk], Optional[str]]:
    model = _load_model(config.model)
    chunks: List[TranscriptChunk] = []
    detected_language: Optional[str] = None

    work_dir.mkdir(parents=True, exist_ok=True)

    for idx, (t0, t1) in enumerate(segments):
        duration = max(0.0, t1 - t0)
        if duration <= 0.0:
            continue
        chunk_path = work_dir / f"chunk_{idx:04d}.wav"
        extract_wav_segment(
            wav_path,
            chunk_path,
            start_s=t0,
            duration_s=duration,
            sample_rate=sample_rate,
            channels=channels,
        )
        try:
            segment_iter, info = model.transcribe(
                str(chunk_path),
                beam_size=config.beam_size,
                language=config.language,
                word_timestamps=config.word_timestamps,
                vad_filter=config.vad_filter,
            )
        except Exception as exc:  # pragma: no cover - runtime/model errors
            chunks.append(
                TranscriptChunk(
                    t0=t0,
                    t1=t1,
                    text="",
                    asr_confidence=None,
                    error=str(exc),
                )
            )
            continue
        if detected_language is None:
            detected_language = info.language
        for segment in segment_iter:
            abs_t0 = t0 + float(segment.start)
            abs_t1 = t0 + float(segment.end)
            chunks.append(
                TranscriptChunk(
                    t0=abs_t0,
                    t1=abs_t1,
                    text=segment.text.strip(),
                    asr_confidence=float(getattr(segment, "avg_logprob", 0.0)),
                    error=None,
                )
            )
    return chunks, detected_language
