"""Who must look at a request, and in what capacity (BR-EL-016..020).

The route is resolved once, at submission, and snapshotted onto the request, so
a later change to the hierarchy configuration never reroutes work in flight.
"""
from __future__ import annotations

from dataclasses import dataclass

from modules.elm.domain import categories as cat
from modules.elm.domain.errors import RuleViolation

UNIT_HEAD = "unit_head"
ESTABLISHMENT = "establishment"
DEAN = "dean"
REGISTRAR = "registrar"
DIRECTOR = "director"

ROLES = (UNIT_HEAD, ESTABLISHMENT, DEAN, REGISTRAR, DIRECTOR)

FACULTY = "faculty"
STAFF = "staff"
APPLICANT_GROUPS = (FACULTY, STAFF, DEAN, REGISTRAR, DIRECTOR)

#: What each role must hold to act. Stated here so the authority for every step
#: lives in one table; the service reads it to make the check.
ROLE_PERMISSION = {
    UNIT_HEAD: "elm_leave.review.unit_head",
    ESTABLISHMENT: "elm_leave.review.establishment",
    DEAN: "elm_leave.sanction.dean",
    REGISTRAR: "elm_leave.sanction.registrar",
    DIRECTOR: "elm_leave.sanction.director",
}

RECOMMEND = "recommend"   # Unit Head on higher-sanction leave: records, never rejects
FORWARD = "forward"       # Establishment / intermediate: verifies and routes on
FINAL = "final"           # decides

#: What the hierarchy configuration falls back to (BR-EL-019, BR-EL-030).
DEFAULT_PATHS = {
    FACULTY: [UNIT_HEAD, ESTABLISHMENT, DEAN],
    STAFF: [UNIT_HEAD, ESTABLISHMENT, REGISTRAR],
    DEAN: [DIRECTOR],
    REGISTRAR: [DIRECTOR],
}


@dataclass(frozen=True)
class Step:
    role: str
    mode: str

    def as_dict(self) -> dict:
        return {"role": self.role, "mode": self.mode}


def applicant_group(*, is_faculty: bool, authority_roles: set[str]) -> str:
    """The most senior hat the applicant wears decides the route."""
    for role in (DIRECTOR, REGISTRAR, DEAN):
        if role in authority_roles:
            return role
    return FACULTY if is_faculty else STAFF


def resolve_route(*, category: str, group: str, is_unit_head: bool,
                  configured: list[str] | None) -> list[Step]:
    """Empty list means the applicant sanctions their own leave (the Director)."""
    if not cat.is_valid(category):
        raise RuleViolation("unknown_category", f"Unknown leave category {category}.")
    if group == DIRECTOR:
        return []

    path = list(configured) if configured else list(DEFAULT_PATHS[group])
    bad = [r for r in path if r not in ROLES]
    if bad:
        raise RuleViolation("bad_hierarchy",
                            f"The hierarchy names an unknown authority: {bad[0]}.")
    if is_unit_head or group in (DEAN, REGISTRAR):
        path = [r for r in path if r != UNIT_HEAD]
    if not path and category not in cat.UNIT_HEAD_FINAL:
        raise RuleViolation("bad_hierarchy",
                            "The hierarchy configuration leaves no sanctioning authority.")

    if category in cat.UNIT_HEAD_FINAL:
        if is_unit_head or group in (DEAN, REGISTRAR):
            return [Step(path[-1], FINAL)] if path else []
        return [Step(UNIT_HEAD, FINAL)]

    steps: list[Step] = []
    for i, role in enumerate(path):
        if i == len(path) - 1:
            steps.append(Step(role, FINAL))
        elif role == UNIT_HEAD:
            steps.append(Step(role, RECOMMEND))
        else:
            steps.append(Step(role, FORWARD))
    return steps


def outcomes_for(mode: str) -> tuple[str, ...]:
    return {
        RECOMMEND: ("recommended", "not_recommended"),
        FORWARD: ("forwarded",),
        FINAL: ("approved", "rejected"),
    }[mode]
