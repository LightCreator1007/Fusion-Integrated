"""The lifecycle end to end through the services, against a real database."""
from decimal import Decimal

import pytest
from freezegun import freeze_time

from core.api.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from modules.elm.models import (
    ApprovalTask,
    HierarchyRule,
    LeaveApplication,
    LedgerEntry,
    Notification,
)
from modules.elm.selectors import leave as scope
from modules.elm.services import (
    applications,
    balances,
    records,
    sla,
    workflow,
    yearend,
)
from modules.elm.services import resumption as resumption_service
from modules.elm.services.validation import RuleRefused
from modules.elm.tests import helpers as h
from modules.elm.tests.helpers import actor, d

pytestmark = pytest.mark.django_db

HOD, ESTT, REG, DEAN, DIRECTOR = (
    actor(h.HEAD, h.HOD, "faculty"), actor(h.ESTT_ID, h.ESTT),
    actor(h.REG_ID, h.REGISTRAR), actor(h.DEAN_ID, h.DEAN, "faculty"),
    actor(h.DIR_ID, h.DIRECTOR, "faculty"))


@pytest.fixture(autouse=True)
def _world(stub_iam):
    with freeze_time("2026-03-02 09:00"):
        h.world()
        stub_iam(users=h.USERS)
        yield


@pytest.fixture(autouse=True)
def _calendar(_world):
    h.publish_calendar(closed=["2026-03-16"], restricted=["2026-03-04"])
    h.vacation("2026-05-01", "2026-07-31")


def apply(who=h.STAFF, kind="staff", **over):
    data = {"category": "CL", "start_date": d("2026-03-09"),
            "end_date": d("2026-03-09"), "half_day": "", "reason": "Family",
            "station_leave": False, "station_destination": "", "station_contact": "",
            "evidence_reference": "", "substitute_user_id": None, **over}
    return applications.apply(actor=actor(who, kind=kind), data=data)


def decide_next(app, who, outcome, remark=""):
    task = app.tasks.get(status="pending")
    return workflow.decide(actor=who, task_id=task.pk, outcome=outcome, remark=remark)


def balance(uid, category, year=2026):
    return balances.balance_of(uid, category, year)


# -- casual leave: the unit head is final ----------------------------------------
def test_cl_is_decided_by_the_unit_head_and_deducted_on_approval():
    app = apply()
    assert app.status == "pending"
    assert app.tasks.get().assignee_user_id == h.HEAD
    assert balance(h.STAFF, "CL") == 8

    app = decide_next(app, HOD, "approved")
    assert app.status == "approved"
    assert balance(h.STAFF, "CL") == 7
    assert Notification.objects.filter(recipient_user_id=h.STAFF, topic="decision")


def test_a_rejection_needs_a_reason_and_deducts_nothing():
    app = apply()
    with pytest.raises(RuleRefused):
        decide_next(app, HOD, "rejected")
    app = decide_next(app, HOD, "rejected", "Short staffed")
    assert app.status == "rejected"
    assert balance(h.STAFF, "CL") == 8


def test_only_the_applicants_unit_head_may_decide():
    app = apply()
    other_head = actor(99, h.HOD)
    task = app.tasks.get()
    with pytest.raises(PermissionDeniedError):
        workflow.decide(actor=other_head, task_id=task.pk, outcome="approved")
    assert scope.tasks_for(other_head).count() == 0       # invisible, not just refused


def test_nobody_decides_their_own_request():
    # The unit head applies for CL; the task goes up, never back to themselves.
    app = apply(h.HEAD, kind="faculty")
    task = app.tasks.get()
    assert task.role == "dean"
    with pytest.raises(PermissionDeniedError):
        workflow.decide(actor=actor(h.HEAD, [*h.HOD, *h.DEAN], "faculty"),
                        task_id=task.pk, outcome="approved")


# -- validation ----------------------------------------------------------------
def test_leave_cannot_start_in_the_past():
    with pytest.raises(RuleRefused) as e:
        apply(start_date=d("2026-02-27"), end_date=d("2026-02-27"))
    assert e.value.code == "start_in_past"


