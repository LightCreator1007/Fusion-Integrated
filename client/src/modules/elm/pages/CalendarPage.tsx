import { useState } from "react";
import {
  ActionIcon, Badge, Button, Card, Container, Group, NumberInput, Select, Stack,
  Text, TextInput, Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaCalendarAlt, FaTrash } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useAddHoliday, useAddVacation, useCalendars, useCreateCalendar,
  usePublishCalendar, useRemoveHoliday, useRemoveVacation, useVacationPeriods,
} from "../api/hooks";
import type { Holiday, HolidayCalendar } from "../api/types";

const fail = (e: unknown) => notifications.show({
  color: "red", title: "Could not save", message: errorMessage(e),
});

function CalendarCard({ calendar }: { calendar: HolidayCalendar }) {
  const add = useAddHoliday();
  const remove = useRemoveHoliday();
  const publish = usePublishCalendar();
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState<string | null>("closed");

  return (
    <Card padding="lg" withBorder>
      <Group justify="space-between" mb="sm">
        <Group gap="xs">
          <Title order={4}>{calendar.title || calendar.year}</Title>
          <Badge color={calendar.status === "published" ? "green" : "gray"} variant="light">
            {calendar.status}
          </Badge>
          <Text size="xs" c="dimmed">{calendar.year}</Text>
        </Group>
        <Button
          size="xs" loading={publish.isPending}
          onClick={() => publish.mutate(calendar.id!, {
            onSuccess: () => notifications.show({
              color: "green", title: "Published",
              message: "Date and RH checks now use this calendar.",
            }),
            onError: fail,
          })}
        >
          {calendar.status === "published" ? "Publish again" : "Publish"}
        </Button>
      </Group>

      <DataTable<Holiday>
        rows={calendar.holidays} rowKey={(h) => h.id} minWidth={520}
        columns={[
          { key: "date", header: "Date" },
          { key: "name", header: "Name" },
          { key: "kind", header: "Kind",
            render: (h) => (h.kind === "closed" ? "Closed" : "Restricted (RH)") },
          { key: "x", header: "", align: "right",
            render: (h) => (
              <ActionIcon variant="subtle" color="red" aria-label="Remove"
                onClick={() => remove.mutate(h.id, { onError: fail })}>
                <FaTrash size={12} />
              </ActionIcon>
            ) },
        ]}
        empty={{ title: "No dates yet", description: "Add the closed and restricted holidays." }}
      />

      <Group mt="md" align="flex-end" wrap="wrap">
        <TextInput type="date" label="Date" value={date}
          onChange={(e) => setDate(e.currentTarget.value)} />
        <TextInput label="Name" value={name}
          onChange={(e) => setName(e.currentTarget.value)} />
        <Select label="Kind" allowDeselect={false} w={190} value={kind}
          onChange={setKind}
          data={[{ value: "closed", label: "Closed holiday" },
                 { value: "restricted", label: "Restricted holiday" }]} />
        <Button
          variant="light" disabled={!date || !name.trim()} loading={add.isPending}
          onClick={() => add.mutate(
            { calendarId: calendar.id!, date, name: name.trim(), kind: kind! },
            { onSuccess: () => { setDate(""); setName(""); }, onError: fail })}
        >
          Add date
        </Button>
      </Group>
    </Card>
  );
}

/** Holiday / RH calendar and vacation periods (EL-UC-015).
 *
 *  Publishing replaces the effective calendar for that year; until then the
 *  previous one keeps governing date and RH validation. */
export default function CalendarPage() {
  const calendars = useCalendars();
  const vacations = useVacationPeriods();
  const create = useCreateCalendar();
  const addVacation = useAddVacation();
  const removeVacation = useRemoveVacation();

  const [year, setYear] = useState<number | string>(new Date().getFullYear() + 1);
  const [title, setTitle] = useState("");
  const [label, setLabel] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  if (calendars.error) {
    return <Container size="lg"><ErrorState error={calendars.error} /></Container>;
  }

  return (
    <Container size="lg">
      <PageHeader
        title="Holiday Calendar"
        subtitle="Closed holidays, Restricted Holidays and vacation periods"
      />
      <Stack gap="lg">
        <Card padding="lg" withBorder>
          <Group align="flex-end">
            <NumberInput label="Year" hideControls w={110} value={year} onChange={setYear} />
            <TextInput label="Title" placeholder="Holiday list 2027" value={title}
              onChange={(e) => setTitle(e.currentTarget.value)} />
            <Button
              loading={create.isPending} disabled={!year || !title.trim()}
              onClick={() => create.mutate({ year: Number(year), title: title.trim() }, {
                onSuccess: () => setTitle(""), onError: fail,
              })}
            >
              New draft calendar
            </Button>
          </Group>
        </Card>

        {(calendars.data ?? []).map((c) => <CalendarCard key={c.id} calendar={c} />)}
        {!calendars.isPending && !calendars.data?.length && (
          <Text c="dimmed" ta="center">No calendars yet.</Text>
        )}

        <Card padding="lg" withBorder>
          <Title order={4} mb="xs">Vacation periods</Title>
          <Text size="xs" c="dimmed" mb="sm">
            Normally supplied by the Academic Calendar; kept here until that feed
            exists. Vacation Leave is only valid inside one of these.
          </Text>
          <DataTable
            rows={vacations.data ?? []} rowKey={(v) => v.id} minWidth={520}
            loading={vacations.isPending}
            columns={[
              { key: "label", header: "Period" },
              { key: "start_date", header: "From" },
              { key: "end_date", header: "To" },
              { key: "x", header: "", align: "right",
                render: (v) => (
                  <ActionIcon variant="subtle" color="red" aria-label="Remove"
                    onClick={() => removeVacation.mutate(v.id, { onError: fail })}>
                    <FaTrash size={12} />
                  </ActionIcon>
                ) },
            ]}
            empty={{ icon: FaCalendarAlt, title: "No vacation periods" }}
          />
          <Group mt="md" align="flex-end">
            <TextInput label="Label" value={label}
              onChange={(e) => setLabel(e.currentTarget.value)} />
            <TextInput type="date" label="From" value={from}
              onChange={(e) => setFrom(e.currentTarget.value)} />
            <TextInput type="date" label="To" value={to}
              onChange={(e) => setTo(e.currentTarget.value)} />
            <Button
              variant="light" disabled={!label.trim() || !from || !to}
              loading={addVacation.isPending}
              onClick={() => addVacation.mutate(
                { label: label.trim(), start_date: from, end_date: to },
                { onSuccess: () => { setLabel(""); setFrom(""); setTo(""); },
                  onError: fail })}
            >
              Add period
            </Button>
          </Group>
        </Card>
      </Stack>
    </Container>
  );
}
