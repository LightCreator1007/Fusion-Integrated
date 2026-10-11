"""What the server tells the shell about this module (ADR-0010).

Authority roles are matched by permission, not by designation name: a step in
the sanction path is open to whoever holds that role's `sanction`/`review`
permission, so the IAM decides who the Dean or Registrar currently is.
"""
MODULE = {
    "code": "elm_leave", "label": "Leave Management", "icon": "FaCalendarAlt",
    "base_path": "/elm", "nav_section": "Employee Services", "sort_order": 20,
    "status": "active",
}

NAV_ITEMS = [
    {"code": "elm.apply", "label": "Apply for Leave", "icon": "FaClipboardList",
     "to": "/elm/apply", "required_permission": "elm_leave.leave.apply",
     "sort_order": 10},
    {"code": "elm.mine", "label": "My Leave", "icon": "FaCalendarAlt",
     "to": "/elm/mine", "required_permission": "elm_leave.leave.view_self",
     "sort_order": 20},
    {"code": "elm.approvals", "label": "Approvals", "icon": "FaClipboardCheck",
     "to": "/elm/approvals", "required_permission": "elm_leave.task.view",
     "sort_order": 30},
    {"code": "elm.records", "label": "Leave Records", "icon": "FaFileSignature",
     "to": "/elm/records", "required_permission": "elm_leave.record.view",
     "sort_order": 50},
    {"code": "elm.calendar", "label": "Holiday Calendar", "icon": "FaCalendarAlt",
     "to": "/elm/calendar", "required_permission": "elm_leave.calendar.manage",
     "sort_order": 60},
    {"code": "elm.policy", "label": "Policy & Hierarchy", "icon": "FaCog",
     "to": "/elm/policy", "required_permission": "elm_leave.policy.manage",
     "sort_order": 70},
]

#: Every permission this module recognises; ROLE_GRANTS below says who holds each.
PERMISSIONS = [
    ("elm_leave.leave.apply", "Apply for leave and request an extension"),
    ("elm_leave.leave.view_self", "See one's own leave, balances and history"),
    ("elm_leave.leave.withdraw", "Withdraw a pending request"),
    ("elm_leave.leave.cancel", "Request cancellation of approved leave"),
    ("elm_leave.leave.resume", "Submit a resumption of duty"),
    ("elm_leave.task.view", "See tasks addressed to you (substitute, review)"),
    ("elm_leave.review.unit_head",
     "Review requests for one's own unit as Unit Head"),
    ("elm_leave.review.establishment",
     "Verify and route higher-sanction requests (Establishment)"),
    ("elm_leave.sanction.dean", "Sanction leave as Dean"),
    ("elm_leave.sanction.registrar", "Sanction leave as Registrar"),
    ("elm_leave.sanction.director", "Sanction leave as Director"),
    ("elm_leave.record.view", "See every employee's leave records"),
    ("elm_leave.record.manage",
     "Record offline-sanctioned leave and correct balances"),
    ("elm_leave.policy.manage",
     "Maintain leave policy, hierarchy and SLA configuration"),
    ("elm_leave.calendar.manage",
     "Maintain and publish the holiday calendar and vacation periods"),
    ("elm_leave.yearend.run", "Run year-end leave processing"),
]

#: Performed by a service or a scheduled task, so no designation holds them.
SYSTEM_PERMISSIONS: list[str] = []

_EMPLOYEE = [
    "elm_leave.leave.apply",
    "elm_leave.leave.view_self",
    "elm_leave.leave.withdraw",
    "elm_leave.leave.cancel",
    "elm_leave.leave.resume",
    "elm_leave.task.view",
]

_ADMIN = [
    *_EMPLOYEE,
    "elm_leave.record.view",
    "elm_leave.record.manage",
    "elm_leave.policy.manage",
    "elm_leave.calendar.manage",
    "elm_leave.yearend.run",
]

#: Keyed by the designation name as it exists in globals_designation.
ROLE_GRANTS = {
    "faculty": _EMPLOYEE,
    "staff": _EMPLOYEE,
    "hod": [*_EMPLOYEE, "elm_leave.review.unit_head"],
    "Deputy Registrar": [*_EMPLOYEE, "elm_leave.review.establishment"],
    "Dean Academic": [*_EMPLOYEE, "elm_leave.sanction.dean"],
    "Registrar": [*_EMPLOYEE, "elm_leave.sanction.registrar"],
    "Director": [*_EMPLOYEE, "elm_leave.sanction.director"],
    "leave_admin": _ADMIN,
}