def test_insufficient_balance_is_refused():
    with pytest.raises(RuleRefused) as e:
        apply(start_date=d("2026-03-09"), end_date=d("2026-03-27"))
    assert e.value.code == "insufficient_balance"


def test_pending_requests_reserve_balance():
    apply(start_date=d("2026-03-09"), end_date=d("2026-03-16"))   # 8 working days minus the closed 16th = 6
    with pytest.raises(RuleRefused) as e:
        apply(start_date=d("2026-03-17"), end_date=d("2026-03-20"))
    assert e.value.code == "insufficient_balance"


def test_overlap_with_active_leave_is_refused():
    apply()
    with pytest.raises(RuleRefused) as e:
        apply(category="SCL")
    assert e.value.code == "overlap"


def test_first_and_second_half_cl_on_one_date_are_both_allowed():
    apply(half_day="first")
    second = apply(half_day="second")
    assert second.days == Decimal("0.5")
    with pytest.raises(RuleRefused):
        apply(half_day="first")


def test_withdrawn_leave_no_longer_blocks():
    first = apply()
    workflow.withdraw(actor=actor(h.STAFF), application_id=first.pk)
    assert apply().status == "pending"


def test_rh_must_be_a_restricted_holiday_in_the_published_calendar():
    ok = apply(category="RH", start_date=d("2026-03-04"), end_date=d("2026-03-04"))
    assert ok.days == 1
    with pytest.raises(RuleRefused) as e:
        apply(category="RH", start_date=d("2026-03-05"), end_date=d("2026-03-05"))
    assert e.value.code == "rh_not_applicable"


def test_closed_holidays_are_not_counted_for_cl():
    app = apply(start_date=d("2026-03-13"), end_date=d("2026-03-18"))
    assert app.days == 3            # Fri, Tue and Wed: Sat, Sun and the closed Monday 16th


def test_vl_is_for_faculty_inside_a_vacation_period():
    with pytest.raises(RuleRefused) as e:
        apply(h.STAFF, category="VL", start_date=d("2026-05-04"),
              end_date=d("2026-05-08"), substitute_user_id=h.SUBSTITUTE)
    assert e.value.code == "not_eligible"
    with pytest.raises(RuleRefused) as e:
        apply(h.FACULTY, "faculty", category="VL", start_date=d("2026-04-06"),
              end_date=d("2026-04-10"), substitute_user_id=h.SUBSTITUTE)
    assert e.value.code == "outside_vacation"
    ok = apply(h.FACULTY, "faculty", category="VL", start_date=d("2026-05-04"),
               end_date=d("2026-05-08"), substitute_user_id=h.SUBSTITUTE)
    assert ok.days == 5


def test_non_faculty_get_el_directly_and_faculty_do_not():
    assert balance(h.STAFF, "EL") == 0
    balances.ensure_credited(h.STAFF, 2026)
    balances.ensure_credited(h.FACULTY, 2026)
    assert balance(h.STAFF, "EL") == 30
    assert balance(h.FACULTY, "EL") == 0
    assert balance(h.FACULTY, "VL") == 60
    assert balance(h.STAFF, "VL") == 0


def test_station_leave_needs_a_destination():
    with pytest.raises(RuleRefused) as e:
        apply(station_leave=True)
    assert e.value.code == "station_details_required"
    assert apply(station_leave=True, station_destination="Delhi").station_leave


def test_an_employee_without_a_unit_cannot_apply():
    h.person(300)
    with pytest.raises(ConflictError) as e:
        apply(300)
    assert e.value.code == "no_unit"


# -- substitute ----------------------------------------------------------------
def el_request(**over):
    return apply(category="EL", start_date=d("2026-03-09"), end_date=d("2026-03-13"),
                 substitute_user_id=h.SUBSTITUTE, **over)


