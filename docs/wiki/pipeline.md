# Pipeline

1) Ingestion
- Accept file/folder input.
- Copy original to the per-recording folder.
- Convert to 16 kHz mono PCM.

2) VAD
- Run WebRTC VAD with configurable thresholds.
- Apply padding, merge gaps, and min speech.
- Write `segments.json`.

3) ASR
- Transcribe per VAD segment using faster-whisper.
- Store transcript chunks and text view.

4) Merge
- Compose canonical `events.jsonl` and human-friendly `events.csv`.

5) Validation
- CLI validation checks presence and basic invariants.