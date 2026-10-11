"""Request and response shapes. Thin: rules live in services/ and domain/."""
from __future__ import annotations

from rest_framework import serializers

from modules.elm.domain import categories as cat
from modules.elm.models import (
    ApplicationEvent,
    ApprovalTask,
    HierarchyRule,
    Holiday,
    HolidayCalendar,
    LeaveApplication,
    LeavePolicy,
    LeaveResumption,
    Notification,
    OrgUnit,
    SlaSetting,
    UnitMember,
    VacationPeriod,
)
from modules.elm.models.leave import HALF_DAY
from modules.elm.selectors import leave as scope

CATEGORY = serializers.ChoiceField(choices=[(c, cat.LABELS[c]) for c in cat.ALL])
HALF = serializers.ChoiceField(choices=HALF_DAY, required=False,
                               allow_blank=True, default="")


# -- reads ---------------------------------------------------------------------
class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationEvent
        fields = ["id", "event", "actor_user_id", "detail", "at"]


class ResumptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveResumption
        fields = ["id", "actual_resumption_date", "details", "status",
                  "adjustment_days", "reviewed_at", "review_remark"]


class TaskStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalTask
        fields = ["id", "role", "mode", "status", "outcome", "remark",
                  "assignee_user_id", "actor_user_id", "created_at", "acted_at"]


class LeaveApplicationSerializer(serializers.ModelSerializer):
    category_label = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()
    substitute_name = serializers.SerializerMethodField()
    awaiting = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()
    parent_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveApplication
        fields = [
            "id", "kind", "parent_id", "applicant_user_id", "applicant_name",
            "category", "category_label", "start_date", "end_date", "half_day",
            "days", "reason", "station_leave", "station_destination",
            "station_contact", "evidence_reference", "substitute_user_id",
            "substitute_name", "substitute_status", "status", "recommendation",
            "awaiting", "decided_at", "decision_remark",
            "actual_resumption_date", "entry_channel", "offline_reference",
            "allowed_actions", "created_at",
        ]

    def get_category_label(self, obj) -> str:
        return cat.LABELS.get(obj.category, obj.category)

    def get_applicant_name(self, obj) -> str:
        return self.context.get("names", {}).get(obj.applicant_user_id, "")

    def get_substitute_name(self, obj) -> str:
        return self.context.get("names", {}).get(obj.substitute_user_id, "")

    def get_awaiting(self, obj) -> str:
        """Who the request is waiting on, in a word the employee understands."""
        if obj.status != "pending":
            return ""
        if obj.substitute_status == "pending":
            return "substitute"
        if obj.substitute_status == "declined":
            return "applicant"
        if obj.current_step < len(obj.route):
            return obj.route[obj.current_step]["role"]
        return ""

    def get_allowed_actions(self, obj) -> list[str]:
        if obj.applicant_user_id != self.context.get("viewer_id"):
            return []
        return scope.allowed_actions(obj, self.context["today"])


class LeaveApplicationDetailSerializer(LeaveApplicationSerializer):
    route = serializers.JSONField(read_only=True)
    tasks = TaskStepSerializer(many=True, read_only=True)
    events = EventSerializer(many=True, read_only=True)
    resumptions = ResumptionSerializer(many=True, read_only=True)

    class Meta(LeaveApplicationSerializer.Meta):
        fields = [*LeaveApplicationSerializer.Meta.fields, "route", "tasks",
                  "events", "resumptions"]


class BalanceSerializer(serializers.Serializer):
    category = serializers.CharField()
    label = serializers.CharField()
    entitlement = serializers.DecimalField(max_digits=7, decimal_places=2)
    used = serializers.DecimalField(max_digits=7, decimal_places=2)
    pending = serializers.DecimalField(max_digits=7, decimal_places=2)
    balance = serializers.DecimalField(max_digits=7, decimal_places=2)
    available = serializers.DecimalField(max_digits=7, decimal_places=2)


class TaskSerializer(serializers.ModelSerializer):
    application = serializers.SerializerMethodField()
    resumption = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalTask
        fields = ["id", "role", "mode", "status", "assignee_user_id",
                  "created_at", "application", "resumption"]

    def get_application(self, obj) -> dict:
        a = obj.application
        return {
            "id": a.id, "kind": a.kind, "category": a.category,
            "applicant_user_id": a.applicant_user_id,
            "applicant_name": self.context.get("names", {}).get(a.applicant_user_id, ""),
            "start_date": a.start_date, "end_date": a.end_date, "days": a.days,
            "half_day": a.half_day, "reason": a.reason,
            "station_leave": a.station_leave,
            "station_destination": a.station_destination,
            "recommendation": a.recommendation,
        }

    def get_resumption(self, obj) -> dict | None:
        r = obj.resumption
        if r is None:
            return None
        return {"actual_resumption_date": r.actual_resumption_date,
                "details": r.details, "adjustment_days": r.adjustment_days}


