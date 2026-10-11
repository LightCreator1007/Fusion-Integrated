import { useState } from "react";
import {
  ActionIcon, Button, Card, Container, Group, MultiSelect, NumberInput, Select,
  Stack, Switch, Tabs, Text, TextInput, Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaTrash } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useDeleteRule, useHierarchyRules, usePlaceMember, usePolicies, useSavePolicy,
  useSaveRule, useSaveSla, useSaveUnit, useSla, useUnitMembers, useUnits,
} from "../api/hooks";
import { CATEGORY_LABELS, ROLE_LABELS } from "../api/labels";
import type { HierarchyRule, OrgUnit, Policy, SlaSetting } from "../api/types";

const fail = (e: unknown) => notifications.show({
  color: "red", title: "Could not save", message: errorMessage(e),
});
const saved = () => notifications.show({ color: "green", title: "Saved", message: "" });

const AUTHORITIES = ["unit_head", "establishment", "dean", "registrar", "director"]
  .map((r) => ({ value: r, label: ROLE_LABELS[r] ?? r }));
const GROUPS = [
  { value: "faculty", label: "Faculty" }, { value: "staff", label: "Staff" },
  { value: "dean", label: "Dean" }, { value: "registrar", label: "Registrar" },
];
const HIGHER = ["SCL", "EL", "COL", "VL"].map((c) => ({
  value: c, label: CATEGORY_LABELS[c as keyof typeof CATEGORY_LABELS],
}));

function PolicyTab() {
  const { data, error, isPending } = usePolicies();
  const save = useSavePolicy();
  if (error) return <ErrorState error={error} />;

  function patch(p: Policy, change: Partial<Policy>) {
    save.mutate({ category: p.category, ...change }, { onSuccess: saved, onError: fail });
  }
  return (
    <DataTable<Policy>
      rows={data ?? []} loading={isPending} rowKey={(p) => p.category} minWidth={760}
      columns={[
        { key: "category", header: "Category",
          render: (p) => CATEGORY_LABELS[p.category] },
        { key: "annual_days", header: "Days per year",
          render: (p) => (
            <NumberInput
              w={110} min={0} decimalScale={1} defaultValue={Number(p.annual_days)}
              onBlur={(e) => {
                const v = e.currentTarget.value;
                if (v !== "" && Number(v) !== Number(p.annual_days)) {
                  patch(p, { annual_days: v });
                }
              }}
            />
          ) },
        { key: "applies_to", header: "Credited to",
          render: (p) => (
            <Select
              w={150} allowDeselect={false} value={p.applies_to}
              data={[{ value: "all", label: "Everyone" },
                     { value: "faculty", label: "Faculty" },
                     { value: "non_faculty", label: "Non-faculty" }]}
              onChange={(v) => v && patch(p, { applies_to: v as Policy["applies_to"] })}
            />
          ) },
        { key: "requires_substitute", header: "Needs substitute",
          render: (p) => (
            <Switch checked={p.requires_substitute}
              onChange={(e) => patch(p, { requires_substitute: e.currentTarget.checked })} />
          ) },
        { key: "is_active", header: "Open for requests",
          render: (p) => (
            <Switch checked={p.is_active}
              onChange={(e) => patch(p, { is_active: e.currentTarget.checked })} />
          ) },
      ]}
      empty={{ title: "No policy rows" }}
    />
  );
}

function HierarchyTab() {
  const rules = useHierarchyRules();
  const save = useSaveRule();
  const del = useDeleteRule();
  const [group, setGroup] = useState<string | null>("staff");
  const [category, setCategory] = useState<string | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  if (rules.error) return <ErrorState error={rules.error} />;

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        Without a rule, faculty go Unit Head, Establishment, Dean; staff go Unit Head,
        Establishment, Registrar. The last authority listed decides. CL and RH always
        end with the Unit Head. The Director sanctions their own leave.
      </Text>
      <DataTable<HierarchyRule>
        rows={rules.data ?? []} loading={rules.isPending} rowKey={(r) => r.id} minWidth={640}
        columns={[
          { key: "applicant_group", header: "Applicant" },
          { key: "category", header: "Category", render: (r) => r.category || "All higher-sanction" },
          { key: "steps", header: "Path",
            render: (r) => r.steps.map((s) => ROLE_LABELS[s] ?? s).join(" → ") },
          { key: "x", header: "", align: "right",
            render: (r) => (
              <ActionIcon variant="subtle" color="red" aria-label="Delete rule"
                onClick={() => del.mutate(r.id, { onError: fail })}>
                <FaTrash size={12} />
              </ActionIcon>
            ) },
        ]}
        empty={{ title: "Using the default paths" }}
      />
      <Group align="flex-end">
        <Select label="Applicant" data={GROUPS} value={group} onChange={setGroup}
          allowDeselect={false} w={150} />
        <Select label="Category" data={HIGHER} value={category} onChange={setCategory}
          clearable placeholder="All" w={150} />
        <MultiSelect label="Path, in order" data={AUTHORITIES} value={steps}
          onChange={setSteps} w={380} />
        <Button
          disabled={!group || !steps.length} loading={save.isPending}
          onClick={() => save.mutate({
            applicant_group: group!, category: category ?? "", steps, is_active: true,
          }, { onSuccess: () => { setSteps([]); saved(); }, onError: fail })}
        >
          Add rule
        </Button>
      </Group>
    </Stack>
  );
}