def test_el_needs_a_substitute():
    with pytest.raises(RuleRefused) as e:
        apply(category="EL", start_date=d("2026-03-09"), end_date=d("2026-03-13"))
    assert e.value.code == "substitute_required"


def test_substitute_cannot_be_the_applicant_or_a_non_employee():
    with pytest.raises(RuleRefused) as e:
        apply(category="EL", start_date=d("2026-03-09"), end_date=d("2026-03-13"),
              substitute_user_id=h.STAFF)
    assert e.value.code == "substitute_is_applicant"
    h.person(500, kind="student")
    with pytest.raises(RuleRefused) as e:
        apply(category="EL", start_date=d("2026-03-09"), end_date=d("2026-03-13"),
              substitute_user_id=500)
    assert e.value.code == "substitute_not_employee"


def test_a_substitute_on_leave_is_unavailable():
    apply(h.SUBSTITUTE, category="CL", start_date=d("2026-03-10"),
          end_date=d("2026-03-10"))
    with pytest.raises(RuleRefused) as e:
        el_request()
    assert e.value.code == "substitute_unavailable"


def test_routing_waits_for_the_substitutes_consent():
    app = el_request()
    assert app.substitute_status == "pending"
    assert [t.role for t in app.tasks.filter(status="pending")] == ["substitute"]

    app = decide_next(app, actor(h.SUBSTITUTE), "accepted")
    assert app.substitute_status == "accepted"
    assert app.tasks.get(status="pending").role == "unit_head"


def test_a_declined_substitute_can_be_replaced_or_the_request_withdrawn():
    h.person(13)
    app = el_request()
    app = decide_next(app, actor(h.SUBSTITUTE), "declined")
    assert app.status == "pending" and app.substitute_status == "declined"
    assert "nominate_substitute" in scope.allowed_actions(app, d("2026-03-02"))
    assert not app.tasks.filter(status="pending").exists()

    app = workflow.renominate_substitute(actor=actor(h.STAFF), application_id=app.pk,
                                         substitute_user_id=13)
    assert app.tasks.get(status="pending").assignee_user_id == 13


def test_only_the_named_substitute_can_answer():
    app = el_request()
    with pytest.raises(PermissionDeniedError):
        workflow.decide(actor=actor(h.HEAD, h.HOD), task_id=app.tasks.get().pk,
                        outcome="accepted")


# -- higher sanction -----------------------------------------------------------
def el_through_to_final(app):
    app = decide_next(app, actor(h.SUBSTITUTE), "accepted")
    app = decide_next(app, HOD, "not_recommended", "Busy period")
    assert app.recommendation == "not_recommended"
    assert app.status == "pending"                  # not a final rejection (BR-EL-017)
    app = decide_next(app, ESTT, "forwarded")
    assert app.status == "pending"
    return app


def test_el_goes_unit_head_then_establishment_then_registrar():
    app = el_through_to_final(el_request())
    task = app.tasks.get(status="pending")
    assert task.role == "registrar" and task.assignee_user_id is None
    assert scope.tasks_for(REG).filter(pk=task.pk).exists()
    assert not scope.tasks_for(DEAN).filter(pk=task.pk).exists()

    app = decide_next(app, REG, "approved")
    assert app.status == "approved"
    balances.ensure_credited(h.STAFF, 2026)
    assert balance(h.STAFF, "EL") == 25


def test_a_step_outside_the_right_role_is_refused():
    app = el_request()
    app = decide_next(app, actor(h.SUBSTITUTE), "accepted")
    app = decide_next(app, HOD, "recommended")
    with pytest.raises(PermissionDeniedError):
        workflow.decide(actor=REG, task_id=app.tasks.get(status="pending").pk,
                        outcome="forwarded")


def test_forward_steps_cannot_approve_or_reject():
    app = decide_next(el_request(), actor(h.SUBSTITUTE), "accepted")
    app = decide_next(app, HOD, "recommended")
    with pytest.raises(RuleRefused) as e:
        decide_next(app, ESTT, "approved")
    assert e.value.code == "invalid_outcome"


