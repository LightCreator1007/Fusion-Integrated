/** Wire types for the ELM API. Day counts and dates arrive as strings (Django
 *  serialises Decimal and date that way); only format them, never add them. */

export interface Page<T> {
  results: T[];
  next: string | null;
  previous: string | null;
}

export type Category = "CL" | "RH" | "SCL" | "EL" | "COL" | "VL";
export type RequestStatus =
  "pending" | "approved" | "rejected" | "withdrawn" | "cancelled";
export type RequestKind = "leave" | "extension" | "cancellation";
export type ElmAction =
  "withdraw" | "cancel" | "extend" | "resume" | "nominate_substitute";

export interface Balance {
  category: Category;
  label: string;
  entitlement: string;
  used: string;
  pending: string;
  balance: string;
  available: string;
}

export interface LeaveRequest {
  id: number;
  kind: RequestKind;
  parent_id: number | null;
  applicant_user_id: number;
  applicant_name: string;
  category: Category;
  category_label: string;
  start_date: string;
  end_date: string;
  half_day: "" | "first" | "second";
  days: string;
  reason: string;
  station_leave: boolean;
  station_destination: string;
  station_contact: string;
  evidence_reference: string;
  substitute_user_id: number | null;
  substitute_name: string;
  substitute_status: "not_required" | "pending" | "accepted" | "declined";
  status: RequestStatus;
  recommendation: "" | "recommended" | "not_recommended";
  /** Who the request is waiting on, in the server's words. */
  awaiting: string;
  decided_at: string | null;
  decision_remark: string;
  actual_resumption_date: string | null;
  entry_channel: "online" | "offline";
  offline_reference: string;
  allowed_actions: ElmAction[];
  created_at: string;
}

export interface TaskStep {
  id: number;
  role: string;
  mode: string;
  status: "pending" | "done" | "cancelled";
  outcome: string;
  remark: string;
  assignee_user_id: number | null;
  actor_user_id: number | null;
  created_at: string;
  acted_at: string | null;
}

export interface HistoryEvent {
  id: number;
  event: string;
  actor_user_id: number | null;
  detail: string;
  at: string;
}

export interface Resumption {
  id: number;
  actual_resumption_date: string;
  details: string;
  status: "pending" | "approved" | "rejected";
  adjustment_days: number;
  reviewed_at: string | null;
  review_remark: string;
}

export interface LeaveDetail extends LeaveRequest {
  route: { role: string; mode: string }[];
  tasks: TaskStep[];
  events: HistoryEvent[];
  resumptions: Resumption[];
}

export interface ApplyBody {
  category: Category;
  start_date: string;
  end_date: string;
  half_day?: "" | "first" | "second";
  reason: string;
  station_leave?: boolean;
  station_destination?: string;
  station_contact?: string;
  evidence_reference?: string;
  substitute_user_id?: number | null;
}

export interface Task {
  id: number;
  role: string;
  mode: string;
  status: string;
  assignee_user_id: number | null;
  created_at: string;
  application: {
    id: number;
    kind: RequestKind;
    category: Category;
    applicant_user_id: number;
    applicant_name: string;
    start_date: string;
    end_date: string;
    days: string;
    half_day: string;
    reason: string;
    station_leave: boolean;
    station_destination: string;
    recommendation: string;
  };
  resumption: {
    actual_resumption_date: string;
    details: string;
    adjustment_days: number;
  } | null;
}

export interface Notice {
  id: number;
  topic: string;
  subject: string;
  body: string;
  application_id: number | null;
  read_at: string | null;
  created_at: string;
}

export interface Colleague {
  user_id: number;
  display_name: string;
  department: string;
}

export interface Holiday {
  id: number;
  date: string;
  name: string;
  kind: "closed" | "restricted";
}

export interface HolidayCalendar {
  id: number | null;
  year: number;
  title: string;
  status: "draft" | "published" | "none";
  published_at: string | null;
  holidays: Holiday[];
}

export interface VacationPeriod {
  id: number;
  label: string;
  start_date: string;
  end_date: string;
}

export interface EffectiveCalendar extends HolidayCalendar {
  vacation_periods: VacationPeriod[];
}

export interface Policy {
  category: Category;
  annual_days: string;
  applies_to: "all" | "faculty" | "non_faculty";
  carry_forward: boolean;
  requires_substitute: boolean;
  is_active: boolean;
}

export interface HierarchyRule {
  id: number;
  applicant_group: string;
  category: string;
  steps: string[];
  is_active: boolean;
}

export interface OrgUnit {
  id: number;
  code: string;
  name: string;
  kind: "department" | "section" | "office";
  head_user_id: number | null;
}

export interface UnitMember {
  id: number;
  user_id: number;
  unit_id: number;
  designation: string;
}

export interface SlaSetting {
  reminder_after_hours: number;
  escalate_after_hours: number;
  escalate_to_user_id: number | null;
}

export interface OfflineBody {
  employee_user_id: number;
  category: Category;
  start_date: string;
  end_date: string;
  half_day?: "" | "first" | "second";
  reason: string;
  offline_reference: string;
  offline_reason: string;
  sanction_date: string;
}

export interface YearEndReport {
  year: number;
  processed: number;
  entries: number;
  exceptions: string[];
}
