"""elm's public surface. Plural by signature.

What the rest of the ERP may ask ELM: who is away on a given day (attendance,
timetabling) and who holds an unresolved task.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from modules.elm.models import LeaveApplication


@dataclass(frozen=True)
class LeaveStatusDTO:
    user_id: int
    on_leave: bool
    category: str = ""
    until: date | None = None


def get_leave_statuses(user_ids: Sequence[int], on: date) -> dict[int, LeaveStatusDTO]:
    """Whether each employee holds approved leave covering `on`.

    A full-day or either half counts as on leave for the date; callers that
    care about the half can read the application through the API.
    """
    ids = {int(i) for i in user_ids if i is not None}
    if not ids:
        return {}
    away: dict[int, LeaveStatusDTO] = {}
    rows = (LeaveApplication.objects
            .filter(applicant_user_id__in=ids, status="approved",
                    kind__in=["leave", "extension"],
                    start_date__lte=on, end_date__gte=on)
            .order_by("end_date"))
    for row in rows:
        away[row.applicant_user_id] = LeaveStatusDTO(
            row.applicant_user_id, True, row.category, row.end_date)
    return {uid: away.get(uid, LeaveStatusDTO(uid, False)) for uid in ids}
