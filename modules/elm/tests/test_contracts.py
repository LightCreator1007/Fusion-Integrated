import pytest

from modules.elm import contracts
from modules.elm.models import LeaveApplication

pytestmark = pytest.mark.django_db


def test_leave_statuses_are_batched_and_report_only_approved_leave():
    from datetime import date

    mk = lambda uid, status: LeaveApplication.objects.create(   # noqa: E731
        applicant_user_id=uid, category="EL", days=3, reason="x", status=status,
        start_date=date(2026, 3, 9), end_date=date(2026, 3, 11))
    mk(1, "approved")
    mk(2, "pending")
    out = contracts.get_leave_statuses([1, 2, 3], date(2026, 3, 10))
    assert out[1].on_leave and out[1].until == date(2026, 3, 11)
    assert not out[2].on_leave and not out[3].on_leave
    assert contracts.get_leave_statuses([], date(2026, 3, 10)) == {}
    assert not contracts.get_leave_statuses([1], date(2026, 3, 12))[1].on_leave
