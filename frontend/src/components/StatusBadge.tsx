import { Badge } from "@/components/ui/badge";
import { STATUS_META } from "@/lib/status";
import type { TicketStatus } from "@/types/ticket";

export function StatusBadge({ status }: { status: TicketStatus | string }) {
  const meta = STATUS_META[status as TicketStatus];
  return (
    <Badge variant="outline" className={meta?.className ?? "border-muted bg-muted text-muted-foreground"}>
      {meta?.label ?? status.replaceAll("_", " ")}
    </Badge>
  );
}
