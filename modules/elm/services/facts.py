"""Reads the services need from outside ELM, behind one door.

Person data comes through the directory contract, batched; the rest is ELM's
own configuration.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from core.api.exceptions import ConflictError
from modules.directory import contracts as directory
from modules.elm.models import (
    HierarchyRule,
    Holiday,
    HolidayCalendar,
    OrgUnit,
    UnitMember,
    VacationPeriod,
)

EMPLOYEE_KINDS = ("faculty", "staff")


@dataclass(frozen=True)
class Person:
    user_id: int
    name: str
    kind: str

    @property
    def is_faculty(self) -> bool:
        return self.kind == "faculty"

    @property
    def is_employee(self) -> bool:
        return self.kind in EMPLOYEE_KINDS


def people(user_ids: Sequence[int]) -> dict[int, Person]:
    found = directory.get_users(list(user_ids))
    return {uid: Person(uid, u.display_name, u.kind) for uid, u in found.items()}


def names(user_ids: Sequence[int]) -> dict[int, str]:
    return {uid: p.name for uid, p in people(user_ids).items()}


def unit_of(user_id: int) -> OrgUnit | None:
    member = (UnitMember.objects.select_related("unit")
              .filter(user_id=user_id).first())
    return member.unit if member else None


def require_unit(user_id: int) -> OrgUnit:
    unit = unit_of(user_id)
    if unit is None:
        raise ConflictError(
            "You are not assigned to an organizational unit yet. Ask a Leave "
            "Administrator to place you in one.", code="no_unit")
    return unit


def configured_path(group: str, category: str) -> list[str] | None:
    """Category-specific rule first, then the group-wide one."""
    rules = HierarchyRule.objects.filter(applicant_group=group, is_active=True,
                                         category__in=[category, ""])
    by_category = {r.category: r.steps for r in rules}
    return by_category.get(category) or by_category.get("") or None


def effective_calendar(year: int) -> HolidayCalendar | None:
    """The latest published calendar for the year (BR-EL-031)."""
    return (HolidayCalendar.objects
            .filter(year=year, status="published")
            .order_by("-published_at", "-id").first())


def holidays_between(start: date, end: date) -> dict[date, str]:
    """date -> kind, for every year the span touches."""
    out: dict[date, str] = {}
    for year in range(start.year, end.year + 1):
        calendar = effective_calendar(year)
        if calendar is None:
            continue
        for h in Holiday.objects.filter(calendar=calendar,
                                        date__range=(start, end)):
            out[h.date] = h.kind
    return out


def vacation_covering(start: date, end: date) -> VacationPeriod | None:
    return VacationPeriod.objects.filter(start_date__lte=start,
                                         end_date__gte=end).first()
