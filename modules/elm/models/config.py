"""Hierarchy and policy configuration (EL-UC-014, EL-UC-018).

Current values only: there is no draft/publish lifecycle for these (BR-EL-030).
People are plain `user_id` integers; there is no user table in this database.
"""
from django.db import models

from core.db.mixins import TimeStampedModel


class OrgUnit(TimeStampedModel):
    KIND = [("department", "Department"), ("section", "Section"),
            ("office", "Office")]

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=12, choices=KIND, default="department")
    head_user_id = models.IntegerField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "elm_org_unit"

    def __str__(self) -> str:
        return self.name


class UnitMember(TimeStampedModel):
    """An employee belongs to exactly one unit."""

    user_id = models.IntegerField(unique=True)
    unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE,
                             related_name="members")
    designation = models.CharField(max_length=80, blank=True)

    class Meta:
        db_table = "elm_unit_member"


class LeavePolicy(TimeStampedModel):
    APPLIES_TO = [("all", "Every employee"), ("faculty", "Faculty"),
                  ("non_faculty", "Non-faculty")]

    category = models.CharField(max_length=3, unique=True)
    annual_days = models.DecimalField(max_digits=6, decimal_places=1)
    applies_to = models.CharField(max_length=12, choices=APPLIES_TO,
                                  default="all")
    carry_forward = models.BooleanField(default=False)
    requires_substitute = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "elm_leave_policy"


class HierarchyRule(TimeStampedModel):
    """The approval path for an applicant group, optionally per category.

    `steps` is an ordered list of authority roles; the last one decides.
    """

    applicant_group = models.CharField(max_length=12)
    #: Blank applies to every higher-sanction category.
    category = models.CharField(max_length=3, blank=True)
    steps = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "elm_hierarchy_rule"
        constraints = [
            models.UniqueConstraint(fields=["applicant_group", "category"],
                                    name="elm_hierarchy_rule_unique"),
        ]


class SlaSetting(TimeStampedModel):
    """One row. Thresholds are hours since the task was assigned (BR-EL-038)."""

    reminder_after_hours = models.PositiveIntegerField(default=24)
    escalate_after_hours = models.PositiveIntegerField(default=72)
    #: Who hears about an overdue task; blank means the audit log only.
    escalate_to_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "elm_sla_setting"
