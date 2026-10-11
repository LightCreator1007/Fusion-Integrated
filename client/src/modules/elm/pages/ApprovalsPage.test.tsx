import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { http } from "../../../lib/http";
import type { Task } from "../api/types";
import ApprovalsPage from "./ApprovalsPage";

function task(over: Partial<Task>): Task {
  return {
    id: 1, role: "unit_head", mode: "final", status: "pending",
    assignee_user_id: 20, created_at: "2026-03-02T09:00:00Z",
    application: {
      id: 5, kind: "leave", category: "CL", applicant_user_id: 10,
      applicant_name: "Asha Verma", start_date: "2026-03-09",
      end_date: "2026-03-09", days: "1.00", half_day: "", reason: "Family",
      station_leave: false, station_destination: "", recommendation: "",
    },
    resumption: null,
    ...over,
  };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MantineProvider><ApprovalsPage /></MantineProvider>
    </QueryClientProvider>,
  );
}

describe("ApprovalsPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("offers each task only the outcomes its step allows", async () => {
    vi.spyOn(http, "get").mockResolvedValue({
      data: {
        results: [
          task({ id: 1, role: "unit_head", mode: "final" }),
          task({ id: 2, role: "unit_head", mode: "recommend" }),
          task({ id: 3, role: "substitute", mode: "consent" }),
        ],
        next: null, previous: null,
      },
    });
    renderPage();

    expect(await screen.findAllByText("Asha Verma")).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: "Approve" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Reject" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Recommend" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Do not recommend" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decline" })).toBeInTheDocument();
  });

  it("says plainly when nothing is waiting", async () => {
    vi.spyOn(http, "get").mockResolvedValue({
      data: { results: [], next: null, previous: null },
    });
    renderPage();
    expect(await screen.findByText("Nothing is waiting on you")).toBeInTheDocument();
  });
});
