import {
  Crosshair,
  FileSearch,
  Filter,
  GitBranch,
  Inbox,
  PenLine,
  Route,
  Send,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  UserSearch,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatLocal } from "@/lib/time";
import type { AuditSummary, TicketDetail as TicketDetailModel } from "@/types/ticket";

function resolveAudit(audit: AuditSummary[]): AuditSummary | undefined {
  return [...audit].reverse().find((entry) => entry.action === "resolve");
}

const NODE_ICONS: Record<string, LucideIcon> = {
  ingest: Inbox,
  security: ShieldCheck,
  thread: GitBranch,
  triage: Filter,
  intent: Crosshair,
  sender: UserSearch,
  routing: Route,
  resolution: FileSearch,
  draft: PenLine,
  hitl: UserCheck,
  send: Send,
};

function Value({ children }: { children: ReactNode }) {
  return <dd className="break-words text-right font-medium">{children || "—"}</dd>;
}

export function TicketDetail({
  detail,
  onReview,
}: {
  detail: TicketDetailModel | null;
  onReview: () => void;
}) {
  if (!detail) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
        Select a ticket from the queue.
      </div>
    );
  }
  const match = resolveAudit(detail.audit ?? []);
  const meta = match?.metadata ?? {};
  const inHitl = detail.status === "awaiting_human";
  const draftAudit = [...detail.audit].reverse().find((entry) => entry.node === "draft");
  const draftMeta = draftAudit?.metadata ?? {};

  return (
    <Card className="flex h-full min-h-0 flex-col gap-0 overflow-hidden py-0">
      <div className="flex shrink-0 items-start justify-between gap-4 p-5">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-lg font-semibold">{detail.subject || "(no subject)"}</h2>
            <StatusBadge status={detail.status} />
          </div>
          <p className="text-sm text-muted-foreground">{detail.sender_email}</p>
        </div>
        {inHitl && (
          <Button onClick={onReview}>
            <UserCheck />
            Review & decide
          </Button>
        )}
      </div>
      <Separator />

      <Tabs
        key={detail.id}
        defaultValue={inHitl ? "draft" : "audit"}
        className="min-h-0 flex-1 gap-0"
      >
        <TabsList className="mx-5 mt-4 grid w-auto grid-cols-4">
          <TabsTrigger value="email">Email</TabsTrigger>
          <TabsTrigger value="invoice">Invoice</TabsTrigger>
          <TabsTrigger value="draft">Draft</TabsTrigger>
          <TabsTrigger value="audit">Audit</TabsTrigger>
        </TabsList>

        <ScrollArea className="min-h-0 flex-1">
          <TabsContent value="email" className="space-y-5 p-5">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">From</dt>
              <dd>{detail.sender_email}</dd>
              <dt className="text-muted-foreground">Received</dt>
              <dd>{formatLocal(detail.received_at)}</dd>
              <dt className="text-muted-foreground">Subject</dt>
              <dd>{detail.subject}</dd>
            </dl>
            {detail.is_thread_continuation && (
              <Badge variant="secondary">Thread continuation</Badge>
            )}
            <Separator />
            <p className="whitespace-pre-wrap text-sm leading-6">{detail.body}</p>
          </TabsContent>

          <TabsContent value="invoice" className="space-y-5 p-5">
            {detail.invoice ? (
              <>
                {detail.invoice.status === "paid" && !detail.invoice.clearing_document && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                    SAP shows paid, no clearing document — do not confirm payment
                  </div>
                )}
                <dl className="grid grid-cols-[minmax(8rem,1fr)_minmax(8rem,2fr)] gap-x-6 gap-y-3 text-sm">
                  <dt className="text-muted-foreground">Reference</dt>
                  <Value>{detail.invoice.invoice_ref}</Value>
                  <dt className="text-muted-foreground">Supplier</dt>
                  <Value>{detail.invoice.supplier_name}</Value>
                  <dt className="text-muted-foreground">Amount</dt>
                  <Value>{`${detail.invoice.amount} ${detail.invoice.currency}`}</Value>
                  <dt className="text-muted-foreground">Stage</dt>
                  <Value>{detail.invoice.stage}</Value>
                  <dt className="text-muted-foreground">Status</dt>
                  <Value>{detail.invoice.status}</Value>
                  <dt className="text-muted-foreground">Due date</dt>
                  <Value>{detail.invoice.due_date}</Value>
                  <dt className="text-muted-foreground">Clearing document</dt>
                  <Value>{detail.invoice.clearing_document}</Value>
                  <dt className="text-muted-foreground">Payment date</dt>
                  <Value>{detail.invoice.payment_date}</Value>
                  <dt className="text-muted-foreground">Approval owner</dt>
                  <Value>{detail.invoice.approval_owner_email}</Value>
                  <dt className="text-muted-foreground">Blocking reason</dt>
                  <Value>{detail.invoice.payment_blocking_reason}</Value>
                </dl>
                <Separator />
                <div className="text-sm">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Match
                  </p>
                  <p className="mt-1">
                    {String(meta.match_result ?? "—")}
                    {meta.match_method ? ` · ${String(meta.match_method)}` : ""}
                    {match?.confidence !== null && match?.confidence !== undefined
                      ? ` · ${Math.round(match.confidence * 100)}%`
                      : ""}
                  </p>
                </div>
              </>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">No invoice matched</p>
            )}
          </TabsContent>

          <TabsContent value="draft" className="space-y-4 p-5">
            {detail.draft ? (
              <>
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <Badge variant="secondary">{detail.draft.target}</Badge>
                  <span className="text-muted-foreground">to</span>
                  <span>{detail.draft.to_email}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {detail.draft.attach_payment_proof && (
                    <Badge variant="outline">Payment proof attached</Badge>
                  )}
                  {detail.draft.attach_invoice_pdf && (
                    <Badge variant="outline">Invoice PDF attached</Badge>
                  )}
                  {detail.draft.edited_by_human && <Badge variant="outline">Edited by human</Badge>}
                </div>
                <div className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm leading-6">
                  {detail.draft.final_text ?? detail.draft.generated_text}
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                {draftMeta.skipped
                  ? `No draft — this case needs a human decision (match: ${String(draftMeta.match_result ?? "unknown")})`
                  : "No draft available"}
              </div>
            )}
          </TabsContent>

          <TabsContent value="audit" className="p-5">
            <ol className="relative ml-4 border-l">
              {detail.audit.map((entry, index) => {
                const Icon =
                  entry.node === "security" && entry.action === "quarantine"
                    ? ShieldAlert
                    : (NODE_ICONS[entry.node] ?? FileSearch);
                return (
                  <li
                    key={`${entry.node}-${entry.action}-${index}`}
                    className="relative pb-6 pl-8 last:pb-0"
                  >
                    <span className="absolute -left-4 grid size-8 place-items-center rounded-full border bg-background">
                      <Icon className="size-4" />
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium capitalize">{entry.node}</span>
                      <Badge variant="outline">{entry.action}</Badge>
                      {entry.confidence !== null && (
                        <span className="text-xs text-muted-foreground">
                          {Math.round(entry.confidence * 100)}%
                        </span>
                      )}
                    </div>
                    <time className="text-xs text-muted-foreground">
                      {formatLocal(entry.created_at)}
                    </time>
                  </li>
                );
              })}
            </ol>
          </TabsContent>
        </ScrollArea>
      </Tabs>
    </Card>
  );
}
