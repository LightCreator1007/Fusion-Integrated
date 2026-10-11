import { useState } from "react";
import {
  Alert, Button, Card, Container, Group, NumberInput, Select, Stack, Text,
  Textarea, TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaFileSignature } from "react-icons/fa";

import { useAuth } from "../../../auth/AuthProvider";
import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { FormModal } from "../../../ui/components/FormModal";
import { Field, FormRow } from "../../../ui/components/FormSection";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useAdjustBalance, useRecordOffline, useRecords, useRunYearEnd,
} from "../api/hooks";
import { CATEGORY_LABELS, formatDays, formatPeriod } from "../api/labels";
import type { Category, LeaveRequest, YearEndReport } from "../api/types";
import { ApplicationDrawer } from "../components/ApplicationDrawer";
import { LeaveStatusBadge } from "../components/LeaveStatusBadge";

const CATEGORY_OPTIONS = Object.entries(CATEGORY_LABELS)
  .map(([value, label]) => ({ value, label }));
const STATUS_OPTIONS = ["pending", "approved", "rejected", "withdrawn", "cancelled"]
  .map((s) => ({ value: s, label: s }));

/** Leave Administrator's view (EL-UC-016, 017, 020).
 *
 *  Recording offline leave and correcting a balance are record keeping, not
 *  sanctioning: nothing here asks anyone to approve. */