def test_hierarchy_configuration_changes_the_path_for_new_requests():
    HierarchyRule.objects.create(applicant_group="staff", steps=["unit_head", "director"])
    app = decide_next(el_request(), actor(h.SUBSTITUTE), "accepted")
    assert [s["role"] for s in app.route] == ["unit_head", "director"]


def test_the_director_sanctions_their_own_leave_without_routing():
    from modules.elm.models import OrgUnit, UnitMember

    UnitMember.objects.create(user_id=h.DIR_ID, unit=OrgUnit.objects.get())
    app = applications.apply(actor=DIRECTOR, data={
        "category": "SCL", "start_date": d("2026-03-09"), "end_date": d("2026-03-09"),
        "reason": "Conference"})
    assert app.status == "approved" and app.route == []
    assert not app.tasks.exists()


# -- withdrawal ----------------------------------------------------------------
def test_withdrawal_ends_all_remaining_processing():
    app = apply()
    task = app.tasks.get()
    app = workflow.withdraw(actor=actor(h.STAFF), application_id=app.pk)
    assert app.status == "withdrawn"
    task.refresh_from_db()
    assert task.status == "cancelled"
    assert Notification.objects.filter(recipient_user_id=h.HEAD, topic="withdrawn")
    with pytest.raises(NotFoundError):
        workflow.decide(actor=HOD, task_id=999999, outcome="approved")
    with pytest.raises(ConflictError):
        workflow.decide(actor=HOD, task_id=task.pk, outcome="approved")


def test_approved_leave_cannot_be_withdrawn():
    app = decide_next(apply(), HOD, "approved")
    with pytest.raises(ConflictError) as e:
        workflow.withdraw(actor=actor(h.STAFF), application_id=app.pk)
    assert e.value.code == "not_withdrawable"


def test_someone_elses_request_is_not_found():
    app = apply()
    with pytest.raises(NotFoundError):
        workflow.withdraw(actor=actor(h.FACULTY, kind="faculty"), application_id=app.pk)


# -- cancellation --------------------------------------------------------------
def approved_cl():
    return decide_next(apply(), HOD, "approved")


def test_cancellation_follows_the_same_hierarchy_and_restores_the_balance():
    app = approved_cl()
    cancel = applications.request_cancellation(
        actor=actor(h.STAFF), application_id=app.pk, reason="Plans changed")
    assert cancel.kind == "cancellation" and cancel.tasks.get().role == "unit_head"
    decide_next(cancel, HOD, "approved")
    app.refresh_from_db()
    assert app.status == "cancelled"
    assert balance(h.STAFF, "CL") == 8


def test_a_rejected_cancellation_leaves_the_leave_untouched():
    app = approved_cl()
    cancel = applications.request_cancellation(
        actor=actor(h.STAFF), application_id=app.pk, reason="Plans changed")
    decide_next(cancel, HOD, "rejected", "Needed")
    app.refresh_from_db()
    assert app.status == "approved" and balance(h.STAFF, "CL") == 7
    assert "cancel" in scope.allowed_actions(
        LeaveApplication.objects.prefetch_related("children", "resumptions").get(pk=app.pk),
        d("2026-03-02"))


def test_leave_that_has_begun_cannot_be_cancelled():
    app = approved_cl()
    with freeze_time("2026-03-09"), pytest.raises(ConflictError) as e:
        applications.request_cancellation(actor=actor(h.STAFF),
                                          application_id=app.pk, reason="x")
    assert e.value.code == "already_started"


def test_only_one_cancellation_may_be_pending():
    app = approved_cl()
    applications.request_cancellation(actor=actor(h.STAFF), application_id=app.pk,
                                      reason="a")
    with pytest.raises(ConflictError):
        applications.request_cancellation(actor=actor(h.STAFF),
                                          application_id=app.pk, reason="b")


# -- extension and resumption --------------------------------------------------
def approved_el():
    app = el_through_to_final(el_request())
    return decide_next(app, REG, "approved")


