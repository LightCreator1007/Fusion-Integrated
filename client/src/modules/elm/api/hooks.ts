/** Data access for the ELM module.
 *
 *  Every mutation invalidates the whole module key. These pages are small, and
 *  a stale "Withdraw" button on a request that was just decided is worse than
 *  one extra fetch.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { http } from "../../../lib/http";
import type {
  ApplyBody, Balance, Colleague, EffectiveCalendar, HierarchyRule,
  HolidayCalendar, LeaveDetail, LeaveRequest, Notice, OfflineBody, OrgUnit,
  Page, Policy, SlaSetting, Task, UnitMember, VacationPeriod, YearEndReport,
} from "./types";

const KEY = "elm";
const LIMIT = { limit: 100 };

export const keys = {
  balances: (year?: number) => [KEY, "balances", year] as const,
  mine: (status?: string) => [KEY, "mine", status] as const,
  detail: (id: number | null) => [KEY, "detail", id] as const,
  tasks: () => [KEY, "tasks"] as const,
  notices: () => [KEY, "notices"] as const,
  calendar: (year?: number) => [KEY, "calendar", year] as const,
  colleagues: (q: string) => [KEY, "colleagues", q] as const,
  records: (f?: unknown) => [KEY, "records", f] as const,
};

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: [KEY] });
}

function useWrite<TBody, TOut>(fn: (body: TBody) => Promise<TOut>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => invalidateAll(qc) });
}

// -- the employee --------------------------------------------------------------
export function useBalances(year?: number) {
  return useQuery({
    queryKey: keys.balances(year),
    queryFn: async () =>
      (await http.get<Balance[]>("/elm/balances", { params: { year } })).data,
  });
}

export function useMyLeaves(status?: string) {
  return useQuery({
    queryKey: keys.mine(status),
    queryFn: async () =>
      (await http.get<Page<LeaveRequest>>("/elm/applications",
        { params: { ...LIMIT, status } })).data,
  });
}

export function useLeaveDetail(id: number | null) {
  return useQuery({
    queryKey: keys.detail(id),
    queryFn: async () =>
      (await http.get<LeaveDetail>(`/elm/applications/${id}`)).data,
    enabled: id != null,
  });
}

export function useEffectiveCalendar(year?: number) {
  return useQuery({
    queryKey: keys.calendar(year),
    queryFn: async () =>
      (await http.get<EffectiveCalendar>("/elm/calendar", { params: { year } })).data,
    staleTime: 60_000,
  });
}

/** Substitute picker: two characters minimum, matching the server. */
export function useColleagues(q: string) {
  return useQuery({
    queryKey: keys.colleagues(q),
    queryFn: async () =>
      (await http.get<Colleague[]>("/elm/colleagues", { params: { q } })).data,
    enabled: q.trim().length >= 2,
    staleTime: 30_000,
  });
}

export function useApply() {
  return useWrite(async (body: ApplyBody) =>
    (await http.post<LeaveRequest>("/elm/applications", body)).data);
}

export function useWithdraw() {
  return useWrite(async (id: number) =>
    (await http.post<LeaveRequest>(`/elm/applications/${id}/withdraw`, {})).data);
}

export function useRequestCancellation() {
  return useWrite(async ({ id, reason }: { id: number; reason: string }) =>
    (await http.post<LeaveRequest>(`/elm/applications/${id}/cancel`, { reason })).data);
}

export function useRequestExtension() {
  return useWrite(async ({ id, ...body }: {
    id: number; new_end_date: string; reason: string;
    substitute_user_id?: number | null;
  }) => (await http.post<LeaveRequest>(`/elm/applications/${id}/extend`, body)).data);
}

export function useSubmitResumption() {
  return useWrite(async ({ id, ...body }: {
    id: number; actual_resumption_date: string; details?: string;
  }) => (await http.post<LeaveRequest>(`/elm/applications/${id}/resume`, body)).data);
}

export function useNominateSubstitute() {
  return useWrite(async ({ id, substitute_user_id }: {
    id: number; substitute_user_id: number;
  }) => (await http.post<LeaveRequest>(
    `/elm/applications/${id}/substitute`, { substitute_user_id })).data);
}

// -- tasks and notices ---------------------------------------------------------
export function useTasks() {
  return useQuery({
    queryKey: keys.tasks(),
    queryFn: async () =>
      (await http.get<Page<Task>>("/elm/tasks", { params: LIMIT })).data,
    staleTime: 15_000,
  });
}

export function useDecide() {
  return useWrite(async ({ id, outcome, remark }: {
    id: number; outcome: string; remark?: string;
  }) => (await http.post<LeaveRequest>(
    `/elm/tasks/${id}/decide`, { outcome, remark: remark ?? "" })).data);
}

export function useNotices() {
  return useQuery({
    queryKey: keys.notices(),
    queryFn: async () =>
      (await http.get<Page<Notice>>("/elm/notifications", { params: { limit: 20 } })).data,
  });
}

