import type { TicketStatus } from "@/types/ticket";

export type FilterKey = "all" | TicketStatus;

export function statusForFilter(filter: FilterKey): TicketStatus | undefined {
  return filter === "all" ? undefined : filter;
}
