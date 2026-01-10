"""Configuration handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


@dataclass(frozen=True)
class VadConfig:
    mode: int = 2
    frame_ms: int = 30
    padding_pre_s: float = 0.3
    padding_post_s: float = 0.3
    merge_gap_s: float = 0.6
    min_speech_s: float = 0.4


@dataclass(frozen=True)
class AsrConfig:
    model: str = "base"
    language: Optional[str] = None
    word_timestamps: bool = False
    beam_size: int = 5
    vad_filter: bool = False


@dataclass(frozen=True)
class DiarizeConfig:
    enabled: bool = False


@dataclass(frozen=True)
class AudioConfig:
    sample_rate_hz: int = 16000
    channels: int = 1


@dataclass(frozen=True)
class OutputConfig:
    root_dir: str = "Recordings"
    keep_intermediate: bool = False


@dataclass(frozen=True)
class DaylogConfig:
    vad: VadConfig = VadConfig()
    asr: AsrConfig = AsrConfig()
    diarize: DiarizeConfig = DiarizeConfig()
    audio: AudioConfig = AudioConfig()
    output: OutputConfig = OutputConfig()


DEFAULT_CONFIG_PATH = Path("daylog.toml")


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _config_to_dict(config: DaylogConfig) -> Dict[str, Any]:
    return {
        "vad": config.vad.__dict__,
        "asr": config.asr.__dict__,
        "diarize": config.diarize.__dict__,
        "audio": config.audio.__dict__,
        "output": config.output.__dict__,
    }


def load_config(path: Optional[Path] = None) -> DaylogConfig:
    path = path or DEFAULT_CONFIG_PATH
    base = _config_to_dict(DaylogConfig())
    if path.exists():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        merged = _deep_merge(base, data)
    else:
        merged = base
    return DaylogConfig(
        vad=VadConfig(**merged.get("vad", {})),
        asr=AsrConfig(**merged.get("asr", {})),
        diarize=DiarizeConfig(**merged.get("diarize", {})),
        audio=AudioConfig(**merged.get("audio", {})),
        output=OutputConfig(**merged.get("output", {})),
    )