export default function RecordsPage() {
  const { can } = useAuth();
  const [status, setStatus] = useState<string | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const records = useRecords({
    status: status ?? undefined, category: category ?? undefined,
  });
  const [open, setOpen] = useState<number | null>(null);
  const [form, setForm] = useState<"offline" | "adjust" | null>(null);
  const [yearEnd, setYearEnd] = useState<YearEndReport | null>(null);

  const offline = useRecordOffline();
  const adjust = useAdjustBalance();
  const run = useRunYearEnd();

  const [emp, setEmp] = useState<number | string>("");
  const [cat, setCat] = useState<string | null>("CL");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [ref, setRef] = useState("");
  const [why, setWhy] = useState("");
  const [sanctioned, setSanctioned] = useState("");
  const [days, setDays] = useState<number | string>("");
  const [year, setYear] = useState<number | string>(new Date().getFullYear());

  const canManage = can("elm_leave.record.manage");

  if (records.error) {
    return <Container size="xl"><ErrorState error={records.error} /></Container>;
  }

  const ok = (title: string) => {
    notifications.show({ color: "green", title, message: "Saved to the leave account." });
    setForm(null);
  };
  const fail = (e: unknown) => notifications.show({
    color: "red", title: "Could not save", message: errorMessage(e),
  });

  return (
    <Container size="xl">
      <PageHeader
        title="Leave Records"
        subtitle="Every employee's requests, offline entries and account corrections"
        action={(
          <Group>
            {canManage && (
              <>
                <Button variant="default" onClick={() => setForm("adjust")}>
                  Correct balance
                </Button>
                <Button onClick={() => setForm("offline")}>Record offline leave</Button>
              </>
            )}
            {can("elm_leave.yearend.run") && (
              <Button
                variant="light" color="orange" loading={run.isPending}
                onClick={() => run.mutate(new Date().getFullYear() - 1, {
                  onSuccess: setYearEnd, onError: fail,
                })}
              >
                Run last year's year-end
              </Button>
            )}
          </Group>
        )}
      />

      {yearEnd && (
        <Alert mb="lg" color={yearEnd.exceptions.length ? "orange" : "green"}
          title={`Year-end ${yearEnd.year}`} withCloseButton onClose={() => setYearEnd(null)}>
          <Text size="sm">
            {yearEnd.processed} account(s) processed, {yearEnd.entries} entr(ies) posted.
          </Text>
          {yearEnd.exceptions.map((x) => <Text key={x} size="xs">{x}</Text>)}
        </Alert>
      )}

      <Card padding="lg">
        <Group mb="md">
          <Select placeholder="Any status" clearable data={STATUS_OPTIONS}
            value={status} onChange={setStatus} w={180} />
          <Select placeholder="Any category" clearable data={CATEGORY_OPTIONS}
            value={category} onChange={setCategory} w={220} />
        </Group>
        <DataTable<LeaveRequest>
          rows={records.data?.results ?? []}
          loading={records.isPending}
          rowKey={(r) => r.id}
          minWidth={900}
          columns={[
            { key: "who", header: "Employee",
              render: (r) => r.applicant_name || r.applicant_user_id },
            { key: "cat", header: "Leave", render: (r) => r.category_label },
            { key: "period", header: "Period",
              render: (r) => formatPeriod(r.start_date, r.end_date, r.half_day) },
            { key: "days", header: "Days", render: (r) => formatDays(r.days) },
            { key: "status", header: "Status",
              render: (r) => <LeaveStatusBadge status={r.status} /> },
            { key: "channel", header: "Entered",
              render: (r) => r.entry_channel === "offline"
                ? `Offline (${r.offline_reference})` : "Online" },
            { key: "actions", header: "", align: "right",
              render: (r) => (
                <Button size="compact-xs" variant="subtle" onClick={() => setOpen(r.id)}>
                  Details
                </Button>
              ) },
          ]}
          empty={{ icon: FaFileSignature, title: "No leave records match" }}
        />
      </Card>

      <FormModal
        opened={form === "offline"} onClose={() => setForm(null)}
        title="Record offline-sanctioned leave"
        subtitle="Leave already sanctioned on paper. No approval is requested."
        submitLabel="Record" submitting={offline.isPending} error={offline.error}
        disabled={!emp || !from || !to || !reason.trim() || !ref.trim()
          || !why.trim() || !sanctioned}
        onSubmit={() => offline.mutate({
          employee_user_id: Number(emp), category: cat as Category,
          start_date: from, end_date: to, reason: reason.trim(),
          offline_reference: ref.trim(), offline_reason: why.trim(),
          sanction_date: sanctioned,
        }, { onSuccess: () => ok("Offline leave recorded"), onError: fail })}
      >
        <Stack>
          <FormRow>
            <Field><NumberInput label="Employee user id" required hideControls
              value={emp} onChange={setEmp} /></Field>
            <Field><Select label="Category" required allowDeselect={false}
              data={CATEGORY_OPTIONS} value={cat} onChange={setCat} /></Field>
            <Field><TextInput type="date" label="From" required value={from}
              onChange={(e) => setFrom(e.currentTarget.value)} /></Field>
            <Field><TextInput type="date" label="To" required value={to}
              onChange={(e) => setTo(e.currentTarget.value)} /></Field>
          </FormRow>
          <Textarea label="Reason for the leave" required value={reason}
            onChange={(e) => setReason(e.currentTarget.value)} />
          <TextInput label="Sanction reference" required
            description="File or order number of the paper sanction."
            value={ref} onChange={(e) => setRef(e.currentTarget.value)} />
          <TextInput type="date" label="Sanctioned on" required value={sanctioned}
            onChange={(e) => setSanctioned(e.currentTarget.value)} />
          <TextInput label="Why ELM could not be used" required
            description="Illness, connectivity, server unavailability…"
            value={why} onChange={(e) => setWhy(e.currentTarget.value)} />
        </Stack>
      </FormModal>

      <FormModal
        opened={form === "adjust"} onClose={() => setForm(null)}
        title="Correct a leave balance"
        subtitle="A signed entry with a reason, added to the employee's account."
        submitLabel="Post correction" submitting={adjust.isPending}
        error={adjust.error}
        disabled={!emp || !days || !reason.trim()}
        onSubmit={() => adjust.mutate({
          employee_user_id: Number(emp), category: cat!, year: Number(year),
          days: String(days), note: reason.trim(),
        }, { onSuccess: () => ok("Balance corrected"), onError: fail })}
      >
        <Stack>
          <FormRow>
            <Field><NumberInput label="Employee user id" required hideControls
              value={emp} onChange={setEmp} /></Field>
            <Field><Select label="Category" required allowDeselect={false}
              data={CATEGORY_OPTIONS} value={cat} onChange={setCat} /></Field>
            <Field><NumberInput label="Leave year" required hideControls
              value={year} onChange={setYear} /></Field>
            <Field><NumberInput label="Days (negative to deduct)" required
              decimalScale={2} step={0.5} value={days} onChange={setDays} /></Field>
          </FormRow>
          <Textarea label="Reason" required value={reason}
            onChange={(e) => setReason(e.currentTarget.value)} />
        </Stack>
      </FormModal>

      <ApplicationDrawer id={open} onClose={() => setOpen(null)} />
    </Container>
  );
}
