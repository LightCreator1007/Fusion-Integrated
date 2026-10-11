from django.urls import path

from modules.elm.api import views as v

urlpatterns = [
    # the employee
    path("balances", v.BalancesView.as_view(), name="elm-balances"),
    path("calendar", v.EffectiveCalendarView.as_view(), name="elm-calendar"),
    path("colleagues", v.ColleagueSearchView.as_view(), name="elm-colleagues"),
    path("applications", v.ApplicationListCreateView.as_view(),
         name="elm-applications"),
    path("applications/<int:pk>", v.ApplicationDetailView.as_view(),
         name="elm-application"),
    path("applications/<int:pk>/withdraw", v.WithdrawView.as_view(),
         name="elm-application-withdraw"),
    path("applications/<int:pk>/cancel", v.CancelView.as_view(),
         name="elm-application-cancel"),
    path("applications/<int:pk>/extend", v.ExtendView.as_view(),
         name="elm-application-extend"),
    path("applications/<int:pk>/substitute", v.NominateSubstituteView.as_view(),
         name="elm-application-substitute"),
    path("applications/<int:pk>/resume", v.ResumeView.as_view(),
         name="elm-application-resume"),

    # tasks and notices
    path("tasks", v.TaskListView.as_view(), name="elm-tasks"),
    path("tasks/<int:pk>/decide", v.TaskDecideView.as_view(), name="elm-task-decide"),
    path("notifications", v.NotificationListView.as_view(), name="elm-notifications"),
    path("notifications/<int:pk>/read", v.NotificationReadView.as_view(),
         name="elm-notification-read"),

    # records
    path("records", v.RecordListView.as_view(), name="elm-records"),
    path("records/offline", v.OfflineRecordView.as_view(), name="elm-records-offline"),
    path("records/adjustments", v.AdjustmentView.as_view(), name="elm-adjustments"),
    path("records/ledger", v.LedgerView.as_view(), name="elm-ledger"),
    path("year-end", v.YearEndView.as_view(), name="elm-year-end"),

    # configuration
    path("policies", v.PolicyListView.as_view(), name="elm-policies"),
    path("policies/<str:category>", v.PolicyDetailView.as_view(), name="elm-policy"),
    path("hierarchy-rules", v.HierarchyRuleListView.as_view(),
         name="elm-hierarchy-rules"),
    path("hierarchy-rules/<int:pk>", v.HierarchyRuleDetailView.as_view(),
         name="elm-hierarchy-rule"),
    path("units", v.OrgUnitListView.as_view(), name="elm-units"),
    path("units/<int:pk>", v.OrgUnitDetailView.as_view(), name="elm-unit"),
    path("unit-members", v.UnitMemberListView.as_view(), name="elm-unit-members"),
    path("unit-members/<int:pk>", v.UnitMemberDetailView.as_view(),
         name="elm-unit-member"),
    path("sla", v.SlaSettingView.as_view(), name="elm-sla"),
    path("sla/run", v.SlaRunView.as_view(), name="elm-sla-run"),

    # calendar
    path("calendars", v.CalendarListView.as_view(), name="elm-calendars"),
    path("calendars/<int:pk>/holidays", v.HolidayCreateView.as_view(),
         name="elm-calendar-holidays"),
    path("calendars/<int:pk>/publish", v.CalendarPublishView.as_view(),
         name="elm-calendar-publish"),
    path("holidays/<int:pk>", v.HolidayDetailView.as_view(), name="elm-holiday"),
    path("vacation-periods", v.VacationPeriodListView.as_view(),
         name="elm-vacation-periods"),
    path("vacation-periods/<int:pk>", v.VacationPeriodDetailView.as_view(),
         name="elm-vacation-period"),
]
