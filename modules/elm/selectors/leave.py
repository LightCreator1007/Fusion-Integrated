"""Who may see what, decided once (BR-EL-036).

Visibility is the queryset: a request or task that is not yours is simply
absent, so a foreign id is a 404 and never confirms the row exists.
"""
from __future__ import annotations

from datetime import date

from django.db.models import Max, Q, QuerySet

from modules.elm.domain import routing
from modules.elm.models import ApprovalTask, LeaveApplication

P_VIEW_ALL = "elm_leave.record.view"
P_VIEW_SELF = "elm_leave.leave.view_self"


def applications_for(actor) -> QuerySet[LeaveApplication]:
    qs = LeaveApplication.objects.all()
    if actor.has_permission(P_VIEW_ALL):
        return qs
    return qs.filter(applicant_user_id=actor.user_id)


def own_applications(actor) -> QuerySet[LeaveApplication]:
    return LeaveApplication.objects.filter(applicant_user_id=actor.user_id)


def readable_application(actor, pk: int) -> LeaveApplication | None:
    """An application the caller owns, or is asked to act on, or may audit."""
    visible = Q(applicant_user_id=actor.user_id) | Q(
        tasks__in=tasks_for(actor, pending_only=False))
    qs = LeaveApplication.objects.filter(pk=pk)
    if actor.has_permission(P_VIEW_ALL):
        return qs.first()
    return qs.filter(visible).distinct().first()


def roles_held(actor) -> set[str]:
    return {role for role, code in routing.ROLE_PERMISSION.items()
            if actor.has_permission(code)}


def tasks_for(actor, *, pending_only: bool = True) -> QuerySet[ApprovalTask]:
    """Tasks addressed to the caller, or queued for a role the caller holds.
    Never the caller's own request."""
    held = roles_held(actor)
    q = Q(assignee_user_id=actor.user_id)
    queue_roles = held - {routing.UNIT_HEAD}
    if queue_roles:
        q |= Q(assignee_user_id__isnull=True, role__in=queue_roles)
    qs = (ApprovalTask.objects.filter(q)
          .exclude(application__applicant_user_id=actor.user_id)
          .select_related("application", "resumption"))
    return qs.filter(status="pending") if pending_only else qs


def effective_end(app: LeaveApplication) -> date:
    """The approved end, counting extensions already granted."""
    extended = app.children.filter(kind="extension", status="approved").aggregate(
        e=Max("end_date"))["e"]
    return max(app.end_date, extended) if extended else app.end_date


def allowed_actions(app: LeaveApplication, today: date) -> list[str]:
    """What the owner may still do. Reads prefetched `children`/`resumptions`
    so a list page costs no per-row queries."""
    from modules.elm.domain import categories as cat

    actions: list[str] = []
    if app.status == "pending":
        actions.append("withdraw")
        if app.substitute_status == "declined":
            actions.append("nominate_substitute")
    if app.status == "approved" and app.kind != "cancellation":
        kids = list(app.children.all())
        if app.start_date > today and not any(
                k.kind == "cancellation" and k.status == "pending" for k in kids):
            actions.append("cancel")
        if app.kind == "leave" and app.category in cat.EXTENDABLE:
            end = max([app.end_date, *[k.end_date for k in kids
                                       if k.kind == "extension"
                                       and k.status == "approved"]])
            pending_ext = any(k.kind == "extension" and k.status == "pending"
                              for k in kids)
            if app.start_date <= today <= end and not pending_ext:
                actions.append("extend")
            if app.start_date <= today and not any(
                    r.status in ("pending", "approved")
                    for r in app.resumptions.all()):
                actions.append("resume")
    return actions
