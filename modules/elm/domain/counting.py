"""How many leave days a request consumes (BR-EL-010, BR-EL-011).

EL, COL and VL count every calendar day, weekends and closed holidays inside
the interval included. CL and SCL count working days only, and RH is a single
named day.
"""
from __future__ import annotations

from collections.abc import Collection
from datetime import date, timedelta
from decimal import Decimal

from modules.elm.domain import categories as cat
from modules.elm.domain.errors import RuleViolation

FIRST_HALF = "first"
SECOND_HALF = "second"
FULL_DAY = ""
HALVES = (FIRST_HALF, SECOND_HALF)

WEEKEND = (5, 6)          # Saturday, Sunday


def is_working_day(day: date, closed_dates: Collection[date]) -> bool:
    return day.weekday() not in WEEKEND and day not in closed_dates


def count_days(category: str, start: date, end: date, half: str,
               closed_dates: Collection[date]) -> Decimal:
    if end < start:
        raise RuleViolation("invalid_period",
                            "The end date cannot be before the start date.")

    if half:
        if half not in HALVES:
            raise RuleViolation("invalid_half_day", "Half must be first or second.")
        if category not in cat.HALF_DAY:
            raise RuleViolation("half_day_not_allowed",
                                f"{category} cannot be taken as a half day.")
        if start != end:
            raise RuleViolation("half_day_single_date",
                                "A half-day request must be for a single date.")
        if not is_working_day(start, closed_dates):
            raise RuleViolation("no_working_days",
                                "That date is a weekend or closed holiday.")
        return Decimal("0.5")

    if category == cat.RH:
        if start != end:
            raise RuleViolation("rh_single_day",
                                "A Restricted Holiday is a single day.")
        return Decimal(1)

    if category in cat.CONTINUOUS:
        return Decimal((end - start).days + 1)

    days = 0
    cursor = start
    while cursor <= end:
        if is_working_day(cursor, closed_dates):
            days += 1
        cursor += timedelta(days=1)
    if days == 0:
        raise RuleViolation("no_working_days",
                            "The period contains no working days.")
    return Decimal(days)
