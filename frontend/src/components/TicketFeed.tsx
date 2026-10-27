import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { formatLocal, formatRelative } from "@/lib/time";
import type { Ticket } from "@/types/ticket";
import { StatusBadge } from "@/components/StatusBadge";

export function TicketFeed({
  tickets,
  selectedId,
  loading,
  onSelect,
}: {
  tickets: Ticket[];
  selectedId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <ScrollArea className="h-full">
      <div className="space-y-3 p-3">
        {loading &&
          Array.from({ length: 5 }, (_, index) => (
            <Card key={index} className="gap-3 p-4">
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-3 w-2/3" />
              <Skeleton className="h-2 w-full" />
            </Card>
          ))}

        {!loading && tickets.length === 0 && (
          <div className="grid min-h-48 place-items-center text-sm text-muted-foreground">
            No tickets in this view
          </div>
        )}

        {!loading &&
          tickets.map((ticket) => (
            <Card
              key={ticket.id}
              className={cn(
                "gap-0 overflow-hidden py-0 transition-colors",
                selectedId === ticket.id && "border-primary bg-accent/50",
              )}
            >
              <button
                type="button"
                className="w-full space-y-3 p-4 text-left"
                onClick={() => onSelect(ticket.id)}
                aria-pressed={selectedId === ticket.id}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold">{ticket.subject || "(no subject)"}</p>
                  <p className="truncate text-xs text-muted-foreground">{ticket.sender_email}</p>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <StatusBadge status={ticket.status} />
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="text-xs text-muted-foreground">
                        {formatRelative(ticket.received_at)}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>{formatLocal(ticket.received_at)}</TooltipContent>
                  </Tooltip>
                </div>
                {ticket.confidence !== null && (
                  <div className="space-y-1">
                    <Progress value={ticket.confidence * 100} className="h-1" />
                    <span className="sr-only">
                      Confidence {Math.round(ticket.confidence * 100)}%
                    </span>
                  </div>
                )}
              </button>
            </Card>
          ))}
      </div>
    </ScrollArea>
  );
}
