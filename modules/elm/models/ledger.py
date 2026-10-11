"""The leave account. Balance is the sum of its entries, never a stored total."""
from django.db import models
from django.db.models import Q

from modules.elm.models.leave import LeaveApplication

#: Posted once per user, category and year, so re-running year-end is harmless.
ONCE_PER_YEAR = ["credit", "carry_in", "conversion_in", "conversion_out", "lapse"]


class LedgerEntry(models.Model):
    TYPE = [
        ("credit", "Annual credit"), ("carry_in", "Carried forward"),
        ("conversion_in", "Converted from VL"),
        ("conversion_out", "Converted to EL"), ("lapse", "Lapsed"),
        ("debit", "Leave taken"), ("restore", "Restored"),
        ("adjustment", "Adjustment"),
    ]

    user_id = models.IntegerField(db_index=True)
    category = models.CharField(max_length=3)
    year = models.PositiveSmallIntegerField()
    entry_type = models.CharField(max_length=16, choices=TYPE)
    days = models.DecimalField(max_digits=7, decimal_places=2)   # signed
    application = models.ForeignKey(LeaveApplication, null=True, blank=True,
                                    on_delete=models.PROTECT,
                                    related_name="ledger_entries")
    note = models.CharField(max_length=300, blank=True)
    created_by_user_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "elm_ledger_entry"
        indexes = [models.Index(fields=["user_id", "year", "category"],
                                name="elm_ledger_account_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "category", "year", "entry_type"],
                condition=Q(entry_type__in=ONCE_PER_YEAR),
                name="elm_ledger_once_per_year"),
        ]

    def __str__(self) -> str:
        return f"{self.category} {self.days:+} ({self.entry_type})"
