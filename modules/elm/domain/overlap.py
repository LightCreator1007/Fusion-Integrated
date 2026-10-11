"""Applicant non-overlap, with the half-day exception (BR-EL-012)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from modules.elm.domain.counting import FULL_DAY


@dataclass(frozen=True)
class Span:
    start: date
    end: date
    half: str = FULL_DAY


def overlaps(a: Span, b: Span) -> bool:
    if a.end < b.start or b.end < a.start:
        return False
    # First-half and second-half of the same date occupy different halves.
    same_single_day = a.start == a.end == b.start == b.end
    return not (same_single_day and a.half and b.half and a.half != b.half)
