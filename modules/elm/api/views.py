"""HTTP layer: parse, scope, delegate, serialise.

Reads start from `selectors.leave`, so ownership is the queryset and a foreign
id is a 404. Writes go through `services/`, which raise domain errors that the
platform handler turns into the standard envelope.
"""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.exceptions import BadRequestError, NotFoundError
from fusion_auth.permissions import HasModuleGrant, HasPermission
from modules.directory import contracts as directory
from modules.elm.api import serializers as s
from modules.elm.models import (
    ApprovalTask,
    HierarchyRule,
    Holiday,
    HolidayCalendar,
    LeaveApplication,
    LeavePolicy,
    LedgerEntry,
    Notification,
    OrgUnit,
    UnitMember,
    VacationPeriod,
)
from modules.elm.selectors import leave as scope
from modules.elm.services import applications, balances, facts, records, sla, workflow
from modules.elm.services import config as config_service
from modules.elm.services import resumption as resumption_service
from modules.elm.services import yearend as yearend_service

MODULE = HasModuleGrant("elm_leave")

P_APPLY = "elm_leave.leave.apply"
P_VIEW_SELF = "elm_leave.leave.view_self"
P_WITHDRAW = "elm_leave.leave.withdraw"
P_CANCEL = "elm_leave.leave.cancel"
P_RESUME = "elm_leave.leave.resume"
P_TASKS = "elm_leave.task.view"
P_RECORD_VIEW = "elm_leave.record.view"
P_RECORD_MANAGE = "elm_leave.record.manage"
P_POLICY = "elm_leave.policy.manage"
P_CALENDAR = "elm_leave.calendar.manage"
P_YEAR_END = "elm_leave.yearend.run"


def _actor(request):
    return request.principal


def _int_param(params, name):
    raw = params.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise BadRequestError(f"{name} must be a number.",
                              code="invalid_filter") from exc


def _context(request, objs=()):
    """One batched directory call per page for every name shown."""
    ids = set()
    for o in objs:
        ids.add(getattr(o, "applicant_user_id", None))
        ids.add(getattr(o, "substitute_user_id", None))
    ids.discard(None)
    return {"names": facts.names(ids) if ids else {},
            "viewer_id": _actor(request).user_id, "today": timezone.localdate()}


def _ser_app(request, app, detail=False):
    cls = s.LeaveApplicationDetailSerializer if detail else s.LeaveApplicationSerializer
    return cls(app, context=_context(request, [app])).data


# -- balances and calendar -------------------------------------------------------
class BalancesView(APIView):
    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]

    @extend_schema(
        parameters=[OpenApiParameter("year", int, required=False)],
        responses=s.BalanceSerializer(many=True))
    def get(self, request):
        year = _int_param(request.query_params, "year") or timezone.localdate().year
        rows = balances.statement(_actor(request).user_id, year)
        out = [{**b.__dict__, "available": b.available} for b in rows]
        return Response(s.BalanceSerializer(out, many=True).data)


class EffectiveCalendarView(APIView):
    """What the apply form checks dates against: the published calendar."""

    permission_classes = [MODULE, HasPermission(P_APPLY, P_CALENDAR)]

    @extend_schema(parameters=[OpenApiParameter("year", int, required=False)],
                   responses=s.HolidayCalendarSerializer)
    def get(self, request):
        year = _int_param(request.query_params, "year") or timezone.localdate().year
        calendar = facts.effective_calendar(year)
        body = (s.HolidayCalendarSerializer(calendar).data if calendar else
                {"id": None, "year": year, "title": "", "status": "none",
                 "published_at": None, "holidays": []})
        return Response({
            **body,
            "vacation_periods": s.VacationPeriodSerializer(
                VacationPeriod.objects.order_by("start_date"), many=True).data,
        })


class ColleagueSearchView(APIView):
    """Substitute picker. Employees only, and never fewer than two characters."""

    permission_classes = [MODULE, HasPermission(P_APPLY)]

    @extend_schema(parameters=[OpenApiParameter("q", str, required=True)],
                   responses=s.ColleagueSerializer(many=True))
    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response([])
        me = _actor(request).user_id
        found = {}
        for kind in facts.EMPLOYEE_KINDS:
            for u in directory.search(q=q, kind=kind, limit=10):
                if u.user_id != me:
                    found[u.user_id] = {"user_id": u.user_id,
                                        "display_name": u.display_name,
                                        "department": u.department}
        return Response(s.ColleagueSerializer(list(found.values()), many=True).data)


