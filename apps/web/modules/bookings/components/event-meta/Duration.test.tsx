import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EventDuration, getDurationAriaLabel } from "./Duration";

const translate = (key: string, opts?: Record<string, unknown>) => {
  const count = opts?.count as number | undefined;
  switch (key) {
    case "minute":
      return `${count} ${count === 1 ? "minute" : "minutes"}`;
    case "hour":
      return `${count} ${count === 1 ? "hour" : "hours"}`;
    case "duration_aria_label":
      return `Duration: ${opts?.duration}`;
    case "minute_one_short":
      return "1m";
    case "hour_one_short":
      return "1h";
    case "multiple_duration_timeUnit_short":
      return `${count}${opts?.unit === "hour" ? "h" : "m"}`;
    default:
      return key;
  }
};

let mockSelectedDuration: number | null = null;

vi.mock("@calcom/lib/hooks/useLocale", () => ({
  useLocale: () => ({ t: translate }),
}));
vi.mock("@calcom/atoms/hooks/useIsPlatform", () => ({ useIsPlatform: () => false }));
vi.mock("@calcom/embed-core/embed-iframe", () => ({ useIsEmbed: () => false }));
vi.mock("@calcom/web/modules/apps/components/AllApps", () => ({
  useShouldShowArrows: () => ({
    ref: { current: null },
    calculateScroll: vi.fn(),
    leftVisible: false,
    rightVisible: false,
  }),
}));
vi.mock("@calcom/features/bookings/Booker/BookerStoreProvider", () => ({
  useBookerStoreContext: (selector: (s: unknown) => unknown) =>
    selector({ selectedDuration: mockSelectedDuration, setSelectedDuration: vi.fn(), state: "selecting_date" }),
}));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const t = translate as any;

describe("getDurationAriaLabel", () => {
  it("formats minutes, hours and combinations", () => {
    expect(getDurationAriaLabel(30, t)).toBe("Duration: 30 minutes");
    expect(getDurationAriaLabel(1, t)).toBe("Duration: 1 minute");
    expect(getDurationAriaLabel(60, t)).toBe("Duration: 1 hour");
    expect(getDurationAriaLabel(90, t)).toBe("Duration: 1 hour 30 minutes");
    expect(getDurationAriaLabel(120, t)).toBe("Duration: 2 hours");
  });

  it("returns undefined without a duration", () => {
    expect(getDurationAriaLabel(undefined, t)).toBeUndefined();
  });
});

describe("EventDuration", () => {
  it("labels a single-duration event and keeps visible text", () => {
    mockSelectedDuration = null;
    render(<EventDuration event={{ length: 30, metadata: null, isDynamic: false }} />);
    const el = screen.getByLabelText("Duration: 30 minutes");
    expect(el.textContent).toBe("30m");
  });

  it("labels the selected duration when the selector is hidden", () => {
    mockSelectedDuration = 60;
    render(
      <EventDuration
        event={{
          length: 30,
          isDynamic: false,
          metadata: { multipleDuration: [30, 60], hideDurationSelectorInBookingPage: true },
        }}
      />
    );
    expect(screen.getByLabelText("Duration: 1 hour").textContent).toBe("1h");
  });

  it("labels each selector option", () => {
    mockSelectedDuration = 30;
    render(
      <EventDuration
        event={{ length: 30, isDynamic: false, metadata: { multipleDuration: [30, 90] } }}
      />
    );
    expect(screen.getByLabelText("Duration: 30 minutes").textContent).toBe("30m");
    expect(screen.getByLabelText("Duration: 1 hour 30 minutes").textContent).toBe("1h 30m");
  });
});
