"""Holiday / RH calendar and vacation periods (EL-UC-015, BR-EL-031)."""
from django.db import models

from core.db.mixins import TimeStampedModel

CALENDAR_STATUS = [("draft", "Draft"), ("published", "Published")]
HOLIDAY_KIND = [("closed", "Closed holiday"), ("restricted", "Restricted holiday")]


class HolidayCalendar(TimeStampedModel):
    year = models.PositiveSmallIntegerField(db_index=True)
    title = models.CharField(max_length=150)
    status = models.CharField(max_length=10, choices=CALENDAR_STATUS, default="draft")
    published_at = models.DateTimeField(null=True, blank=True)
    published_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "elm_holiday_calendar"
        indexes = [models.Index(fields=["year", "status", "-published_at"],
                                name="elm_calendar_effective_idx")]


class Holiday(TimeStampedModel):
    calendar = models.ForeignKey(HolidayCalendar, on_delete=models.CASCADE,
                                 related_name="holidays")
    date = models.DateField()
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=10, choices=HOLIDAY_KIND, default="closed")

    class Meta:
        db_table = "elm_holiday"
        constraints = [models.UniqueConstraint(fields=["calendar", "date"],
                                               name="elm_holiday_date_unique")]


class VacationPeriod(TimeStampedModel):
    """The Academic Calendar's vacation windows, as ELM sees them.

    That calendar is maintained outside ELM; until a feed exists this table is
    its local stand-in, so VL applicability is checked against one source.
    """

    label = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = "elm_vacation_period"
        constraints = [models.CheckConstraint(
            condition=models.Q(end_date__gte=models.F("start_date")),
            name="elm_vacation_period_ordered")]
