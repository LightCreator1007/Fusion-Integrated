"""Administrative configuration (EL-UC-014, 015, 018)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError
from modules.elm.domain import routing
from modules.elm.models import HolidayCalendar, OrgUnit, UnitMember
from modules.elm.services import validation


@transaction.atomic
def publish_calendar(*, actor, calendar_id: int) -> HolidayCalendar:
    """Publishing replaces the effective calendar for that year (BR-EL-031)."""
    calendar = HolidayCalendar.objects.select_for_update().filter(pk=calendar_id).first()
    if calendar is None:
        raise ConflictError("No such calendar.", code="not_found")
    if not calendar.holidays.exists():
        raise validation.RuleRefused("A calendar with no dates cannot be published.",
                                     code="empty_calendar")
    calendar.status = "published"
    calendar.published_at = timezone.now()
    calendar.published_by_user_id = actor.user_id
    calendar.save(update_fields=["status", "published_at", "published_by_user_id",
                                 "updated_at"])
    return calendar


def check_steps(steps: list[str]) -> None:
    bad = [s for s in steps if s not in routing.ROLES]
    if bad or not steps:
        raise validation.RuleRefused(
            f"Steps must be a non-empty list of: {', '.join(routing.ROLES)}.",
            code="bad_hierarchy")


def check_group(group: str) -> None:
    if group not in routing.APPLICANT_GROUPS:
        raise validation.RuleRefused(
            f"Applicant group must be one of: {', '.join(routing.APPLICANT_GROUPS)}.",
            code="bad_hierarchy")


@transaction.atomic
def place_member(*, user_id: int, unit: OrgUnit, designation: str = "") -> UnitMember:
    member, _ = UnitMember.objects.update_or_create(
        user_id=user_id, defaults={"unit": unit, "designation": designation})
    return member

