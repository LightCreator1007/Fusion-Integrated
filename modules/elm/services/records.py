"""Administrative record keeping (EL-UC-016, EL-UC-017; BR-EL-029, BR-EL-037).

Maintaining a record is not sanctioning one: nothing here routes a request or
asks anyone to approve it. An offline entry captures evidence that approval
already happened elsewhere and synchronises the account.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from modules.elm.models import LeaveApplication
from modules.elm.services import audit, balances, facts, validation


@transaction.atomic
def record_offline(*, actor, data: dict, today: date | None = None) -> LeaveApplication:
    today = today or timezone.localdate()
    user_id = data["employee_user_id"]
    person = facts.people([user_id]).get(user_id)
    if person is None or not person.is_employee:
        raise validation.RuleRefused("The employee was not found.",
                                     code="not_employee")
    if not data.get("offline_reference", "").strip():
        raise validation.RuleRefused(
            "The sanction reference is required to record offline leave.",
            code="reference_required")
    if not data.get("offline_reason", "").strip():
        raise validation.RuleRefused(
            "State why the leave could not be applied for in ELM.",
            code="reason_required")
    if data["sanction_date"] > today:
        raise validation.RuleRefused("The sanction date cannot be in the future.",
                                     code="invalid_period")

    checked = validation.check_request(
        user_id=user_id, is_faculty=person.is_faculty, category=data["category"],
        start=data["start_date"], end=data["end_date"],
        half=data.get("half_day", ""), station_leave=False, station_destination="",
        substitute_id=None, today=today, retrospective=True,
        require_substitute=False)

    unit = facts.unit_of(user_id)
    app = LeaveApplication.objects.create(
        applicant_user_id=user_id, kind="leave", category=data["category"],
        start_date=data["start_date"], end_date=data["end_date"],
        half_day=data.get("half_day", ""), days=checked.days,
        reason=data["reason"], status="approved", entry_channel="offline",
        offline_reference=data["offline_reference"],
        offline_reason=data["offline_reason"], unit=unit,
        recorded_by_user_id=actor.user_id, decided_at=timezone.now(),
        decided_by_user_id=actor.user_id,
        decision_remark=f"Sanctioned offline on {data['sanction_date']}")
    balances.post(user_id=user_id, category=app.category, year=checked.year,
                  entry_type="debit", days=-checked.days, application=app,
                  note=f"Offline: {app.offline_reference}",
                  actor_user_id=actor.user_id)
    audit.record(app, "recorded_offline", actor_user_id=actor.user_id,
                 detail=app.offline_reference)
    audit.notify(topic="decision", user_id=user_id, application=app,
                 subject="Offline leave was recorded in your account",
                 body=app.offline_reference)
    return app


@transaction.atomic
def adjust_balance(*, actor, user_id: int, category: str, year: int,
                   days: Decimal, note: str) -> None:
    """A signed correction, with its reason, in the employee's account."""
    if not note.strip():
        raise validation.RuleRefused("An adjustment needs a reason.",
                                     code="reason_required")
    if days == 0:
        raise validation.RuleRefused("An adjustment cannot be zero days.",
                                     code="invalid_period")
    balances.policy_for(category)
    balances.post(user_id=user_id, category=category, year=year,
                  entry_type="adjustment", days=days, note=note,
                  actor_user_id=actor.user_id)
    audit_target = (LeaveApplication.objects
                    .filter(applicant_user_id=user_id).order_by("-id").first())
    if audit_target:
        audit.record(audit_target, "balance_adjusted", actor_user_id=actor.user_id,
                     detail=f"{category} {days:+} for {year}: {note}")
