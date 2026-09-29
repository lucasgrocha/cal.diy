import { useState } from "react";

import dayjs from "@calcom/dayjs";
import { useBookerTime } from "@calcom/features/bookings/Booker/hooks/useBookerTime";
import { useLocale } from "@calcom/lib/hooks/useLocale";
import { Button } from "@calcom/ui/components/button";

import { pickRandomAvailableSlot } from "~/schedules/lib/pickRandomAvailableSlot";
import type { Slot, Slots } from "~/schedules/lib/types";

type ChooseForMeSlotProps = {
  slots: Slots | undefined;
  unavailableTimeSlots: string[];
  disabled?: boolean;
  onConfirm: (slot: Slot) => void;
};

/**
 * Lets the booker draw a random available slot instead of scanning the grid
 * themselves. Drawing a slot doesn't book it immediately - it's shown back to
 * the booker, who then explicitly confirms or dismisses it.
 */
export const ChooseForMeSlot = ({
  slots,
  unavailableTimeSlots,
  disabled,
  onConfirm,
}: ChooseForMeSlotProps) => {
  const { t } = useLocale();
  const { timezone, timeFormat } = useBookerTime();
  const [suggestedSlot, setSuggestedSlot] = useState<Slot | null>(null);
  const [noSlotsFound, setNoSlotsFound] = useState(false);

  const onChooseForMe = () => {
    const slot = pickRandomAvailableSlot(slots, unavailableTimeSlots);
    setSuggestedSlot(slot);
    setNoSlotsFound(!slot);
  };

  const onDismiss = () => {
    setSuggestedSlot(null);
    setNoSlotsFound(false);
  };

  if (suggestedSlot) {
    const suggestedDate = dayjs.utc(suggestedSlot.time).tz(timezone);
    return (
      <div className="mb-3 flex flex-col gap-2 rounded-md border border-subtle bg-subtle p-3 text-sm">
        <p className="text-emphasis">
          {t("choose_for_me_suggested_time", {
            time: suggestedDate.format(timeFormat),
            date: suggestedDate.format("dddd, MMMM D"),
          })}
        </p>
        <div className="flex gap-2">
          <Button color="primary" onClick={() => onConfirm(suggestedSlot)}>
            {t("book_this_time")}
          </Button>
          <Button color="secondary" onClick={onDismiss}>
            {t("nevermind")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-3 flex flex-col gap-2">
      <Button color="secondary" disabled={disabled} onClick={onChooseForMe}>
        {t("choose_for_me")}
      </Button>
      {noSlotsFound && <p className="text-sm text-subtle">{t("no_available_slots")}</p>}
    </div>
  );
};
