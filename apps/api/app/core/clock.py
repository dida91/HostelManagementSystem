"""Hostel-local calendar.

The server clock is UTC, but the hostel's day starts at midnight in Pokhara
(UTC+05:45). A fee due "on the 10th", or a leave that ended "yesterday", must
be judged on the hostel's date -- otherwise anything scheduled near midnight
lands on the wrong day.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def hostel_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().hostel_timezone)


def hostel_today() -> date:
    return datetime.now(hostel_tz()).date()
