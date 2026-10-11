import { useState } from "react";
import { Stack, Text, Textarea, TextInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";

import { errorMessage } from "../../../lib/http";
import { FormModal } from "../../../ui/components/FormModal";
import {
  useNominateSubstitute, useRequestCancellation, useRequestExtension,
  useSubmitResumption,
} from "../api/hooks";
import { CATEGORY_LABELS } from "../api/labels";
import type { LeaveRequest } from "../api/types";
import { ColleaguePicker } from "./ColleaguePicker";

export type ModalKind = "cancel" | "extend" | "resume" | "nominate";

interface Props {
  kind: ModalKind | null;
  leave: LeaveRequest | null;
  onClose: () => void;
}

/** The four follow-up requests an employee can make on a leave request. They
 *  share one shell because each is "a short form, then a POST". */
export function ActionModals({ kind, leave, onClose }: Props) {
  const [reason, setReason] = useState("");
  const [date, setDate] = useState("");
  const [substitute, setSubstitute] = useState<number | null>(null);

  const cancel = useRequestCancellation();
  const extend = useRequestExtension();
  const resume = useSubmitResumption();
  const nominate = useNominateSubstitute();

  if (!kind || !leave) return null;

  function done(title: string, message: string) {
    notifications.show({ color: "blue", title, message });
    setReason(""); setDate(""); setSubstitute(null);
    onClose();
  }
  const fail = (e: unknown) => notifications.show({
    color: "red", title: "Could not submit", message: errorMessage(e),
  });
  const label = `${CATEGORY_LABELS[leave.category]}, ${leave.start_date} to ${leave.end_date}`;

  if (kind === "cancel") {
    return (
      <FormModal
        opened onClose={onClose} title="Request cancellation" subtitle={label}
        submitLabel="Request cancellation" danger submitting={cancel.isPending}
        error={cancel.error} disabled={!reason.trim()}
        onSubmit={() => cancel.mutate({ id: leave.id, reason: reason.trim() }, {
          onSuccess: () => done("Cancellation requested",
            "It follows the same approvers as the original leave."),
          onError: fail,
        })}
      >
        <Stack>
          <Text size="sm" c="dimmed">
            The approved leave stays in force until the cancellation is approved.
          </Text>
          <Textarea label="Reason" required value={reason}
            onChange={(e) => setReason(e.currentTarget.value)} />
        </Stack>
      </FormModal>
    );
  }

  if (kind === "extend") {
    return (
      <FormModal
        opened onClose={onClose} title="Request extension" subtitle={label}
        submitLabel="Request extension" submitting={extend.isPending}
        error={extend.error} disabled={!date || !reason.trim() || !substitute}
        onSubmit={() => extend.mutate({
          id: leave.id, new_end_date: date, reason: reason.trim(),
          substitute_user_id: substitute,
        }, {
          onSuccess: () => done("Extension requested",
            "Only the additional days are posted if it is approved."),
          onError: fail,
        })}
      >
        <Stack>
          <TextInput type="date" label="New end date" required value={date}
            min={leave.end_date}
            onChange={(e) => setDate(e.currentTarget.value)} />
          <Textarea label="Reason" required value={reason}
            onChange={(e) => setReason(e.currentTarget.value)} />
          <ColleaguePicker value={substitute} required
            onChange={(id) => setSubstitute(id)} />
        </Stack>
      </FormModal>
    );
  }

  if (kind === "resume") {
    return (
      <FormModal
        opened onClose={onClose} title="Resume duty" subtitle={label}
        submitLabel="Submit resumption" submitting={resume.isPending}
        error={resume.error} disabled={!date}
        onSubmit={() => resume.mutate({
          id: leave.id, actual_resumption_date: date, details: reason.trim(),
        }, {
          onSuccess: () => done("Resumption submitted",
            "The sanctioning authority will review it."),
          onError: fail,
        })}
      >
        <Stack>
          <Text size="sm" c="dimmed">
            Returning on {leave.end_date} changes nothing. An earlier or later date
            adjusts your balance once reviewed.
          </Text>
          <TextInput type="date" label="Date you resumed" required value={date}
            min={leave.start_date} max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setDate(e.currentTarget.value)} />
          <Textarea label="Details" value={reason}
            onChange={(e) => setReason(e.currentTarget.value)} />
        </Stack>
      </FormModal>
    );
  }

  return (
    <FormModal
      opened onClose={onClose} title="Nominate another substitute"
      subtitle={`${leave.substitute_name || "Your substitute"} declined.`}
      submitLabel="Nominate" submitting={nominate.isPending}
      error={nominate.error} disabled={!substitute}
      onSubmit={() => nominate.mutate({
        id: leave.id, substitute_user_id: substitute!,
      }, {
        onSuccess: () => done("Substitute asked", "Routing resumes once they accept."),
        onError: fail,
      })}
    >
      <ColleaguePicker value={substitute} required
        onChange={(id) => setSubstitute(id)} />
    </FormModal>
  );
}
