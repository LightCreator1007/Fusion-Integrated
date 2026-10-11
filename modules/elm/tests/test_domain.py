"""The rules, with no database."""
from datetime import date
from decimal import Decimal

import pytest

from modules.elm.domain import categories as cat
from modules.elm.domain import resumption, routing, yearend
from modules.elm.domain import state_machine as sm
from modules.elm.domain.counting import count_days
from modules.elm.domain.errors import InvalidTransition, RuleViolation
from modules.elm.domain.overlap import Span, overlaps

MON, TUE, FRI, SAT, SUN, NEXT_MON = (
    date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 6), date(2026, 3, 7),
    date(2026, 3, 8), date(2026, 3, 9))


# -- counting ------------------------------------------------------------------
def test_casual_leave_skips_weekends_and_closed_holidays():
    # Fri..Tue is five calendar days but three working days; Mon is closed.
    assert count_days("CL", FRI, date(2026, 3, 10), "", {NEXT_MON}) == Decimal(2)


def test_el_counts_every_calendar_day_across_weekends():
    assert count_days("EL", FRI, NEXT_MON, "", {SAT}) == Decimal(4)


def test_half_day_cl_is_half_a_day():
    assert count_days("CL", MON, MON, "first", set()) == Decimal("0.5")


@pytest.mark.parametrize("category", ["SCL", "EL", "RH"])
def test_only_cl_may_be_a_half_day(category):
    with pytest.raises(RuleViolation) as e:
        count_days(category, MON, MON, "second", set())
    assert e.value.code == "half_day_not_allowed"


def test_half_day_must_be_one_date():
    with pytest.raises(RuleViolation) as e:
        count_days("CL", MON, TUE, "first", set())
    assert e.value.code == "half_day_single_date"


def test_a_weekend_only_cl_request_is_refused():
    with pytest.raises(RuleViolation) as e:
        count_days("CL", SAT, SUN, "", set())
    assert e.value.code == "no_working_days"


def test_end_before_start_is_refused():
    with pytest.raises(RuleViolation):
        count_days("EL", TUE, MON, "", set())


def test_rh_is_a_single_day():
    assert count_days("RH", MON, MON, "", set()) == Decimal(1)
    with pytest.raises(RuleViolation):
        count_days("RH", MON, TUE, "", set())


# -- overlap -------------------------------------------------------------------
def test_overlapping_ranges_collide():
    assert overlaps(Span(MON, TUE), Span(TUE, FRI))


def test_disjoint_ranges_do_not_collide():
    assert not overlaps(Span(MON, MON), Span(TUE, FRI))


def test_first_and_second_half_of_one_day_do_not_overlap():
    assert not overlaps(Span(MON, MON, "first"), Span(MON, MON, "second"))


def test_same_half_or_a_full_day_still_overlaps():
    assert overlaps(Span(MON, MON, "first"), Span(MON, MON, "first"))
    assert overlaps(Span(MON, MON, "first"), Span(MON, MON, ""))


# -- routing -------------------------------------------------------------------
def roles(steps):
    return [(s.role, s.mode) for s in steps]


def test_cl_and_rh_end_at_the_unit_head():
    for category in ("CL", "RH"):
        steps = routing.resolve_route(category=category, group="staff",
                                      is_unit_head=False, configured=None)
        assert roles(steps) == [("unit_head", "final")]


def test_higher_sanction_leave_is_recommended_then_forwarded_then_decided():
    steps = routing.resolve_route(category="EL", group="staff",
                                  is_unit_head=False, configured=None)
    assert roles(steps) == [("unit_head", "recommend"),
                            ("establishment", "forward"), ("registrar", "final")]


def test_faculty_default_path_ends_at_the_dean():
    steps = routing.resolve_route(category="VL", group="faculty",
                                  is_unit_head=False, configured=None)
    assert steps[-1] == routing.Step("dean", "final")


def test_a_unit_head_does_not_review_their_own_request():
    steps = routing.resolve_route(category="EL", group="faculty",
                                  is_unit_head=True, configured=None)
    assert "unit_head" not in [s.role for s in steps]


def test_unit_head_cl_goes_to_the_top_of_their_path():
    steps = routing.resolve_route(category="CL", group="faculty",
                                  is_unit_head=True, configured=None)
    assert roles(steps) == [("dean", "final")]


def test_the_director_sanctions_their_own_leave():
    assert routing.resolve_route(category="EL", group="director",
                                 is_unit_head=False, configured=None) == []


def test_configured_path_overrides_the_default():
    steps = routing.resolve_route(category="EL", group="staff", is_unit_head=False,
                                  configured=["unit_head", "director"])
    assert roles(steps) == [("unit_head", "recommend"), ("director", "final")]


def test_an_unknown_authority_in_the_path_is_refused():
    with pytest.raises(RuleViolation):
        routing.resolve_route(category="EL", group="staff", is_unit_head=False,
                              configured=["unit_head", "chancellor"])


def test_applicant_group_uses_the_most_senior_hat():
    assert routing.applicant_group(is_faculty=True, authority_roles={"dean", "director"}
                                   ) == routing.DIRECTOR
    assert routing.applicant_group(is_faculty=True, authority_roles=set()) == "faculty"
    assert routing.applicant_group(is_faculty=False, authority_roles=set()) == "staff"


def test_every_routing_role_has_a_permission():
    assert set(routing.ROLE_PERMISSION) == set(routing.ROLES)


# -- lifecycle -----------------------------------------------------------------
def test_pending_may_be_withdrawn_but_approved_may_not():
    assert sm.next_status(sm.PENDING, sm.WITHDRAW) == sm.WITHDRAWN
    with pytest.raises(InvalidTransition):
        sm.next_status(sm.APPROVED, sm.WITHDRAW)


def test_only_approved_leave_can_be_cancelled():
    assert sm.next_status(sm.APPROVED, sm.CANCEL) == sm.CANCELLED
    with pytest.raises(InvalidTransition):
        sm.next_status(sm.PENDING, sm.CANCEL)


@pytest.mark.parametrize("status", sorted(sm.FINAL))
def test_final_states_have_no_way_out(status):
    assert not [k for k in sm.TRANSITIONS if k[0] == status]


# -- resumption and year-end ---------------------------------------------------
def test_resuming_on_the_approved_end_changes_nothing():
    out = resumption.assess(date(2026, 3, 10), date(2026, 3, 10))
    assert (out.kind, out.adjustment_days) == ("on_time", 0)


def test_early_resumption_restores_days_and_late_deducts():
    assert resumption.assess(date(2026, 3, 10), date(2026, 3, 8)).adjustment_days == 2
    assert resumption.assess(date(2026, 3, 10), date(2026, 3, 13)).adjustment_days == -3


def test_cl_rh_scl_lapse_el_col_carry():
    for c in (cat.CL, cat.RH, cat.SCL):
        assert yearend.settle(c, Decimal(3)).lapse == Decimal(3)
    for c in (cat.EL, cat.COL):
        assert yearend.settle(c, Decimal(3)).carry == Decimal(3)


def test_vl_converts_to_el_two_for_one_with_fractions():
    out = yearend.settle(cat.VL, Decimal(11))
    assert out.credit_el == Decimal("5.5")
    assert out.carry == 0
