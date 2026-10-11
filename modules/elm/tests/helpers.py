"""Builders shared by the ELM tests."""
from datetime import date

from conftest import make_principal
from fusion_auth.client import UserRef
from modules.elm.models import (
    Holiday,
    HolidayCalendar,
    OrgUnit,
    UnitMember,
    VacationPeriod,
)

EMPLOYEE = [
    "elm_leave.leave.apply", "elm_leave.leave.view_self",
    "elm_leave.leave.withdraw", "elm_leave.leave.cancel",
    "elm_leave.leave.resume", "elm_leave.task.view",
]
HOD = [*EMPLOYEE, "elm_leave.review.unit_head"]
ESTT = [*EMPLOYEE, "elm_leave.review.establishment"]
DEAN = [*EMPLOYEE, "elm_leave.sanction.dean"]
REGISTRAR = [*EMPLOYEE, "elm_leave.sanction.registrar"]
DIRECTOR = [*EMPLOYEE, "elm_leave.sanction.director"]
ADMIN = [*EMPLOYEE, "elm_leave.record.view", "elm_leave.record.manage",
         "elm_leave.policy.manage", "elm_leave.calendar.manage",
         "elm_leave.yearend.run"]

# ids used across the suite
STAFF, FACULTY, SUBSTITUTE, HEAD, ESTT_ID, REG_ID, DEAN_ID, DIR_ID, ADMIN_ID = (
    10, 11, 12, 20, 30, 40, 50, 60, 70)


#: The identity service's directory for the test. Shared by reference with the
#: stubbed IAM client, so adding a person mid-test makes them visible.
USERS: dict[int, UserRef] = {}


def person(uid, name=None, kind="staff"):
    USERS[uid] = UserRef(user_id=uid, username=f"u{uid}",
                         display_name=name or f"Person {uid}", kind=kind)
    return USERS[uid]


def actor(uid, permissions=EMPLOYEE, kind="staff"):
    return make_principal(user_id=uid, permissions=permissions,
                          modules=("elm_leave",), kind=kind,
                          roles=("employee",), active_role="employee")


def world():
    """One unit with a head, a staff member, a faculty member and a colleague."""
    USERS.clear()
    for uid, kind in [(STAFF, "staff"), (FACULTY, "faculty"), (SUBSTITUTE, "staff"),
                      (HEAD, "faculty"), (ESTT_ID, "staff"), (REG_ID, "staff"),
                      (DEAN_ID, "faculty"), (DIR_ID, "faculty"), (ADMIN_ID, "staff")]:
        person(uid, kind=kind)
    unit = OrgUnit.objects.create(code="CSE", name="Computer Science",
                                  head_user_id=HEAD)
    for uid in (STAFF, FACULTY, SUBSTITUTE, HEAD):
        UnitMember.objects.create(user_id=uid, unit=unit)
    return unit


def publish_calendar(year=2026, closed=(), restricted=()):
    cal = HolidayCalendar.objects.create(year=year, title=f"{year}", status="published",
                                         published_at="2026-01-01T00:00:00Z")
    for d in closed:
        Holiday.objects.create(calendar=cal, date=d, name="Holiday", kind="closed")
    for d in restricted:
        Holiday.objects.create(calendar=cal, date=d, name="Festival", kind="restricted")
    return cal


def vacation(start, end):
    return VacationPeriod.objects.create(label="Summer", start_date=start, end_date=end)


def d(s: str) -> date:
    return date.fromisoformat(s)
