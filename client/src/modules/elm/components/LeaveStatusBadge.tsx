import { Badge } from "@mantine/core";

import { STATUS_COLORS } from "../api/labels";
import type { RequestStatus } from "../api/types";

export function LeaveStatusBadge({ status }: { status: RequestStatus }) {
  return (
    <Badge color={STATUS_COLORS[status] ?? "gray"} variant="light" size="sm">
      {status}
    </Badge>
  );
}
