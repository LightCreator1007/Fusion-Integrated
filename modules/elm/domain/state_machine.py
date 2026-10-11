"""Lifecycle of a request (BR-EL-022, BR-EL-023, BR-EL-034).

There is no edit edge: a submitted request is never modified in place, only
withdrawn (pending) or cancelled (approved, before it starts).
"""
from __future__ import annotations

from modules.elm.domain.errors import InvalidTransition

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"
CANCELLED = "cancelled"

STATUSES = (PENDING, APPROVED, REJECTED, WITHDRAWN, CANCELLED)
FINAL = frozenset({REJECTED, WITHDRAWN, CANCELLED})
#: Occupies the applicant's calendar and so blocks an overlapping request.
ACTIVE = frozenset({PENDING, APPROVED})

APPROVE = "approve"
REJECT = "reject"
WITHDRAW = "withdraw"
CANCEL = "cancel"

TRANSITIONS = {
    (PENDING, APPROVE): APPROVED,
    (PENDING, REJECT): REJECTED,
    (PENDING, WITHDRAW): WITHDRAWN,
    (APPROVED, CANCEL): CANCELLED,
}


def next_status(status: str, event: str) -> str:
    try:
        return TRANSITIONS[(status, event)]
    except KeyError:
        raise InvalidTransition(status, event) from None
