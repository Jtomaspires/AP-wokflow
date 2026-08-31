# Mini-lab — infra + dois nós reais (até ao primeiro LLM)

Este projecto **não** reconstrói o P2P. Reconstróis **à mão**:

1. O caminho **API → Celery → worker → Postgres (Alembic)**.
2. Os **primeiros nós do grafo** do P2P, em **LangGraph**, com a mesma ideia **ports / adapters**.

No P2P a spine começa assim:

```
Ingestion → Security → Thread → Triage (1.º LLM) → Intent → …
```

Aqui **cortas no Triage** (primeiro nó que chama o LLM). **Não** implementas Thread (continuação de emails).

```
Ingestion → Security → Triage → END
```

- Ingestão + segurança = dois nós de domínio **completos** (parse, persistir ticket, whitelist).
- Triage = tecto: estrutura `LLMPort` + mock, sem Intent/SAP/draft/HITL.

## Como trabalhar (manual)

- **Escreve tu** cada ficheiro. Não peças ao Cursor para gerar o lab inteiro.
- O `p2p-ai-assistant` é **referência**: abre um nó, percebe, reimplementa em LangGraph (funções + `StateGraph`), não copies `TicketWorkflow` / `core/`.
- Se ficares bloqueado, lê o P2P; depois fecha e escreve a tua versão mais pequena.

Referência útil no P2P:

| Peça | Onde olhar (só ler) |
|---|---|
| `IncomingEmail` | `app/domain/events.py` |
| `Ticket` / `TicketStatus` | `app/domain/models.py`, `enums.py` |
| `EmailPort` | `app/ports/email_port.py` |
| Tickets | `app/ports/invoice_store_port.py` (podes nomear `TicketStorePort`) |
| `LLMPort` | `app/ports/llm_port.py` |
| Ingestão | `app/workflow/nodes/ingestion.py` |
| Segurança | `app/workflow/nodes/security.py` |
| Triagem | `app/workflow/nodes/triage.py` |
| Mocks | `app/adapters/mock_email.py`, `mock_llm.py` |
| Wiring | `app/api/deps.py` `build_workflow_deps` |
| Fila | `app/api/main.py` + `app/workflow/tasks.py` |

## O que entra vs o que fica de fora

| Entra | Fica de fora |
|---|---|
| FastAPI `POST` ingest + `GET` ticket | Streamlit, Nylas, HITL approve |
| Celery + Redis | Eval, 20 fixtures golden |
| Alembic + tabela `tickets` (mínima) | SAP, drafts, audit por nó, senders |
| Ports: email, tickets, LLM | SAPPort, DraftPort, SenderDirectory |
| Adapters: mock email, mock LLM, Postgres + memória para testes | OpenAI obrigatório |
| LangGraph: ingest → security → triage | Thread, Intent, Sender, Routing, Resolution, Draft, HITL, Send |
| Settings (whitelist, flags) | Matching fatura, VAT, dashboard |

## Planos

| Dia | Ficheiro | Foco |
|---|---|---|
| 0 | [PLAN_DAY0.md](PLAN_DAY0.md) | Scaffold, Docker, settings |
| 1 | [PLAN_DAY1.md](PLAN_DAY1.md) | Domain + ports + adapters + Alembic |
| 2 | [PLAN_DAY2.md](PLAN_DAY2.md) | LangGraph (3 nós) + Celery + FastAPI |

Notas do Alembic deste lab (migration `tickets` + pgAdmin na porta 5434): [ALEMBIC_PGADMIN.md](ALEMBIC_PGADMIN.md).

Cerca de **um dia e meio** de trabalho manual, não três dias de produto.

## Diagramas

Mesmo formato que `P2P/diagrams/` (Mermaid + draw.io), âmbito do lab:

- [diagrams/LAB_CALL_DIAGRAMS.md](diagrams/LAB_CALL_DIAGRAMS.md) — hexágono (3 ports), grafo de 3 nós, sequência API → Redis → worker → Postgres
- [diagrams/LAB_CALL_DIAGRAMS.drawio](diagrams/LAB_CALL_DIAGRAMS.drawio) — as mesmas vistas no diagrams.net

## Relação com o P2P

| P2P | Este lab |
|---|---|
| `POST /webhook/mock` → `process_email.delay` | `POST /ingest` → `process_email.delay` |
| `TicketWorkflow(deps).run(payload)` | `build_graph(deps).invoke(state)` |
| Ingestion + Security + Triage | os mesmos três, em LangGraph |
| `build_workflow_deps` | o mesmo padrão, menos ports |
| Dashboard | `GET /tickets/{id}` |
