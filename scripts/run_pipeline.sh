#!/usr/bin/env bash
set -euo pipefail

INPUT="$1"
DATE="${2:-}"
START_TIME="${3:-}"
USE_MTIME="${4:-}"

cmd=(daylog run --input "$INPUT")
if [[ -n "$DATE" ]]; then
  cmd+=(--date "$DATE")
fi
if [[ -n "$START_TIME" ]]; then
  cmd+=(--start-time "$START_TIME")
fi
if [[ -n "$USE_MTIME" ]]; then
  cmd+=(--use-mtime)
fi

"${cmd[@]}"
