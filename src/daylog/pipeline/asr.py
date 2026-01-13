"""ASR transcription using faster-whisper with GPU acceleration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from daylog.config import AsrConfig
from daylog.io.ffmpeg import extract_wav_segment

# Global model cache to avoid CTranslate2 cleanup crash
_MODEL_CACHE: dict = {}


@dataclass(frozen=True)
class TranscriptChunk:
    t0: float
    t1: float
    text: str
    asr_confidence: Optional[float]
    error: Optional[str]


def _detect_device() -> Tuple[str, str]:
    """
    Detect best available device (cuda/cpu) and compute type.

    Returns:
        (device, compute_type) tuple
    """
    try:
        import torch
        if torch.cuda.is_available():
            logging.info("CUDA GPU detected - using GPU acceleration with int8")
            return "cuda", "int8"
    except Exception:
        pass

    logging.info("No CUDA GPU detected - using CPU with int8")
    return "cpu", "int8"


def _load_model(model_name: str):
    """
    Load faster-whisper model with GPU acceleration if available.

    For 3GB VRAM: medium model with int8 quantization fits perfectly.

    IMPORTANT: Models are cached globally to avoid CTranslate2 cleanup crashes.
    This is a known issue where deleting WhisperModel objects causes segfaults.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "faster-whisper is not installed. "
            "Install with: pip install faster-whisper"
        ) from exc

    device, compute_type = _detect_device()

    # Check if model is already loaded (avoids cleanup crash)
    cache_key = f"{model_name}_{device}_{compute_type}"
    if cache_key in _MODEL_CACHE:
        logging.info(f"Using cached {model_name} model on {device}")
        return _MODEL_CACHE[cache_key]

    logging.info(f"Loading {model_name} model on {device} with {compute_type} quantization...")

    # cpu_threads: i5 9600k has 6 cores, use 4 threads to leave headroom
    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
        cpu_threads=4,
        num_workers=1,
    )

    logging.info(f"✓ Model loaded successfully on {device}")

    # Cache model to prevent cleanup crash
    _MODEL_CACHE[cache_key] = model

    return model


def _split_large_segments(segments: List[Tuple[float, float]], max_duration_s: float = 30.0) -> List[Tuple[float, float]]:
    """Split segments longer than max_duration_s into smaller chunks."""
    split_segments = []
    for t0, t1 in segments:
        duration = t1 - t0
        if duration <= max_duration_s:
            split_segments.append((t0, t1))
        else:
            # Split into chunks
            n_chunks = int(duration / max_duration_s) + 1
            chunk_duration = duration / n_chunks
            for i in range(n_chunks):
                chunk_start = t0 + i * chunk_duration
                chunk_end = min(t0 + (i + 1) * chunk_duration, t1)
                split_segments.append((chunk_start, chunk_end))
    return split_segments


def transcribe_segments(
    wav_path: Path,
    segments: Iterable[Tuple[float, float]],
    config: AsrConfig,
    work_dir: Path,
    sample_rate: int,
    channels: int,
    progress_callback=None,
) -> Tuple[List[TranscriptChunk], Optional[str]]:
    """
    Transcribe audio segments using faster-whisper with GPU acceleration.

    Faster-whisper provides 4-12x speedup over openai-whisper with same accuracy.
    Uses int8 quantization to fit in 3GB VRAM (40% memory savings).
    """
    model = _load_model(config.model)
    chunks: List[TranscriptChunk] = []
    detected_language: Optional[str] = None

    work_dir.mkdir(parents=True, exist_ok=True)

    # Split large segments to avoid memory issues and timeouts
    segments_list = list(segments)
    split_segments = _split_large_segments(segments_list, max_duration_s=30.0)
    total_segments = len(split_segments)
    logging.info(f"Processing {total_segments} segments (split from {len(segments_list)})")

    for idx, (t0, t1) in enumerate(split_segments):
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

        logging.info(f"Processing segment {idx+1}/{total_segments}: {duration:05.2f}s")

        # Report progress
        if progress_callback:
            progress_callback(idx + 1, total_segments)

        try:
            # faster-whisper returns (segments_iterator, info) tuple
            segments_iter, info = model.transcribe(
                str(chunk_path),
                language=config.language,
                word_timestamps=config.word_timestamps,
                beam_size=1,  # Faster inference, minimal accuracy loss
                vad_filter=False,  # We already did VAD
            )

            # Detect language from first segment
            if detected_language is None:
                detected_language = info.language

            # Convert generator to list and process segments
            for segment in segments_iter:
                abs_t0 = t0 + segment.start
                abs_t1 = t0 + segment.end
                chunks.append(
                    TranscriptChunk(
                        t0=abs_t0,
                        t1=abs_t1,
                        text=segment.text.strip(),
                        asr_confidence=None,  # faster-whisper doesn't provide per-segment confidence
                        error=None,
                    )
                )

        except Exception as exc:  # pragma: no cover - runtime/model errors
            logging.error(f"Error transcribing segment {idx+1}: {exc}")
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

    logging.info(f"✓ Transcribed {len(chunks)} chunks, language={detected_language}")

    # NOTE: Model is cached globally - never deleted to avoid CTranslate2 cleanup crash
    return chunks, detected_language
