import { useState } from "react";
import { Button, Card, Container, Group, Stack, Text, Textarea } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaClipboardCheck } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { FormModal } from "../../../ui/components/FormModal";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useDecide, useTasks } from "../api/hooks";
import {
  KIND_LABELS, OUTCOME_LABELS, ROLE_LABELS, formatDays, formatPeriod, outcomesFor,
} from "../api/labels";
import type { Task } from "../api/types";
import { ApplicationDrawer } from "../components/ApplicationDrawer";

const NEEDS_REMARK = new Set(["rejected"]);

function taskTitle(t: Task): string {
  if (t.resumption) return "Review resumption";
  if (t.role === "substitute") return "Confirm you will cover";
  return {
    recommend: "Recommend", forward: "Verify and route", final: "Decide",
  }[t.mode] ?? "Review";
}

/** Everything waiting on this person: substitute consent, Unit Head review,
 *  Establishment routing, final sanction and resumption review.
 *
 *  The server decides what appears here. A request that is not addressed to
 *  you or to a role you hold is simply not in the list. */
export default function ApprovalsPage() {
  const { data, isPending, error } = useTasks();
  const decide = useDecide();
  const [active, setActive] = useState<{ task: Task; outcome: string } | null>(null);
  const [remark, setRemark] = useState("");
  const [peek, setPeek] = useState<number | null>(null);

  if (error) return <Container size="xl"><ErrorState error={error} /></Container>;

  function submit() {
    if (!active) return;
    decide.mutate(
      { id: active.task.id, outcome: active.outcome, remark: remark.trim() },
      {
        onSuccess: () => {
          notifications.show({
            color: "green", title: "Recorded",
            message: `${OUTCOME_LABELS[active.outcome] ?? active.outcome} recorded.`,
          });
          setActive(null); setRemark("");
        },
        onError: (e) => notifications.show({
          color: "red", title: "Could not record", message: errorMessage(e),
        }),
      },
    );
  }

  return (
    <Container size="xl">
      <PageHeader
        title="Approvals"
        subtitle="Requests waiting on you, oldest first"
      />
      <Card padding="lg">
        <DataTable<Task>
          rows={data?.results ?? []}
          loading={isPending}
          rowKey={(t) => t.id}
          minWidth={980}
          columns={[
            {
              key: "who", header: "Employee",
              render: (t) => (
                <Stack gap={0}>
                  <Text fw={600}>{t.application.applicant_name || t.application.applicant_user_id}</Text>
                  <Text size="xs" c="dimmed">
                    {ROLE_LABELS[t.role] ?? t.role}: {taskTitle(t)}
                  </Text>
                </Stack>
              ),
            },
            {
              key: "leave", header: "Request",
              render: (t) => (
                <Stack gap={0}>
                  <Text size="sm">
                    {t.application.category} {KIND_LABELS[t.application.kind].toLowerCase()},{" "}
                    {formatDays(t.application.days)} day(s)
                  </Text>
                  <Text size="xs" c="dimmed">
                    {formatPeriod(t.application.start_date, t.application.end_date,
                      t.application.half_day)}
                  </Text>
                </Stack>
              ),
            },
            {
              key: "detail", header: "Note",
              render: (t) => (
                <Stack gap={0}>
                  {t.resumption ? (
                    <Text size="xs">
                      Resumed {t.resumption.actual_resumption_date}
                      {t.resumption.adjustment_days !== 0
                        && ` (${t.resumption.adjustment_days > 0 ? "+" : ""}${t.resumption.adjustment_days} day(s))`}
                    </Text>
                  ) : (
                    <Text size="xs" lineClamp={2}>{t.application.reason}</Text>
                  )}
                  {t.application.station_leave && (
                    <Text size="xs" c="dimmed">Station: {t.application.station_destination}</Text>
                  )}
                  {t.application.recommendation && (
                    <Text size="xs" c="dimmed">
                      Unit Head: {t.application.recommendation.replace("_", " ")}
                    </Text>
                  )}
                </Stack>
              ),
            },
            {
              key: "actions", header: "", align: "right",
              render: (t) => (
                <Group justify="flex-end" gap={6} wrap="nowrap">
                  <Button size="compact-xs" variant="subtle" color="gray"
                    onClick={() => setPeek(t.application.id)}>
                    Details
                  </Button>
                  {(t.resumption ? ["approved", "rejected"] : outcomesFor(t.mode)).map(
                    (o) => (
                      <Button
                        key={o} size="compact-xs"
                        variant={NEEDS_REMARK.has(o) || o === "declined" || o === "not_recommended"
                          ? "light" : "filled"}
                        color={NEEDS_REMARK.has(o) || o === "declined" ? "red" : undefined}
                        onClick={() => { setRemark(""); setActive({ task: t, outcome: o }); }}
                      >
                        {t.resumption && o === "approved" ? "Accept"
                          : t.resumption && o === "rejected" ? "Return"
                          : OUTCOME_LABELS[o] ?? o}
                      </Button>
                    ))}
                </Group>
              ),
            },
          ]}
          empty={{
            icon: FaClipboardCheck,
            title: "Nothing is waiting on you",
            description: "New requests and substitute asks appear here.",
          }}
        />
      </Card>

      <FormModal
        opened={active != null} onClose={() => setActive(null)}
        title={active ? OUTCOME_LABELS[active.outcome] ?? active.outcome : ""}
        subtitle={active ? `${active.task.application.applicant_name} — ${active.task.application.category}` : ""}
        submitLabel="Confirm" submitting={decide.isPending}
        danger={active ? NEEDS_REMARK.has(active.outcome) || active.outcome === "declined" : false}
        disabled={active != null && NEEDS_REMARK.has(active.outcome) && !remark.trim()}
        disabledReason="A reason is required."
        error={decide.error} onSubmit={submit} size="md"
      >
        <Textarea
          label="Remark"
          description={active && NEEDS_REMARK.has(active.outcome)
            ? "Required. The employee will see this." : "Optional."}
          value={remark} onChange={(e) => setRemark(e.currentTarget.value)}
        />
      </FormModal>
      <ApplicationDrawer id={peek} onClose={() => setPeek(null)} />
    </Container>
  );
}
