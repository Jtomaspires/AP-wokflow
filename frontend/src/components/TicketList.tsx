import type { Ticket } from "../types/ticket";
import { formatLocal } from "../lib/time";
import { StatusBadge } from "./StatusBadge";

export function TicketList({
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
  if (loading) {
    return <p className="p-4 text-sm text-slate-500">Loading tickets…</p>;
  }
  if (tickets.length === 0) {
    return (
      <p className="p-4 text-sm text-slate-500">
        No tickets. Ingest one with POST /webhook/mock.
      </p>
    );
  }
  return (
    <div className="overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">Subject</th>
            <th className="px-3 py-2 font-medium">Sender</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Intent</th>
            <th className="px-3 py-2 font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => {
            const selected = ticket.id === selectedId;
            return (
              <tr
                key={ticket.id}
                onClick={() => onSelect(ticket.id)}
                className={`cursor-pointer border-t border-slate-100 ${
                  selected ? "bg-slate-100" : "hover:bg-slate-50"
                }`}
              >
                <td className="max-w-[12rem] truncate px-3 py-2" title={ticket.subject}>
                  {ticket.subject}
                  {ticket.confidence != null && (
                    <span className="ml-2 text-xs text-slate-400">
                      {ticket.confidence.toFixed(2)}
                    </span>
                  )}
                </td>
                <td className="max-w-[10rem] truncate px-3 py-2 text-slate-600">
                  {ticket.sender_email}
                </td>
                <td className="px-3 py-2">
                  <StatusBadge status={ticket.status} />
                </td>
                <td className="px-3 py-2 text-slate-600">
                  {ticket.intent?.replaceAll("_", " ") ?? "—"}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                  {formatLocal(ticket.updated_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
