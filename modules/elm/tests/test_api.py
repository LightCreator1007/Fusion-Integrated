"""HTTP behaviour: the two gates, scoping, and the envelope."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time
from rest_framework.test import APIClient

from conftest import make_session
from modules.elm.models import LeaveApplication
from modules.elm.tests import helpers as h

pytestmark = pytest.mark.django_db

BASE = "/api/v1/elm"


@pytest.fixture(autouse=True)
def _frozen():
    with freeze_time("2026-03-02 09:00"):
        h.world()
        h.publish_calendar(closed=["2026-03-16"], restricted=["2026-03-04"])
        yield


@pytest.fixture
def as_user(stub_iam):
    def _as(uid, permissions=h.EMPLOYEE, modules=("elm_leave",), kind="staff"):
        stub_iam(make_session(user_id=uid, permissions=permissions, modules=modules,
                              kind=kind, roles=("employee",), active_role="employee"),
                 users=h.USERS)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Token abc")
        return c
    return _as


PAYLOAD = {"category": "CL", "start_date": "2026-03-09", "end_date": "2026-03-09",
           "reason": "Family"}


def test_the_module_grant_is_required(as_user):
    c = as_user(h.STAFF, modules=())
    assert c.get(f"{BASE}/applications").status_code == 403


def test_a_missing_permission_is_forbidden(as_user):
    c = as_user(h.STAFF, permissions=["elm_leave.leave.view_self"])
    assert c.post(f"{BASE}/applications", PAYLOAD, format="json").status_code == 403


def test_unauthenticated_callers_are_refused():
    assert APIClient().get(f"{BASE}/applications").status_code in (401, 403)


def test_apply_then_list_and_read_the_detail(as_user):
    c = as_user(h.STAFF)
    r = c.post(f"{BASE}/applications", PAYLOAD, format="json")
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["status"] == "pending" and body["awaiting"] == "unit_head"
    assert body["allowed_actions"] == ["withdraw"]

    rows = c.get(f"{BASE}/applications").json()["results"]
    assert [x["id"] for x in rows] == [body["id"]]

    detail = c.get(f"{BASE}/applications/{body['id']}").json()
    assert detail["route"] == [{"role": "unit_head", "mode": "final"}]
    assert [t["role"] for t in detail["tasks"]] == ["unit_head"]
    assert detail["events"][0]["event"] == "submitted"


def test_a_rule_violation_is_a_422_with_a_stable_code(as_user):
    c = as_user(h.STAFF)
    r = c.post(f"{BASE}/applications", {**PAYLOAD, "end_date": "2026-03-30"},
               format="json")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "insufficient_balance"


def test_a_malformed_body_is_a_validation_error(as_user):
    c = as_user(h.STAFF)
    r = c.post(f"{BASE}/applications", {"category": "ZZ"}, format="json")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"


def test_a_foreign_application_is_a_404_not_a_403(as_user):
    mine = as_user(h.STAFF).post(f"{BASE}/applications", PAYLOAD, format="json").json()
    other = as_user(h.FACULTY, kind="faculty")
    assert other.get(f"{BASE}/applications/{mine['id']}").status_code == 404
    assert other.post(f"{BASE}/applications/{mine['id']}/withdraw", {},
                      format="json").status_code == 404
    assert other.get(f"{BASE}/applications").json()["results"] == []


def test_withdraw_over_http(as_user):
    c = as_user(h.STAFF)
    app = c.post(f"{BASE}/applications", PAYLOAD, format="json").json()
    r = c.post(f"{BASE}/applications/{app['id']}/withdraw", {}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    again = c.post(f"{BASE}/applications/{app['id']}/withdraw", {}, format="json")
    assert again.status_code == 409


def test_the_unit_head_sees_and_decides_the_task(as_user):
    app = as_user(h.STAFF).post(f"{BASE}/applications", PAYLOAD, format="json").json()

    head = as_user(h.HEAD, h.HOD, kind="faculty")
    tasks = head.get(f"{BASE}/tasks").json()["results"]
    assert len(tasks) == 1
    assert tasks[0]["application"]["applicant_user_id"] == h.STAFF

    r = head.post(f"{BASE}/tasks/{tasks[0]['id']}/decide",
                  {"outcome": "approved"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert LeaveApplication.objects.get(pk=app["id"]).status == "approved"


def test_a_task_for_someone_else_is_invisible(as_user):
    as_user(h.STAFF).post(f"{BASE}/applications", PAYLOAD, format="json")
    task_id = LeaveApplication.objects.get().tasks.get().pk
    bystander = as_user(h.SUBSTITUTE)
    assert bystander.get(f"{BASE}/tasks").json()["results"] == []
    r = bystander.post(f"{BASE}/tasks/{task_id}/decide", {"outcome": "approved"},
                       format="json")
    assert r.status_code == 404


def test_an_employee_cannot_use_admin_endpoints(as_user):
    c = as_user(h.STAFF)
    assert c.get(f"{BASE}/records").status_code == 403
    assert c.post(f"{BASE}/year-end", {"year": 2026}, format="json").status_code == 403
    assert c.patch(f"{BASE}/policies/CL", {"annual_days": "99"},
                   format="json").status_code == 403
    assert c.post(f"{BASE}/calendars", {"year": 2027, "title": "x"},
                  format="json").status_code == 403


def test_the_balances_endpoint_lists_the_account(as_user):
    rows = as_user(h.STAFF).get(f"{BASE}/balances").json()
    by_cat = {r["category"]: r for r in rows}
    assert float(by_cat["CL"]["balance"]) == 8
    assert float(by_cat["EL"]["balance"]) == 30
    assert "VL" not in by_cat                       # faculty only


def test_admin_maintains_policy_and_the_current_value_applies(as_user):
    admin = as_user(h.ADMIN_ID, h.ADMIN)
    r = admin.patch(f"{BASE}/policies/CL", {"annual_days": "10"}, format="json")
    assert r.status_code == 200
    rows = as_user(h.FACULTY, kind="faculty").get(f"{BASE}/balances").json()
    assert float({x["category"]: x for x in rows}["CL"]["entitlement"]) == 10


def test_admin_builds_and_publishes_a_calendar(as_user):
    admin = as_user(h.ADMIN_ID, h.ADMIN)
    cal = admin.post(f"{BASE}/calendars", {"year": 2027, "title": "2027"},
                     format="json").json()
    assert admin.post(f"{BASE}/calendars/{cal['id']}/publish", {},
                      format="json").status_code == 422          # empty
    admin.post(f"{BASE}/calendars/{cal['id']}/holidays",
               {"date": "2027-01-26", "name": "Republic Day", "kind": "closed"},
               format="json")
    pub = admin.post(f"{BASE}/calendars/{cal['id']}/publish", {}, format="json")
    assert pub.status_code == 200 and pub.json()["status"] == "published"
    eff = as_user(h.STAFF).get(f"{BASE}/calendar?year=2027").json()
    assert [x["name"] for x in eff["holidays"]] == ["Republic Day"]


def test_admin_records_offline_leave_and_lists_all_records(as_user):
    admin = as_user(h.ADMIN_ID, h.ADMIN)
    r = admin.post(f"{BASE}/records/offline", {
        "employee_user_id": h.STAFF, "category": "CL", "start_date": "2026-02-23",
        "end_date": "2026-02-23", "reason": "Illness", "offline_reference": "F-1",
        "offline_reason": "Server down", "sanction_date": "2026-02-20"},
        format="json")
    assert r.status_code == 201, r.content
    rows = admin.get(f"{BASE}/records").json()["results"]
    assert rows[0]["entry_channel"] == "offline" and rows[0]["applicant_name"]
    assert admin.get(f"{BASE}/records/ledger?employee={h.STAFF}").status_code == 200


def test_year_end_endpoint_reports(as_user):
    r = as_user(h.ADMIN_ID, h.ADMIN).post(f"{BASE}/year-end", {"year": 2026},
                                          format="json")
    assert r.status_code == 200 and r.json()["year"] == 2026


def test_list_cost_does_not_grow_with_the_number_of_requests(as_user, stub_iam):
    c = as_user(h.STAFF)
    for day in (9, 10, 11, 12):
        LeaveApplication.objects.create(
            applicant_user_id=h.STAFF, category="CL", days=1, reason="x",
            start_date=f"2026-04-{day:02d}", end_date=f"2026-04-{day:02d}")
    c.get(f"{BASE}/applications")                  # warms the directory cache
    with CaptureQueriesContext(connection) as few:
        c.get(f"{BASE}/applications")
    for day in range(13, 23):
        LeaveApplication.objects.create(
            applicant_user_id=h.STAFF, category="CL", days=1, reason="x",
            start_date=f"2026-04-{day:02d}", end_date=f"2026-04-{day:02d}")
    with CaptureQueriesContext(connection) as many:
        c.get(f"{BASE}/applications")
    assert len(many) == len(few)
