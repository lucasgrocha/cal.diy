import enTranslations from "@calcom/i18n/locales/en/common.json";
import { fireEvent, render, screen } from "@testing-library/react";
import { createInstance } from "i18next";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { EventDuration, getDurationFormatted, getDurationLabelFormatted } from "./Duration";

const { i18n, mockStore } = vi.hoisted(() => {
  return {
    i18n: { t: (key: string) => key } as { t: (...args: unknown[]) => string },
    mockStore: {
      selectedDuration: null as number | null,
      setSelectedDuration: (() => undefined) as (duration: number | null) => void,
      state: "selecting_date",
    },
  };
});

vi.mock("@calcom/lib/hooks/useLocale", () => ({
  useLocale: () => ({ t: i18n.t, i18n: { language: "en" } }),
}));

vi.mock("@calcom/features/bookings/Booker/BookerStoreProvider", () => ({
  useBookerStoreContext: (selector: (state: typeof mockStore) => unknown) => selector(mockStore),
}));

vi.mock("@calcom/atoms/hooks/useIsPlatform", () => ({
  useIsPlatform: () => false,
}));

vi.mock("@calcom/web/modules/apps/components/AllApps", () => ({
  useShouldShowArrows: () => ({
    ref: { current: null },
    calculateScroll: () => undefined,
    leftVisible: false,
    rightVisible: false,
  }),
}));

const instance = createInstance();
instance.init({
  lng: "en",
  resources: { en: { common: enTranslations } },
  defaultNS: "common",
  interpolation: { escapeValue: false },
  initImmediate: false,
});
i18n.t = instance.t.bind(instance) as typeof i18n.t;

describe("getDurationFormatted", () => {
  test("keeps the short visible format", () => {
    expect(getDurationFormatted(30, instance.t)).toBe("30m");
    expect(getDurationFormatted(60, instance.t)).toBe("1h");
    expect(getDurationFormatted(90, instance.t)).toBe("1h 30m");
  });
});

describe("getDurationLabelFormatted", () => {
  test("uses full units", () => {
    expect(getDurationLabelFormatted(undefined, instance.t)).toBeNull();
    expect(getDurationLabelFormatted(1, instance.t)).toBe("1 minute");
    expect(getDurationLabelFormatted(30, instance.t)).toBe("30 minutes");
    expect(getDurationLabelFormatted(120, instance.t)).toBe("2 hours");
    expect(getDurationLabelFormatted(90, instance.t)).toBe("1 hour 30 minutes");
  });
});

describe("EventDuration", () => {
  beforeEach(() => {
    mockStore.selectedDuration = null;
    mockStore.setSelectedDuration = vi.fn();
    mockStore.state = "selecting_date";
  });

  test("adds an accessible label to a fixed duration without changing the visible text", () => {
    render(<EventDuration event={{ length: 30, metadata: {}, isDynamic: false }} />);

    const element = screen.getByLabelText("Duration: 30 minutes");
    expect(element).toHaveTextContent(/^30m$/);
  });

  test("uses full units for durations over an hour", () => {
    render(<EventDuration event={{ length: 90, metadata: {}, isDynamic: false }} />);

    const element = screen.getByLabelText("Duration: 1 hour 30 minutes");
    expect(element).toHaveTextContent(/^1h 30m$/);
  });

  test("adds the accessible label when the duration selector is hidden", () => {
    mockStore.selectedDuration = 60;
    render(
      <EventDuration
        event={{
          length: 30,
          metadata: { multipleDuration: [30, 60], hideDurationSelectorInBookingPage: true },
          isDynamic: false,
        }}
      />
    );

    const element = screen.getByLabelText("Duration: 1 hour");
    expect(element).toHaveTextContent(/^1h$/);
  });

  test("keeps the multiple duration selector unchanged", () => {
    mockStore.selectedDuration = 30;
    render(
      <EventDuration event={{ length: 30, metadata: { multipleDuration: [30, 60] }, isDynamic: false }} />
    );

    expect(screen.queryByLabelText(/Duration:/)).toBeNull();
    expect(screen.getByTestId("multiple-choice-30mins")).toHaveTextContent("30m");
    const option = screen.getByTestId("multiple-choice-60mins");
    expect(option).toHaveTextContent("1h");

    fireEvent.click(option);
    expect(mockStore.setSelectedDuration).toHaveBeenCalledWith(60);
  });
});
