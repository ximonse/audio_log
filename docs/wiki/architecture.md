# Architecture

The system processes local audio recordings into a canonical event log. The pipeline is
linear and deterministic: input audio is converted to a fixed PCM format, segmented by
VAD, transcribed per segment, and merged into an events stream.

Key properties:
- Local-first: no cloud calls required for MVP.
- Traceable: every output links to the original file and timestamps.
- Reproducible: stable IDs and schema versioning.

Modules:
- `io/`: file IO, ffmpeg helpers, serialization, and validation.
- `pipeline/`: VAD, ASR, diarization (optional), merge layer.
- `cli.py`: user entrypoint.
