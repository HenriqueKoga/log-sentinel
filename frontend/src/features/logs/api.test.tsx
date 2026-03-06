import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useLogs } from "./api";
import { http } from "../../shared/api/http";

vi.mock("../../shared/api/http");

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useLogs", () => {
  beforeEach(() => {
    vi.mocked(http.get).mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            timestamp: "2026-03-04T12:00:00Z",
            level: "error",
            message: "test",
            project_id: 1,
            project_name: "Backend",
            source: "api",
          },
        ],
        total: 1,
      },
      status: 200,
      statusText: "OK",
      headers: {},
      config: {} as never,
    });
  });

  it("fetches logs and returns data", async () => {
    const { result } = renderHook(() => useLogs({ page: 1, page_size: 50 }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].level).toBe("error");
    expect(result.current.data?.total).toBe(1);
  });

  it("calls API with query params", async () => {
    renderHook(
      () => useLogs({ q: "foo", level: ["error"], project_id: 1, page: 2, page_size: 10 }),
      { wrapper }
    );
    await waitFor(() => {
      expect(http.get).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/v1\/logs\?.*page=2.*page_size=10/)
      );
    });
  });
});
