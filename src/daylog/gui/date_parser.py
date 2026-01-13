"""Date and time parsing from filenames and file metadata."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from daylog.constants import DEFAULT_TIMEZONE


# Swedish month name mapping
SWEDISH_MONTHS = {
    "jan": 1, "jan.": 1,
    "feb": 2, "feb.": 2,
    "mar": 3, "mars": 3,
    "apr": 4, "apr.": 4,
    "maj": 5,
    "jun": 6, "juni": 6,
    "jul": 7, "juli": 7,
    "aug": 8, "aug.": 8,
    "sep": 9, "sep.": 9, "sept": 9,
    "okt": 10, "okt.": 10,
    "nov": 11, "nov.": 11,
    "dec": 12, "dec.": 12,
}


class DateTimeParser:
    """Parse dates and times from filenames or file metadata."""

    # Filename patterns to try (ordered by specificity)
    # Format: (regex_pattern, datetime_format, has_time)
    PATTERNS = [
        # DD mmm YYYY HH-MM-SS - e.g., "1 sep. 2024 18-46-16 (5).m4a"
        (
            r"(\d{1,2})\s+(jan\.?|feb\.?|mar[s]?|apr\.?|maj|jun[i]?|jul[i]?|aug\.?|sep[t]?\.?|okt\.?|nov\.?|dec\.?)\s+(\d{4})\s+(\d{2})-(\d{2})-(\d{2})",
            lambda m: datetime(
                int(m.group(3)),  # year
                SWEDISH_MONTHS[m.group(2).lower()],  # month
                int(m.group(1)),  # day
                int(m.group(4)),  # hour
                int(m.group(5)),  # minute
                int(m.group(6)),  # second
            ),
            True,
        ),
        # YYYYMMDDHHMMSS - e.g., "20260110180044.wav"
        (
            r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})",
            lambda m: datetime(
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                int(m.group(6)),
            ),
            True,
        ),
        # YYYY-MM-DD_HH-MM-SS - e.g., "2026-01-10_18-00-44.wav"
        (
            r"(\d{4})-(\d{2})-(\d{2})[_T](\d{2})-(\d{2})-(\d{2})",
            lambda m: datetime(
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                int(m.group(6)),
            ),
            True,
        ),
        # YYYY-MM-DDTHH:MM:SS - ISO-ish - e.g., "2026-01-10T18:00:44.wav"
        (
            r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})",
            lambda m: datetime(
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                int(m.group(6)),
            ),
            True,
        ),
        # YYYYMMDD - e.g., "20260110.wav" (date only)
        (
            r"(\d{4})(\d{2})(\d{2})",
            lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))),
            False,
        ),
        # YYYY-MM-DD - e.g., "2026-01-10.wav" (date only)
        (
            r"(\d{4})-(\d{2})-(\d{2})",
            lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))),
            False,
        ),
    ]

    @classmethod
    def parse_filename(cls, filename: str) -> Optional[Tuple[datetime, bool]]:
        """
        Parse datetime from filename.

        Args:
            filename: The filename to parse (without path)

        Returns:
            Tuple of (datetime, has_time) if match found, None otherwise
            has_time indicates if pattern included time component
        """
        for pattern, parser, has_time in cls.PATTERNS:
            match = re.search(pattern, filename)
            if match:
                try:
                    dt = parser(match)
                    # Add timezone (assume local timezone)
                    dt_tz = dt.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
                    return (dt_tz, has_time)
                except (ValueError, IndexError):
                    # Invalid date values, try next pattern
                    continue
        return None

    @staticmethod
    def get_mtime(path: Path) -> datetime:
        """
        Get file modification time with timezone.

        Args:
            path: Path to file

        Returns:
            File modification datetime with timezone
        """
        mtime_timestamp = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime_timestamp, tz=ZoneInfo(DEFAULT_TIMEZONE))
        return dt

    @classmethod
    def extract_date_time(
        cls, path: Path
    ) -> Tuple[str, Optional[str], bool]:
        """
        Extract date and optionally time from filename or file metadata.

        Args:
            path: Path to audio file

        Returns:
            Tuple of (date_str, start_time_iso, use_mtime)
            - date_str: YYYY-MM-DD format
            - start_time_iso: ISO 8601 string if time available, else None
            - use_mtime: True if using file mtime (fallback)
        """
        # Try filename first
        result = cls.parse_filename(path.name)
        if result:
            dt, has_time = result
            date_str = dt.strftime("%Y-%m-%d")
            start_time_iso = dt.isoformat() if has_time else None
            return (date_str, start_time_iso, False)

        # Fallback to file mtime
        dt = cls.get_mtime(path)
        date_str = dt.strftime("%Y-%m-%d")
        start_time_iso = dt.isoformat()
        return (date_str, start_time_iso, True)
