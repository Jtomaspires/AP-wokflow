import { useCallback, useEffect, useState } from "react";
import { HitlBar } from "./components/HitlBar";
import { MetricBar } from "./components/MetricBar";
import { TicketDetail } from "./components/TicketDetail";
import { statusForFilter, TicketFilters, type FilterKey } from "./components/TicketFilters";
import { TicketList } from "./components/TicketList";
import { ApiError, approveTicket, escalateTicket, getHealth, getStats, getTicket, getTickets } from "./lib/api";
import type { Stats, Ticket, TicketDetail as TicketDetailModel } from "./types/ticket";

export default function App() {
  const [filter, setFilter] = useState<FilterKey>("awaiting_human");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TicketDetailModel | null>(null);
  const [stats, setStats] = useState<Stats>({});
  const [healthOk, setHealthOk] = useState(false);
  const [operatorId, setOperatorId] = useState("op_joao");
  const [draftEdit, setDraftEdit] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadStatsAndHealth = useCallback(async () => {
    try {
      const health = await getHealth();
      setHealthOk(health.status === "ok");
    } catch {
      setHealthOk(false);
    }
    try {
      setStats(await getStats());
    } catch {
      setStats({});
    }
  }, []);

  const loadList = useCallback(async () => {
    setListLoading(true);
    setListError(null);
    try {
      setTickets(await getTickets(statusForFilter(filter)));
    } catch (err) {
      setTickets([]);
      setListError(err instanceof ApiError ? err.detail : "Failed to load tickets");
    } finally {
      setListLoading(false);
    }
  }, [filter]);

  const loadDetail = useCallback(async (id: string) => {
    const next = await getTicket(id);
    setDetail(next);
    setDraftEdit(next.draft?.generated_text ?? "");
    setActionError(null);
  }, []);

  const refreshAll = useCallback(async () => {
    await loadStatsAndHealth();
    await loadList();
    if (selectedId) {
      try {
        await loadDetail(selectedId);
      } catch {
        setSelectedId(null);
        setDetail(null);
      }
    }
  }, [loadDetail, loadList, loadStatsAndHealth, selectedId]);

  useEffect(() => {
    void loadStatsAndHealth();
  }, [loadStatsAndHealth]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setDraftEdit("");
      return;
    }
    void loadDetail(selectedId).catch((err) => {
      setActionError(err instanceof ApiError ? err.detail : "Failed to load ticket");
      setDetail(null);
    });
  }, [loadDetail, selectedId]);

  async function afterHitl() {
    setSelectedId(null);
    setDetail(null);
    setDraftEdit("");
    setActionError(null);
    await loadStatsAndHealth();
    await loadList();
  }

  async function onApprove() {
    if (!detail) return;
    setBusy(true);
    setActionError(null);
    try {
      const generated = detail.draft?.generated_text ?? "";
      const body: { operator_id: string; final_text?: string } = {
        operator_id: operatorId.trim(),
      };
      if (draftEdit !== generated) {
        body.final_text = draftEdit;
      }
      await approveTicket(detail.id, body);
      await afterHitl();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function onEscalate() {
    if (!detail) return;
    setBusy(true);
    setActionError(null);
    try {
      await escalateTicket(detail.id, { operator_id: operatorId.trim() });
      await afterHitl();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Escalate failed");
    } finally {
      setBusy(false);
    }
  }

  const showHitl = detail?.status === "awaiting_human";

  return (
    <div className="flex h-screen flex-col bg-slate-100 text-slate-900">
      <header className="flex h-16 shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-4">
        <div className="shrink-0">
          <p className="text-sm font-semibold">P2P AP</p>
          <p className="text-xs text-slate-500">Operator console</p>
        </div>
        <div className="min-w-0 flex-1">
          <MetricBar stats={stats} filter={filter} onSelect={setFilter} />
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span
            className={`rounded-full px-2 py-1 text-xs ${
              healthOk ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
            }`}
          >
            API {healthOk ? "ok" : "down"}
          </span>
          <label className="flex items-center gap-1 text-xs text-slate-500">
            Operator
            <input
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              className="w-28 rounded border border-slate-300 px-2 py-1 text-sm text-slate-900"
            />
          </label>
          <button
            type="button"
            onClick={() => void refreshAll()}
            className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50"
          >
            Refresh
          </button>
        </div>
      </header>

      {listError && (
        <div className="bg-red-50 px-4 py-2 text-sm text-red-800">{listError}</div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[38%] min-w-[280px] flex-col border-r border-slate-200 bg-white">
          <TicketFilters value={filter} onChange={setFilter} />
          <div className="min-h-0 flex-1 overflow-auto">
            <TicketList
              tickets={tickets}
              selectedId={selectedId}
              loading={listLoading}
              onSelect={setSelectedId}
            />
          </div>
        </aside>
        <main className="min-h-0 min-w-0 flex-1">
          <TicketDetail detail={detail} />
        </main>
      </div>

      {showHitl && detail && (
        <HitlBar
          detail={detail}
          draftEdit={draftEdit}
          onDraftChange={setDraftEdit}
          operatorId={operatorId}
          healthOk={healthOk}
          busy={busy}
          error={actionError}
          onApprove={() => void onApprove()}
          onEscalate={() => void onEscalate()}
        />
      )}
    </div>
  );
}
