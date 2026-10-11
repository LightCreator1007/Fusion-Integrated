"""Pre-submission checks (EL-UC-001, EL-UC-009, EL-UC-016).

Every rule that can refuse a request lives here so that applying, extending and
recording an offline sanction cannot drift apart. Domain violations are
translated into 422s at this boundary.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from core.api.exceptions import DomainError
from modules.elm.domain import categories as cat
from modules.elm.domain import state_machine as sm
from modules.elm.domain.counting import count_days
from modules.elm.domain.errors import RuleViolation
from modules.elm.domain.overlap import Span, overlaps
from modules.elm.models import LeaveApplication
from modules.elm.services import balances, facts


class RuleRefused(DomainError):
    """422: a leave rule said no. `code` names the rule for the client."""

    code = "rule_refused"


@dataclass(frozen=True)
class Checked:
    days: Decimal
    year: int


def refuse(violation: RuleViolation) -> RuleRefused:
    return RuleRefused(violation.message, code=violation.code)


def overlapping(user_id: int, start: date, end: date, half: str,
                exclude: Iterable[int] = ()) -> list[LeaveApplication]:
    """The user's pending or approved leave that collides with the span (BR-EL-012)."""
    candidates = (LeaveApplication.objects
                  .filter(applicant_user_id=user_id, status__in=sm.ACTIVE,
                          kind__in=["leave", "extension"],
                          start_date__lte=end, end_date__gte=start)
                  .exclude(pk__in=list(exclude)))
    span = Span(start, end, half)
    return [c for c in candidates
            if overlaps(span, Span(c.start_date, c.end_date, c.half_day))]


def check_substitute(*, applicant_id: int, substitute_id: int, start: date,
                     end: date, exclude: Iterable[int] = ()) -> None:
    """BR-EL-014: another employee, free for the whole responsibility period."""
    if substitute_id == applicant_id:
        raise RuleRefused("You cannot nominate yourself as substitute.",
                          code="substitute_is_applicant")
    person = facts.people([substitute_id]).get(substitute_id)
    if person is None or not person.is_employee:
        raise RuleRefused("The substitute must be a faculty or staff employee.",
                          code="substitute_not_employee")
    if overlapping(substitute_id, start, end, "", exclude=exclude):
        raise RuleRefused(
            "That colleague has leave during the responsibility period.",
            code="substitute_unavailable")


def check_request(*, user_id: int, is_faculty: bool, category: str, start: date,
                  end: date, half: str, station_leave: bool,
                  station_destination: str, substitute_id: int | None,
                  today: date, exclude: Iterable[int] = (),
                  retrospective: bool = False,
                  require_substitute: bool = True) -> Checked:
    """Raises RuleRefused for the first rule broken; returns days and leave year."""
    if not cat.is_valid(category):
        raise RuleRefused(f"{category} is not a supported leave category.",
                          code="unknown_category")
    policy = balances.policy_for(category)
    if not policy.is_active:
        raise RuleRefused(f"{category} is not currently available.",
                          code="category_inactive")

    year = start.year
    balances.ensure_credited(user_id, year, is_faculty=is_faculty)
    # BR-EL-001: credited to this kind of employee, or holding a balance anyway
    # (a faculty member's EL arrives by VL conversion rather than by credit).
    if not (balances.credited_to(policy, is_faculty=is_faculty)
            or balances.balance_of(user_id, category, year) > 0):
        raise RuleRefused(f"{category} does not apply to you.",
                          code="not_eligible")

    if not retrospective and start < today:
        raise RuleRefused("Leave cannot start in the past. Ask a Leave "
                          "Administrator to record leave that was sanctioned offline.",
                          code="start_in_past")
    if category in cat.SINGLE_YEAR and start.year != end.year:
        raise RuleRefused(f"{category} cannot run across two leave years. "
                          "Submit one request for each year.",
                          code="spans_years")

    holidays = facts.holidays_between(start, end)
    closed = {d for d, kind in holidays.items() if kind == "closed"}

    if category == cat.RH and holidays.get(start) != "restricted":
        raise RuleRefused("That date is not a Restricted Holiday in the published "
                          "holiday calendar.", code="rh_not_applicable")

    if category == cat.VL and facts.vacation_covering(start, end) is None:
        raise RuleRefused("Vacation Leave can only be taken within a single "
                          "vacation period of the Academic Calendar.",
                          code="outside_vacation")

    try:
        days = count_days(category, start, end, half, closed)
    except RuleViolation as v:
        raise refuse(v) from v

    if station_leave and not station_destination.strip():
        raise RuleRefused("Station Leave needs the destination.",
                          code="station_details_required")

    free = balances.available(user_id, category, year)
    if days > free:
        raise RuleRefused(
            f"Insufficient {category} balance: {free} day(s) available, "
            f"{days} requested.", code="insufficient_balance")

    clash = overlapping(user_id, start, end, half, exclude=exclude)
    if clash:
        c = clash[0]
        raise RuleRefused(
            f"This overlaps your {c.category} leave from {c.start_date} to "
            f"{c.end_date}.", code="overlap")

    if substitute_id is None:
        if policy.requires_substitute and require_substitute:
            raise RuleRefused(f"{category} needs a nominated substitute.",
                              code="substitute_required")
    else:
        check_substitute(applicant_id=user_id, substitute_id=substitute_id,
                         start=start, end=end, exclude=exclude)

    return Checked(days=days, year=year)
