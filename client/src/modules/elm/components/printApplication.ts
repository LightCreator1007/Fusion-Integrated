import { KIND_LABELS, formatDays, formatPeriod } from "../api/labels";
import type { LeaveDetail } from "../api/types";

function esc(value: string): string {
  return value.replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}

/** The printable form of an application (EL-UC-013): a self-contained page the
 *  browser can print or save as PDF. Every value is escaped, because the
 *  reason and remarks are free text. */
export function printApplication(d: LeaveDetail) {
  const rows: [string, string][] = [
    ["Application no.", String(d.id)],
    ["Type", KIND_LABELS[d.kind]],
    ["Employee", d.applicant_name || String(d.applicant_user_id)],
    ["Leave category", d.category_label],
    ["Period", formatPeriod(d.start_date, d.end_date, d.half_day)],
    ["Days", formatDays(d.days)],
    ["Reason", d.reason],
    ["Station Leave", d.station_leave
      ? `Yes, to ${d.station_destination}${d.station_contact ? ` (${d.station_contact})` : ""}`
      : "No"],
    ["Substitute", d.substitute_name || "None"],
    ["Status", d.status],
    ["Decision remark", d.decision_remark || "—"],
    ["Decided on", d.decided_at ? new Date(d.decided_at).toLocaleString() : "—"],
  ];
  const trail = d.tasks.filter((t) => t.status === "done").map(
    (t) => `<tr><td>${esc(t.role)}</td><td>${esc(t.outcome)}</td>`
      + `<td>${esc(t.remark)}</td>`
      + `<td>${t.acted_at ? esc(new Date(t.acted_at).toLocaleString()) : ""}</td></tr>`);

  const html = `<!doctype html><html><head><meta charset="utf-8">
<title>Leave application ${d.id}</title>
<style>body{font-family:sans-serif;margin:32px;color:#111}
h1{font-size:20px}table{border-collapse:collapse;width:100%;margin-bottom:24px}
td,th{border:1px solid #bbb;padding:6px 10px;text-align:left;font-size:14px}
th{background:#f3f3f3;width:30%}</style></head><body>
<h1>Leave application</h1>
<table>${rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join("")}</table>
${trail.length ? `<h1>Review trail</h1><table><tr><th>Step</th><th>Outcome</th>
<th>Remark</th><th>When</th></tr>${trail.join("")}</table>` : ""}
</body></html>`;

  const w = window.open("", "_blank", "noopener=no");
  if (!w) return false;
  w.document.write(html);
  w.document.close();
  w.focus();
  w.print();
  return true;
}
