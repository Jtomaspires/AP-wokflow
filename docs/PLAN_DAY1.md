# Day 1 — Domain, ports, adapters, Alembic (~3h, à mão)

> Objectivo: a **mesma forma** que o P2P (`domain` → `ports` → `adapters`), só o que Ingestão + Segurança + Triagem precisam.
>
> Referência (ler, não colar o ficheiro inteiro): `p2p-ai-assistant/app/domain/`, `app/ports/`, `app/adapters/mock_*.py`, `app/adapters/postgres_repos.py` (só a parte de tickets).

**Status:** fechado — Domain, ports, adapters, Alembic, Gates 1–3, wiring. LangGraph / Celery = Day 2.

---

## 1. Domain (~40 min)

Enums **mínimos** (`app/domain/enums.py`):

- [x] `TicketStatus`: `open`, `quarantined`, `discarded`  
  (não precisas de `awaiting_human`, `delegated`, etc.)

Evento de entrada (`app/domain/events.py`) — espelha o P2P:

- [x] `IncomingEmail`: `thread_id`, `message_id`, `from_email`, `subject`, `body`, `received_at`, `attachments` (lista simples), opcional `spf_pass` / `dkim_pass`

Ticket persistido (`app/domain/models.py`) — subconjunto:

- [x] `id` UUID, `thread_id`, `message_id`, `sender_email`, `subject`, `body`, `received_at`, `status`, `created_at`, `updated_at`
- [x] Sem `intent`, `assigned_operator_id`, flags de thread — `is_ap: bool | None` incluído para a triagem

Deps (`app/domain/deps.py`):

- [x] Dataclass `WorkflowDeps`: `settings`, `email`, `tickets`, `llm`  
  (sem sap, senders, drafts, audit — podes acrescentar `audit` mais tarde se quiseres um log simples)

Estado LangGraph **ainda não** — isso é Day 2. Hoje os tipos de domínio e I/O.

### Gate 1

```bash
pytest tests/test_domain.py -v
```

- [x] Enums `.value`
- [x] `IncomingEmail` / `Ticket` validam; ticket rejeita sem `thread_id`
- [x] Round-trip Pydantic
- [x] `pytest tests/test_domain.py -v` — 7 passed

---

## 2. Ports (~25 min)

ABCs em `app/ports/`. Assinaturas alinhadas ao P2P, nomes teus se quiseres (`TicketStorePort` em vez de `InvoiceStorePort`).

- [x] `EmailPort.parse_webhook(payload: dict) -> IncomingEmail`
- [x] `TicketStorePort`: `get_by_id`, `get_by_message_id`, `save_ticket`  
  (`list_by_thread_id` **não** é obrigatório — não há ThreadNode)
- [x] `LLMPort.generate(*, system_prompt, user_prompt, output_schema: type[BaseModel]) -> BaseModel`  
  (igual ao P2P; o mock valida um dict contra o schema)

Nenhum adapter ainda fala com LangGraph.

---

## 3. Adapters (~50 min)

Escreve implementações **pequenas**:

| Adapter | Papel | Olhar no P2P |
|---|---|---|
| `mock_email.py` | `from` / `from_email`, subject, body → `IncomingEmail` | `mock_email.py` |
| `mock_llm.py` | fila de dicts → `output_schema.model_validate` | `mock_llm.py` |
| `memory_ticket_store.py` | dict em memória para testes de nós | `memory_ticket_store.py` |
| `db_models.py` | `TicketTable` SQLModel `table=True` | `db_models.py` (só tickets) |
| `postgres_tickets.py` | `TicketRepo` com `Session` | `postgres_repos.TicketRepo` (métodos que precisas) |

- [x] Mock LLM: `enqueue({...})`; se a fila estiver vazia, erro claro
- [x] Não implementes `OpenAILLMAdapter` neste dia (opcional no Day 2 se tiveres chave)

### Gate 2 — mocks + memória

```bash
pytest tests/test_adapters.py -v
```

- `parse_webhook` mapeia `from` → `from_email`
- `MockLLMAdapter` devolve um `TriageOutput` (`is_ap: bool`, `confidence: float`)
- Memory store: save + get_by_message_id
- [x] `pytest tests/test_adapters.py -v` — 4 passed

---

## 4. Alembic (~40 min)

- [x] `alembic init alembic` (pasta `alembic/` + `alembic.ini`)
- [x] `env.py` importa `app.adapters.db_models` e usa `target_metadata = SQLModel.metadata`
- [x] `env.py` usa `settings.DATABASE_URL` (`config.set_main_option("sqlalchemy.url", ...)`)
- [x] `alembic revision --autogenerate -m "tickets"` → `alembic/versions/edb81d2a0b75_tickets.py`
- [x] **Lê** a migration: tabela `tickets`, índice unique em `message_id`
- [x] `alembic upgrade head` (`Running upgrade  -> edb81d2a0b75, tickets`)
- [x] Confirmar `tickets` no pgAdmin (`lab` em `127.0.0.1:5434`) — ver [ALEMBIC_PGADMIN.md](ALEMBIC_PGADMIN.md)

### Gate 3 — repo Postgres

```bash
pytest tests/test_ticket_repo.py -v
```

- save + get_by_id na BD real (compose)
- [x] `pytest tests/test_ticket_repo.py -v` — 1 passed

---

## 5. Wiring (10 min)

- [x] Função `build_workflow_deps(session)` em `app/api/deps.py`:  
  `MockEmailAdapter`, `TicketRepo(session)`, `MockLLMAdapter`, `settings`

Ainda **não** ligues Celery (Day 2).

---

## Definition of Done — Day 1

- [x] Hexágono mínimo: 3 ports, mocks + Postgres tickets
- [x] Tabela `tickets` criada pelo Alembic
- [x] **Nenhum** ficheiro LangGraph ainda (amanhã)
- [x] Tudo escrito por ti, com o P2P aberto ao lado só como guia

---

## Fora deste dia

`ThreadResolutionNode`, Intent, Sender, SAP, drafts, `core/` Launchpad, copiar `postgres_repos.py` inteiro.