function UnitsTab() {
  const units = useUnits();
  const members = useUnitMembers();
  const saveUnit = useSaveUnit();
  const place = usePlaceMember();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState<string | null>("department");
  const [head, setHead] = useState<number | string>("");
  const [user, setUser] = useState<number | string>("");
  const [unit, setUnit] = useState<string | null>(null);
  if (units.error) return <ErrorState error={units.error} />;

  const count = (id: number) =>
    (members.data ?? []).filter((m) => m.unit_id === id).length;

  return (
    <Stack>
      <DataTable<OrgUnit>
        rows={units.data ?? []} loading={units.isPending} rowKey={(u) => u.id} minWidth={640}
        columns={[
          { key: "code", header: "Code" },
          { key: "name", header: "Name" },
          { key: "kind", header: "Kind" },
          { key: "head", header: "Unit Head (user id)",
            render: (u) => (
              <NumberInput
                w={130} hideControls defaultValue={u.head_user_id ?? ""}
                onBlur={(e) => {
                  const v = e.currentTarget.value;
                  if (v !== "" && Number(v) !== u.head_user_id) {
                    saveUnit.mutate({ id: u.id, head_user_id: Number(v) },
                      { onSuccess: saved, onError: fail });
                  }
                }}
              />
            ) },
          { key: "members", header: "Members", render: (u) => count(u.id) },
        ]}
        empty={{ title: "No units yet", description: "Create a department, section or office." }}
      />
      <Group align="flex-end">
        <TextInput label="Code" w={110} value={code} onChange={(e) => setCode(e.currentTarget.value)} />
        <TextInput label="Name" value={name} onChange={(e) => setName(e.currentTarget.value)} />
        <Select label="Kind" w={140} allowDeselect={false} value={kind} onChange={setKind}
          data={["department", "section", "office"]} />
        <NumberInput label="Head user id" hideControls w={120} value={head} onChange={setHead} />
        <Button
          disabled={!code.trim() || !name.trim()} loading={saveUnit.isPending}
          onClick={() => saveUnit.mutate({
            code: code.trim(), name: name.trim(), kind: kind as OrgUnit["kind"],
            head_user_id: head === "" ? null : Number(head),
          }, { onSuccess: () => { setCode(""); setName(""); saved(); }, onError: fail })}
        >
          Add unit
        </Button>
      </Group>

      <Title order={5} mt="md">Place an employee in a unit</Title>
      <Group align="flex-end">
        <NumberInput label="Employee user id" hideControls w={150} value={user} onChange={setUser} />
        <Select label="Unit" w={260} value={unit} onChange={setUnit}
          data={(units.data ?? []).map((u) => ({ value: String(u.id), label: u.name }))} />
        <Button
          disabled={!user || !unit} loading={place.isPending}
          onClick={() => place.mutate({ user_id: Number(user), unit_id: Number(unit) },
            { onSuccess: () => { setUser(""); saved(); }, onError: fail })}
        >
          Place
        </Button>
      </Group>
    </Stack>
  );
}

function SlaForm({ initial }: { initial: SlaSetting }) {
  const save = useSaveSla();
  const [reminder, setReminder] = useState<number | string>(initial.reminder_after_hours);
  const [escalate, setEscalate] = useState<number | string>(initial.escalate_after_hours);
  const [target, setTarget] = useState<number | string>(initial.escalate_to_user_id ?? "");
  return (
    <Stack maw={420}>
      <Text size="sm" c="dimmed">
        Measured in hours from when a task is assigned. A task that has been decided
        or withdrawn is never reminded or escalated.
      </Text>
      <NumberInput label="Remind after (hours)" min={1} value={reminder}
        onChange={setReminder} />
      <NumberInput label="Escalate after (hours)" min={2} value={escalate}
        onChange={setEscalate} />
      <NumberInput label="Escalate to (user id)" hideControls value={target}
        description="Leave blank to record the escalation in the audit trail only."
        onChange={setTarget} />
      <Button
        loading={save.isPending}
        onClick={() => save.mutate({
          reminder_after_hours: Number(reminder),
          escalate_after_hours: Number(escalate),
          escalate_to_user_id: target === "" ? null : Number(target),
        }, { onSuccess: saved, onError: fail })}
      >
        Save thresholds
      </Button>
    </Stack>
  );
}

function SlaTab() {
  const sla = useSla();
  if (sla.error) return <ErrorState error={sla.error} />;
  if (!sla.data) return <Text size="sm" c="dimmed">Loading…</Text>;
  return <SlaForm initial={sla.data} />;
}

/** Policy, hierarchy and SLA configuration (EL-UC-014, 018). Current values
 *  only: there is no draft or publish step, so a change applies to the next
 *  request that is submitted. */
export default function PolicyPage() {
  return (
    <Container size="lg">
      <PageHeader
        title="Policy & Hierarchy"
        subtitle="Entitlements, approval paths, organizational units and SLA thresholds"
      />
      <Card padding="lg">
        <Tabs defaultValue="policy" keepMounted={false}>
          <Tabs.List mb="md">
            <Tabs.Tab value="policy">Leave policy</Tabs.Tab>
            <Tabs.Tab value="hierarchy">Approval paths</Tabs.Tab>
            <Tabs.Tab value="units">Units</Tabs.Tab>
            <Tabs.Tab value="sla">SLA</Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="policy"><PolicyTab /></Tabs.Panel>
          <Tabs.Panel value="hierarchy"><HierarchyTab /></Tabs.Panel>
          <Tabs.Panel value="units"><UnitsTab /></Tabs.Panel>
          <Tabs.Panel value="sla"><SlaTab /></Tabs.Panel>
        </Tabs>
      </Card>
    </Container>
  );
}
