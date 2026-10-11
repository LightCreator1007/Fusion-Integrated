"""Year-end processing (EL-UC-020; BR-EL-002..009).

Idempotent: every entry it posts is unique per user, category and year, so a
second run over the same year changes nothing. Failures are collected and
reported, not allowed to stop the run.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import IntegrityError, transaction

from modules.directory import contracts as directory
from modules.elm.domain import categories as cat
from modules.elm.domain import yearend as rules
from modules.elm.models import LedgerEntry
from modules.elm.services import balances, facts

log = logging.getLogger("fusion.elm.yearend")


@dataclass
class YearEndReport:
    year: int
    processed: int = 0
    entries: int = 0
    exceptions: list[str] = field(default_factory=list)


def _post_once(**kw) -> bool:
    try:
        with transaction.atomic():
            balances.post(**kw)
    except IntegrityError:
        return False
    return True


def run(year: int) -> YearEndReport:
    report = YearEndReport(year=year)
    employees = {e.user_id: e.kind == "faculty" for e in directory.get_employees()}
    holders = set(LedgerEntry.objects.filter(year=year).values_list("user_id", flat=True))
    for uid in sorted(set(employees) | holders):
        try:
            with transaction.atomic():
                report.entries += _settle_user(uid, year, employees.get(uid))
            report.processed += 1
        except Exception as exc:        # noqa: BLE001 - reported, never fatal to the run
            log.warning("year-end failed for user %s: %s", uid, exc)
            report.exceptions.append(f"user {uid}: {exc}")
    return report


def _settle_user(user_id: int, year: int, is_faculty: bool | None) -> int:
    if is_faculty is None:
        person = facts.people([user_id]).get(user_id)
        is_faculty = bool(person and person.is_faculty)
    balances.ensure_credited(user_id, year, is_faculty=is_faculty)
    balances.ensure_credited(user_id, year + 1, is_faculty=is_faculty)

    posted = 0
    for category in cat.ALL:
        remaining = balances.balance_of(user_id, category, year)
        outcome = rules.settle(category, remaining)
        if outcome.lapse:
            posted += _post_once(user_id=user_id, category=category, year=year,
                                 entry_type="lapse", days=-outcome.lapse,
                                 note=f"{year} year-end lapse")
        if outcome.carry:
            posted += _post_once(user_id=user_id, category=category, year=year + 1,
                                 entry_type="carry_in", days=outcome.carry,
                                 note=f"Carried forward from {year}")
        if outcome.convert_from_vl:
            first = _post_once(user_id=user_id, category=cat.VL, year=year,
                               entry_type="conversion_out",
                               days=-outcome.convert_from_vl,
                               note=f"Converted to EL at {cat.VL_PER_EL}:1")
            if first:
                posted += 1
                posted += _post_once(
                    user_id=user_id, category=cat.EL, year=year + 1,
                    entry_type="conversion_in", days=_round(outcome.credit_el),
                    note=f"Converted from {outcome.convert_from_vl} VL")
    return posted


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
