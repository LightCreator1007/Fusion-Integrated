import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { http } from "../../../lib/http";
import { useApply, useColleagues, useDecide, useMyLeaves } from "./hooks";

function setup() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  return { qc, wrapper };
}

describe("ELM hooks", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("posts an application to the ELM endpoint", async () => {
    const post = vi.spyOn(http, "post").mockResolvedValue({ data: { id: 1 } });
    const { wrapper } = setup();
    const { result } = renderHook(() => useApply(), { wrapper });

    result.current.mutate({
      category: "CL", start_date: "2026-03-09", end_date: "2026-03-09", reason: "x",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(post).toHaveBeenCalledWith("/elm/applications", expect.objectContaining({
      category: "CL", start_date: "2026-03-09",
    }));
  });

  it("refetches the lists after a decision", async () => {
    vi.spyOn(http, "post").mockResolvedValue({ data: {} });
    const { qc, wrapper } = setup();
    const invalidate = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useDecide(), { wrapper });

    result.current.mutate({ id: 7, outcome: "approved" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(http.post).toHaveBeenCalledWith(
      "/elm/tasks/7/decide", { outcome: "approved", remark: "" });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["elm"] });
  });

  it("does not search colleagues for fewer than two characters", () => {
    const get = vi.spyOn(http, "get");
    const { wrapper } = setup();
    renderHook(() => useColleagues("a"), { wrapper });
    expect(get).not.toHaveBeenCalled();
  });

  it("passes the status filter to the server", async () => {
    const get = vi.spyOn(http, "get").mockResolvedValue({ data: { results: [] } });
    const { wrapper } = setup();
    const { result } = renderHook(() => useMyLeaves("pending"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(get).toHaveBeenCalledWith("/elm/applications",
      { params: { limit: 100, status: "pending" } });
  });
});
