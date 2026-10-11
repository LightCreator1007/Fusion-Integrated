"""Resumption outcome (BR-EL-028)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

ON_TIME = "on_time"
EARLY = "early"
LATE = "late"


@dataclass(frozen=True)
class ResumptionOutcome:
    kind: str
    #: Days to post to the balance: positive restores (early), negative
    #: deducts (late), zero leaves the approved period untouched.
    adjustment_days: int


def assess(approved_end: date, actual: date) -> ResumptionOutcome:
    delta = (approved_end - actual).days
    if delta == 0:
        return ResumptionOutcome(ON_TIME, 0)
    return ResumptionOutcome(EARLY if delta > 0 else LATE, delta)
