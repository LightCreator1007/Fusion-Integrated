"""Return to duty after EL, COL or VL (EL-UC-010, EL-UC-011; BR-EL-027, 028)."""
from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError
from modules.elm.domain import categories as cat
from modules.elm.domain import resumption as rules
from modules.elm.domain import routing
from modules.elm.domain import state_machine as sm
from modules.elm.models import ApprovalTask, LeaveApplication, LeaveResumption
from modules.elm.selectors import leave as leave_scope
from modules.elm.services import audit, authz, balances, validation


def _review_role(app: LeaveApplication) -> str | None:
    """The Sanctioning Authority of the original leave: the last step."""
    return app.route[-1]["role"] if app.route else None


@transaction.atomic
def submit(*, actor, application_id: int, actual_date: date, details: str = "",
           today: date | None = None) -> LeaveResumption:
    today = today or timezone.localdate()
    app = (LeaveApplication.objects.select_for_update()
           .filter(pk=application_id, applicant_user_id=actor.user_id,
                   kind="leave").first())
    if app is None:
        raise NotFoundError("No such leave request.")
    if app.category not in cat.RESUMABLE:
        raise ConflictError(f"{app.category} has no resumption step.",
                            code="not_resumable")
    if app.status != sm.APPROVED or app.start_date > today:
        raise ConflictError("Resumption applies to approved leave that has begun.",
                            code="not_ongoing")
    if app.resumptions.filter(status__in=["pending", "approved"]).exists():
        raise ConflictError("Resumption has already been submitted.",
                            code="resumption_exists")
    if actual_date < app.start_date or actual_date > today:
        raise validation.RuleRefused(
            "The resumption date must fall between the leave start and today.",
            code="invalid_period")

    approved_end = leave_scope.effective_end(app)
    outcome = rules.assess(approved_end, actual_date)
    resumption = LeaveResumption.objects.create(
        application=app, actual_resumption_date=actual_date, details=details,
        adjustment_days=outcome.adjustment_days)
    audit.record(app, "resumption_submitted", actor_user_id=actor.user_id,
                 detail=f"{outcome.kind}: {actual_date}")

    role = _review_role(app)
    if role is None:                       # Director: reviews their own return
        _apply(resumption, app, reviewer_id=actor.user_id, remark="")
        return resumption
    assignee = None
    if role == routing.UNIT_HEAD:
        assignee = app.unit.head_user_id if app.unit else None
    task = ApprovalTask.objects.create(
        application=app, resumption=resumption, role=role, mode="resumption",
        assignee_user_id=assignee)
    audit.notify(topic="task_assigned", subject="A resumption is waiting for review",
                 user_id=assignee, role="" if assignee else task.role,
                 application=app)
    return resumption


def review(*, actor, task: ApprovalTask, outcome: str, remark: str) -> LeaveApplication:
    """Called by workflow.decide for a task that belongs to a resumption."""
    resumption = (LeaveResumption.objects.select_for_update()
                  .get(pk=task.resumption_id))
    app = LeaveApplication.objects.select_for_update().get(pk=task.application_id)
    if task.status != "pending" or resumption.status != "pending":
        raise ConflictError("This task is no longer pending.", code="task_closed")
    authz.require_for_task(actor, task, app.applicant_user_id)
    if outcome not in ("approved", "rejected"):
        raise validation.RuleRefused("Choose approved or rejected.",
                                     code="invalid_outcome")
    if outcome == "rejected" and not remark.strip():
        raise validation.RuleRefused("Returning a resumption needs a reason.",
                                     code="remark_required")

    task.status, task.outcome, task.actor_user_id = "done", outcome, actor.user_id
    task.remark, task.acted_at = remark[:500], timezone.now()
    task.save(update_fields=["status", "outcome", "actor_user_id", "remark",
                             "acted_at", "updated_at"])
    if outcome == "approved":
        _apply(resumption, app, reviewer_id=actor.user_id, remark=remark)
    else:
        resumption.status, resumption.reviewed_by_user_id = "rejected", actor.user_id
        resumption.reviewed_at, resumption.review_remark = timezone.now(), remark[:500]
        resumption.save(update_fields=["status", "reviewed_by_user_id",
                                       "reviewed_at", "review_remark", "updated_at"])
        audit.record(app, "resumption_returned", actor_user_id=actor.user_id,
                     detail=remark)
        audit.notify(topic="decision", user_id=app.applicant_user_id,
                     subject="Your resumption was returned", body=remark,
                     application=app)
    return app


def _apply(resumption: LeaveResumption, app: LeaveApplication, *, reviewer_id: int,
           remark: str) -> None:
    """Record the actual period and adjust the account for an early or late return."""
    resumption.status = "approved"
    resumption.reviewed_by_user_id = reviewer_id
    resumption.reviewed_at = timezone.now()
    resumption.review_remark = remark[:500]
    resumption.save(update_fields=["status", "reviewed_by_user_id", "reviewed_at",
                                   "review_remark", "updated_at"])
    if resumption.adjustment_days:
        delta = resumption.adjustment_days
        balances.post(
            user_id=app.applicant_user_id, category=app.category,
            year=app.start_date.year,
            entry_type="restore" if delta > 0 else "adjustment",
            days=delta, application=app,
            note=("Early resumption" if delta > 0 else "Late resumption"),
            actor_user_id=reviewer_id)
    app.actual_resumption_date = resumption.actual_resumption_date
    app.save(update_fields=["actual_resumption_date", "updated_at"])
    audit.record(app, "resumption_reviewed", actor_user_id=reviewer_id,
                 detail=f"adjustment {resumption.adjustment_days} day(s)")
    audit.notify(topic="decision", user_id=app.applicant_user_id,
                 subject="Your resumption was accepted", application=app)
