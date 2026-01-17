# Work Log

## 2026-01-10 16:10
- What changed: bootstrapped repo structure, CLI, pipeline modules (ffmpeg, VAD, ASR, merge), config, tests, docs, and CI scaffolding.
- Why: establish MVP baseline with reproducible outputs and schema tracking.
- Risks/known issues: ASR requires faster-whisper model download; integration tests gated by env flag.
- Next steps: wire diarization hook, add real audio fixtures, and improve VAD confidence metrics.
## 2026-01-10 16:40
- What changed: added validation script, CI config, docs wiki, and updated pipeline with stable IDs and ASR error handling.
- Why: enforce schema/documentation consistency and improve traceability.
- Risks/known issues: ASR model download still required for full transcripts; VAD uses WebRTC and may miss low-volume speech.
- Next steps: add real speech fixtures and refine VAD confidence metrics.

## 2026-01-10 16:50
- What changed: updated default ASR language to auto-detect and improved recording metadata timezone handling.
- Why: keep mixed-language support and consistent timestamp provenance.
- Risks/known issues: auto language detection can be slower on short segments.
- Next steps: add speech fixtures and diarization scaffold tests.

## 2026-01-10 16:55
- What changed: added CLI helper flags to pipeline scripts for start time and mtime usage.
- Why: make local runs more convenient.
- Risks/known issues: none.
- Next steps: run end-to-end with a real recording.

## 2026-01-10 17:05
- What changed: made recording output names deterministic with a short hash suffix and updated README output path notes.
- Why: avoid collisions when multiple recordings share a name.
- Risks/known issues: hashing large files adds initial overhead.
- Next steps: consider chunked hashing for very large inputs.

## 2026-01-10 17:12
- What changed: fixed output naming to include hash suffix and corrected pipeline error handling string formatting.
- Why: prevent path collisions and keep runtime errors clear.
- Risks/known issues: none.
- Next steps: run a dry run on a short recording to validate outputs.

## 2026-01-10 17:15
- What changed: documented hashed recording folder naming in README.
- Why: clarify output structure for users.
- Risks/known issues: none.
- Next steps: none.

## 2026-01-10 18:45
- What changed: rewrote troubleshooting Git/ACL section with proper Swedish encoding and clearer steps.
- Why: fix mojibake and correct guidance on Windows ACL handling.
- Risks/known issues: none.
- Next steps: commit and push when Git permissions are stable.