class NotificationSerializer(serializers.ModelSerializer):
    application_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "topic", "subject", "body", "application_id", "read_at",
                  "created_at"]


class ColleagueSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    display_name = serializers.CharField()
    department = serializers.CharField(allow_blank=True)


# -- employee writes -------------------------------------------------------------
class LeaveRequestSerializer(serializers.Serializer):
    category = CATEGORY
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    half_day = HALF
    reason = serializers.CharField(max_length=1000)
    station_leave = serializers.BooleanField(default=False)
    station_destination = serializers.CharField(max_length=200, required=False,
                                                allow_blank=True, default="")
    station_contact = serializers.CharField(max_length=120, required=False,
                                            allow_blank=True, default="")
    evidence_reference = serializers.CharField(max_length=300, required=False,
                                               allow_blank=True, default="")
    substitute_user_id = serializers.IntegerField(required=False, allow_null=True,
                                                  default=None)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class ExtendSerializer(serializers.Serializer):
    new_end_date = serializers.DateField()
    reason = serializers.CharField(max_length=1000)
    substitute_user_id = serializers.IntegerField(required=False, allow_null=True,
                                                  default=None)


class ResumeSerializer(serializers.Serializer):
    actual_resumption_date = serializers.DateField()
    details = serializers.CharField(max_length=1000, required=False,
                                    allow_blank=True, default="")


class NominateSerializer(serializers.Serializer):
    substitute_user_id = serializers.IntegerField()


class DecideSerializer(serializers.Serializer):
    outcome = serializers.CharField(max_length=20)
    remark = serializers.CharField(max_length=500, required=False,
                                   allow_blank=True, default="")


# -- administration ------------------------------------------------------------
class LeavePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeavePolicy
        fields = ["category", "annual_days", "applies_to", "carry_forward",
                  "requires_substitute", "is_active"]
        read_only_fields = ["category"]


class HierarchyRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = HierarchyRule
        fields = ["id", "applicant_group", "category", "steps", "is_active"]

    def validate(self, attrs):
        from modules.elm.services import config

        if "applicant_group" in attrs:
            config.check_group(attrs["applicant_group"])
        if "steps" in attrs:
            config.check_steps(attrs["steps"])
        if attrs.get("category") and attrs["category"] not in cat.HIGHER_SANCTION:
            raise serializers.ValidationError(
                {"category": "Only higher-sanction categories take a path."})
        return attrs


class OrgUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgUnit
        fields = ["id", "code", "name", "kind", "head_user_id"]


class UnitMemberSerializer(serializers.ModelSerializer):
    unit_id = serializers.PrimaryKeyRelatedField(
        source="unit", queryset=OrgUnit.objects.all())

    class Meta:
        model = UnitMember
        fields = ["id", "user_id", "unit_id", "designation"]


class SlaSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlaSetting
        fields = ["reminder_after_hours", "escalate_after_hours",
                  "escalate_to_user_id"]

    def validate(self, attrs):
        reminder = attrs.get("reminder_after_hours",
                             getattr(self.instance, "reminder_after_hours", 0))
        escalate = attrs.get("escalate_after_hours",
                             getattr(self.instance, "escalate_after_hours", 0))
        if escalate <= reminder:
            raise serializers.ValidationError(
                {"escalate_after_hours": "Escalation must come after the reminder."})
        return attrs


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "name", "kind"]


class HolidayCalendarSerializer(serializers.ModelSerializer):
    holidays = HolidaySerializer(many=True, read_only=True)

    class Meta:
        model = HolidayCalendar
        fields = ["id", "year", "title", "status", "published_at", "holidays"]
        read_only_fields = ["status", "published_at"]


class VacationPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacationPeriod
        fields = ["id", "label", "start_date", "end_date"]

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "The end cannot be before the start."})
        return attrs


class OfflineRecordSerializer(serializers.Serializer):
    employee_user_id = serializers.IntegerField()
    category = CATEGORY
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    half_day = HALF
    reason = serializers.CharField(max_length=1000)
    offline_reference = serializers.CharField(max_length=200)
    offline_reason = serializers.CharField(max_length=300)
    sanction_date = serializers.DateField()


class AdjustmentSerializer(serializers.Serializer):
    employee_user_id = serializers.IntegerField()
    category = CATEGORY
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    days = serializers.DecimalField(max_digits=7, decimal_places=2)
    note = serializers.CharField(max_length=300)


class LedgerEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    category = serializers.CharField()
    year = serializers.IntegerField()
    entry_type = serializers.CharField()
    days = serializers.DecimalField(max_digits=7, decimal_places=2)
    note = serializers.CharField()
    application_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()


class YearEndRequestSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)


class YearEndReportSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    processed = serializers.IntegerField()
    entries = serializers.IntegerField()
    exceptions = serializers.ListField(child=serializers.CharField())
