from datetime import datetime
from zoneinfo import ZoneInfo

from daylog.io.time import seconds_to_iso


def test_seconds_to_iso():
    start = datetime(2026, 1, 10, 7, 12, 0, tzinfo=ZoneInfo("Europe/Stockholm"))
    result = seconds_to_iso(start, 30.5)
    assert result.endswith("07:12:30.500000+01:00")