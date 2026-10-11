"""Reminder and escalation of overdue tasks (EL-UC-021; BR-EL-032, 033, 038).

Both are guarded on the task still being pending: a task decided or withdrawn
between the threshold and this run gets neither.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from modules.elm.models import ApprovalTask, SlaSetting
from modules.elm.services import audit


@dataclass
class SlaReport:
    reminded: int = 0
    escalated: int = 0


def settings() -> SlaSetting:
    row = SlaSetting.objects.order_by("id").first()
    return row or SlaSetting.objects.create()


def process(now: datetime | None = None) -> SlaReport:
    now = now or timezone.now()
    cfg = settings()
    report = SlaReport()
    remind_before = now - timedelta(hours=cfg.reminder_after_hours)
    escalate_before = now - timedelta(hours=cfg.escalate_after_hours)

    due = (ApprovalTask.objects
           .filter(status="pending", created_at__lte=remind_before,
                   reminded_at__isnull=True)
           .values_list("pk", flat=True))
    for pk in list(due):
        report.reminded += _remind(pk, now)

    late = (ApprovalTask.objects
            .filter(status="pending", created_at__lte=escalate_before,
                    escalated_at__isnull=True)
            .values_list("pk", flat=True))
    for pk in list(late):
        report.escalated += _escalate(pk, now, cfg)
    return report


@transaction.atomic
def _remind(pk: int, now: datetime) -> int:
    task = (ApprovalTask.objects.select_for_update().select_related("application")
            .filter(pk=pk, status="pending", reminded_at__isnull=True).first())
    if task is None:
        return 0            # decided or withdrawn since: no reminder (BR-EL-032)
    task.reminded_at = now
    task.save(update_fields=["reminded_at", "updated_at"])
    audit.notify(topic="sla_reminder", user_id=task.assignee_user_id,
                 role="" if task.assignee_user_id else task.role,
                 subject="A leave request is still waiting for your action",
                 application=task.application)
    audit.record(task.application, "sla_reminder", detail=f"{task.role} task {task.pk}")
    return 1


@transaction.atomic
def _escalate(pk: int, now: datetime, cfg: SlaSetting) -> int:
    task = (ApprovalTask.objects.select_for_update().select_related("application")
            .filter(pk=pk, status="pending", escalated_at__isnull=True).first())
    if task is None:
        return 0            # BR-EL-033
    task.escalated_at = now
    task.save(update_fields=["escalated_at", "updated_at"])
    audit.notify(topic="sla_escalation", user_id=cfg.escalate_to_user_id,
                 subject="A leave request is overdue",
                 body=f"The {task.role} step has been pending since "
                      f"{task.created_at:%Y-%m-%d %H:%M}.",
                 application=task.application)
    audit.record(task.application, "sla_escalation", detail=f"{task.role} task {task.pk}")
    return 1
