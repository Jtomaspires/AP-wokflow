import type { Stats, TicketStatus } from "../types/ticket";
import type { FilterKey } from "./TicketFilters";

const CHIPS: { key: FilterKey; label: string; status?: TicketStatus }[] = [
  { key: "awaiting_human", label: "HITL", status: "awaiting_human" },
  { key: "resolved", label: "Resolved", status: "resolved" },
  { key: "escalated", label: "Escalated", status: "escalated" },
  { key: "quarantined", label: "Quarantined", status: "quarantined" },
  { key: "delegated", label: "Delegated", status: "delegated" },
  { key: "discarded", label: "Discarded", status: "discarded" },
  { key: "open", label: "Open", status: "open" },
];

export function MetricBar({
  stats,
  filter,
  onSelect,
}: {
  stats: Stats;
  filter: FilterKey;
  onSelect: (key: FilterKey) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {CHIPS.map((chip) => {
        const n = stats[chip.status ?? ""] ?? 0;
        if (chip.key === "open" && n === 0) {
          return null;
        }
        const active = filter === chip.key;
        return (
          <button
            key={chip.key}
            type="button"
            onClick={() => onSelect(chip.key)}
            className={`rounded-full border px-3 py-1 text-xs ${
              active
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
            }`}
          >
            {chip.label} {n}
          </button>
        );
      })}
    </div>
  );
}
