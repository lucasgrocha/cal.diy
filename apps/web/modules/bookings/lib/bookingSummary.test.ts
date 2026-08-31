import { describe, it, expect } from "vitest";

import { buildBookingSummary } from "./bookingSummary";

describe("buildBookingSummary", () => {
  const date = "2026-03-10T15:00:00.000Z";

  it("includes title, date, time range and timezone", () => {
    const summary = buildBookingSummary({
      title: "Product Demo",
      date,
      durationInMinutes: 30,
      is24h: true,
      locale: "en",
      timeZone: "UTC",
    });

    const lines = summary.split("\n");
    expect(lines[0]).toBe("Product Demo");
    expect(lines[1]).toContain("15:00");
    expect(lines[1]).toContain("15:30");
    expect(lines[2]).toBe("(Coordinated Universal Time)");
  });

  it("falls back to a single start time when no duration is provided", () => {
    const summary = buildBookingSummary({
      title: "Quick Chat",
      date,
      is24h: true,
      locale: "en",
      timeZone: "UTC",
    });

    const [, secondLine] = summary.split("\n");
    expect(secondLine).toContain("15:00");
    expect(secondLine).not.toContain(" - ");
  });

  it("appends the location as a final line when provided", () => {
    const summary = buildBookingSummary({
      title: "Onsite Interview",
      date,
      durationInMinutes: 60,
      is24h: true,
      locale: "en",
      timeZone: "UTC",
      location: "123 Main St",
    });

    const lines = summary.split("\n");
    expect(lines).toHaveLength(4);
    expect(lines[3]).toBe("123 Main St");
  });

  it("omits the location line when no location is given", () => {
    const summary = buildBookingSummary({
      title: "Onsite Interview",
      date,
      durationInMinutes: 60,
      is24h: true,
      locale: "en",
      timeZone: "UTC",
    });

    expect(summary.split("\n")).toHaveLength(3);
  });

  it("respects the requested timezone when formatting the time", () => {
    const summary = buildBookingSummary({
      title: "Cross Timezone Sync",
      date,
      durationInMinutes: 30,
      is24h: true,
      locale: "en",
      timeZone: "America/New_York",
    });

    const lines = summary.split("\n");
    expect(lines[1]).toContain("11:00");
    expect(lines[2]).toMatch(/Eastern/);
  });

  it("formats times in 12-hour format when is24h is false", () => {
    const summary = buildBookingSummary({
      title: "Evening Sync",
      date,
      durationInMinutes: 30,
      is24h: false,
      locale: "en",
      timeZone: "UTC",
    });

    const lines = summary.split("\n");
    expect(lines[1]).toMatch(/3:00\s?pm/i);
  });
});
