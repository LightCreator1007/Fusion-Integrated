"""The request, its routing tasks, and its audit trail."""
from django.db import models
from django.db.models import Q

from core.db.mixins import TimeStampedModel
from modules.elm.models.config import OrgUnit

REQUEST_KIND = [("leave", "Leave"), ("extension", "Extension"),
                ("cancellation", "Cancellation")]
REQUEST_STATUS = [("pending", "Pending"), ("approved", "Approved"),
                  ("rejected", "Rejected"), ("withdrawn", "Withdrawn"),
                  ("cancelled", "Cancelled")]
HALF_DAY = [("", "Full day"), ("first", "First half"), ("second", "Second half")]
SUBSTITUTE_STATUS = [("not_required", "Not required"), ("pending", "Pending"),
                     ("accepted", "Accepted"), ("declined", "Declined")]
ENTRY_CHANNEL = [("online", "Online"), ("offline", "Offline record")]
TASK_STATUS = [("pending", "Pending"), ("done", "Done"), ("cancelled", "Cancelled")]
RESUMPTION_STATUS = [("pending", "Pending"), ("approved", "Reviewed"),
                     ("rejected", "Returned")]


class LeaveApplication(TimeStampedModel):
    """One request. Extensions and cancellations are requests of their own that
    point at the leave they act on; the approved original is never edited."""

    applicant_user_id = models.IntegerField(db_index=True)
    kind = models.CharField(max_length=12, choices=REQUEST_KIND, default="leave")
    parent = models.ForeignKey("self", null=True, blank=True,
                               on_delete=models.PROTECT, related_name="children")
    category = models.CharField(max_length=3)
    start_date = models.DateField()
    end_date = models.DateField()
    half_day = models.CharField(max_length=6, choices=HALF_DAY, blank=True, default="")
    days = models.DecimalField(max_digits=7, decimal_places=2)
    reason = models.TextField()

    # Station Leave rides on the same application (BR-EL-013).
    station_leave = models.BooleanField(default=False)
    station_destination = models.CharField(max_length=200, blank=True)
    station_contact = models.CharField(max_length=120, blank=True)
    evidence_reference = models.CharField(max_length=300, blank=True)

    substitute_user_id = models.IntegerField(null=True, blank=True, db_index=True)
    substitute_status = models.CharField(max_length=12, choices=SUBSTITUTE_STATUS,
                                         default="not_required")

    status = models.CharField(max_length=10, choices=REQUEST_STATUS, default="pending")
    #: Snapshot of the resolved route: [{"role": ..., "mode": ...}, ...].
    route = models.JSONField(default=list)
    current_step = models.PositiveSmallIntegerField(default=0)
    unit = models.ForeignKey(OrgUnit, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="+")
    recommendation = models.CharField(max_length=20, blank=True)

    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by_user_id = models.IntegerField(null=True, blank=True)
    decision_remark = models.CharField(max_length=500, blank=True)
    actual_resumption_date = models.DateField(null=True, blank=True)

    entry_channel = models.CharField(max_length=8, choices=ENTRY_CHANNEL, default="online")
    offline_reference = models.CharField(max_length=200, blank=True)
    offline_reason = models.CharField(max_length=300, blank=True)
    recorded_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "elm_leave_application"
        indexes = [
            models.Index(fields=["applicant_user_id", "-created_at"],
                         name="elm_app_applicant_idx"),
            models.Index(fields=["applicant_user_id", "start_date", "end_date"],
                         condition=Q(status__in=["pending", "approved"]),
                         name="elm_app_active_span_idx"),
            models.Index(fields=["status", "-created_at"], name="elm_app_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=models.F("start_date")),
                                   name="elm_app_period_ordered"),
            models.CheckConstraint(
                condition=Q(kind="leave") | Q(parent__isnull=False),
                name="elm_app_child_has_parent"),
        ]

    def __str__(self) -> str:
        return f"{self.category} {self.start_date}..{self.end_date} ({self.status})"


class ApprovalTask(TimeStampedModel):
    """One actionable item: a substitute's consent, a routing step, or a
    resumption review. `created_at` is when it was assigned, which the SLA
    thresholds measure from."""

    application = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE,
                                    related_name="tasks")
    resumption = models.ForeignKey("elm.LeaveResumption", null=True, blank=True,
                                   on_delete=models.CASCADE, related_name="tasks")
    step_index = models.PositiveSmallIntegerField(default=0)
    role = models.CharField(max_length=20)       # substitute | routing role
    mode = models.CharField(max_length=10)       # consent | recommend | forward | final
    assignee_user_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=TASK_STATUS, default="pending")
    outcome = models.CharField(max_length=20, blank=True)
    actor_user_id = models.IntegerField(null=True, blank=True)
    remark = models.CharField(max_length=500, blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)
    reminded_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "elm_approval_task"
        indexes = [
            models.Index(fields=["status", "role"], name="elm_task_queue_idx"),
            models.Index(fields=["assignee_user_id", "status"],
                         name="elm_task_assignee_idx"),
        ]


class LeaveResumption(TimeStampedModel):
    application = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE,
                                    related_name="resumptions")
    actual_resumption_date = models.DateField()
    details = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=RESUMPTION_STATUS,
                              default="pending")
    #: approved end minus actual date; positive when early, negative when late.
    adjustment_days = models.IntegerField(default=0)
    reviewed_by_user_id = models.IntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_remark = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "elm_leave_resumption"
        constraints = [
            models.UniqueConstraint(fields=["application"],
                                    condition=Q(status="pending"),
                                    name="elm_one_pending_resumption"),
        ]


class ApplicationEvent(models.Model):
    """Append-only history shown as the request's status trail (BR-EL-035)."""

    application = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE,
                                    related_name="events")
    event = models.CharField(max_length=40)
    actor_user_id = models.IntegerField(null=True, blank=True)
    detail = models.CharField(max_length=500, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "elm_application_event"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.event} on {self.application_id}"
