# Day 10 — Operator console redesign with shadcn/ui (~4h)

> Replace the hand-rolled Tailwind components with [shadcn/ui](https://ui.shadcn.com). Same data, same API calls, same HITL rules — only the presentation changes (plus one small backend tweak for the audit timeline).
>
> Previous: [PLAN_DAY9.md](PLAN_DAY9.md). Next: [PLAN_DAY11.md](PLAN_DAY11.md). Charter: [README.md](README.md).

**Status:** done. The checklist below is the original brief and was not re-ticked. The shadcn console (tiles, feed, tabs, review dialog) is in `frontend/`.

Why shadcn/ui: it is not a runtime dependency — the CLI copies component source into `src/components/ui/`, built on Tailwind 4 and Radix, both compatible with what `frontend/` already has (React 19, Tailwind 4, Vite 6). You own the code, so nothing breaks on a library upgrade.

Can be done before or after Day 9. Day 11 (login page) needs both.

---

## Current state → target

| Area | Today (file) | After Day 10 |
|---|---|---|
| Header | `App.tsx` inline | `AppHeader.tsx`: name, awaiting counter, live API badge, refresh |
| Metrics | `MetricBar.tsx` chips | `StatTiles.tsx`: one `Card` per status, big number, click = filter |
| Filters | `TicketFilters.tsx` | removed — stat tiles are the filter |
| List | `TicketList.tsx` table | `TicketFeed.tsx`: `Card` per ticket in a `ScrollArea` |
| Detail | `TicketDetail.tsx` 2-column grid | `Tabs`: Email / Invoice / Draft / Audit |
| Audit | collapsible list | vertical timeline, icon per node |
| HITL | `HitlBar.tsx` fixed bottom bar | `HitlDialog.tsx` modal |
| Feedback | inline error text | inline errors + toasts (`sonner`) |

---

## Block (~4h)

### 10.0 Baseline (5 min)

- [ ] Backend + Celery + UI running; three demo tickets ingested (happy path, quarantine, delegate — see `Demo.md`)
- [ ] `cd frontend; npm run build` passes **before** you change anything
- [ ] Take a screenshot of the current console (for the before/after)

### 10.1 Path alias `@/` (15 min)

The shadcn CLI reads the alias from the **root** `tsconfig.json`, and Vite must resolve it too.

- [ ] `frontend/tsconfig.json`:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ],
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

- [ ] `frontend/tsconfig.app.json` — add the same `baseUrl` + `paths` inside `compilerOptions`
- [ ] `frontend/vite.config.ts`:

```ts
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
```

- [ ] `npm run build` still passes

### 10.2 Init shadcn (15 min)

- [ ] `npx shadcn@latest init` — answers: base colour **neutral** (or slate), CSS variables **yes**
- [ ] Check what it created/changed and nothing else:
  - `components.json`
  - `src/lib/utils.ts` (`cn()` helper — sits next to the existing `api.ts` and `time.ts`)
  - `src/index.css` — theme variables + `@import "tw-animate-css"` added after `@import "tailwindcss"`
  - `package.json` — `clsx`, `tailwind-merge`, `class-variance-authority`, `lucide-react`, `tw-animate-css`
- [ ] `npm run dev` — console still renders (colours may shift slightly; that is the new base theme)
- [ ] If `npm install` fails on Node 20.18 with an engine error, pin the offending package one major down — do **not** upgrade Vite (Vite 7+ needs Node 20.19+, already hit on the dashboard day)

### 10.3 Add components (10 min)

```powershell
npx shadcn@latest add button card badge tabs dialog textarea scroll-area separator skeleton progress tooltip sonner
```

- [ ] Files land in `src/components/ui/`
- [ ] Rule: do not hand-edit `src/components/ui/*` except theme tokens. Compose them in your own components.

### 10.4 Shared helpers (20 min)

- [ ] `src/lib/status.ts` — one place for status label + colour (used by tiles, feed, detail):

