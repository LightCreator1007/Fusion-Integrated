import type { Category, RequestStatus } from "./types";

export const CATEGORY_LABELS: Record<Category, string> = {
  CL: "Casual Leave",
  RH: "Restricted Holiday",
  SCL: "Special Casual Leave",
  EL: "Earned Leave",
  COL: "Commuted Leave",
  VL: "Vacation Leave",
};

export const STATUS_COLORS: Record<RequestStatus, string> = {
  pending: "yellow",
  approved: "green",
  rejected: "red",
  withdrawn: "gray",
  cancelled: "gray",
};

export const ROLE_LABELS: Record<string, string> = {
  substitute: "Substitute",
  unit_head: "Unit Head",
  establishment: "Establishment (Dy. Registrar)",
  dean: "Dean",
  registrar: "Registrar",
  director: "Director",
  applicant: "You (nominate a new substitute)",
};

export const KIND_LABELS = {
  leave: "Leave",
  extension: "Extension",
  cancellation: "Cancellation",
} as const;

/** What the server's `awaiting` / task role means to an employee. */
export function awaitingLabel(awaiting: string): string {
  return ROLE_LABELS[awaiting] ?? awaiting;
}

export function formatDays(days: string): string {
  const n = Number(days);
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function formatPeriod(start: string, end: string, half: string): string {
  const s = new Date(`${start}T00:00:00`).toLocaleDateString();
  if (start === end) {
    return half ? `${s} (${half} half)` : s;
  }
  return `${s} to ${new Date(`${end}T00:00:00`).toLocaleDateString()}`;
}

export const OUTCOME_LABELS: Record<string, string> = {
  accepted: "Accept",
  declined: "Decline",
  recommended: "Recommend",
  not_recommended: "Do not recommend",
  forwarded: "Verify and forward",
  approved: "Approve",
  rejected: "Reject",
};

/** The choices a task offers, by its mode. */
export function outcomesFor(mode: string): string[] {
  switch (mode) {
    case "consent": return ["accepted", "declined"];
    case "recommend": return ["recommended", "not_recommended"];
    case "forward": return ["forwarded"];
    default: return ["approved", "rejected"];
  }
}
