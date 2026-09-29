import type { Slot, Slots } from "./types";

/**
 * Picks a random bookable slot out of an already-fetched schedule.
 * Excludes OOO slots and any slot already flagged unavailable by the
 * quick-availability-check feature.
 */
export const pickRandomAvailableSlot = (
  slots: Slots | undefined,
  unavailableTimeSlots: string[] = []
): Slot | null => {
  const allSlots: Slot[] = Object.values(slots ?? {}).flat();
  const candidates = allSlots.filter(
    (slot) => !slot.away && !unavailableTimeSlots.includes(slot.time)
  );

  if (!candidates.length) return null;

  return candidates[Math.floor(Math.random() * candidates.length)];
};
