# Day 2 — LangGraph (Ingestão → Segurança → Triagem) + fila (~3–4h, à mão)

> Substitui o `TicketWorkflow` por **LangGraph**. Mesma lógica dos três primeiros nós “úteis” do P2P, **sem** Thread.
>
> Escreve os nós tu. Abre `ingestion.py` / `security.py` / `triage.py` no P2P, percebe os caminhos, reimplementa como funções `(state) -> dict` (updates).

**Status:** aberto.

---

## Grafo

```
START → ingest → security → triage → END
              ↘ stop (sem ids / duplicado)
                    ↘ stop (quarentena)
                          ↘ stop (discard)  ou  END com ticket OPEN
```

LangGraph: `add_conditional_edges` quando `should_stop` (ou status terminal). Não copies `BaseRouter`.

Estado sugerido (`app/graph/state.py`): `raw_payload`, `event` (opcional), `ticket_id` ou ticket serializado, `should_stop: bool`, campos que precisares. **Não** metas `deps` no state (não serializa bem) — `build_graph(deps)` fecha `deps` nas funções dos nós, como `TicketWorkflow(deps)`.

---

## Nó 1 — Ingestão (`app/graph/nodes/ingest.py`)

Referência: `p2p-ai-assistant/app/workflow/nodes/ingestion.py`

- [ ] `deps.email.parse_webhook(raw_payload)` → `IncomingEmail`
- [ ] Sem `message_id` ou `thread_id` → `should_stop=True`, **não** crias ticket (ou crias e marcas rejeitado — escolhe uma e documenta)
- [ ] `get_by_message_id` → duplicado → stop, reutiliza o ticket existente
- [ ] Senão: constrói `Ticket(status=open)`, `save_ticket`
- [ ] Devolve update do state com `ticket_id` / dados necessários

Testes (`tests/test_node_ingest.py`) com **memory store** + mock email:

- payload válido → ticket OPEN na store
- mesmo `message_id` duas vezes → não cria segundo
- falta `thread_id` → stop

---

## Nó 2 — Segurança (`app/graph/nodes/security.py`)

Referência: `security.py` no P2P. Versão **reduzida** aceite:

- [ ] Se `SECURITY_CHECK_ENABLED=False` → passa (grava ticket se quiseres)
- [ ] Extrai domínio do `from_email`
- [ ] Se domínio **não** está em `SENDER_DOMAIN_WHITELIST` → `status=quarantined`, `save_ticket`, `should_stop=True`
- [ ] Caso contrário → passa para triagem
- [ ] SPF/DKIM: opcional (se implementares, copia a ideia do P2P; se não, documenta “só whitelist”)

Testes:

- domínio na whitelist → continua, ticket OPEN
- domínio fora + flag on → QUARANTINED, stop
- flag off → passa mesmo fora da lista

---

## Nó 3 — Triagem = primeiro LLM (`app/graph/nodes/triage.py`)

Referência: `triage.py` + `TriageOutput` + prompts em `app/llm/prompts.py` (podes um prompt curto no próprio nó).

- [ ] Schema Pydantic `TriageOutput`: `is_ap: bool`, `confidence: float`
- [ ] `await deps.llm.generate(system_prompt=..., user_prompt=subject+body, output_schema=TriageOutput)`  
  LangGraph: nó **async** (`ainvoke`) **ou** `asyncio.run` no worker sync — escolhe uma e usa-a em todos os sítios
- [ ] `not is_ap` e `confidence >= TRIAGE_DISCARD_MIN_CONFIDENCE` → `discarded`, save, stop
- [ ] Senão → ticket fica OPEN (mail AP); END

Testes com `MockLLMAdapter.enqueue({"is_ap": False, "confidence": 0.9})` → DISCARDED; `is_ap True` → OPEN.

**Não** implementes IntentNode.

---

## Compilar o grafo (`app/graph/app.py`)

- [ ] `StateGraph(LabState)`
- [ ] `add_node` ingest, security, triage
- [ ] edges + conditionais em `should_stop` / status
- [ ] `compile()`
- [ ] `build_graph(deps) -> compiled graph`

Teste de integração **sem Celery** (`tests/test_graph.py`):

- email ACME (domínio whitelist) + mock LLM `is_ap=True` → ticket OPEN
- email domínio estranho + security on → QUARANTINED, triage **não** corre (assert: mock LLM `calls` vazio)
- AP false alta confiança → DISCARDED

---

## Celery (`app/worker/tasks.py`)

Como o P2P `process_email`, à mão:

- [ ] `Celery` broker/backend = `REDIS_URL`
- [ ] `process_email(raw_payload: dict)`:
  - `Session(engine)`
  - `deps = build_workflow_deps(session)`
  - `build_graph(deps).invoke(...)` ou `ainvoke`
  - return `{ticket_id, status}`
- [ ] Worker Windows: `--pool=solo`

Primeiro corre a task **síncrona** num teste (sem `.delay`) contra Postgres.

---

## FastAPI (`app/api/main.py`)

- [ ] `GET /health`
- [ ] `POST /ingest` (ou `/webhook/mock`): body = payload tipo P2P (`thread_id`, `message_id`, `from`/`from_email`, `subject`, `body`)
  - `process_email.delay(payload)` → 202 `{task_id}` ou `{ticket_id}` se souberes
- [ ] `GET /tickets/{id}` → repo Postgres

Três terminais + curl (payload com `thread_id` + `message_id` + `from` de um domínio da whitelist).

---

## Definition of Done — Day 2

- [ ] Consegues explicar: POST → Redis → worker → três nós LangGraph → `tickets` row
- [ ] Sabes porque o Triage usa `LLMPort` e não `openai` no nó
- [ ] Sabes porque Security não precisa de port extra (só `settings` + ticket store)
- [ ] README na raiz: uvicorn, celery, curl de exemplo
- [ ] **Não** há Intent, SAP, HITL, Streamlit

---

## P2P ↔ lab (nós)

| P2P | Lab |
|---|---|
| `IngestionNode.process` | `ingest` (LangGraph) |
| `SecurityNode.process` | `security` |
| `TriageNode.process` + `call_llm` | `triage` + `LLMPort` |
| `ThreadResolutionNode` | **omitido** |
| `TicketWorkflow` + `core/` | `StateGraph` |

---

## Se sobrar tempo (opcional)

- Fallback síncrono no POST se Redis estiver down (ideia do `app/api/main.py` P2P)
- `OpenAILLMAdapter` atrás da mesma `LLMPort` — o nó de triagem **não muda**
