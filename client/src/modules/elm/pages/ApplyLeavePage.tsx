import { useMemo, useState } from "react";
import {
  Alert, Badge, Button, Card, Container, Group, SegmentedControl, Select, Stack,
  Switch, Text, Textarea, TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaInfoCircle } from "react-icons/fa";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "../../../lib/http";
import { ErrorState } from "../../../ui/components/ErrorState";
import { Field, FormRow, FormSection } from "../../../ui/components/FormSection";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useApply, useBalances, useEffectiveCalendar } from "../api/hooks";
import { CATEGORY_LABELS, formatDays } from "../api/labels";
import type { ApplyBody, Category } from "../api/types";
import { ColleaguePicker } from "../components/ColleaguePicker";

const ONE_DAY_ONLY: Category[] = ["RH"];
const SUBSTITUTE_CATEGORIES: Category[] = ["EL", "COL", "VL"];

/** Apply for leave (EL-UC-001).
 *
 *  The server is the judge of every rule. This page only helps the employee
 *  avoid the obvious refusals: it shows the balance for the chosen category,
 *  the Restricted Holidays that can be claimed, and asks for a substitute
 *  when the category is one that needs coverage. */
export default function ApplyLeavePage() {
  const navigate = useNavigate();
  const year = new Date().getFullYear();
  const balances = useBalances(year);
  const calendar = useEffectiveCalendar(year);
  const apply = useApply();

  const [category, setCategory] = useState<Category>("CL");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [half, setHalf] = useState<"" | "first" | "second">("");
  const [reason, setReason] = useState("");
  const [station, setStation] = useState(false);
  const [destination, setDestination] = useState("");
  const [contact, setContact] = useState("");
  const [evidence, setEvidence] = useState("");
  const [substitute, setSubstitute] = useState<number | null>(null);

  const categories = useMemo(
    () => (balances.data ?? []).map((b) => ({
      value: b.category,
      label: `${CATEGORY_LABELS[b.category]} — ${formatDays(b.available)} available`,
    })),
    [balances.data],
  );
  const restricted = (calendar.data?.holidays ?? []).filter((h) => h.kind === "restricted");

  const single = ONE_DAY_ONLY.includes(category) || half !== "";
  const effectiveEnd = single ? start : end;
  const needsSubstitute = SUBSTITUTE_CATEGORIES.includes(category);
  const ready = Boolean(start && effectiveEnd && reason.trim()
    && (!station || destination.trim()) && (!needsSubstitute || substitute));

  function submit() {
    const body: ApplyBody = {
      category, start_date: start, end_date: effectiveEnd, half_day: half,
      reason: reason.trim(), station_leave: station,
      station_destination: station ? destination.trim() : "",
      station_contact: station ? contact.trim() : "",
      evidence_reference: category === "COL" ? evidence.trim() : "",
      substitute_user_id: substitute,
    };
    apply.mutate(body, {
      onSuccess: (r) => {
        notifications.show({
          color: r.status === "approved" ? "green" : "blue",
          title: r.status === "approved" ? "Leave approved" : "Request submitted",
          message: r.substitute_status === "pending"
            ? "Your substitute has been asked to confirm. Routing starts once they accept."
            : "It is now with the approving authority.",
        });
        navigate("../mine");
      },
      onError: (e) => notifications.show({
        color: "red", title: "Could not submit", message: errorMessage(e),
      }),
    });
  }

  if (balances.error) {
    return <Container size="md"><ErrorState error={balances.error} /></Container>;
  }

  return (
    <Container size="md">
      <PageHeader
        title="Apply for Leave"
        subtitle="A submitted request cannot be edited. Withdraw it and apply again if something changes."
      />
      <Card padding="lg">
        <Stack gap="lg">
          <FormSection first title="Leave" hint="Balances are for the current leave year.">
            <FormRow>
              <Field span={12}>
                <Select
                  label="Category" required data={categories} value={category}
                  allowDeselect={false}
                  onChange={(v) => {
                    setCategory((v ?? "CL") as Category);
                    if (v !== "CL") setHalf("");
                  }}
                />
              </Field>
              {category === "CL" && (
                <Field span={12}>
                  <Text size="sm" fw={500} mb={4}>Duration</Text>
                  <SegmentedControl
                    value={half} onChange={(v) => setHalf(v as typeof half)}
                    data={[
                      { value: "", label: "Full day(s)" },
                      { value: "first", label: "First half" },
                      { value: "second", label: "Second half" },
                    ]}
                  />
                </Field>
              )}
              <Field span={single ? 12 : 6}>
                <TextInput
                  type="date" label={single ? "Date" : "From"} required
                  value={start} onChange={(e) => setStart(e.currentTarget.value)}
                />
              </Field>
              {!single && (
                <Field>
                  <TextInput
                    type="date" label="To" required min={start || undefined}
                    value={end} onChange={(e) => setEnd(e.currentTarget.value)}
                  />
                </Field>
              )}
            </FormRow>

            {category === "RH" && (
              <Alert mt="sm" variant="light" icon={<FaInfoCircle />} p="sm">
                <Text size="sm" mb={4}>
                  Restricted Holidays in the published calendar:
                </Text>
                {restricted.length === 0
                  ? <Text size="xs">None published for {year}.</Text>
                  : (
                    <Group gap={6}>
                      {restricted.map((h) => (
                        <Badge
                          key={h.id} variant="light" style={{ cursor: "pointer" }}
                          onClick={() => setStart(h.date)}
                        >
                          {h.date} {h.name}
                        </Badge>
                      ))}
                    </Group>
                  )}
              </Alert>
            )}
            {category === "VL" && (
              <Alert mt="sm" variant="light" icon={<FaInfoCircle />} p="sm">
                <Text size="sm">Vacation Leave must fall inside one vacation period:</Text>
                {(calendar.data?.vacation_periods ?? []).map((v) => (
                  <Text key={v.id} size="xs">
                    {v.label}: {v.start_date} to {v.end_date}
                  </Text>
                ))}
              </Alert>
            )}
          </FormSection>

          <FormSection title="Purpose">
            <Textarea
              label="Reason" required autosize minRows={2} maxLength={1000}
              value={reason} onChange={(e) => setReason(e.currentTarget.value)}
            />
            {category === "COL" && (
              <TextInput
                mt="sm" label="Medical evidence reference"
                description="Certificate or document number, where it applies."
                value={evidence} onChange={(e) => setEvidence(e.currentTarget.value)}
              />
            )}
          </FormSection>

          <FormSection
            title="Station Leave"
            hint="Needed only if you will be away from Jabalpur. It travels with this application."
          >
            <Switch
              label="I will be outside Jabalpur" checked={station}
              onChange={(e) => setStation(e.currentTarget.checked)}
            />
            {station && (
              <FormRow>
                <Field>
                  <TextInput
                    mt="sm" label="Destination" required value={destination}
                    onChange={(e) => setDestination(e.currentTarget.value)}
                  />
                </Field>
                <Field>
                  <TextInput
                    mt="sm" label="Contact while away" value={contact}
                    onChange={(e) => setContact(e.currentTarget.value)}
                  />
                </Field>
              </FormRow>
            )}
          </FormSection>

          {(needsSubstitute || substitute) && (
            <FormSection
              title="Responsibility cover"
              hint="Your substitute must accept before the request goes to your Unit Head."
            >
              <ColleaguePicker
                value={substitute} required={needsSubstitute}
                onChange={(id) => setSubstitute(id)}
              />
            </FormSection>
          )}

          <Group justify="flex-end">
            <Button variant="default" onClick={() => navigate("../mine")}>
              Cancel
            </Button>
            <Button onClick={submit} loading={apply.isPending} disabled={!ready}>
              Submit request
            </Button>
          </Group>
        </Stack>
      </Card>
    </Container>
  );
}
