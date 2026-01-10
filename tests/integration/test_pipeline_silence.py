import os
from pathlib import Path
import wave

import pytest

from daylog.config import DaylogConfig, OutputConfig
from daylog.pipeline.run import process_recording


def _ffmpeg_available() -> bool:
    import shutil

    return shutil.which("ffmpeg") is not None


@pytest.mark.skipif(
    os.environ.get("DAYLOG_RUN_INTEGRATION") != "1", reason="integration disabled"
)
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not available")
def test_pipeline_silence(tmp_path: Path) -> None:
    wav_path = tmp_path / "silence.wav"
    sample_rate = 16000
    duration_s = 1.0
    frames = int(sample_rate * duration_s)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frames)

    config = DaylogConfig(output=OutputConfig(root_dir=str(tmp_path / "out")))
    output_dir = process_recording(
        wav_path,
        config,
        date_override="2026-01-10",
        start_time=None,
        use_mtime=False,
    )

    processed = output_dir / "processed"
    assert (processed / "recording.json").exists()
    assert (processed / "segments.json").exists()
    assert (processed / "transcript.json").exists()
    assert (processed / "events.jsonl").exists()
    assert (processed / "events.csv").exists()
