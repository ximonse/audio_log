"""Time helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from daylog.constants import DEFAULT_TIMEZONE


@dataclass(frozen=True)
class StartTimeInfo:
    start_time: Optional[datetime]
    source: str


def parse_start_time(value: Optional[str]) -> StartTimeInfo:
    if not value:
        return StartTimeInfo(start_time=None, source="unknown")
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return StartTimeInfo(start_time=dt, source="user_set")


def seconds_to_iso(start: Optional[datetime], offset_s: float) -> Optional[str]:
    if start is None:
        return None
    return (start + timedelta(seconds=offset_s)).isoformat()