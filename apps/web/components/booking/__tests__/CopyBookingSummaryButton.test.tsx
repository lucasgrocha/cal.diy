import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CopyBookingSummaryButton } from "../CopyBookingSummaryButton";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

vi.mock("@calcom/lib/hooks/useLocale", () => ({
  useLocale: () => ({
    t: (key: string) => key,
  }),
}));

const copyToClipboard = vi.fn();
let isCopied = false;

vi.mock("@calcom/lib/hooks/useCopy", () => ({
  useCopy: () => ({
    copyToClipboard,
    isCopied,
  }),
}));

vi.mock("@calcom/ui/components/toast", () => ({
  showToast: vi.fn(),
}));

const defaultProps = {
  title: "Team Sync",
  formattedDate: "Monday, January 15, 2024",
  formattedTimeRange: "10:00 AM - 10:30 AM",
  formattedTimeZone: "America/New_York",
  location: "Google Meet",
};

describe("CopyBookingSummaryButton", () => {
  it("renders the copy summary label", () => {
    render(<CopyBookingSummaryButton {...defaultProps} />);

    expect(screen.getByTestId("copy-booking-summary")).toHaveTextContent("copy_summary");
  });

  it("copies the composed summary text, including the location, when clicked", () => {
    render(<CopyBookingSummaryButton {...defaultProps} />);

    fireEvent.click(screen.getByTestId("copy-booking-summary"));

    expect(copyToClipboard).toHaveBeenCalledTimes(1);
    const [summary] = copyToClipboard.mock.calls[0];
    expect(summary).toBe(
      [
        "Team Sync",
        "Monday, January 15, 2024",
        "10:00 AM - 10:30 AM (America/New_York)",
        "where: Google Meet",
      ].join("\n")
    );
  });

  it("omits the location line when there is no location", () => {
    render(<CopyBookingSummaryButton {...defaultProps} location={null} />);

    fireEvent.click(screen.getByTestId("copy-booking-summary"));

    const [summary] = copyToClipboard.mock.calls[0];
    expect(summary).toBe(
      ["Team Sync", "Monday, January 15, 2024", "10:00 AM - 10:30 AM (America/New_York)"].join("\n")
    );
  });

  it("shows the copied label once copying has succeeded", () => {
    isCopied = true;
    render(<CopyBookingSummaryButton {...defaultProps} />);

    expect(screen.getByTestId("copy-booking-summary")).toHaveTextContent("copied");
    isCopied = false;
  });
});
