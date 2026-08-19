import type { RouterInputs, RouterOutputs } from "@calcom/trpc/react";
import type { WorkingHours } from "@calcom/types/schedule";

export type BookingListingStatus = NonNullable<
  RouterInputs["viewer"]["bookings"]["get"]["filters"]["statuses"]
>[number];

type BookingItem = RouterOutputs["viewer"]["bookings"]["get"]["bookings"][number];

export type BookingItemProps = BookingItem & {
  listingStatus: BookingListingStatus;
  recurringInfo: RouterOutputs["viewer"]["bookings"]["get"]["recurringInfo"][number] | undefined;
  loggedInUser: {
    userId: number | undefined;
    userTimeZone: string | undefined;
    userTimeFormat: number | null | undefined;
    userEmail: string | undefined;
    workingHours?: WorkingHours[];
    workingHoursTimeZone?: string;
  };
  isToday: boolean;
  onClick?: () => void;
};
