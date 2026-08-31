import type { TFunction } from "i18next";
import { describe, expect, it } from "vitest";
import { getBookingSummaryText } from "./getBookingSummaryText";

const mockT = ((key: string) => (key === "where" ? "Where" : key)) as TFunction;

describe("getBookingSummaryText", () => {
  it("includes title, date, time range with timezone, and location", () => {
    const result = getBookingSummaryText({
      title: "Team Sync",
      formattedDate: "Monday, January 15, 2024",
      formattedTimeRange: "10:00 AM - 10:30 AM",
      formattedTimeZone: "America/New_York",
      location: "Google Meet",
      t: mockT,
    });

    expect(result).toBe(
      [
        "Team Sync",
        "Monday, January 15, 2024",
        "10:00 AM - 10:30 AM (America/New_York)",
        "Where: Google Meet",
      ].join("\n")
    );
  });

  it("omits the location line when location is null", () => {
    const result = getBookingSummaryText({
      title: "Team Sync",
      formattedDate: "Monday, January 15, 2024",
      formattedTimeRange: "10:00 AM - 10:30 AM",
      formattedTimeZone: "America/New_York",
      location: null,
      t: mockT,
    });

    expect(result).toBe(
      ["Team Sync", "Monday, January 15, 2024", "10:00 AM - 10:30 AM (America/New_York)"].join("\n")
    );
  });

  it("omits the location line when location is an empty string", () => {
    const result = getBookingSummaryText({
      title: "Team Sync",
      formattedDate: "Monday, January 15, 2024",
      formattedTimeRange: "10:00 AM - 10:30 AM",
      formattedTimeZone: "America/New_York",
      location: "",
      t: mockT,
    });

    expect(result).toBe(
      ["Team Sync", "Monday, January 15, 2024", "10:00 AM - 10:30 AM (America/New_York)"].join("\n")
    );
  });

  it("omits the location line when location is undefined", () => {
    const result = getBookingSummaryText({
      title: "Team Sync",
      formattedDate: "Monday, January 15, 2024",
      formattedTimeRange: "10:00 AM - 10:30 AM",
      formattedTimeZone: "America/New_York",
      t: mockT,
    });

    expect(result).toBe(
      ["Team Sync", "Monday, January 15, 2024", "10:00 AM - 10:30 AM (America/New_York)"].join("\n")
    );
  });
});
