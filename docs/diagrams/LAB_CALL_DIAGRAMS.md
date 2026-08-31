# Mini-lab — diagramas

Espelho de `P2P/diagrams/P2P_AI_CALL_DIAGRAMS.md`, **só** o âmbito do lab (Ingestão → Segurança → Triagem + API/Celery/Postgres).

Cola cada bloco Mermaid em [mermaid.live](https://mermaid.live), Notion, ou diagrams.net → *Arrange → Insert → Advanced → Mermaid*.

`LAB_CALL_DIAGRAMS.drawio` tem as mesmas três vistas, editável no draw.io.

---

## 1. Arquitectura hexagonal

**Pitch:** o grafo e o domínio não importam Postgres, Redis nem o cliente LLM. Entram e saem por **ports**; os **adapters** mudam (memória nos testes, Postgres no worker) sem reescrever os nós.

```mermaid
flowchart LR
  classDef driving fill:#E8F1FF,stroke:#3B6EA5,color:#1A1A1A
  classDef core fill:#FFF8E7,stroke:#C4A000,color:#1A1A1A
  classDef port fill:#F3E8FF,stroke:#6B4C9A,color:#1A1A1A
  classDef driven fill:#E8F6EE,stroke:#2E7D4F,color:#1A1A1A

  subgraph IN["Driving adapters — inbound"]
    direction TB
    CURL["curl / TestClient"]
    API["FastAPI<br/>POST /ingest · GET /tickets/id"]
  end

  subgraph HEX["Core — vendor-agnostic"]
    direction TB
    subgraph DOM["Domain"]
      M["IncomingEmail · Ticket<br/>TicketStatus · WorkflowDeps"]
    end
    subgraph UC["Use case"]
      WF["LangGraph<br/>ingest → security → triage"]
    end
    subgraph PORTS["Ports — contracts"]
      PE["EmailPort"]
      PT["TicketStorePort"]
      PL["LLMPort"]
    end
    DOM --> UC --> PORTS
  end

  subgraph OUT["Driven adapters — outbound"]
    direction TB
    EM["MockEmailAdapter"]
    LLM["MockLLMAdapter<br/>optional OpenAI later"]
    PG[("Postgres tickets<br/>Alembic")]
    MEM["InMemoryTicketStore<br/>tests"]
  end

  IN --> HEX --> OUT

  class CURL,API driving
  class M,WF core
  class PE,PT,PL port
  class EM,LLM,PG,MEM driven
```

**O que nunca atravessa o hexágono:** o endpoint FastAPI não fala com o LLM; o nó de triagem não importa `openai`; o nó de ingestão não importa SQLModel — só `TicketStorePort.save_ticket`.

---

## 2. Grafo LangGraph (3 nós)

**Pitch:** um payload percorre no máximo **três** nós. Há três saídas cedo (rejeitar ingest, quarentena, discard). **Não** há Thread, Intent, HITL nem Send.

Numeração = P2P. Ordem de execução = ingestão **antes** de segurança (para poder gravar `QUARANTINED` no ticket).

```mermaid
flowchart TD
  classDef node fill:#E8F1FF,stroke:#3B6EA5,color:#1A1A1A
  classDef stop fill:#FDECEC,stroke:#C0392B,color:#1A1A1A
  classDef ok fill:#E8F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef llm fill:#F3E8FF,stroke:#6B4C9A,color:#1A1A1A

  START([POST /ingest<br/>thread_id · message_id · from · subject · body]) --> N1

  N1["1 · Ingest<br/>EmailPort.parse_webhook<br/>Ticket OPEN · save"] --> N1D{ids ok e não duplicado?}
  N1D -->|Não — sem ids / duplicate message_id| REJ["STOP · sem ticket novo<br/>ou ticket existente"]
  N1D -->|Sim| N0

  N0["0 · Security<br/>whitelist domínio<br/>settings only"] --> N0D{Sender aceite?}
  N0D -->|Não| QUAR["STOP · QUARANTINED"]
  N0D -->|Sim| N2

  N2["2 · Triage · 1.º LLM<br/>LLMPort.generate<br/>TriageOutput is_ap + confidence"] --> N2D{AP?}
  N2D -->|Não + confiança alta| DISC["STOP · DISCARDED"]
  N2D -->|Sim ou incerto| OPEN["END · ticket OPEN<br/>mail tratado como AP"]

  class N1,N0 node
  class N2 llm
  class REJ,QUAR,DISC stop
  class OPEN ok
```

**LLM só no nó 2.** Ingestão e segurança são 100% determinísticos. Thread (1.5 no P2P) **não existe** neste lab.

---

## 3. Runtime — request → fila → worker → BD

**Pitch:** isto é o que o lab existe para sentires. O LangGraph corre **dentro** do worker, não no processo do FastAPI (salvo fallback).

```mermaid
sequenceDiagram
  participant C as curl / cliente
  participant API as FastAPI
  participant R as Redis
  participant W as Celery worker
  participant G as LangGraph
  participant P as Postgres

  C->>API: POST /ingest payload
  API->>P: opcional: ainda não (ticket nasce no ingest)
  API->>R: process_email.delay(payload)
  API-->>C: 202 accepted

  W->>R: puxa task
  W->>P: Session + TicketRepo
  W->>G: invoke(state) com WorkflowDeps

  G->>G: ingest · EmailPort + save_ticket
  G->>P: INSERT tickets OPEN
  G->>G: security · whitelist
  alt quarentena
    G->>P: UPDATE QUARANTINED
  else passa
    G->>G: triage · LLMPort
    alt discard
      G->>P: UPDATE DISCARDED
    else AP
      G->>P: ticket permanece OPEN
    end
  end

  C->>API: GET /tickets/{id}
  API->>P: TicketRepo.get_by_id
  API-->>C: status + campos
```

**Se o worker estiver parado:** o POST devolve 202, o GET fica `queued` / ticket ainda não existe até o ingest correr — documenta o que a tua implementação faz (criar ticket só no grafo vs criar `queued` na API).

**Se `alembic upgrade` não correu:** o worker falha ao `save_ticket` (tabela `tickets` inexistente).

---

## Mapa spec → código (lab)

| Passo | P2P | Lab |
|---|---|---|
| 1 Ingestion | `IngestionNode` | `app/graph/nodes/ingest.py` |
| 0 Security | `SecurityNode` | `app/graph/nodes/security.py` |
| 2 Triage | `TriageNode` | `app/graph/nodes/triage.py` |
| Grafo | `TicketWorkflow` | `StateGraph` em `app/graph/app.py` |
| Fila | `process_email.delay` | idem, `app/worker/tasks.py` |
| Ports | 7 | 3: Email, TicketStore, LLM |

---

## O que estes diagramas **não** mostram (de propósito)

HITL, SendNode, SAP, Sender directory, 10 nós, Streamlit. Isso está em `P2P/diagrams/`.
