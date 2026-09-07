import type { TicketDetail } from "../types/ticket";

export function HitlBar({
  detail,
  draftEdit,
  onDraftChange,
  operatorId,
  healthOk,
  busy,
  error,
  onApprove,
  onEscalate,
}: {
  detail: TicketDetail;
  draftEdit: string;
  onDraftChange: (value: string) => void;
  operatorId: string;
  healthOk: boolean;
  busy: boolean;
  error: string | null;
  onApprove: () => void;
  onEscalate: () => void;
}) {
  const hasDraft = detail.draft != null;
  const approveDisabled = !hasDraft || !healthOk || busy || !operatorId.trim();

  return (
    <div className="flex min-h-[88px] items-stretch gap-4 border-t border-slate-200 bg-white p-3">
      <label className="flex min-w-0 flex-1 flex-col text-xs text-slate-500">
        Draft to send
        <textarea
          value={draftEdit}
          onChange={(e) => onDraftChange(e.target.value)}
          disabled={!hasDraft || busy}
          className="mt-1 min-h-[56px] flex-1 resize-none rounded border border-slate-300 p-2 text-sm text-slate-900 disabled:bg-slate-50"
        />
      </label>
      <div className="flex shrink-0 flex-col justify-end gap-2">
        {error && <p className="max-w-xs text-xs text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onEscalate}
            disabled={busy || !operatorId.trim()}
            className="rounded border border-orange-400 px-4 py-2 text-sm text-orange-800 hover:bg-orange-50 disabled:opacity-50"
          >
            Escalate
          </button>
          <button
            type="button"
            onClick={onApprove}
            disabled={approveDisabled}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
