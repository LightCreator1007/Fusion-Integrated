"""Routing and decisions (EL-UC-002..005, EL-UC-019; BR-EL-014..020, BR-EL-022).

All writes happen inside one transaction with the rows locked, so a withdrawal
and a late approval cannot both win.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError
from modules.elm.domain import routing
from modules.elm.domain import state_machine as sm
from modules.elm.domain.errors import InvalidTransition
from modules.elm.models import ApprovalTask, LeaveApplication, LeaveResumption
from modules.elm.services import audit, authz, balances, resumption, validation

SUBSTITUTE_OUTCOMES = ("accepted", "declined")


# -- tasks ---------------------------------------------------------------------
def _open_task(app: LeaveApplication, *, role: str, mode: str, step_index: int,
               assignee: int | None, resumption: LeaveResumption | None = None
               ) -> ApprovalTask:
    task = ApprovalTask.objects.create(
        application=app, resumption=resumption, step_index=step_index,
        role=role, mode=mode, assignee_user_id=assignee)
    subject = ("Please confirm you will cover for a colleague"
               if role == authz.SUBSTITUTE
               else "A leave request is waiting for you")
    audit.notify(topic="task_assigned", subject=subject,
                 body=f"{app.category} {app.start_date} to {app.end_date}",
                 user_id=assignee, role="" if assignee else role, application=app)
    return task


def begin_routing(app: LeaveApplication, *, actor_user_id: int) -> None:
    """Start (or resume, after substitute consent) the sanction path."""
    if not app.route:
        _finalize(app, approved=True, actor_user_id=actor_user_id,
                  remark="Self-sanctioned by the Director.", event="self_sanctioned")
        return
    _open_step(app)


def _open_step(app: LeaveApplication) -> None:
    step = app.route[app.current_step]
    assignee = None
    if step["role"] == routing.UNIT_HEAD:
        unit = app.unit
        assignee = unit.head_user_id if unit else None
        if assignee is None:
            raise ConflictError(
                "The applicant's unit has no Unit Head configured.",
                code="no_unit_head")
    _open_task(app, role=step["role"], mode=step["mode"],
               step_index=app.current_step, assignee=assignee)


def open_substitute_task(app: LeaveApplication) -> None:
    app.substitute_status = "pending"
    app.save(update_fields=["substitute_status", "updated_at"])
    _open_task(app, role=authz.SUBSTITUTE, mode="consent", step_index=0,
               assignee=app.substitute_user_id)
    audit.record(app, "substitute_requested", actor_user_id=app.applicant_user_id,
                 detail=f"Substitute user {app.substitute_user_id}")


# -- deciding ------------------------------------------------------------------
@transaction.atomic
def decide(*, actor, task_id: int, outcome: str, remark: str = "") -> LeaveApplication:
    task = ApprovalTask.objects.select_for_update().filter(pk=task_id).first()
    if task is None:
        raise NotFoundError("No such task.")
    if task.resumption_id:
        return resumption.review(actor=actor, task=task, outcome=outcome, remark=remark)

    app = LeaveApplication.objects.select_for_update().get(pk=task.application_id)
    if task.status != "pending" or app.status != sm.PENDING:
        raise ConflictError("This task is no longer pending.", code="task_closed")
    authz.require_for_task(actor, task, app.applicant_user_id)

    if task.role == authz.SUBSTITUTE:
        return _answer_substitute(app, task, actor, outcome, remark)

    allowed = routing.outcomes_for(task.mode)
    if outcome not in allowed:
        raise validation.RuleRefused(
            f"Choose one of: {', '.join(allowed)}.", code="invalid_outcome")
    if outcome == "rejected" and not remark.strip():
        raise validation.RuleRefused("A rejection needs a reason.",
                                     code="remark_required")

    now = timezone.now()
    task.status, task.outcome, task.actor_user_id = "done", outcome, actor.user_id
    task.remark, task.acted_at = remark[:500], now
    task.save(update_fields=["status", "outcome", "actor_user_id", "remark",
                             "acted_at", "updated_at"])
    audit.record(app, f"{task.role}_{outcome}", actor_user_id=actor.user_id,
                 detail=remark)

    if task.mode == routing.RECOMMEND:
        app.recommendation = outcome
    if task.mode == routing.FINAL:
        _finalize(app, approved=outcome == "approved", actor_user_id=actor.user_id,
                  remark=remark)
        return app

    app.current_step += 1
    app.save(update_fields=["current_step", "recommendation", "updated_at"])
    _open_step(app)
    return app


def _answer_substitute(app, task, actor, outcome, remark) -> LeaveApplication:
    if outcome not in SUBSTITUTE_OUTCOMES:
        raise validation.RuleRefused("Answer accepted or declined.",
                                     code="invalid_outcome")
    task.status, task.outcome, task.actor_user_id = "done", outcome, actor.user_id
    task.remark, task.acted_at = remark[:500], timezone.now()
    task.save(update_fields=["status", "outcome", "actor_user_id", "remark",
                             "acted_at", "updated_at"])
    app.substitute_status = outcome
    app.save(update_fields=["substitute_status", "updated_at"])
    audit.record(app, f"substitute_{outcome}", actor_user_id=actor.user_id,
                 detail=remark)
    if outcome == "accepted":
        begin_routing(app, actor_user_id=actor.user_id)
    else:
        audit.notify(
            topic="substitute_declined", user_id=app.applicant_user_id,
            subject="Your substitute declined",
            body="Nominate another colleague or withdraw the request.",
            application=app)
    return app


@transaction.atomic
def renominate_substitute(*, actor, application_id: int,
                          substitute_user_id: int) -> LeaveApplication:
    """EL-UC-019: after a decline the applicant may name someone else."""
    app = (LeaveApplication.objects.select_for_update()
           .filter(pk=application_id, applicant_user_id=actor.user_id).first())
    if app is None:
        raise NotFoundError("No such leave request.")
    if app.status != sm.PENDING or app.substitute_status != "declined":
        raise ConflictError("A new substitute can only be named after a decline.",
                            code="substitute_not_declined")
    validation.check_substitute(
        applicant_id=app.applicant_user_id, substitute_id=substitute_user_id,
        start=app.start_date, end=app.end_date, exclude=[app.pk])
    app.substitute_user_id = substitute_user_id
    app.save(update_fields=["substitute_user_id", "updated_at"])
    open_substitute_task(app)
    return app


# -- final effects -------------------------------------------------------------
def _finalize(app: LeaveApplication, *, approved: bool, actor_user_id: int,
              remark: str, event: str | None = None) -> None:
    status = sm.next_status(app.status, sm.APPROVE if approved else sm.REJECT)
    year = app.start_date.year
    if approved:
        if app.kind in ("leave", "extension"):
            if balances.balance_of(app.applicant_user_id, app.category, year) < app.days:
                raise ConflictError(
                    "The balance no longer covers this request.",
                    code="insufficient_balance")
            balances.post(user_id=app.applicant_user_id, category=app.category,
                          year=year, entry_type="debit", days=-app.days,
                          application=app, note=f"{app.kind} approved")
        elif app.kind == "cancellation":
            _apply_cancellation(app, actor_user_id)
    app.status = status
    app.decided_at = timezone.now()
    app.decided_by_user_id = actor_user_id
    app.decision_remark = remark[:500]
    app.save(update_fields=["status", "decided_at", "decided_by_user_id",
                            "decision_remark", "updated_at"])
    audit.record(app, event or ("approved" if approved else "rejected"),
                 actor_user_id=actor_user_id, detail=remark)
    audit.notify(
        topic="decision", user_id=app.applicant_user_id,
        subject=f"Your {app.get_kind_display().lower()} request was "
                f"{'approved' if approved else 'rejected'}",
        body=remark, application=app)


def _apply_cancellation(app: LeaveApplication, actor_user_id: int) -> None:
    parent = LeaveApplication.objects.select_for_update().get(pk=app.parent_id)
    if parent.start_date <= timezone.localdate():
        raise ConflictError("The leave has already begun, so it can no longer "
                            "be cancelled.", code="already_started")
    try:
        parent.status = sm.next_status(parent.status, sm.CANCEL)
    except InvalidTransition as exc:
        raise ConflictError(str(exc), code="invalid_transition") from exc
    parent.save(update_fields=["status", "updated_at"])
    audit.record(parent, "cancelled", actor_user_id=actor_user_id,
                 detail=f"Cancellation request {app.pk} approved")
    deducted = sum((-e.days for e in parent.ledger_entries.filter(entry_type="debit")),
                   Decimal(0))
    if deducted:
        balances.post(user_id=parent.applicant_user_id, category=parent.category,
                      year=parent.start_date.year, entry_type="restore",
                      days=deducted, application=parent,
                      note="Restored on cancellation")


# -- withdrawal ----------------------------------------------------------------
@transaction.atomic
def withdraw(*, actor, application_id: int) -> LeaveApplication:
    """EL-UC-007: immediate, and it ends all remaining approval processing."""
    app = (LeaveApplication.objects.select_for_update()
           .filter(pk=application_id, applicant_user_id=actor.user_id).first())
    if app is None:
        raise NotFoundError("No such leave request.")
    try:
        app.status = sm.next_status(app.status, sm.WITHDRAW)
    except InvalidTransition:
        raise ConflictError(
            "Only a pending request can be withdrawn. Approved leave is "
            "cancelled instead.", code="not_withdrawable") from None

    open_tasks = list(app.tasks.select_for_update().filter(status="pending"))
    for task in open_tasks:
        task.status = "cancelled"
        task.save(update_fields=["status", "updated_at"])
        audit.notify(topic="withdrawn", user_id=task.assignee_user_id,
                     role="" if task.assignee_user_id else task.role,
                     subject="A leave request was withdrawn",
                     body=f"{app.category} {app.start_date} to {app.end_date}",
                     application=app)
    app.save(update_fields=["status", "updated_at"])
    audit.record(app, "withdrawn", actor_user_id=actor.user_id)
    return app
