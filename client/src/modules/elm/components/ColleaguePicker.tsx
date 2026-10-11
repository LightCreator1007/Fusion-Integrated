import { useState } from "react";
import { Select } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";

import { useColleagues } from "../api/hooks";

/** Type-ahead over faculty and staff, for naming a substitute.
 *
 *  The server refuses anything under two characters, so the query is gated
 *  here too rather than sending a request that cannot succeed. */
export function ColleaguePicker({ value, onChange, label = "Substitute", required }: {
  value: number | null;
  onChange: (userId: number | null, name: string) => void;
  label?: string;
  required?: boolean;
}) {
  const [text, setText] = useState("");
  const [debounced] = useDebouncedValue(text, 250);
  const { data, isFetching } = useColleagues(debounced);
  const [picked, setPicked] = useState<{ value: string; label: string } | null>(null);

  const options = (data ?? []).map((c) => ({
    value: String(c.user_id),
    label: c.department ? `${c.display_name} (${c.department})` : c.display_name,
  }));
  if (picked && !options.some((o) => o.value === picked.value)) options.unshift(picked);

  return (
    <Select
      label={label} required={required} searchable clearable
      placeholder="Type at least two letters of a name"
      data={options} value={value == null ? null : String(value)}
      searchValue={text} onSearchChange={setText}
      filter={({ options: o }) => o}      // the server already filtered
      nothingFoundMessage={
        debounced.trim().length < 2 ? "Keep typing…"
          : isFetching ? "Searching…" : "No colleague found"}
      onChange={(v) => {
        const option = options.find((o) => o.value === v) ?? null;
        setPicked(option);
        onChange(v ? Number(v) : null, option?.label ?? "");
      }}
    />
  );
}