def test_an_approved_extension_posts_only_the_extra_days():
    app = approved_el()
    with freeze_time("2026-03-11"):
        ext = applications.request_extension(
            actor=actor(h.STAFF), application_id=app.pk, new_end_date=d("2026-03-16"),
            reason="Recovery", substitute_user_id=h.SUBSTITUTE)
        assert (ext.start_date, ext.days) == (d("2026-03-14"), 3)
        ext = decide_next(ext, actor(h.SUBSTITUTE), "accepted")
        ext = decide_next(ext, HOD, "recommended")
        ext = decide_next(ext, ESTT, "forwarded")
        ext = decide_next(ext, REG, "approved")
    app.refresh_from_db()
    assert app.end_date == d("2026-03-13")              # the base is never edited
    assert balance(h.STAFF, "EL") == 22                  # 30 - 5 - 3


def test_only_ongoing_el_col_vl_can_be_extended():
    app = approved_el()
    with pytest.raises(ConflictError) as e:
        applications.request_extension(actor=actor(h.STAFF), application_id=app.pk,
                                       new_end_date=d("2026-03-16"), reason="x",
                                       substitute_user_id=h.SUBSTITUTE)
    assert e.value.code == "not_ongoing"
    cl = decide_next(apply(start_date=d("2026-03-23"), end_date=d("2026-03-23")),
                     HOD, "approved")
    with freeze_time("2026-03-23"), pytest.raises(ConflictError) as e:
        applications.request_extension(actor=actor(h.STAFF), application_id=cl.pk,
                                       new_end_date=d("2026-03-24"), reason="x")
    assert e.value.code == "not_extendable"


def submit_resumption(app, on, today):
    with freeze_time(today):
        r = resumption_service.submit(actor=actor(h.STAFF), application_id=app.pk,
                                      actual_date=d(on), details="Back")
        task = r.tasks.get()
        workflow.decide(actor=REG, task_id=task.pk, outcome="approved")
    return r


def test_resuming_on_the_approved_end_date_adjusts_nothing():
    app = approved_el()
    r = submit_resumption(app, "2026-03-13", "2026-03-13")
    assert r.adjustment_days == 0 and balance(h.STAFF, "EL") == 25


def test_early_resumption_restores_the_unused_days():
    app = approved_el()
    r = submit_resumption(app, "2026-03-11", "2026-03-11")
    assert r.adjustment_days == 2 and balance(h.STAFF, "EL") == 27
    app.refresh_from_db()
    assert app.actual_resumption_date == d("2026-03-11")


def test_late_resumption_deducts_the_extra_days():
    app = approved_el()
    r = submit_resumption(app, "2026-03-16", "2026-03-16")
    assert r.adjustment_days == -3 and balance(h.STAFF, "EL") == 22


def test_resumption_is_reviewed_by_the_sanctioning_authority_only():
    app = approved_el()
    with freeze_time("2026-03-13"):
        r = resumption_service.submit(actor=actor(h.STAFF), application_id=app.pk,
                                      actual_date=d("2026-03-13"))
        task = r.tasks.get()
        with pytest.raises(PermissionDeniedError):
            workflow.decide(actor=ESTT, task_id=task.pk, outcome="approved")
        with pytest.raises(ConflictError):
            resumption_service.submit(actor=actor(h.STAFF), application_id=app.pk,
                                      actual_date=d("2026-03-13"))


def test_cl_has_no_resumption():
    app = approved_cl()
    with freeze_time("2026-03-09"), pytest.raises(ConflictError) as e:
        resumption_service.submit(actor=actor(h.STAFF), application_id=app.pk,
                                  actual_date=d("2026-03-09"))
    assert e.value.code == "not_resumable"


