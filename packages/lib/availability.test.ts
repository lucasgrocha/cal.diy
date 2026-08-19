import { describe, expect, it } from "vitest";

import { isTimeOutsideWorkingHours } from "./availability";

// Mon-Fri 09:00-17:00
const workingHours = [
  {
    days: [1, 2, 3, 4, 5],
    startTime: 9 * 60,
    endTime: 17 * 60,
  },
];

describe("isTimeOutsideWorkingHours", () => {
  it("returns false for a time within working hours", () => {
    expect(isTimeOutsideWorkingHours("2024-05-06T10:00:00Z", workingHours, "UTC")).toBe(false);
  });

  it("returns true for a time before working hours start", () => {
    expect(isTimeOutsideWorkingHours("2024-05-06T07:00:00Z", workingHours, "UTC")).toBe(true);
  });

  it("returns true for a time after working hours end", () => {
    expect(isTimeOutsideWorkingHours("2024-05-06T18:00:00Z", workingHours, "UTC")).toBe(true);
  });

  it("returns true for a time on a day without any working hours", () => {
    // 2024-05-05 is a Sunday
    expect(isTimeOutsideWorkingHours("2024-05-05T10:00:00Z", workingHours, "UTC")).toBe(true);
  });

  it("returns false when no working hours are defined", () => {
    expect(isTimeOutsideWorkingHours("2024-05-05T10:00:00Z", [], "UTC")).toBe(false);
  });

  it("localises the time to the given timeZone before comparing", () => {
    // 10:00 UTC is 06:00 in America/New_York, before working hours start
    expect(isTimeOutsideWorkingHours("2024-05-06T10:00:00Z", workingHours, "America/New_York")).toBe(true);
    // 14:00 UTC is 10:00 in America/New_York, within working hours
    expect(isTimeOutsideWorkingHours("2024-05-06T14:00:00Z", workingHours, "America/New_York")).toBe(false);
  });
});