```ts
export const STATUS_META: Record<TicketStatus, { label: string; className: string }> = {
  awaiting_human: { label: "Awaiting human", className: "bg-amber-100 text-amber-900 border-amber-200" },
  resolved:       { label: "Resolved",       className: "bg-emerald-100 text-emerald-900 border-emerald-200" },
  escalated:      { label: "Escalated",      className: "bg-red-100 text-red-900 border-red-200" },
  quarantined:    { label: "Quarantined",    className: "bg-rose-100 text-rose-900 border-rose-200" },
  delegated:      { label: "Delegated",      className: "bg-sky-100 text-sky-900 border-sky-200" },
  discarded:      { label: "Discarded",      className: "bg-slate-100 text-slate-700 border-slate-200" },
  open:           { label: "Open",           className: "bg-blue-100 text-blue-900 border-blue-200" },
  awaiting_sender_reply: { label: "Awaiting sender", className: "bg-violet-100 text-violet-900 border-violet-200" },
};
```

- [ ] Rewrite `StatusBadge.tsx` as a thin wrapper around shadcn `Badge` + `STATUS_META`
- [ ] `src/lib/filters.ts` — move `FilterKey` and `statusForFilter` out of `TicketFilters.tsx` (that file goes away in 10.7)
- [ ] `src/lib/time.ts` — add `formatRelative(iso)` next to `formatLocal`, using `Intl.RelativeTimeFormat` (no new dependency). Reuse the same "naive ISO = UTC" parsing as `formatLocal`, otherwise every time is off by your UTC offset.

### 10.5 Header — `src/components/AppHeader.tsx` (25 min)

- [ ] Left: "P2P AP" + "Operator console"
- [ ] Centre: awaiting counter — `stats.awaiting_human`, large, amber when > 0
- [ ] Right:
  - API badge: green dot with `animate-ping` halo when `healthOk`, solid red dot + "API down" otherwise
  - Refresh: `Button variant="outline" size="sm"` with lucide `RefreshCw` (spin while loading)
  - Operator: keep the existing operator text input **until Day 11** replaces it with the logged-in operator
- [ ] `App.tsx` renders `<AppHeader … />` instead of the inline header

### 10.6 Stat tiles — `src/components/StatTiles.tsx` (25 min)

- [ ] One shadcn `Card` per status in a horizontal row (`grid grid-cols-3 md:grid-cols-6 gap-3`)
- [ ] Big number (`text-2xl font-semibold`), small label, coloured left border from `STATUS_META`
- [ ] Click → `onSelect(filterKey)`; active tile gets `ring-2`
- [ ] Hide "Open" when zero (same rule as `MetricBar` today)
- [ ] **No "variation vs yesterday"** — `/stats` returns current counts only. Showing a delta would need a time-series endpoint; do not fake it.
- [ ] Delete `MetricBar.tsx`

### 10.7 Ticket feed — `src/components/TicketFeed.tsx` (35 min)

- [ ] `ScrollArea` with one `Card` per ticket (a `<button>` inside for keyboard + `aria-pressed` for the selected one)
- [ ] Card content:
  - subject, bold, one line (`truncate`)
  - sender email, small, muted
  - `StatusBadge` + relative time (`formatRelative(received_at)`), with `Tooltip` showing `formatLocal` on hover
  - confidence as a thin `Progress` bar (`value={confidence * 100}`); hidden when `confidence` is null
- [ ] Loading → 5 `Skeleton` cards; empty → "No tickets in this view"
- [ ] Delete `TicketList.tsx` and `TicketFilters.tsx`

### 10.8 Detail with tabs — `src/components/TicketDetail.tsx` (45 min)

Header above the tabs: subject, `StatusBadge`, sender, and (when `awaiting_human`) the **Review & decide** button that opens the dialog from 10.10.

- [ ] **Email** tab: from, received (`formatLocal`), subject, body with `whitespace-pre-wrap`; badge "Thread continuation" when `is_thread_continuation`
- [ ] **Invoice** tab: definition list of the matched invoice (ref, supplier, amount + currency, stage, status, due date, clearing document, payment date, approval owner, blocking reason); match method + confidence from the last `resolve` audit entry (the logic already exists in `resolveAudit`)
  - callout (amber) when status is `paid` and `clearing_document` is null: "SAP shows paid, no clearing document — do not confirm payment"
  - empty state: "No invoice matched"
- [ ] **Draft** tab: target + to email, generated text (read-only here — editing happens in the dialog), `attach_payment_proof` / `edited_by_human` badges
  - empty state uses the `draft` audit entry: when `metadata.skipped` is true → "No draft — this case needs a human decision (match: {metadata.match_result})"
- [ ] **Audit** tab: vertical timeline, one row per entry: icon, node name, action `Badge`, confidence (if any), time

