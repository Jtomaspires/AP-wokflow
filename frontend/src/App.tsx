import { useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/AppHeader";
import { HitlDialog } from "@/components/HitlDialog";
import { StatTiles } from "@/components/StatTiles";
import { TicketDetail } from "@/components/TicketDetail";
import { TicketFeed } from "@/components/TicketFeed";
import { ApiError, approveTicket, escalateTicket, getHealth, getStats, getTicket, getTickets } from "@/lib/api";
import { statusForFilter, type FilterKey } from "@/lib/filters";
import type { Stats, Ticket, TicketDetail as TicketDetailModel } from "@/types/ticket";

export default function App() {
  const [filter, setFilter] = useState<FilterKey>("awaiting_human");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TicketDetailModel | null>(null);
  const [stats, setStats] = useState<Stats>({});
  const [healthOk, setHealthOk] = useState(false);
  const [draftEdit, setDraftEdit] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

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
    setRefreshing(true);
    try {
      await Promise.all([loadStatsAndHealth(), loadList()]);
      if (selectedId) {
        try {
          await loadDetail(selectedId);
        } catch {
          setSelectedId(null);
          setDetail(null);
        }
      }
    } finally {
      setRefreshing(false);
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
    await Promise.all([loadStatsAndHealth(), loadList()]);
  }

  async function onApprove(): Promise<boolean> {
    if (!detail) return false;
    setBusy(true);
    setActionError(null);
    try {
      const generated = detail.draft?.generated_text ?? "";
      const body: { final_text?: string } = {};
      if (draftEdit !== generated) body.final_text = draftEdit;
      await approveTicket(detail.id, body);
      await afterHitl();
      return true;
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Approve failed");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function onEscalate(): Promise<boolean> {
    if (!detail) return false;
    setBusy(true);
    setActionError(null);
    try {
      await escalateTicket(detail.id);
      await afterHitl();
      return true;
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Escalate failed");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function selectFilter(next: FilterKey) {
    setFilter(next);
    setSelectedId(null);
    setDetail(null);
    setDialogOpen(false);
  }

  return (
    <div className="flex h-screen flex-col bg-muted/30 text-foreground">
      <AppHeader
        stats={stats}
        healthOk={healthOk}
        refreshing={refreshing}
        onRefresh={() => void refreshAll()}
      />

      <div className="shrink-0 p-3 md:px-5 md:py-4">
        <StatTiles stats={stats} filter={filter} onSelect={selectFilter} />
      </div>

      {listError && (
        <div role="alert" className="mx-5 mb-3 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {listError}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 px-3 pb-3 md:grid-cols-[38%_minmax(0,1fr)] md:px-5 md:pb-5">
        <section className="min-h-0 overflow-hidden rounded-xl border bg-background">
          <TicketFeed
            tickets={tickets}
            selectedId={selectedId}
            loading={listLoading}
            onSelect={setSelectedId}
          />
        </section>
        <main className="min-h-0 min-w-0">
          <TicketDetail detail={detail} onReview={() => setDialogOpen(true)} />
        </main>
      </div>

      <HitlDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        detail={detail}
        draftEdit={draftEdit}
        onDraftChange={setDraftEdit}
        healthOk={healthOk}
        busy={busy}
        error={actionError}
        onApprove={onApprove}
        onEscalate={onEscalate}
      />
    </div>
  );
}
