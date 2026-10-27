import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { FilterKey } from "@/lib/filters";
import { STATUS_META } from "@/lib/status";
import type { Stats, TicketStatus } from "@/types/ticket";

const ORDER: TicketStatus[] = [
  "awaiting_human",
  "resolved",
  "escalated",
  "quarantined",
  "delegated",
  "discarded",
  "open",
  "awaiting_sender_reply",
];

export function StatTiles({
  stats,
  filter,
  onSelect,
}: {
  stats: Stats;
  filter: FilterKey;
  onSelect: (filter: FilterKey) => void;
}) {
  const total = ORDER.reduce((sum, status) => sum + (stats[status] ?? 0), 0);
  const tiles: Array<{ key: FilterKey; label: string; count: number; border: string }> = [
    { key: "all", label: "All tickets", count: total, border: "border-l-foreground/50" },
    ...ORDER.filter((status) => status !== "open" || (stats.open ?? 0) > 0).map((status) => ({
      key: status,
      label: STATUS_META[status].label,
      count: stats[status] ?? 0,
      border: STATUS_META[status].borderClassName,
    })),
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">
      {tiles.map((tile) => (
        <Card
          key={tile.key}
          className={cn(
            "gap-0 border-l-4 py-0 transition-shadow",
            tile.border,
            filter === tile.key && "ring-2 ring-primary",
          )}
        >
          <button
            type="button"
            className="w-full px-4 py-3 text-left"
            onClick={() => onSelect(tile.key)}
            aria-pressed={filter === tile.key}
          >
            <span className="block text-2xl font-semibold tabular-nums">{tile.count}</span>
            <span className="block truncate text-xs text-muted-foreground">{tile.label}</span>
          </button>
        </Card>
      ))}
    </div>
  );
}
