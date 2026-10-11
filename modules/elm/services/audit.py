"""History rows and notices, written in the transaction that causes them."""
from __future__ import annotations

from modules.elm.models import ApplicationEvent, LeaveApplication, Notification


def record(application: LeaveApplication, event: str, *, actor_user_id=None,
           detail: str = "") -> None:
    ApplicationEvent.objects.create(
        application=application, event=event, actor_user_id=actor_user_id,
        detail=detail[:500])


def notify(*, topic: str, subject: str, body: str = "", user_id=None, role="",
           application: LeaveApplication | None = None) -> None:
    if user_id is None and not role:
        return
    Notification.objects.create(
        recipient_user_id=user_id, recipient_role=role, topic=topic,
        subject=subject[:200], body=body[:500], application=application)
