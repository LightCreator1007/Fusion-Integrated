"""Who may act on a task. Authority comes from the route table in the domain
layer; this module only applies it to a caller."""
from __future__ import annotations

from core.api.exceptions import PermissionDeniedError
from modules.elm.domain import routing
from modules.elm.models import ApprovalTask

SUBSTITUTE = "substitute"
P_TASK_VIEW = "elm_leave.task.view"


def require_for_task(actor, task: ApprovalTask, applicant_user_id: int) -> None:
    """Raise unless `actor` is the person this task is waiting for."""
    if task.role == SUBSTITUTE:
        if task.assignee_user_id != actor.user_id:
            raise PermissionDeniedError("This request was not addressed to you.")
        return
    code = routing.ROLE_PERMISSION[task.role]
    if not actor.has_permission(code):
        raise PermissionDeniedError(
            "Your role may not act on this step of the request.")
    if actor.user_id == applicant_user_id:
        raise PermissionDeniedError("You cannot decide your own leave request.")
    if task.role == routing.UNIT_HEAD and task.assignee_user_id != actor.user_id:
        raise PermissionDeniedError(
            "Only the head of the applicant's unit may review this request.")
