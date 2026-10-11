import { Alert, Badge, Button, Drawer, Group, Stack, Table, Text, Timeline } from "@mantine/core";
import { FaInfoCircle, FaPrint } from "react-icons/fa";

import { ErrorState } from "../../../ui/components/ErrorState";
import { useLeaveDetail } from "../api/hooks";
import {
  KIND_LABELS, ROLE_LABELS, awaitingLabel, formatDays, formatPeriod,
} from "../api/labels";
import { LeaveStatusBadge } from "./LeaveStatusBadge";
import { printApplication } from "./printApplication";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Table.Tr>
      <Table.Th w="34%">{label}</Table.Th>
      <Table.Td>{children}</Table.Td>
    </Table.Tr>
  );
}

/** One request in full: what was asked, where it stands, and every step it
 *  has been through, so "why is my leave still pending?" needs no phone call. */
export function ApplicationDrawer({ id, onClose }: {
  id: number | null;
  onClose: () => void;
}) {
  const { data, isPending, error } = useLeaveDetail(id);

  return (
    <Drawer
      opened={id != null} onClose={onClose} position="right" size="lg"
      title={<Text fw={700}>Leave request {id ? `#${id}` : ""}</Text>}
    >
      {error && <ErrorState error={error} />}
      {isPending && !error && <Text size="sm" c="dimmed">Loading…</Text>}
      {data && (
        <Stack gap="md">
          <Group justify="space-between">
            <Group gap="xs">
              <LeaveStatusBadge status={data.status} />
              <Badge variant="outline" color="gray" size="sm">
                {KIND_LABELS[data.kind]}
              </Badge>
              {data.entry_channel === "offline" && (
                <Badge variant="light" color="grape" size="sm">
                  Recorded offline
                </Badge>
              )}
            </Group>
            <Button
              size="xs" variant="default" leftSection={<FaPrint />}
              onClick={() => printApplication(data)}
            >
              Print
            </Button>
          </Group>

          {data.status === "pending" && data.awaiting && (
            <Alert variant="light" color="blue" icon={<FaInfoCircle />} p="sm">
              <Text size="sm">Waiting on: {awaitingLabel(data.awaiting)}</Text>
            </Alert>
          )}

          <Table withTableBorder>
            <Table.Tbody>
              <Row label="Employee">{data.applicant_name || data.applicant_user_id}</Row>
              <Row label="Category">{data.category_label}</Row>
              <Row label="Period">
                {formatPeriod(data.start_date, data.end_date, data.half_day)}
              </Row>
              <Row label="Days">{formatDays(data.days)}</Row>
              <Row label="Reason">{data.reason}</Row>
              {data.station_leave && (
                <Row label="Station Leave">
                  {data.station_destination}
                  {data.station_contact ? ` — ${data.station_contact}` : ""}
                </Row>
              )}
              {data.substitute_user_id && (
                <Row label="Substitute">
                  {data.substitute_name || data.substitute_user_id}{" "}
                  <Badge size="xs" variant="light">{data.substitute_status}</Badge>
                </Row>
              )}
              {data.recommendation && (
                <Row label="Unit Head">{data.recommendation.replace("_", " ")}</Row>
              )}
              {data.offline_reference && (
                <Row label="Sanction reference">{data.offline_reference}</Row>
              )}
              {data.decision_remark && <Row label="Remark">{data.decision_remark}</Row>}
              {data.actual_resumption_date && (
                <Row label="Resumed on">{data.actual_resumption_date}</Row>
              )}
            </Table.Tbody>
          </Table>

          {data.route.length > 0 && (
            <Stack gap={4}>
              <Text fw={600} size="sm">Approval path</Text>
              <Text size="sm" c="dimmed">
                {data.route.map((s) => ROLE_LABELS[s.role] ?? s.role).join("  →  ")}
              </Text>
            </Stack>
          )}

          {data.resumptions.length > 0 && (
            <Stack gap={4}>
              <Text fw={600} size="sm">Resumption</Text>
              {data.resumptions.map((r) => (
                <Text key={r.id} size="sm">
                  {r.actual_resumption_date} — {r.status}
                  {r.adjustment_days !== 0 &&
                    ` (${r.adjustment_days > 0 ? "+" : ""}${r.adjustment_days} day(s) to balance)`}
                </Text>
              ))}
            </Stack>
          )}

          <Stack gap={4}>
            <Text fw={600} size="sm">History</Text>
            <Timeline active={data.events.length} bulletSize={14} lineWidth={2}>
              {data.events.map((e) => (
                <Timeline.Item
                  key={e.id}
                  title={<Text size="sm" fw={500}>{e.event.replace(/_/g, " ")}</Text>}
                >
                  {e.detail && <Text size="xs">{e.detail}</Text>}
                  <Text size="xs" c="dimmed">{new Date(e.at).toLocaleString()}</Text>
                </Timeline.Item>
              ))}
            </Timeline>
          </Stack>
        </Stack>
      )}
    </Drawer>
  );
}
