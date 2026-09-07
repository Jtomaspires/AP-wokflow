import type { TicketStatus } from "../types/ticket";

export type FilterKey = "all" | TicketStatus;

const TABS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "awaiting_human", label: "HITL" },
  { key: "delegated", label: "Delegated" },
  { key: "quarantined", label: "Quarantined" },
  { key: "escalated", label: "Escalated" },
  { key: "resolved", label: "Resolved" },
];

export function TicketFilters({
  value,
  onChange,
}: {
  value: FilterKey;
  onChange: (key: FilterKey) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 border-b border-slate-200">
      {TABS.map((tab) => {
        const active = value === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={`px-3 py-2 text-sm ${
              active
                ? "border-b-2 border-slate-900 font-medium text-slate-900"
                : "text-slate-500 hover:text-slate-800"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

export function statusForFilter(filter: FilterKey): TicketStatus | undefined {
  return filter === "all" ? undefined : filter;
}
