import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useDashboardMetrics } from "./api";
import { http } from "../../shared/api/http";

vi.mock("../../shared/api/http");

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useDashboardMetrics", () => {
  beforeEach(() => {
    vi.mocked(http.get).mockResolvedValue({
      data: {
        log_volume: [{ ts: "10:00", value: 100 }],
        error_rate: [{ ts: "10:00", value: 0.5 }],
      },
      status: 200,
      statusText: "OK",
      headers: {},
      config: {} as never,
    });
  });

  it("fetches dashboard metrics and returns series", async () => {
    const { result } = renderHook(() => useDashboardMetrics(30), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.log_volume).toHaveLength(1);
    expect(result.current.data?.log_volume[0].ts).toBe("10:00");
    expect(result.current.data?.error_rate[0].value).toBe(0.5);
  });

  it("calls API with minutes param", async () => {
    renderHook(() => useDashboardMetrics(60), { wrapper });
    await waitFor(() => {
      expect(http.get).toHaveBeenCalledWith("/api/v1/metrics/dashboard?minutes=60");
    });
  });
});
