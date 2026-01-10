# Daylog

Local-first audio day log processor. It turns long recordings into a timestamped event log
(JSONL + CSV) with transcript outputs, ready for later analysis.

## Requirements

- Python 3.11+
- FFmpeg available on PATH

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .
```

Run the pipeline:

```bash
daylog run --input path/to/audio.wav --date 2026-01-10 --start-time "2026-01-10T07:12:00"
```

Validate outputs:

```bash
daylog validate --input Recordings/2026-01-10/<recording-name>/processed
```

## Configuration

Defaults live in `daylog.toml`. Override with `--config` if needed.

## Output

Each recording writes:

- `recording.json`
- `segments.json`
- `transcript.json`
- `transcript.txt`
- `events.jsonl`
- `events.csv`

See `docs/wiki/data_formats.md` for schema details.

Outputs are stored under `Recordings/YYYY-MM-DD/<recording-name>/processed` by default,
where `<recording-name>` is `<stem>_<hash8>` to avoid collisions.

## Testing

Unit tests:

```bash
pytest
```

Integration tests (requires FFmpeg and model downloads):

```bash
DAYLOG_RUN_INTEGRATION=1 pytest
```
