import { moveAgeMinutes } from "./moveAge";

export const NOTE_AGE_NOTE =
  "Age of this note on this machine. Not an instruction to trade. No order is sent.";

export function noteAgeLine(createdAt: string, now: number): string {
  const minutes = moveAgeMinutes(createdAt, now);
  if (minutes === null) {
    return "Note age is unavailable.";
  }
  const unit = minutes === 1 ? "minute" : "minutes";
  return `Note age ${minutes} ${unit}.`;
}
