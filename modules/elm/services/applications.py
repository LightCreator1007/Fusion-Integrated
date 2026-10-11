"""Submitting, extending and cancelling (EL-UC-001, 008, 009).

A submitted request is never edited (BR-EL-034): the employee withdraws it and
submits a fresh one, or asks for the approved leave to be cancelled.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError
from modules.elm.domain import categories as cat
from modules.elm.domain import routing
from modules.elm.domain import state_machine as sm
from modules.elm.domain.errors import RuleViolation
from modules.elm.models import LeaveApplication
from modules.elm.selectors import leave as scope
from modules.elm.services import audit, facts, validation, workflow


def _person(user_id: int) -> facts.Person:
    person = facts.people([user_id]).get(user_id)
    if person is None or not person.is_employee:
        raise validation.RuleRefused(
            "Only faculty and staff can use leave management.", code="not_employee")
    return person


def _route_for(actor, person: facts.Person, unit, category: str) -> list[dict]:
    group = routing.applicant_group(
        is_faculty=person.is_faculty,
        authority_roles=scope.roles_held(actor) & {
            routing.DEAN, routing.REGISTRAR, routing.DIRECTOR})
    steps = routing.resolve_route(
        category=category, group=group,
        is_unit_head=unit.head_user_id == actor.user_id,
        configured=facts.configured_path(group, category))
    return [s.as_dict() for s in steps]


@transaction.atomic
def apply(*, actor, data: dict, today: date | None = None) -> LeaveApplication:
    today = today or timezone.localdate()
    person = _person(actor.user_id)
    unit = facts.require_unit(actor.user_id)
    substitute_id = data.get("substitute_user_id")

    checked = validation.check_request(
        user_id=actor.user_id, is_faculty=person.is_faculty,
        category=data["category"], start=data["start_date"], end=data["end_date"],
        half=data.get("half_day", ""), station_leave=data.get("station_leave", False),
        station_destination=data.get("station_destination", ""),
        substitute_id=substitute_id, today=today)

    try:
        route = _route_for(actor, person, unit, data["category"])
    except RuleViolation as exc:
        raise validation.refuse(exc) from exc

    app = LeaveApplication.objects.create(
        applicant_user_id=actor.user_id, kind="leave", category=data["category"],
        start_date=data["start_date"], end_date=data["end_date"],
        half_day=data.get("half_day", ""), days=checked.days,
        reason=data["reason"], station_leave=data.get("station_leave", False),
        station_destination=data.get("station_destination", ""),
        station_contact=data.get("station_contact", ""),
        evidence_reference=data.get("evidence_reference", ""),
        substitute_user_id=substitute_id, route=route, unit=unit)
    audit.record(app, "submitted", actor_user_id=actor.user_id)

    if substitute_id:
        workflow.open_substitute_task(app)         # routing waits for consent
    else:
        workflow.begin_routing(app, actor_user_id=actor.user_id)
    return app


def _owned_approved(actor, application_id: int) -> LeaveApplication:
    app = (LeaveApplication.objects.select_for_update()
           .filter(pk=application_id, applicant_user_id=actor.user_id).first())
    if app is None:
        raise NotFoundError("No such leave request.")
    if app.kind == "cancellation" or app.status != sm.APPROVED:
        raise ConflictError("Only approved leave can be changed this way.",
                            code="not_approved")
    return app


@transaction.atomic
def request_cancellation(*, actor, application_id: int, reason: str,
                         today: date | None = None) -> LeaveApplication:
    today = today or timezone.localdate()
    parent = _owned_approved(actor, application_id)
    if parent.start_date <= today:
        raise ConflictError(
            "This leave has already begun. Ask for an extension or record your "
            "resumption instead.", code="already_started")
    if parent.children.filter(kind="cancellation", status="pending").exists():
        raise ConflictError("A cancellation is already awaiting a decision.",
                            code="cancellation_pending")
    app = LeaveApplication.objects.create(
        applicant_user_id=actor.user_id, kind="cancellation", parent=parent,
        category=parent.category, start_date=parent.start_date,
        end_date=parent.end_date, half_day=parent.half_day, days=parent.days,
        reason=reason, route=parent.route, unit=parent.unit)
    audit.record(app, "submitted", actor_user_id=actor.user_id, detail=reason)
    audit.record(parent, "cancellation_requested", actor_user_id=actor.user_id)
    workflow.begin_routing(app, actor_user_id=actor.user_id)
    return app


@transaction.atomic
def request_extension(*, actor, application_id: int, new_end_date: date,
                      reason: str, substitute_user_id: int | None = None,
                      today: date | None = None) -> LeaveApplication:
    today = today or timezone.localdate()
    parent = _owned_approved(actor, application_id)
    if parent.category not in cat.EXTENDABLE:
        raise ConflictError(f"{parent.category} cannot be extended.",
                            code="not_extendable")
    current_end = scope.effective_end(parent)
    if not (parent.start_date <= today <= current_end):
        raise ConflictError("Only leave that is under way can be extended.",
                            code="not_ongoing")
    if new_end_date <= current_end:
        raise validation.RuleRefused(
            "The new end date must be after the current end date.",
            code="invalid_period")
    if parent.children.filter(kind="extension", status="pending").exists():
        raise ConflictError("An extension is already awaiting a decision.",
                            code="extension_pending")

    person = _person(actor.user_id)
    start = current_end + timedelta(days=1)
    checked = validation.check_request(
        user_id=actor.user_id, is_faculty=person.is_faculty, category=parent.category,
        start=start, end=new_end_date, half="", station_leave=False,
        station_destination="", substitute_id=substitute_user_id, today=today,
        retrospective=True)
    app = LeaveApplication.objects.create(
        applicant_user_id=actor.user_id, kind="extension", parent=parent,
        category=parent.category, start_date=start, end_date=new_end_date,
        days=checked.days, reason=reason, substitute_user_id=substitute_user_id,
        route=parent.route, unit=parent.unit)
    audit.record(app, "submitted", actor_user_id=actor.user_id, detail=reason)
    if substitute_user_id:
        workflow.open_substitute_task(app)
    else:
        workflow.begin_routing(app, actor_user_id=actor.user_id)
    return app
