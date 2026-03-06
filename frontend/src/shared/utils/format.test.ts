import { describe, it, expect } from "vitest";
import { formatDateTime, formatNumber } from "./format";

describe("formatNumber", () => {
  it("returns '-' for null", () => {
    expect(formatNumber(null)).toBe("-");
  });
  it("returns '-' for undefined", () => {
    expect(formatNumber(undefined)).toBe("-");
  });
  it("formats positive integer", () => {
    expect(formatNumber(42)).toBe("42");
  });
  it("formats zero", () => {
    expect(formatNumber(0)).toBe("0");
  });
  it("formats large number", () => {
    const out = formatNumber(1_000_000);
    expect(out).toMatch(/1[.,\s]?000[.,\s]?000/);
  });
});

describe("formatDateTime", () => {
  it("returns '-' for null", () => {
    expect(formatDateTime(null)).toBe("-");
  });
  it("returns '-' for undefined", () => {
    expect(formatDateTime(undefined)).toBe("-");
  });
  it("returns '-' for invalid date string", () => {
    expect(formatDateTime("not-a-date")).toBe("-");
  });
  it("formats valid ISO date string", () => {
    const out = formatDateTime("2026-03-04T12:00:00Z");
    expect(out).not.toBe("-");
    expect(out).toMatch(/\d/);
  });
  it("formats Date instance", () => {
    const out = formatDateTime(new Date("2026-03-04T12:00:00Z"));
    expect(out).not.toBe("-");
  });
});
