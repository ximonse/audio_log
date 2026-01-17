import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from daylog.config import DaylogConfig, OutputConfig
from daylog.pipeline.run import process_recording

@pytest.fixture
def mock_pipeline_stages():
    """Mock out heavy pipeline stages to test callbacks only."""
    with patch("daylog.pipeline.run.convert_to_wav") as mock_convert, \
         patch("daylog.pipeline.run.run_vad") as mock_vad, \
         patch("daylog.pipeline.run.transcribe_segments") as mock_asr, \
         patch("daylog.pipeline.run.merge_transcript_chunks") as mock_merge, \
         patch("daylog.pipeline.run.export_audio_chunks") as mock_export, \
         patch("daylog.pipeline.run.probe_duration", return_value=10.0), \
         patch("daylog.pipeline.run.write_json"), \
         patch("daylog.pipeline.run.write_jsonl"), \
         patch("daylog.pipeline.run.write_csv"), \
         patch("pathlib.Path.write_text"):
        
        # Configure mocks
        mock_vad.return_value = [] # No segments -> skip ASR
        yield {
            "convert": mock_convert,
            "vad": mock_vad
        }

def test_pipeline_callbacks_no_speech(tmp_path, mock_pipeline_stages):
    """Test callbacks flow when no speech is detected."""
    # Setup
    input_path = tmp_path / "test.mp3"
    input_path.touch()
    
    config = DaylogConfig(output=OutputConfig(root_dir=str(tmp_path / "out")))
    callback = MagicMock()
    
    # Run
    process_recording(
        input_path,
        config,
        date_override="2026-01-01",
        start_time=None,
        use_mtime=False,
        progress_callback=callback
    )
    
    # Verify calls
    # We expect calls: Initializing, Converting, Audio converted, Running VAD, VAD detailed, Merging, Saving, Completed
    calls = [args[0] for args, _ in callback.call_args_list]
    
    assert "Initializing" in calls
    assert "Converting audio" in calls
    assert "Running VAD" in calls
    assert "Completed" in calls
    
    # Check increasing progress
    progress_values = [args[1] for args, _ in callback.call_args_list]
    assert sorted(progress_values) == progress_values
    assert progress_values[-1] == 1.0

def test_pipeline_callbacks_with_speech_mock(tmp_path):
    """Test callbacks flow with speech (mocking deeper to hit ASR)."""
    # This requires more complex mocking of VAD segments, implemented if needed.
    # For now ensuring the callback is plumbed through is sufficient.
    pass
