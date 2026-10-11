import { useState } from "react";
import {
  ActionIcon, Badge, Button, Card, Container, Group, SimpleGrid, Stack, Text,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaCalendarAlt, FaEye } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useBalances, useMarkRead, useMyLeaves, useNotices, useWithdraw } from "../api/hooks";
import { KIND_LABELS, awaitingLabel, formatDays, formatPeriod } from "../api/labels";
import type { LeaveRequest } from "../api/types";
import { ActionModals, type ModalKind } from "../components/ActionModals";
import { ApplicationDrawer } from "../components/ApplicationDrawer";
import { LeaveStatusBadge } from "../components/LeaveStatusBadge";

/** Balances, history and everything an employee can still do with a request
 *  (EL-UC-007, 008, 009, 010, 012, 019). Which buttons appear is decided by the
 *  server's `allowed_actions`, so a rule change never needs a client change. */
export default function MyLeavesPage() {
  const year = new Date().getFullYear();
  const balances = useBalances(year);
  const leaves = useMyLeaves();
  const notices = useNotices();
  const markRead = useMarkRead();
  const withdraw = useWithdraw();

  const [open, setOpen] = useState<number | null>(null);
  const [modal, setModal] = useState<{ kind: ModalKind; leave: LeaveRequest } | null>(null);

  if (leaves.error) {
    return <Container size="xl"><ErrorState error={leaves.error} /></Container>;
  }

  function doWithdraw(r: LeaveRequest) {
    withdraw.mutate(r.id, {
      onSuccess: () => notifications.show({
        color: "gray", title: "Withdrawn",
        message: "Approval processing for this request has stopped.",
      }),
      onError: (e) => notifications.show({
        color: "red", title: "Could not withdraw", message: errorMessage(e),
      }),
    });
  }

  const unread = (notices.data?.results ?? []).filter((n) => !n.read_at);

  return (
    <Container size="xl">
      <PageHeader
        title="My Leave"
        subtitle={`Balances for ${year} and the history of your requests`}
      />

      <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }} mb="lg">
        {(balances.data ?? []).map((b) => (
          <Card key={b.category} padding="md" withBorder>
            <Text size="xs" c="dimmed">{b.label}</Text>
            <Text fz={28} fw={700} lh={1.1}>{formatDays(b.available)}</Text>
            <Text size="xs" c="dimmed">
              of {formatDays(b.entitlement)} · used {formatDays(b.used)}
              {Number(b.pending) > 0 ? ` · ${formatDays(b.pending)} pending` : ""}
            </Text>
          </Card>
        ))}
      </SimpleGrid>

      {unread.length > 0 && (
        <Card padding="md" mb="lg" withBorder>
          <Stack gap="xs">
            <Text fw={600} size="sm">Updates</Text>
            {unread.map((n) => (
              <Group key={n.id} justify="space-between" wrap="nowrap">
                <Stack gap={0}>
                  <Text size="sm">{n.subject}</Text>
                  {n.body && <Text size="xs" c="dimmed">{n.body}</Text>}
                </Stack>
                <Button size="compact-xs" variant="subtle"
                  onClick={() => markRead.mutate(n.id)}>
                  Dismiss
                </Button>
              </Group>
            ))}
          </Stack>
        </Card>
      )}

      <Card padding="lg">
        <DataTable<LeaveRequest>
          rows={leaves.data?.results ?? []}
          loading={leaves.isPending}
          rowKey={(r) => r.id}
          minWidth={980}
          columns={[
            {
              key: "category", header: "Leave",
              render: (r) => (
                <Stack gap={0}>
                  <Text fw={600}>{r.category_label}</Text>
                  {r.kind !== "leave" && (
                    <Badge size="xs" variant="outline" color="gray" w="fit-content">
                      {KIND_LABELS[r.kind]}
                    </Badge>
                  )}
                </Stack>
              ),
            },
            {
              key: "period", header: "Period",
              render: (r) => formatPeriod(r.start_date, r.end_date, r.half_day),
            },
            { key: "days", header: "Days", render: (r) => formatDays(r.days) },
            {
              key: "status", header: "Status",
              render: (r) => (
                <Stack gap={0}>
                  <LeaveStatusBadge status={r.status} />
                  {r.status === "pending" && r.awaiting && (
                    <Text size="xs" c="dimmed">with {awaitingLabel(r.awaiting)}</Text>
                  )}
                </Stack>
              ),
            },
            {
              key: "actions", header: "", align: "right",
              render: (r) => (
                <Group justify="flex-end" gap={4} wrap="nowrap">
                  <ActionIcon variant="subtle" color="gray" aria-label="Details"
                    onClick={() => setOpen(r.id)}>
                    <FaEye size={13} />
                  </ActionIcon>
                  {r.allowed_actions.includes("nominate_substitute") && (
                    <Button size="compact-xs" variant="light"
                      onClick={() => setModal({ kind: "nominate", leave: r })}>
                      New substitute
                    </Button>
                  )}
                  {r.allowed_actions.includes("extend") && (
                    <Button size="compact-xs" variant="light"
                      onClick={() => setModal({ kind: "extend", leave: r })}>
                      Extend
                    </Button>
                  )}
                  {r.allowed_actions.includes("resume") && (
                    <Button size="compact-xs" variant="light"
                      onClick={() => setModal({ kind: "resume", leave: r })}>
                      Resume duty
                    </Button>
                  )}
                  {r.allowed_actions.includes("cancel") && (
                    <Button size="compact-xs" variant="subtle" color="red"
                      onClick={() => setModal({ kind: "cancel", leave: r })}>
                      Cancel
                    </Button>
                  )}
                  {r.allowed_actions.includes("withdraw") && (
                    <Button size="compact-xs" variant="subtle" color="gray"
                      loading={withdraw.isPending && withdraw.variables === r.id}
                      onClick={() => doWithdraw(r)}>
                      Withdraw
                    </Button>
                  )}
                </Group>
              ),
            },
          ]}
          empty={{
            icon: FaCalendarAlt,
            title: "You have not applied for any leave",
            description: "Requests you submit are tracked here.",
          }}
        />
      </Card>

      <ApplicationDrawer id={open} onClose={() => setOpen(null)} />
      <ActionModals
        kind={modal?.kind ?? null} leave={modal?.leave ?? null}
        onClose={() => setModal(null)}
      />
    </Container>
  );
}
