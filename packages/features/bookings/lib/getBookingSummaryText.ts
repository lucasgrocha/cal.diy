import type { TFunction } from "i18next";

export type BookingSummaryTextInput = {
  title: string;
  formattedDate: string;
  formattedTimeRange: string;
  formattedTimeZone: string;
  location?: string | null;
  t: TFunction;
};

export function getBookingSummaryText({
  title,
  formattedDate,
  formattedTimeRange,
  formattedTimeZone,
  location,
  t,
}: BookingSummaryTextInput): string {
  const lines = [title, formattedDate, `${formattedTimeRange} (${formattedTimeZone})`];

  if (location) {
    lines.push(`${t("where")}: ${location}`);
  }

  return lines.join("\n");
}
