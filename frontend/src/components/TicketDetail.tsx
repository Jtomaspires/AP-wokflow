import { useState } from "react";
import { formatLocal } from "../lib/time";
import type { AuditSummary, TicketDetail } from "../types/ticket";
import { StatusBadge } from "./StatusBadge";

function resolveAudit(audit: AuditSummary[]): AuditSummary | undefined {
  return [...audit].reverse().find((entry) => entry.action === "resolve");
}

export function TicketDetail({ detail }: { detail: TicketDetail | null }) {
  const [auditOpen, setAuditOpen] = useState(false);
  if (!detail) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-slate-500">
        Select a ticket from the queue.
      </div>
    );
  }
  const match = resolveAudit(detail.audit ?? []);
  const meta = (match?.metadata ?? {}) as Record<string, unknown>;
  const inHitl = detail.status === "awaiting_human";

  return (
    <div className="grid h-full min-h-0 grid-cols-2 gap-4 overflow-hidden p-4">
      <section className="min-h-0 overflow-auto rounded border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Email</h2>
        <p className="mt-2 text-base font-medium text-slate-900">{detail.subject}</p>
        <p className="mt-1 text-sm text-slate-700">{detail.sender_email}</p>
        <p className="mt-1 text-xs text-slate-500">
          {formatLocal(detail.received_at)}
        </p>
        <p className="mt-2 font-mono text-[11px] text-slate-400">
          thread {detail.thread_id}
          <br />
          message {detail.message_id}
        </p>
        <pre className="mt-4 whitespace-pre-wrap break-words text-sm text-slate-800">
          {detail.body}
        </pre>
      </section>

      <section className="min-h-0 space-y-4 overflow-auto rounded border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-900">Decision</h2>
          <StatusBadge status={detail.status} />
        </div>
        {!inHitl && (
          <p className="rounded bg-slate-100 px-3 py-2 text-xs text-slate-600">
            Not in HITL queue — read only.
          </p>
        )}

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Invoice</h3>
          {detail.invoice ? (
            <dl className="mt-1 grid grid-cols-2 gap-x-2 gap-y-1 text-sm">
              <dt className="text-slate-500">Ref</dt>
              <dd>{detail.invoice.invoice_ref}</dd>
              <dt className="text-slate-500">Amount</dt>
              <dd>
                {String(detail.invoice.amount)} {detail.invoice.currency}
              </dd>
              <dt className="text-slate-500">Stage</dt>
              <dd>{detail.invoice.stage}</dd>
              <dt className="text-slate-500">Status</dt>
              <dd>{detail.invoice.status ?? "—"}</dd>
              <dt className="text-slate-500">Due</dt>
              <dd>{detail.invoice.due_date ?? "—"}</dd>
              <dt className="text-slate-500">Clearing</dt>
              <dd>{detail.invoice.clearing_document ?? "—"}</dd>
            </dl>
          ) : (
            <p className="mt-1 text-sm text-slate-500">No SAP invoice.</p>
          )}
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Match</h3>
          {match ? (
            <p className="mt-1 text-sm">
              {String(meta.match_result ?? "—")}
              {meta.match_method ? ` · ${String(meta.match_method)}` : ""}
              {meta.invoice_ref ? ` · ${String(meta.invoice_ref)}` : ""}
            </p>
          ) : (
            <p className="mt-1 text-sm text-slate-500">No resolve audit yet.</p>
          )}
        </div>

        {detail.sender && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Sender directory
            </h3>
            <p className="mt-1 text-sm">
              {detail.sender.name} · {detail.sender.company}
            </p>
          </div>
        )}

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Draft</h3>
          {detail.draft ? (
            <div className="mt-1 space-y-1 text-sm">
              <p>
                Target {detail.draft.target} → {detail.draft.to_email}
              </p>
              <p className="text-xs text-slate-500">
                {detail.draft.attach_payment_proof ? "Payment proof attached. " : ""}
                {detail.draft.attach_invoice_pdf ? "Invoice PDF attached." : ""}
                {!detail.draft.attach_payment_proof && !detail.draft.attach_invoice_pdf
                  ? "No attachments."
                  : ""}
              </p>
              <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">
                {detail.draft.generated_text}
              </pre>
            </div>
          ) : (
            <p className="mt-1 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              No draft — requires manual review
            </p>
          )}
        </div>

        <div>
          <button
            type="button"
            className="text-xs font-medium text-slate-600 underline"
            onClick={() => setAuditOpen((open) => !open)}
          >
            {auditOpen ? "Hide audit" : `Audit (${detail.audit.length})`}
          </button>
          {auditOpen && (
            <ol className="mt-2 space-y-1 text-xs text-slate-600">
              {detail.audit.map((entry, i) => (
                <li key={`${entry.node}-${entry.action}-${i}`}>
                  {entry.node} · {entry.action}
                </li>
              ))}
            </ol>
          )}
        </div>
      </section>
    </div>
  );
}
