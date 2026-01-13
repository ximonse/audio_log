"""Voice activity detection with energy and spectral pre-filtering."""

from __future__ import annotations

import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch

from daylog.config import VadConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VadSegment:
    t0: float
    t1: float
    vad_confidence: float


def _read_wav_data(wav_path: Path) -> Tuple[np.ndarray, int]:
    """Read WAV file and return audio data + sample rate."""
    with wave.open(str(wav_path), "rb") as wf:
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        audio_bytes = wf.readframes(n_frames)
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, sample_rate


def _energy_gate(audio: np.ndarray, sample_rate: int, block_s: float = 1.0, db_threshold: float = -50.0) -> List[Tuple[int, int]]:
    """
    Stage 1: Energy-based filtering.

    Find blocks with audio above energy threshold (removes silence).

    Args:
        audio: Audio samples
        sample_rate: Sample rate in Hz
        block_s: Block size in seconds
        db_threshold: Energy threshold in dB (e.g., -50 dB)

    Returns:
        List of (start_sample, end_sample) regions with energy above threshold
    """
    logger.info(f"Stage 1: Energy gate (threshold={db_threshold} dB)")

    block_samples = int(block_s * sample_rate)
    n_blocks = len(audio) // block_samples

    regions = []
    start = None

    for i in range(n_blocks):
        block = audio[i * block_samples:(i + 1) * block_samples]

        # Calculate RMS energy in dB
        rms = np.sqrt(np.mean(block ** 2))
        db = 20 * np.log10(rms + 1e-10)  # Add epsilon to avoid log(0)

        if db > db_threshold:
            if start is None:
                start = i * block_samples
        else:
            if start is not None:
                regions.append((start, i * block_samples))
                start = None

    # Handle final region
    if start is not None:
        regions.append((start, n_blocks * block_samples))

    total_s = sum(end - start for start, end in regions) / sample_rate
    logger.info(f"Energy gate kept {len(regions)} regions ({total_s:.1f}s / {len(audio)/sample_rate:.1f}s)")

    return regions


def _spectral_filter(audio: np.ndarray, sample_rate: int, regions: List[Tuple[int, int]], window_s: float = 0.5) -> List[Tuple[int, int]]:
    """
    Stage 2: Spectral filtering.

    Analyze frequency content to filter speech-like audio.
    Speech has energy in 300-3400 Hz (telephony band).

    Args:
        audio: Audio samples
        sample_rate: Sample rate in Hz
        regions: Regions from energy gate
        window_s: Window size for spectral analysis

    Returns:
        List of (start_sample, end_sample) regions likely containing speech
    """
    logger.info("Stage 2: Spectral filtering (300-3400 Hz band)")

    window_samples = int(window_s * sample_rate)
    speech_regions = []

    for start, end in regions:
        region_audio = audio[start:end]
        n_windows = len(region_audio) // window_samples

        speech_start = None

        for i in range(n_windows):
            window = region_audio[i * window_samples:(i + 1) * window_samples]

            # FFT to get frequency content
            fft = np.fft.rfft(window)
            freqs = np.fft.rfftfreq(len(window), 1 / sample_rate)
            magnitude = np.abs(fft)

            # Calculate energy in speech band (300-3400 Hz)
            speech_band = (freqs >= 300) & (freqs <= 3400)
            speech_energy = np.sum(magnitude[speech_band])

            # Calculate energy in low-freq noise band (20-200 Hz)
            noise_band = (freqs >= 20) & (freqs <= 200)
            noise_energy = np.sum(magnitude[noise_band])

            # Calculate energy in high-freq band (above 3400 Hz)
            high_band = freqs > 3400
            high_energy = np.sum(magnitude[high_band])

            # Speech detection: high energy in speech band, low in noise band
            total_energy = speech_energy + noise_energy + high_energy + 1e-10
            speech_ratio = speech_energy / total_energy

            # Threshold: at least 40% of energy in speech band
            is_speech_like = speech_ratio > 0.4

            if is_speech_like:
                if speech_start is None:
                    speech_start = start + i * window_samples
            else:
                if speech_start is not None:
                    speech_regions.append((speech_start, start + i * window_samples))
                    speech_start = None

        # Handle final region
        if speech_start is not None:
            speech_regions.append((speech_start, end))

    total_s = sum(end - start for start, end in speech_regions) / sample_rate
    logger.info(f"Spectral filter kept {len(speech_regions)} regions ({total_s:.1f}s)")

    return speech_regions


def _merge_close_regions(regions: List[Tuple[int, int]], sample_rate: int, gap_s: float = 0.5) -> List[Tuple[int, int]]:
    """Merge regions that are close together."""
    if not regions:
        return []

    gap_samples = int(gap_s * sample_rate)
    merged = [list(regions[0])]

    for start, end in regions[1:]:
        if start - merged[-1][1] <= gap_samples:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return [(s, e) for s, e in merged]


def run_vad(wav_path: Path, config: VadConfig) -> List[VadSegment]:
    """
    Run VAD with two-stage pre-filtering optimized for long recordings.

    Stage 1: Energy gate - removes silence
    Stage 2: Spectral filter - removes non-speech audio
    Stage 3: Silero VAD - precise speech detection on candidates

    Args:
        wav_path: Path to mono 16-bit WAV file
        config: VAD configuration

    Returns:
        List of speech segments with timestamps in seconds
    """
    logger.info(f"Running VAD on {wav_path}")

    # Read audio
    audio, sample_rate = _read_wav_data(wav_path)
    duration_s = len(audio) / sample_rate
    logger.info(f"Audio duration: {duration_s:.1f}s ({duration_s/3600:.1f}h)")

    # Stage 1: Energy gate
    energy_regions = _energy_gate(audio, sample_rate, block_s=1.0, db_threshold=-50.0)

    if not energy_regions:
        logger.info("No audio above energy threshold")
        return []

    # Stage 2: Spectral filtering
    speech_regions = _spectral_filter(audio, sample_rate, energy_regions, window_s=0.5)

    if not speech_regions:
        logger.info("No speech-like audio found")
        return []

    # Merge close regions before Silero VAD
    speech_regions = _merge_close_regions(speech_regions, sample_rate, gap_s=0.5)

    # Stage 3: Silero VAD on speech candidates
    logger.info("Stage 3: Silero VAD on speech candidates")
    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        onnx=False,
    )
    (get_speech_timestamps, _, _, _, _) = utils

    all_segments = []

    for region_start, region_end in speech_regions:
        # Extract region audio
        region_audio = audio[region_start:region_end]
        region_tensor = torch.from_numpy(region_audio)

        # Run Silero VAD
        speech_timestamps = get_speech_timestamps(
            region_tensor,
            model,
            sampling_rate=sample_rate,
            threshold=config.threshold,
            min_speech_duration_ms=int(config.min_speech_s * 1000),
            min_silence_duration_ms=int(config.min_silence_s * 1000),
            window_size_samples=512,
            speech_pad_ms=int(config.padding_pre_s * 1000),
        )

        # Convert to absolute timestamps
        for ts in speech_timestamps:
            abs_start = (region_start + ts["start"]) / sample_rate
            abs_end = (region_start + ts["end"]) / sample_rate
            all_segments.append(VadSegment(t0=abs_start, t1=abs_end, vad_confidence=1.0))

    total_speech_s = sum(seg.t1 - seg.t0 for seg in all_segments)
    logger.info(f"Found {len(all_segments)} speech segments ({total_speech_s:.1f}s total)")

    return all_segments