# -- the employee's own requests ---------------------------------------------------
class ApplicationListCreateView(generics.ListCreateAPIView):
    serializer_class = s.LeaveApplicationSerializer
    queryset = LeaveApplication.objects.none()      # real scope: get_queryset

    def get_permissions(self):
        code = P_APPLY if self.request.method == "POST" else P_VIEW_SELF
        return [MODULE(), HasPermission(code)()]

    def get_queryset(self):
        qs = (scope.own_applications(_actor(self.request))
              .prefetch_related("children", "resumptions"))
        state = self.request.query_params.get("status")
        return qs.filter(status=state) if state else qs

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        ser = self.get_serializer(page, many=True, context={
            **self.get_serializer_context(), **_context(request, page)})
        return self.get_paginated_response(ser.data)

    @extend_schema(request=s.LeaveRequestSerializer, responses={201: s.LeaveApplicationSerializer})
    def post(self, request, *args, **kwargs):
        payload = s.LeaveRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        app = applications.apply(actor=_actor(request), data=payload.validated_data)
        return Response(_ser_app(request, app), status=status.HTTP_201_CREATED)


class ApplicationDetailView(generics.RetrieveAPIView):
    permission_classes = [MODULE, HasPermission(P_VIEW_SELF, P_TASKS, P_RECORD_VIEW)]
    serializer_class = s.LeaveApplicationDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        app = scope.readable_application(_actor(request), kwargs["pk"])
        if app is None:
            raise NotFoundError("No such leave request.")
        app = (LeaveApplication.objects
               .prefetch_related("children", "resumptions", "tasks", "events")
               .get(pk=app.pk))
        return Response(_ser_app(request, app, detail=True))


class _ActionView(generics.GenericAPIView):
    """POST /applications/<pk>/<action>: validate the body, call one service."""

    permission_code = ""
    request_serializer = None

    def get_permissions(self):
        return [MODULE(), HasPermission(self.permission_code)()]

    def get_serializer_class(self):
        return self.request_serializer

    def act(self, actor, pk, data):
        raise NotImplementedError

    @extend_schema(responses=s.LeaveApplicationSerializer)
    def post(self, request, pk):
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        app = self.act(_actor(request), pk, payload.validated_data)
        return Response(_ser_app(request, app))


class WithdrawView(_ActionView):
    permission_code = P_WITHDRAW

    class _Empty(s.serializers.Serializer):
        pass

    request_serializer = _Empty

    def act(self, actor, pk, data):
        return workflow.withdraw(actor=actor, application_id=pk)


class CancelView(_ActionView):
    permission_code = P_CANCEL
    request_serializer = s.CancelSerializer

    def act(self, actor, pk, data):
        return applications.request_cancellation(
            actor=actor, application_id=pk, reason=data["reason"])


class ExtendView(_ActionView):
    permission_code = P_APPLY
    request_serializer = s.ExtendSerializer

    def act(self, actor, pk, data):
        return applications.request_extension(
            actor=actor, application_id=pk, new_end_date=data["new_end_date"],
            reason=data["reason"], substitute_user_id=data["substitute_user_id"])


class NominateSubstituteView(_ActionView):
    permission_code = P_APPLY
    request_serializer = s.NominateSerializer

    def act(self, actor, pk, data):
        return workflow.renominate_substitute(
            actor=actor, application_id=pk,
            substitute_user_id=data["substitute_user_id"])


class ResumeView(_ActionView):
    permission_code = P_RESUME
    request_serializer = s.ResumeSerializer

    def act(self, actor, pk, data):
        resumption_service.submit(
            actor=actor, application_id=pk,
            actual_date=data["actual_resumption_date"], details=data["details"])
        return scope.own_applications(actor).prefetch_related(
            "children", "resumptions").get(pk=pk)


# -- tasks ---------------------------------------------------------------------
class TaskListView(generics.ListAPIView):
    permission_classes = [MODULE, HasPermission(P_TASKS)]
    serializer_class = s.TaskSerializer
    queryset = ApprovalTask.objects.none()

    def get_queryset(self):
        return scope.tasks_for(_actor(self.request)).order_by("created_at")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        ctx = _context(request, [t.application for t in page])
        ser = self.get_serializer(page, many=True, context={
            **self.get_serializer_context(), **ctx})
        return self.get_paginated_response(ser.data)


class TaskDecideView(generics.GenericAPIView):
    permission_classes = [MODULE, HasPermission(P_TASKS)]
    serializer_class = s.DecideSerializer

    @extend_schema(responses=s.LeaveApplicationSerializer)
    def post(self, request, pk):
        actor = _actor(request)
        task = scope.tasks_for(actor).filter(pk=pk).first()
        if task is None:
            raise NotFoundError("No such task.")
        payload = s.DecideSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        app = workflow.decide(actor=actor, task_id=pk,
                              outcome=payload.validated_data["outcome"],
                              remark=payload.validated_data["remark"])
        return Response(_ser_app(request, app))


