"""Leave categories and the facts about each that the rules branch on.

Pure Python: the same table drives validation, routing and year-end, so a rule
is stated once (EL-BR-001..011).
"""
from __future__ import annotations

CL = "CL"
RH = "RH"
SCL = "SCL"
EL = "EL"
COL = "COL"
VL = "VL"

ALL = (CL, RH, SCL, EL, COL, VL)

LABELS = {
    CL: "Casual Leave",
    RH: "Restricted Holiday",
    SCL: "Special Casual Leave",
    EL: "Earned Leave",
    COL: "Commuted Leave",
    VL: "Vacation Leave",
}

#: The Unit Head is the final authority (BR-EL-016).
UNIT_HEAD_FINAL = frozenset({CL, RH})

#: The Unit Head recommends and the request goes up the hierarchy (BR-EL-017).
HIGHER_SANCTION = frozenset({SCL, EL, COL, VL})

#: Counted over every calendar day of the interval (BR-EL-011).
CONTINUOUS = frozenset({EL, COL, VL})

#: May be extended while ongoing, and resumed from (BR-EL-025, BR-EL-027).
EXTENDABLE = frozenset({EL, COL, VL})
RESUMABLE = EXTENDABLE

#: Only a single-day request can be taken as a half day (BR-EL-010).
HALF_DAY = frozenset({CL})

#: Cannot straddle a leave year: the entitlement lapses at the boundary.
SINGLE_YEAR = frozenset({CL, RH, SCL, VL})

#: Unused days carry into the next year (the rest lapse or convert).
CARRY_FORWARD = frozenset({EL, COL})
LAPSES = frozenset({CL, RH, SCL})

APPLIES_ALL = "all"
APPLIES_FACULTY = "faculty"
APPLIES_NON_FACULTY = "non_faculty"

#: What a fresh install starts from (PS section 3). `applies_to` governs who is
#: CREDITED the annual entitlement; EL for faculty arrives only by conversion.
DEFAULT_POLICIES = {
    CL: {"annual_days": "8", "applies_to": APPLIES_ALL, "carry_forward": False,
         "requires_substitute": False},
    RH: {"annual_days": "2", "applies_to": APPLIES_ALL, "carry_forward": False,
         "requires_substitute": False},
    SCL: {"annual_days": "15", "applies_to": APPLIES_ALL, "carry_forward": False,
          "requires_substitute": False},
    EL: {"annual_days": "30", "applies_to": APPLIES_NON_FACULTY,
         "carry_forward": True, "requires_substitute": True},
    COL: {"annual_days": "20", "applies_to": APPLIES_ALL, "carry_forward": True,
          "requires_substitute": True},
    VL: {"annual_days": "60", "applies_to": APPLIES_FACULTY,
         "carry_forward": False, "requires_substitute": True},
}

#: VL converts to EL at this many VL days per EL day (BR-EL-007).
VL_PER_EL = 2


def is_valid(category: str) -> bool:
    return category in ALL