export function useMarkRead() {
  return useWrite(async (id: number) =>
    (await http.post<Notice>(`/elm/notifications/${id}/read`)).data);
}

// -- records -------------------------------------------------------------------
export function useRecords(filters?: {
  status?: string; category?: string; employee?: number;
}) {
  return useQuery({
    queryKey: keys.records(filters),
    queryFn: async () =>
      (await http.get<Page<LeaveRequest>>("/elm/records",
        { params: { ...LIMIT, ...filters } })).data,
  });
}

export function useRecordOffline() {
  return useWrite(async (body: OfflineBody) =>
    (await http.post<LeaveRequest>("/elm/records/offline", body)).data);
}

export function useAdjustBalance() {
  return useWrite(async (body: {
    employee_user_id: number; category: string; year: number;
    days: string; note: string;
  }) => (await http.post("/elm/records/adjustments", body)).data);
}

export function useRunYearEnd() {
  return useWrite(async (year: number) =>
    (await http.post<YearEndReport>("/elm/year-end", { year })).data);
}

// -- configuration -------------------------------------------------------------
export function usePolicies() {
  return useQuery({
    queryKey: [KEY, "policies"],
    queryFn: async () => (await http.get<Policy[]>("/elm/policies")).data,
  });
}

export function useSavePolicy() {
  return useWrite(async ({ category, ...body }: Partial<Policy> & { category: string }) =>
    (await http.patch<Policy>(`/elm/policies/${category}`, body)).data);
}

export function useHierarchyRules() {
  return useQuery({
    queryKey: [KEY, "rules"],
    queryFn: async () => (await http.get<HierarchyRule[]>("/elm/hierarchy-rules")).data,
  });
}

export function useSaveRule() {
  return useWrite(async (rule: Partial<HierarchyRule>) =>
    rule.id
      ? (await http.patch<HierarchyRule>(`/elm/hierarchy-rules/${rule.id}`, rule)).data
      : (await http.post<HierarchyRule>("/elm/hierarchy-rules", rule)).data);
}

export function useDeleteRule() {
  return useWrite(async (id: number) => {
    await http.delete(`/elm/hierarchy-rules/${id}`);
  });
}

export function useUnits() {
  return useQuery({
    queryKey: [KEY, "units"],
    queryFn: async () => (await http.get<OrgUnit[]>("/elm/units")).data,
  });
}

export function useSaveUnit() {
  return useWrite(async (unit: Partial<OrgUnit>) =>
    unit.id
      ? (await http.patch<OrgUnit>(`/elm/units/${unit.id}`, unit)).data
      : (await http.post<OrgUnit>("/elm/units", unit)).data);
}

export function useUnitMembers() {
  return useQuery({
    queryKey: [KEY, "members"],
    queryFn: async () => (await http.get<UnitMember[]>("/elm/unit-members")).data,
  });
}

export function usePlaceMember() {
  return useWrite(async (body: { user_id: number; unit_id: number; designation?: string }) =>
    (await http.post<UnitMember>("/elm/unit-members", body)).data);
}

export function useSla() {
  return useQuery({
    queryKey: [KEY, "sla"],
    queryFn: async () => (await http.get<SlaSetting>("/elm/sla")).data,
  });
}

export function useSaveSla() {
  return useWrite(async (body: Partial<SlaSetting>) =>
    (await http.patch<SlaSetting>("/elm/sla", body)).data);
}

// -- calendar ------------------------------------------------------------------
export function useCalendars() {
  return useQuery({
    queryKey: [KEY, "calendars"],
    queryFn: async () => (await http.get<HolidayCalendar[]>("/elm/calendars")).data,
  });
}

export function useCreateCalendar() {
  return useWrite(async (body: { year: number; title: string }) =>
    (await http.post<HolidayCalendar>("/elm/calendars", body)).data);
}

export function useAddHoliday() {
  return useWrite(async ({ calendarId, ...body }: {
    calendarId: number; date: string; name: string; kind: string;
  }) => (await http.post(`/elm/calendars/${calendarId}/holidays`, body)).data);
}

export function useRemoveHoliday() {
  return useWrite(async (id: number) => {
    await http.delete(`/elm/holidays/${id}`);
  });
}

export function usePublishCalendar() {
  return useWrite(async (id: number) =>
    (await http.post<HolidayCalendar>(`/elm/calendars/${id}/publish`, {})).data);
}

export function useVacationPeriods() {
  return useQuery({
    queryKey: [KEY, "vacations"],
    queryFn: async () => (await http.get<VacationPeriod[]>("/elm/vacation-periods")).data,
  });
}

export function useAddVacation() {
  return useWrite(async (body: Omit<VacationPeriod, "id">) =>
    (await http.post<VacationPeriod>("/elm/vacation-periods", body)).data);
}

export function useRemoveVacation() {
  return useWrite(async (id: number) => {
    await http.delete(`/elm/vacation-periods/${id}`);
  });
}