class NotificationListView(generics.ListAPIView):
    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]
    serializer_class = s.NotificationSerializer
    queryset = Notification.objects.none()

    def get_queryset(self):
        from django.db.models import Q

        actor = _actor(self.request)
        q = Q(recipient_user_id=actor.user_id)
        roles = scope.roles_held(actor)
        if roles:
            q |= Q(recipient_user_id__isnull=True, recipient_role__in=roles)
        return Notification.objects.filter(q)


class NotificationReadView(generics.GenericAPIView):
    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]
    serializer_class = s.NotificationSerializer

    @extend_schema(request=None, responses=s.NotificationSerializer)
    def post(self, request, pk):
        note = Notification.objects.filter(
            pk=pk, recipient_user_id=_actor(request).user_id).first()
        if note is None:
            raise NotFoundError("No such notification.")
        if note.read_at is None:
            note.read_at = timezone.now()
            note.save(update_fields=["read_at"])
        return Response(s.NotificationSerializer(note).data)


# -- records (administration) ------------------------------------------------------
class RecordListView(generics.ListAPIView):
    permission_classes = [MODULE, HasPermission(P_RECORD_VIEW)]
    serializer_class = s.LeaveApplicationSerializer
    queryset = LeaveApplication.objects.none()

    def get_queryset(self):
        params = self.request.query_params
        qs = scope.applications_for(_actor(self.request)).prefetch_related(
            "children", "resumptions")
        for field, column in (("status", "status"), ("category", "category")):
            if params.get(field):
                qs = qs.filter(**{column: params[field]})
        employee = _int_param(params, "employee")
        if employee:
            qs = qs.filter(applicant_user_id=employee)
        return qs

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        ser = self.get_serializer(page, many=True, context={
            **self.get_serializer_context(), **_context(request, page)})
        return self.get_paginated_response(ser.data)


class OfflineRecordView(generics.GenericAPIView):
    permission_classes = [MODULE, HasPermission(P_RECORD_MANAGE)]
    serializer_class = s.OfflineRecordSerializer

    @extend_schema(responses={201: s.LeaveApplicationSerializer})
    def post(self, request):
        payload = s.OfflineRecordSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        app = records.record_offline(actor=_actor(request), data=payload.validated_data)
        return Response(_ser_app(request, app), status=status.HTTP_201_CREATED)


