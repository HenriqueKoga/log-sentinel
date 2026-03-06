import { describe, it, expect, vi, beforeEach } from "vitest";
import axios from "axios";
import { getErrorCode, getErrorMessage } from "./errors";

describe("getErrorCode", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("returns null for non-axios error", () => {
    vi.spyOn(axios, "isAxiosError").mockReturnValue(false);
    expect(getErrorCode(new Error("x"))).toBe(null);
  });
  it("returns null when response.data.detail has no code", () => {
    const err = Object.assign(new Error("x"), {
      isAxiosError: true,
      response: { data: { detail: {} } },
    }) as unknown as import("axios").AxiosError;
    vi.spyOn(axios, "isAxiosError").mockReturnValue(true);
    expect(getErrorCode(err)).toBe(null);
  });
  it("returns code from detail", () => {
    const err = Object.assign(new Error("x"), {
      isAxiosError: true,
      response: { data: { detail: { code: "INGEST_INVALID_TOKEN" } } },
    }) as unknown as import("axios").AxiosError;
    vi.spyOn(axios, "isAxiosError").mockReturnValue(true);
    expect(getErrorCode(err)).toBe("INGEST_INVALID_TOKEN");
  });
});

describe("getErrorMessage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("returns UNKNOWN_ERROR for non-Error", () => {
    expect(getErrorMessage(null)).toBe("UNKNOWN_ERROR");
  });
  it("returns Error.message when no code", () => {
    expect(getErrorMessage(new Error("network error"))).toBe("network error");
  });
});