# -- administrative records ----------------------------------------------------
def offline(**over):
    data = {"employee_user_id": h.STAFF, "category": "CL",
            "start_date": d("2026-02-23"), "end_date": d("2026-02-24"),
            "half_day": "", "reason": "Illness", "offline_reference": "F-12/2026",
            "offline_reason": "Server down", "sanction_date": d("2026-02-20"), **over}
    return records.record_offline(actor=actor(h.ADMIN_ID, h.ADMIN), data=data)


def test_offline_leave_is_recorded_without_any_approval_workflow():
    app = offline()
    assert app.status == "approved" and app.entry_channel == "offline"
    assert not app.tasks.exists()
    assert balance(h.STAFF, "CL") == 6


def test_offline_entry_is_validated_for_consistency():
    with pytest.raises(RuleRefused) as e:
        offline(offline_reference=" ")
    assert e.value.code == "reference_required"
    with pytest.raises(RuleRefused) as e:
        offline(sanction_date=d("2026-03-20"))
    assert e.value.code == "invalid_period"
    offline()
    with pytest.raises(RuleRefused) as e:
        offline(start_date=d("2026-02-24"), end_date=d("2026-02-24"))
    assert e.value.code == "overlap"


def test_a_balance_adjustment_needs_a_reason_and_lands_in_the_ledger():
    admin = actor(h.ADMIN_ID, h.ADMIN)
    balances.ensure_credited(h.STAFF, 2026)
    with pytest.raises(RuleRefused):
        records.adjust_balance(actor=admin, user_id=h.STAFF, category="CL",
                               year=2026, days=Decimal(1), note=" ")
    records.adjust_balance(actor=admin, user_id=h.STAFF, category="CL", year=2026,
                           days=Decimal("-2"), note="Audit correction")
    assert balance(h.STAFF, "CL") == 6


# -- year-end ------------------------------------------------------------------
def test_year_end_lapses_converts_and_carries_and_is_idempotent():
    balances.ensure_credited(h.STAFF, 2026)
    balances.ensure_credited(h.FACULTY, 2026)
    balances.post(user_id=h.FACULTY, category="VL", year=2026, entry_type="debit",
                  days=Decimal("-49"))                        # 11 VL left

    report = yearend.run(2026)
    assert not report.exceptions

    assert balance(h.STAFF, "CL", 2026) == 0                  # lapsed
    assert balance(h.STAFF, "EL", 2027) == 30 + 30            # carried 30 + 2027 credit
    assert balance(h.FACULTY, "VL", 2026) == 0
    assert balance(h.FACULTY, "EL", 2027) == Decimal("5.5")   # 11 VL at 2:1
    assert balance(h.FACULTY, "COL", 2027) == 40

    before = LedgerEntry.objects.count()
    yearend.run(2026)
    assert LedgerEntry.objects.count() == before


# -- SLA -----------------------------------------------------------------------
def test_sla_reminds_and_escalates_only_tasks_still_pending():
    from datetime import timedelta

    from django.utils import timezone

    stuck, decided = apply(), apply(h.FACULTY, "faculty", start_date=d("2026-03-10"),
                                    end_date=d("2026-03-10"))
    decide_next(decided, HOD, "approved")

    later = timezone.now() + timedelta(hours=30)
    report = sla.process(later)
    assert (report.reminded, report.escalated) == (1, 0)
    assert Notification.objects.filter(topic="sla_reminder",
                                       recipient_user_id=h.HEAD).count() == 1
    assert sla.process(later).reminded == 0                    # not repeated

    report = sla.process(timezone.now() + timedelta(hours=80))
    assert report.escalated == 1
    stuck.refresh_from_db()
    assert ApprovalTask.objects.get(application=stuck, status="pending").escalated_at
    assert stuck.events.filter(event="sla_escalation").exists()


def test_a_withdrawn_task_gets_neither_reminder_nor_escalation():
    from datetime import timedelta

    from django.utils import timezone

    app = apply()
    workflow.withdraw(actor=actor(h.STAFF), application_id=app.pk)
    report = sla.process(timezone.now() + timedelta(hours=100))
    assert (report.reminded, report.escalated) == (0, 0)
