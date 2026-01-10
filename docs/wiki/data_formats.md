# Data Formats

Schema version: 1.0.0

IDs:
- `recording_id` is derived from file hash + duration (uuid5).
- `run_id` is random per pipeline run (uuid4).
- `event_id` is derived from `recording_id` + event type + timestamps (uuid5).

## recording.json

Fields:
- `schema_version`, `pipeline_version`
- `recording_id`, `run_id`
- `input`: path, size, mtime, sha256, duration
- `start_time`, `start_time_source`
- `tool_versions`
- `config`

## segments.json

Fields:
- `schema_version`, `recording_id`
- `segments`: array of `{t0, t1, vad_confidence}`

## transcript.json

Fields:
- `schema_version`, `recording_id`, `language`
- `chunks`: array of `{t0, t1, text, asr_confidence, error}`

## events.jsonl

One event per line. Required fields:
- `event_id`, `recording_id`, `run_id`
- `event_type`
- `t0`, `t1`
- `start_iso`, `end_iso`
- `speaker_id`, `text`, `error`
- `vad_confidence`, `asr_confidence`, `diarization_confidence`
- `schema_version`
- `provenance`

Example:

```json
{"event_id":"...","recording_id":"...","run_id":"...","event_type":"speech_segment","t0":0.0,"t1":2.3,"start_iso":null,"end_iso":null,"speaker_id":null,"text":null,"error":null,"vad_confidence":1.0,"asr_confidence":null,"diarization_confidence":null,"schema_version":"1.0.0","provenance":{"pipeline_version":"0.1.0"}}
```
