# Call diagrams

Current behaviour. The draw.io file has the same four pages.

## 1. Workflow

`poll_nylas.py` and `POST /webhook/nylas` both enter through `POST /webhook/mock`'s enqueue. The compiled graph ends at hitl. Approve and escalate are HTTP calls in the API process.

```mermaid
flowchart TD
  POLL[poll_nylas.py] --> START
  NYLAS[POST /webhook/nylas] --> START
  START([POST /webhook/mock]) --> ingest
  ingest -->|missing ids or duplicate| E1[END]
  ingest --> security
  security -->|quarantine| E2[END]
  security --> thread
  thread -->|escalated| E3[END]
  thread -->|continuation| resolution
  thread -->|new| triage
  triage -->|discard| E4[END]
  triage --> intent
  intent -->|unknown or low conf| resolution
  intent --> sender
  sender --> routing
  routing -->|DELEGATE| E5[END]
  routing -->|MINE| resolution
  resolution --> draft
  draft --> hitl
  hitl -->|AWAITING_HUMAN| wait[Wait for the operator]
  wait -->|POST approve| send
  wait -->|POST escalate| E6[END]
  send -->|flag off| E7[END mock]
  send -->|flag on, key and grant| NYOUT[Nylas messages/send]
  send -->|missing creds or error| E8[stays AWAITING_HUMAN]
```

## 2. Architecture

Seven ports. Auth is not one of them. Nylas send is a direct call from the send node when the flag, key, and grant are set.

```mermaid
flowchart LR
  subgraph IN["Driving"]
    UI["React console"]
    INBOX["poll_nylas.py or POST /webhook/nylas"]
    API["FastAPI"]
  end
  subgraph CORE["Core"]
    SPINE["Graph ends at hitl"]
    PORTS["Email Tickets LLM SAP Audit Senders Drafts"]
  end
  subgraph AD["Adapters"]
    PG[("Postgres")]
    MOCK["Mock SAP and senders"]
    LLM["OpenAI or MockLLM"]
    SEND["Nylas messages/send on Approve"]
  end
  IN --> CORE --> AD
```

## 3. Ticket queue

FastAPI only enqueues. Celery runs `ainvoke`. Approve does not go through Redis.

```mermaid
sequenceDiagram
  participant S as poller or webhook
  participant API as FastAPI
  participant R as Redis
  participant W as Celery worker
  participant G as LangGraph
  participant P as Postgres

  S->>API: POST /webhook/mock or /webhook/nylas
  API->>R: process_email.delay
  API-->>S: 202 from mock, 200 from nylas
  W->>G: ainvoke
  G->>P: tickets drafts audit
  G-->>W: stop at AWAITING_HUMAN
```

If Redis is down, the same POST runs the graph in the API process and returns `ticket_id` and `status`.

## 4. Outcomes

What each email gets. Early stops never reach SAP. Everything that reaches `draft` ends at `AWAITING_HUMAN`; the draft target comes from `pick_target` in `app/graph/nodes/draft.py`, not from the LLM.

### Early stops

| Where | Condition | Result |
|---|---|---|
| ingest | missing `thread_id` or `message_id` | no ticket, no audit row. The worker return drops `stop_reason` |
| ingest | same `message_id` again | old ticket unchanged |
| ingest | same sender, subject, and first 300 characters of the body | `duplicate`, audit reason `content_duplicate` |
| security | domain not whitelisted, or SPF and DKIM both fail | `quarantined` |
| thread | reply on an escalated thread | appended to that ticket, new row `discarded` |
| thread | reply on an open or resolved thread | merged into it, goes to resolution |
| triage | not AP, confidence 0.8 or more | `discarded` |
| intent | unknown or confidence under 0.5 | skips sender and routing, goes to resolution |
| routing | rule points to another operator | `delegated` |

### Draft target

| SAP result | Draft |
|---|---|
| not found | internal note to `INVOICING_EMAIL` |
| multiple, too many, VAT discrepancy | none |
| in approval, on time | reply to the supplier |
| in approval, overdue or near due, owner known | internal note to the approval owner |
| in approval, overdue, no owner | none |
| posted, pending or partial, on time | reply to the supplier |
| posted and blocked, or pending and overdue | internal note to `PAYMENTS_EMAIL` |
| paid with clearing document | reply to the supplier, payment proof attached |
| paid without clearing document | none, UI warns not to confirm payment |

### Operator

```mermaid
flowchart LR
  H[AWAITING_HUMAN] -->|approve, draft exists| S[send in API process]
  H -->|approve, no draft| C[409]
  H -->|escalate| X[ESCALATED]
  S -->|flag off| M[RESOLVED, mock]
  S -->|flag on, Nylas ok| N[RESOLVED, sent to draft.to_email]
  S -->|Nylas error| F[stays AWAITING_HUMAN, send_failed]
```
