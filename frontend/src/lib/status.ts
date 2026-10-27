import type { TicketStatus } from "@/types/ticket";

export const STATUS_META: Record<
  TicketStatus,
  { label: string; className: string; borderClassName: string }
> = {
  awaiting_human: {
    label: "Awaiting human",
    className: "border-amber-200 bg-amber-100 text-amber-900",
    borderClassName: "border-l-amber-500",
  },
  resolved: {
    label: "Resolved",
    className: "border-emerald-200 bg-emerald-100 text-emerald-900",
    borderClassName: "border-l-emerald-500",
  },
  escalated: {
    label: "Escalated",
    className: "border-red-200 bg-red-100 text-red-900",
    borderClassName: "border-l-red-500",
  },
  quarantined: {
    label: "Quarantined",
    className: "border-rose-200 bg-rose-100 text-rose-900",
    borderClassName: "border-l-rose-500",
  },
  delegated: {
    label: "Delegated",
    className: "border-sky-200 bg-sky-100 text-sky-900",
    borderClassName: "border-l-sky-500",
  },
  discarded: {
    label: "Discarded",
    className: "border-slate-200 bg-slate-100 text-slate-700",
    borderClassName: "border-l-slate-500",
  },
  open: {
    label: "Open",
    className: "border-blue-200 bg-blue-100 text-blue-900",
    borderClassName: "border-l-blue-500",
  },
  awaiting_sender_reply: {
    label: "Awaiting sender",
    className: "border-violet-200 bg-violet-100 text-violet-900",
    borderClassName: "border-l-violet-500",
  },
};
