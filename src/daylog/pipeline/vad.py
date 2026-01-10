"""Voice activity detection using WebRTC VAD."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import webrtcvad

from daylog.config import VadConfig


@dataclass(frozen=True)
class VadSegment:
    t0: float
    t1: float
    vad_confidence: float


def _initial_segments(speech_flags: List[bool]) -> List[Tuple[int, int]]:
    segments = []
    start = None
    for idx, is_speech in enumerate(speech_flags):
        if is_speech and start is None:
            start = idx
        elif not is_speech and start is not None:
            segments.append((start, idx))
            start = None
    if start is not None:
        segments.append((start, len(speech_flags)))
    return segments


def _apply_padding(segments: List[Tuple[int, int]], frame_s: float, config: VadConfig) -> List[Tuple[float, float]]:
    padded = []
    for start, end in segments:
        t0 = max(0.0, start * frame_s - config.padding_pre_s)
        t1 = end * frame_s + config.padding_post_s
        padded.append((t0, t1))
    return padded


def _merge_segments(segments: List[Tuple[float, float]], merge_gap_s: float) -> List[Tuple[float, float]]:
    if not segments:
        return []
    segments = sorted(segments, key=lambda seg: seg[0])
    merged = [list(segments[0])]
    for t0, t1 in segments[1:]:
        if t0 - merged[-1][1] <= merge_gap_s:
            merged[-1][1] = max(merged[-1][1], t1)
        else:
            merged.append([t0, t1])
    return [(float(t0), float(t1)) for t0, t1 in merged]


def run_vad(wav_path: Path, config: VadConfig) -> List[VadSegment]:
    if config.frame_ms not in (10, 20, 30):
        raise ValueError("frame_ms must be 10, 20, or 30 for WebRTC VAD")
    frame_s = config.frame_ms / 1000.0
    vad = webrtcvad.Vad(config.mode)
    speech_flags = []
    with wave.open(str(wav_path), "rb") as wf:
        num_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        if num_channels != 1:
            raise ValueError("VAD requires mono audio")
        if sample_width != 2:
            raise ValueError("VAD requires 16-bit PCM")
        frame_samples = int(sample_rate * frame_s)
        while True:
            frame = wf.readframes(frame_samples)
            if len(frame) < frame_samples * sample_width:
                break
            speech_flags.append(vad.is_speech(frame, sample_rate))
    initial = _initial_segments(speech_flags)
    padded = _apply_padding(initial, frame_s, config)
    merged = _merge_segments(padded, config.merge_gap_s)
    segments = []
    for t0, t1 in merged:
        if t1 - t0 < config.min_speech_s:
            continue
        segments.append(VadSegment(t0=t0, t1=t1, vad_confidence=1.0))
    return segments


def merge_segments(segments: List[Tuple[float, float]], merge_gap_s: float) -> List[Tuple[float, float]]:
    return _merge_segments(segments, merge_gap_s)