| node | lucide icon |
|---|---|
| ingest | `Inbox` |
| security | `ShieldCheck` (or `ShieldAlert` when action is `quarantine`) |
| thread | `GitBranch` |
| triage | `Filter` |
| intent | `Crosshair` |
| sender | `UserSearch` |
| routing | `Route` |
| resolution | `FileSearch` |
| draft | `PenLine` |
| hitl | `UserCheck` |
| send | `Send` |

- [ ] Default tab: **Draft** when `awaiting_human`, otherwise **Audit** (for stopped tickets, the audit is what explains why)

### 10.9 Backend tweak — audit timestamps (10 min)

The timeline needs a time per entry; `ticket_detail` currently returns only `node`, `action`, `metadata`.

- [ ] `app/api/tickets.py` — add `"confidence": e.confidence` and `"created_at": e.created_at.isoformat()` to each audit item
- [ ] `frontend/src/types/ticket.ts` — `AuditSummary` gets `confidence: number | null; created_at: string`
- [ ] `tests/test_api.py` — assert the detail audit items contain `created_at`

### 10.10 HITL dialog — `src/components/HitlDialog.tsx` (35 min)

Same rules as `HitlBar` today: approve needs a draft, a healthy API, not busy, and an operator.

- [ ] shadcn `Dialog`, opened by the **Review & decide** button in the detail header
- [ ] Content:
  - "To: {to_email} ({target})"
  - `Textarea` prefilled with the draft, character counter under it (`{draftEdit.length} characters`), "Edited" badge when it differs from `generated_text`
  - inline error (e.g. the 409 detail from the API)
- [ ] Footer:
  - **Escalate** — `Button variant="outline"` with destructive colours + lucide `AlertTriangle`
  - **Approve & send** — green `Button` + lucide `Check`; disabled when there is no draft (show a `Tooltip`: "No draft to send — escalate instead")
- [ ] On success: close the dialog, `toast.success("Approved — reply sent")` / `toast("Escalated")`, then the existing `afterHitl()` refresh
- [ ] Mount `<Toaster />` once (in `main.tsx` or at the root of `App.tsx`)
- [ ] Delete `HitlBar.tsx`; the `onApprove` / `onEscalate` logic in `App.tsx` stays as is

### 10.11 Layout in `App.tsx` (15 min)

```
AppHeader
StatTiles
┌───────────── 38% ─────────────┬──────────── rest ────────────┐
│ TicketFeed (ScrollArea)        │ TicketDetail (Tabs)          │
└────────────────────────────────┴──────────────────────────────┘
HitlDialog (portal)
```

- [ ] Keep the data loading (`loadList`, `loadDetail`, `refreshAll`, `afterHitl`) unchanged — this day is presentational only
- [ ] Optional: extract the loading state into `src/hooks/useTickets.ts` if `App.tsx` gets long

### Gate

```powershell
cd frontend
npm run build
npm run lint
```

Manual checklist with the three demo tickets:

- [ ] Happy path: Draft tab opens by default; dialog → edit text → counter and "Edited" update → Approve → toast → ticket moves to Resolved tile
- [ ] Quarantine: no Review button; Audit tab ends at `security · quarantine` with the alert shield
- [ ] Delegated: Audit ends at `routing · delegate`; Draft tab shows the empty state
- [ ] Stop the API: badge turns red; Approve disabled
- [ ] Ticket with no draft in `awaiting_human` (e.g. paid-without-clearing after Day 8): Approve disabled with tooltip; Escalate works
- [ ] Backend `pytest` still green (10.9)

### Git

- Commit: `chore(frontend): shadcn/ui init and @ alias`
- Commit: `feat(frontend): stat tiles, ticket feed, tabbed detail`
- Commit: `feat(frontend): HITL dialog with toasts`
- Commit: `feat(api): audit timestamps in ticket detail`
- Optional: replace `docs/assets/` screenshot / GIF with the new console

---

## Definition of Done — Day 10

- [ ] No hand-rolled buttons/badges/cards left outside `src/components/ui/`
- [ ] `MetricBar`, `TicketFilters`, `TicketList`, `HitlBar` deleted
- [ ] Same API calls and HITL rules as before; nothing new required from the backend except audit timestamps
- [ ] Build and lint pass on Node 20.18 / Vite 6

---

## Out of scope for this day

Login page and operator identity (Day 11), dark mode toggle (tokens make it easy later), charts, stat deltas, websockets/live updates, mobile layout, Vite or Node upgrades.
