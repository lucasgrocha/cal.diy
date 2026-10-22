import type { ConfigType } from "@calcom/dayjs";
import dayjs from "@calcom/dayjs";
import { formatToLocalizedDate, formatToLocalizedTime, formatToLocalizedTimezone } from "@calcom/lib/dayjs";

type BuildBookingSummaryInput = {
  title: string;
  date: ConfigType;
  durationInMinutes?: number;
  is24h: boolean;
  locale?: string;
  timeZone: string;
  location?: string;
};

export function buildBookingSummary({
  title,
  date,
  durationInMinutes,
  is24h,
  locale,
  timeZone,
  location,
}: BuildBookingSummaryInput): string {
  const parsedDate = dayjs(date);
  const dateText = formatToLocalizedDate(parsedDate, locale, "full", timeZone);
  const startTimeText = formatToLocalizedTime({ date: parsedDate, locale, hour12: !is24h, timeZone });
  const timezoneText = formatToLocalizedTimezone(parsedDate, locale, timeZone);

  const timeRangeText = durationInMinutes
    ? `${startTimeText} - ${formatToLocalizedTime({
        date: parsedDate.add(durationInMinutes, "minute"),
        locale,
        hour12: !is24h,
        timeZone,
      })}`
    : startTimeText;

  const lines = [title, `${dateText}, ${timeRangeText}`, `(${timezoneText})`];

  if (location) {
    lines.push(location);
  }

  return lines.join("\n");
}
