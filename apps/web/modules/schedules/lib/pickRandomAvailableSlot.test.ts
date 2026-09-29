import { describe, expect, it } from "vitest";

import { pickRandomAvailableSlot } from "./pickRandomAvailableSlot";

describe("pickRandomAvailableSlot", () => {
  it("returns null when slots is undefined", () => {
    expect(pickRandomAvailableSlot(undefined)).toBeNull();
  });

  it("returns null when there are no days with slots", () => {
    expect(pickRandomAvailableSlot({})).toBeNull();
  });

  it("returns null when every slot is marked away (OOO)", () => {
    const slots = {
      "2024-02-08": [{ time: "2024-02-08T10:00:00.000Z", away: true }],
    };

    expect(pickRandomAvailableSlot(slots)).toBeNull();
  });

  it("excludes slots passed in unavailableTimeSlots", () => {
    const slots = {
      "2024-02-08": [{ time: "2024-02-08T10:00:00.000Z" }],
    };

    expect(pickRandomAvailableSlot(slots, ["2024-02-08T10:00:00.000Z"])).toBeNull();
  });

  it("returns a slot from the remaining candidates", () => {
    const slots = {
      "2024-02-08": [{ time: "2024-02-08T10:00:00.000Z" }, { time: "2024-02-08T11:00:00.000Z", away: true }],
      "2024-02-09": [{ time: "2024-02-09T10:00:00.000Z" }],
    };

    const picked = pickRandomAvailableSlot(slots);

    expect(picked).not.toBeNull();
    expect(["2024-02-08T10:00:00.000Z", "2024-02-09T10:00:00.000Z"]).toContain(picked?.time);
  });
});
