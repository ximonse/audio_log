# ADR 0001: Core Stack

Date: 2026-01-10

## Decision
Use Python 3.11+, FFmpeg CLI, WebRTC VAD, and faster-whisper for the MVP.

## Context
We need a local-first pipeline with reliable VAD and transcription that runs on
consumer hardware. The Python ecosystem is strongest for this.

## Consequences
- Requires FFmpeg on PATH.
- Model weights for ASR must be downloaded locally.
- The pipeline remains cross-platform with minimal glue code.