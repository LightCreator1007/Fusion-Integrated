"""The leave account (EL-UC-012).

Entitlement is credited lazily: the first time anyone asks about a user's year,
the annual credit for that year is posted. The unique constraint on the ledger
makes that safe under concurrency.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum

from modules.elm.domain import categories as cat
from modules.elm.models import LeaveApplication, LeavePolicy, LedgerEntry
from modules.elm.services import facts

ZERO = Decimal(0)


@dataclass(frozen=True)
class Balance:
    category: str
    label: str
    entitlement: Decimal
    used: Decimal
    pending: Decimal
    balance: Decimal

    @property
    def available(self) -> Decimal:
        return self.balance - self.pending


def policy_for(category: str) -> LeavePolicy:
    policy = LeavePolicy.objects.filter(category=category).first()
    if policy is None:
        raise ValueError(f"No leave policy for {category}.")
    return policy


def credited_to(policy: LeavePolicy, *, is_faculty: bool) -> bool:
    if not policy.is_active:
        return False
    if policy.applies_to == cat.APPLIES_FACULTY:
        return is_faculty
    if policy.applies_to == cat.APPLIES_NON_FACULTY:
        return not is_faculty
    return True


def ensure_credited(user_id: int, year: int, *, is_faculty: bool | None = None) -> None:
    """Post the year's annual entitlement once."""
    if is_faculty is None:
        person = facts.people([user_id]).get(user_id)
        is_faculty = bool(person and person.is_faculty)
    existing = set(LedgerEntry.objects
                   .filter(user_id=user_id, year=year, entry_type="credit")
                   .values_list("category", flat=True))
    for policy in LeavePolicy.objects.all():
        if policy.category in existing or not credited_to(policy, is_faculty=is_faculty):
            continue
        try:
            with transaction.atomic():
                LedgerEntry.objects.create(
                    user_id=user_id, category=policy.category, year=year,
                    entry_type="credit", days=policy.annual_days,
                    note=f"{year} entitlement")
        except IntegrityError:
            continue        # another request credited it first


def post(*, user_id: int, category: str, year: int, entry_type: str,
         days: Decimal, application=None, note: str = "",
         actor_user_id=None) -> LedgerEntry:
    return LedgerEntry.objects.create(
        user_id=user_id, category=category, year=year, entry_type=entry_type,
        days=days, application=application, note=note[:300],
        created_by_user_id=actor_user_id)


def balance_of(user_id: int, category: str, year: int) -> Decimal:
    total = (LedgerEntry.objects
             .filter(user_id=user_id, category=category, year=year)
             .aggregate(t=Sum("days"))["t"])
    return total or ZERO


def pending_days(user_id: int, category: str, year: int) -> Decimal:
    """Days requested but not yet decided, so two requests cannot both claim
    the same balance."""
    total = (LeaveApplication.objects
             .filter(applicant_user_id=user_id, category=category,
                     status="pending", kind__in=["leave", "extension"],
                     start_date__year=year)
             .aggregate(t=Sum("days"))["t"])
    return total or ZERO


def available(user_id: int, category: str, year: int) -> Decimal:
    return balance_of(user_id, category, year) - pending_days(user_id, category, year)


def statement(user_id: int, year: int) -> list[Balance]:
    ensure_credited(user_id, year)
    rows = (LedgerEntry.objects.filter(user_id=user_id, year=year)
            .values("category", "entry_type").annotate(t=Sum("days")))
    grid: dict[str, dict[str, Decimal]] = {}
    for r in rows:
        grid.setdefault(r["category"], {})[r["entry_type"]] = r["t"]
    out = []
    for policy in LeavePolicy.objects.order_by("id"):
        entries = grid.get(policy.category, {})
        if not entries and not policy.is_active:
            continue
        total = sum(entries.values(), ZERO)
        used = -entries.get("debit", ZERO) - entries.get("restore", ZERO)
        entitlement = (entries.get("credit", ZERO) + entries.get("carry_in", ZERO)
                       + entries.get("conversion_in", ZERO))
        if not entries and entitlement == 0:
            # Not credited to this employee (e.g. VL for non-faculty).
            continue
        out.append(Balance(
            category=policy.category, label=cat.LABELS.get(policy.category, policy.category),
            entitlement=entitlement, used=used,
            pending=pending_days(user_id, policy.category, year), balance=total))
    return out
