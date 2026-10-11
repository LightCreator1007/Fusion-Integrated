from django.db import models


class Notification(models.Model):
    """An in-app notice. A task nobody is named for goes to a role's queue."""

    recipient_user_id = models.IntegerField(null=True, blank=True, db_index=True)
    #: Authority role whose holders see it when no individual is named.
    recipient_role = models.CharField(max_length=20, blank=True)
    topic = models.CharField(max_length=40)
    subject = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    application = models.ForeignKey("elm.LeaveApplication", null=True, blank=True,
                                    on_delete=models.CASCADE, related_name="+")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "elm_notification"
        ordering = ["-id"]
        indexes = [models.Index(fields=["recipient_user_id", "read_at"],
                                name="elm_notice_inbox_idx")]

    def __str__(self) -> str:
        return self.subject
