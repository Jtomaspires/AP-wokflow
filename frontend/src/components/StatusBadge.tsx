import type { TicketStatus } from "../types/ticket";

const STYLES: Record<string, string> = {
  awaiting_human: "bg-amber-100 text-amber-900",
  resolved: "bg-green-100 text-green-900",
  escalated: "bg-orange-100 text-orange-900",
  quarantined: "bg-red-100 text-red-900",
  delegated: "bg-slate-200 text-slate-700",
  discarded: "bg-slate-200 text-slate-700",
  open: "bg-slate-200 text-slate-700",
  awaiting_sender_reply: "bg-slate-200 text-slate-700",
};

export function StatusBadge({ status }: { status: TicketStatus | string }) {
  const cls = STYLES[status] ?? "bg-slate-200 text-slate-700";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}
