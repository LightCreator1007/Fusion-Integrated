"""Year-end outcome per category (BR-EL-002..009)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from modules.elm.domain import categories as cat


@dataclass(frozen=True)
class YearEndOutcome:
    lapse: Decimal = Decimal(0)
    carry: Decimal = Decimal(0)
    convert_from_vl: Decimal = Decimal(0)
    credit_el: Decimal = Decimal(0)


def settle(category: str, remaining: Decimal) -> YearEndOutcome:
    """What happens to `remaining` unused days of `category`."""
    remaining = max(remaining, Decimal(0))
    if category in cat.LAPSES:
        return YearEndOutcome(lapse=remaining)
    if category in cat.CARRY_FORWARD:
        return YearEndOutcome(carry=remaining)
    if category == cat.VL:
        # 2 VL : 1 EL, fractions included; the VL itself does not carry.
        return YearEndOutcome(convert_from_vl=remaining,
                              credit_el=remaining / cat.VL_PER_EL)
    return YearEndOutcome()