class AdjustmentView(generics.GenericAPIView):
    permission_classes = [MODULE, HasPermission(P_RECORD_MANAGE)]
    serializer_class = s.AdjustmentSerializer

    @extend_schema(responses={204: None})
    def post(self, request):
        payload = s.AdjustmentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        d = payload.validated_data
        records.adjust_balance(actor=_actor(request), user_id=d["employee_user_id"],
                               category=d["category"], year=d["year"],
                               days=d["days"], note=d["note"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class LedgerView(generics.ListAPIView):
    permission_classes = [MODULE, HasPermission(P_RECORD_VIEW)]
    serializer_class = s.LedgerEntrySerializer
    queryset = LedgerEntry.objects.none()

    def get_queryset(self):
        employee = _int_param(self.request.query_params, "employee")
        if not employee:
            raise BadRequestError("employee is required.", code="invalid_filter")
        return LedgerEntry.objects.filter(user_id=employee).order_by("-id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        data = [{"id": e.id, "category": e.category, "year": e.year,
                 "entry_type": e.entry_type, "days": e.days, "note": e.note,
                 "application_id": e.application_id, "created_at": e.created_at}
                for e in page]
        return self.get_paginated_response(s.LedgerEntrySerializer(data, many=True).data)


class YearEndView(generics.GenericAPIView):
    permission_classes = [MODULE, HasPermission(P_YEAR_END)]
    serializer_class = s.YearEndRequestSerializer

    @extend_schema(responses=s.YearEndReportSerializer)
    def post(self, request):
        payload = s.YearEndRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        report = yearend_service.run(payload.validated_data["year"])
        return Response(s.YearEndReportSerializer(report.__dict__).data)


class SlaRunView(generics.GenericAPIView):
    """Operators may trigger the same pass the scheduler runs."""

    permission_classes = [MODULE, HasPermission(P_POLICY)]
    serializer_class = s.YearEndReportSerializer

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        report = sla.process()
        return Response({"reminded": report.reminded, "escalated": report.escalated})


# -- configuration ---------------------------------------------------------------
class _Config(generics.GenericAPIView):
    pagination_class = None
    permission_code = P_POLICY

    def get_permissions(self):
        if self.request.method == "GET" and getattr(self, "read_codes", None):
            return [MODULE(), HasPermission(*self.read_codes)()]
        return [MODULE(), HasPermission(self.permission_code)()]


class PolicyListView(_Config, generics.ListAPIView):
    serializer_class = s.LeavePolicySerializer
    read_codes = (P_POLICY, P_APPLY)

    def get_queryset(self):
        return LeavePolicy.objects.order_by("id")


class PolicyDetailView(_Config, generics.UpdateAPIView):
    serializer_class = s.LeavePolicySerializer
    lookup_field = "category"
    http_method_names = ["patch", "options"]

    def get_queryset(self):
        return LeavePolicy.objects.all()


class HierarchyRuleListView(_Config, generics.ListCreateAPIView):
    serializer_class = s.HierarchyRuleSerializer

    def get_queryset(self):
        return HierarchyRule.objects.order_by("applicant_group", "category")


class HierarchyRuleDetailView(_Config, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = s.HierarchyRuleSerializer
    http_method_names = ["get", "patch", "delete", "options"]

    def get_queryset(self):
        return HierarchyRule.objects.all()


class OrgUnitListView(_Config, generics.ListCreateAPIView):
    serializer_class = s.OrgUnitSerializer

    def get_queryset(self):
        return OrgUnit.objects.order_by("name")


class OrgUnitDetailView(_Config, generics.RetrieveUpdateAPIView):
    serializer_class = s.OrgUnitSerializer
    http_method_names = ["get", "patch", "options"]

    def get_queryset(self):
        return OrgUnit.objects.all()


class UnitMemberListView(_Config, generics.ListAPIView):
    serializer_class = s.UnitMemberSerializer

    def get_queryset(self):
        qs = UnitMember.objects.order_by("unit_id", "user_id")
        unit = _int_param(self.request.query_params, "unit")
        return qs.filter(unit_id=unit) if unit else qs

    @extend_schema(request=s.UnitMemberSerializer, responses=s.UnitMemberSerializer,
                   methods=["POST"])
    def post(self, request):
        payload = s.UnitMemberSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        d = payload.validated_data
        member = config_service.place_member(
            user_id=d["user_id"], unit=d["unit"], designation=d.get("designation", ""))
        return Response(s.UnitMemberSerializer(member).data,
                        status=status.HTTP_201_CREATED)


class UnitMemberDetailView(_Config, generics.DestroyAPIView):
    serializer_class = s.UnitMemberSerializer

    def get_queryset(self):
        return UnitMember.objects.all()


class SlaSettingView(_Config, generics.RetrieveUpdateAPIView):
    serializer_class = s.SlaSettingSerializer
    http_method_names = ["get", "put", "patch", "options"]

    def get_object(self):
        return sla.settings()


# -- calendar ------------------------------------------------------------------
class _CalendarConfig(_Config):
    permission_code = P_CALENDAR


class CalendarListView(_CalendarConfig, generics.ListCreateAPIView):
    serializer_class = s.HolidayCalendarSerializer

    def get_queryset(self):
        return HolidayCalendar.objects.prefetch_related("holidays").order_by(
            "-year", "-id")


class HolidayCreateView(_CalendarConfig, generics.CreateAPIView):
    serializer_class = s.HolidaySerializer

    def perform_create(self, serializer):
        calendar = HolidayCalendar.objects.filter(pk=self.kwargs["pk"]).first()
        if calendar is None:
            raise NotFoundError("No such calendar.")
        serializer.save(calendar=calendar)


class HolidayDetailView(_CalendarConfig, generics.DestroyAPIView):
    serializer_class = s.HolidaySerializer

    def get_queryset(self):
        return Holiday.objects.all()


class CalendarPublishView(_CalendarConfig):
    serializer_class = s.HolidayCalendarSerializer

    @extend_schema(request=None, responses=s.HolidayCalendarSerializer)
    def post(self, request, pk):
        calendar = config_service.publish_calendar(actor=_actor(request), calendar_id=pk)
        return Response(s.HolidayCalendarSerializer(calendar).data)


class VacationPeriodListView(_CalendarConfig, generics.ListCreateAPIView):
    serializer_class = s.VacationPeriodSerializer

    def get_queryset(self):
        return VacationPeriod.objects.order_by("start_date")


class VacationPeriodDetailView(_CalendarConfig, generics.DestroyAPIView):
    serializer_class = s.VacationPeriodSerializer

    def get_queryset(self):
        return VacationPeriod.objects.all()
