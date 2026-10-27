# Lacunas de testes

Inventário do que a suíte cobre hoje, o que **não** cobre, e o que falta acrescentar — com ficheiros, funções e asserções concretas.

Snapshot: Outubro 2026, depois de auth, adapter OpenAI, consola, fixes do dia 12 e Nylas. A suíte backend inclui `test_auth.py`, `test_auth_primitives.py`, `test_openai_llm.py`, `test_draft_prompt.py`, `test_judge.py`, `test_node_routing.py` e `test_nylas_webhook.py`. Frontend: **zero** testes automatizados. CI: **nenhum** workflow em `.github/`.

Comportamento de produto (grafo, HITL opção 2, eval): [README.md](README.md) e [root README](../README.md).

---

## Como correr hoje

```powershell
# Precisa de Postgres no compose (porta 5434) para a suíte completa.
pytest tests -v

# Só memória (falha assim que chegar a TicketRepo / FastAPI contra a BD).
# Não há marker para saltar Postgres — ver G1.

python scripts/run_eval.py
```

`pyproject.toml` só define `testpaths = ["tests"]` e `asyncio_mode = "auto"`. Não há `markers`, `coverage`, nem job de CI. `ruff` está em `dev` extra e também não corre automaticamente.

---

## Dois mundos (e porque `pytest` na CI rebenta)

| Mundo | Deps | Ficheiros |
|---|---|---|
| Memória | `tests/helpers.py` → `make_test_deps()` (7 ports in-memory / mock) | `test_domain`, `test_adapters`, nós, `test_graph`, maior parte de `test_day3`/`test_day4`, `test_hitl`, `test_eval_suite`, `test_node_resolution*` |
| Postgres lab | `settings.DATABASE_URL` (default `lab:lab_dev` @ `localhost:5434`) | ver tabela abaixo |

Não há `conftest.py`. Os testes Postgres **escrevem na BD de lab** (`commit` em `TicketRepo.save_ticket`, `AuditRepo.append`, `DraftRepo.save`). Não há rollback, schema temporário, nem prefixo de `message_id` partilhado para cleanup. Correr pytest duas vezes deixa lixo; um `GET /stats` no teste vê contagens globais (`>= 1`), não um snapshot isolado.

### Testes que falam com Postgres

| Teste | O que faz na BD |
|---|---|
| `test_ticket_repo.py::test_ticket_repo_save_and_get_by_id` | `TicketRepo.save_ticket` + `get_by_id` |
| `test_day3.py::test_postgres_ticket_extra_fields_and_audit` | extras do ticket + `AuditRepo.append/get` + `list_by_thread_id` + `count_by_status` |
| `test_day4.py::test_postgres_audit_rows_for_happy_path` | `build_workflow_deps(session)` + `ainvoke` + lê `audit` |
| `test_process_email.py` (2 testes) | `run_process_email` / `process_email()` síncrono, relê `TicketRepo` |
| `test_api.py::test_get_ticket_404` | `GET /tickets/{uuid}` → `TicketRepo.get_by_id` |
| `test_api.py::test_get_ticket_from_postgres` | insert + GET detalhe |
| `test_api.py::test_ingest_falls_back_sync_when_redis_down` | `run_process_email` via API (domínio `evil.example`) |
| `test_api.py::test_approve_and_escalate_http` | tickets + `DraftRepo` + approve/escalate |

`test_api.py::test_health`, `test_ingest_queues_celery_task` e `test_webhook_mock_queues_like_ingest` **não** precisam de Postgres no request (Celery `.delay` está patched). O import de `app.api.main` ainda constrói `engine` a partir de `.env`.

---

## Inventário do que já existe

| Camada | Ficheiro | Nº | Garante |
|---|---|---|---|
| Domínio | `test_domain.py` | 9 | Enums `TicketStatus`; validação/round-trip `Ticket`, `IncomingEmail`, `Sender`, `Invoice`, `ResponseDraft`, `AuditEntry` |
| Mock/memória | `test_adapters.py` | 4 | Parse `from`→`from_email`; `MockLLMAdapter` queue/erro; `InMemoryTicketStore` por `message_id` |
| Ingest | `test_node_ingest.py` | 5 | OPEN; duplicado por `message_id`; mesmo conteúdo com outro id; outro remetente não é duplicado; `thread_id` em falta → `missing_ids` |
| Security | `test_node_security.py` | 7 | Whitelist; quarentena; flag off; SPF/DKIM fail total e parcial (penalty 0.2); a penalty baixa a confidence do intent e pode fazer `skip_identity` |
| Triage | `test_node_triage.py` | 3 | Discard alta confiança; AP open; não-AP baixa confiança **não** descarta |
| Thread | `test_node_thread.py` | 6 | Nova → triage; `OPEN` → continuation; `ESCALATED` → stop; truncagem (curto, cauda, separador) |
| Resolution | `test_node_resolution.py` | 12 | Ladder exact/fuzzy/amount/`not_found`/`MULTIPLE`; VAT; PAID sem clearing; parte de `pick_target`; `extraction_confidence` baixa ignora a ref; `eval_date` |
| Retry | `test_node_resolution_retry.py` | 5 | Flag off; cap 1; amount alargado encontra; miss após retry; `widened_match_settings` não muta |
| Routing | `test_node_routing.py` | 3 | Sem regra → `op_joao`; sem regra em modo `hitl` deixa o operador vazio e segue; regra existente ignora o setting |
| HITL serviço | `test_hitl.py` | 9 | Approve+review; approve sem draft → `HitlConflictError`; escalate sem draft; prazo da due date e prazo default; `count_hitl_overdue`; flag off resolve sem HTTP; Nylas envia o texto; erro HTTP deixa `awaiting_human` |
| Grafo memória | `test_graph.py` | 3 | Happy path → `awaiting_human`; quarentena sem LLM; discard |
| Day 3 ports | `test_day3.py` | 4 | SAP fixtures; sender directory; audit/draft memória; extras Postgres |
| Day 4 routing | `test_day4.py` | 7 | Intent+mine; skip identity (unknown / low conf); `extraction_confidence` baixa ignora a ref; discard não chama intent; DELEGATE sem RESOLVE; audit Postgres |
| Worker sync | `test_process_email.py` | 2 | Persist `awaiting_human`; quarentena síncrona |
| HTTP | `test_api.py` | 7 | health, 404, GET ticket, ingest/webhook 202 (delay mock), fallback Redis, approve/escalate |
| Eval smoke | `test_eval_suite.py` | 5 | 30 ficheiros presentes; campo `expected` não declarado não conta; `null` explícito conta; harness sem Streamlit/Launchpad; corre **001** e **004** |
| Webhook Nylas | `test_nylas_webhook.py` | 6 | Segredo vazio; challenge; HMAC válido enfileira; assinatura má → 401; outro tipo ignorado; sem segredo → 503 |

Eval completo (não é pytest): `scripts/run_eval.py` + 30 fixtures em `fixtures/emails/`. Baseline `golden_dataset/baselines/v1.json` = **29/30** (0.967); o 022 falha de propósito (store nova por fixture). Threshold **0.80**. LLM = `FixtureGuidedLLM` (devolve o bloco `expected` da fixture). Retry **off**.

---

## G1 — Infra da suíte (CI, markers, isolamento)

Não é um buraco de regra de negócio; é o que impede a suíte de ser um gate.

| Lacuna | Detalhe | Melhoria concreta |
|---|---|---|
| Sem markers | `pytest tests` exige Postgres | `@pytest.mark.postgres` nos 8 testes da tabela acima; `addopts` / `-m "not postgres"` no job rápido |
| Sem CI | Não existe `.github/workflows/` | Job 1: memória + `python scripts/run_eval.py`. Job 2: Postgres service `5434` + `alembic upgrade head` + pytest completo |
| BD partilhada | `commit` na lab DB | Transacção com rollback, schema `test_*`, ou DB `lab_test`. Não usar `lab:lab_dev` de demo |
| Sem coverage | `pytest-cov` não está em `dev` | Falhar abaixo de um piso em `app/graph/`, `app/api/hitl.py`, `app/domain/` |
| Sem `conftest.py` | Cada teste Postgres abre `create_engine(settings.DATABASE_URL)` | Fixture `session` / `engine` única; `make_test_deps` já está em `tests/helpers.py` |
| Ruff | Extra `dev`, nunca no CI | `ruff check app tests scripts` |

---

## G2 — Nós do grafo sem teste unitário dedicado

O grafo tem 10 nós inbound em `app/graph/app.py`. `send` **não** está no `StateGraph`; corre via `HitlService.approve` → `make_send_node`.

| Nó | Ficheiro de produção | Teste dedicado? | Coberto só por |
|---|---|---|---|
| ingest | `app/graph/nodes/ingest.py` | Sim | — |
| security | `security.py` | Sim | — |
| thread | `thread.py` | Sim (6 casos, inclui truncagem) | — |
| triage | `triage.py` | Sim | — |
| **intent** | `intent.py` | **Não** | `test_day4` (grafo completo) |
| **sender** | `sender.py` | **Não** | `test_day4::test_known_intent_goes_to_sender_and_mine` (só o ramo email 0.9) |
| routing | `routing.py` | Sim (`test_node_routing.py`) | `test_day4` ainda cobre MINE vs DELEGATE no grafo |
| resolution | `resolution.py` + `match.py` | Sim | — |
| **draft** | `draft.py` | Só `pick_target` em `test_node_resolution.py` | eval 001–030; grafo happy path |
| hitl (nó) | `hitl.py` | Sim, o prazo (`test_hitl.py`) | estado final `awaiting_human` ainda vem do grafo / eval |
| **send** | `send.py` | **Não** há ficheiro só do node | `test_hitl.py`: mock, Nylas com sucesso, erro HTTP deixa `awaiting_human` |

### intent (`make_intent_node`)

Código: persiste `intent`, `language`, `confidence`; `skip_identity` se `Intent.UNKNOWN` **ou** `confidence < INTENT_MIN_CONFIDENCE` (default `0.5`).

Falta isolado:

- `ticket_id` inválido → `missing_ticket` (`stop_reason == "missing_ticket"`) — `_ticket.load_ticket` / `missing_ticket` **nunca** são testados em nenhum nó.
- Intent `delay_reason` / `future_timing` (só `payment_status` e `unknown` nos testes pytest; eval tem `013` e `014` mas pytest não os corre).
- Confiança **igual** ao limiar (`0.5`): o código usa `<`, portanto `0.5` **não** deve skippar — não há teste de fronteira.

Ficheiro sugerido: `tests/test_node_intent.py`.

### sender (`make_sender_node`) — nunca pára o grafo

Três scores no código, um testado:

| Score | Condição | Teste |
|---|---|---|
| `0.9` | `get_by_email` encontra | Indirecto no happy path ACME |
| `0.6` | email desconhecido, **exactamente um** sender no domínio | **Ausente** |
| `0.0` | zero ou vários no domínio | **Ausente** (`sender_id is None`) |

O nó não escreve `sender_id` no ticket, só no state/audit. Um teste unitário deve assertar `audit_confidence` e `sender_id` no dict de update.

Ficheiro sugerido: `tests/test_node_sender.py`.

### routing (`make_routing_node`)

Coberto em `test_node_routing.py`: sem regra atribui `op_joao` e faz MINE; sem regra com `ROUTING_NO_RULE_BEHAVIOUR=hitl` deixa `assigned_operator_id` vazio e segue; regra de email `op_other` delega e ignora o setting. O grafo do dia 4 ainda cobre ACME → MINE.

Falta:

- Rule por **domínio** só (`get_routing_rule(..., domain=)`), sem match de email exacto.

### draft (`make_draft_node`)

`test_node_resolution.py::test_pick_target_table` cobre alguns ramos da **função pura**. Não instancia `make_draft_node`.

`pick_target` — ramos **sem** asserção no pytest:

| Situação (código `draft.py`) | Esperado | Teste? |
|---|---|---|
| `TOO_MANY` | `None` (skip draft) | Não (`MULTIPLE` sim, `TOO_MANY` não) |
| `VAT_DISCREPANCY` | `None` | Não nesta tabela (VAT está no nó resolution) |
| IN_APPROVAL + `is_near_due` + owner | `APPROVAL_OWNERS` | Só `is_overdue=True`; **near-due não** |
| POSTED + `PENDING` + overdue | `PAYMENTS` | Não |
| POSTED + `PARTIAL` + not overdue | `SENDER` | Não |
| POSTED + `PAID` + clearing | `SENDER` | Sim |
| POSTED + `PAID` sem clearing | `None` | Sim (via `no_owner`/paid-nc noutros sítios; na tabela paid-nc não está explícito como `pick_target` — o teste paid sem clearing está no **resolution** `requires_hitl`, não em `pick_target`) |

O nó completo ainda faz:

1. `skip_draft=True` e **não** chama LLM quando `target is None`.
2. `attach_payment_proof=True` só se `invoice.status == PAID` **e** `clearing_document` truthy (`draft.py` L104–108). **Nenhum** teste pytest lê `attach_payment_proof` no draft persistido. O eval pontua a dimensão (fixture `003_posted_paid_clearing.json`); pytest smoke não corre o 003.
3. `_to_email`: `INVOICING_EMAIL` / `PAYMENTS_EMAIL` / `approval_owner_email` / fallback `ticket.sender_email`. Só o eval compara `to_email`.
4. Persistência `InMemoryDraftStore.save` a partir do nó (Day 3 testa o store à parte, não o nó).

Ficheiro sugerido: `tests/test_node_draft.py`.

### hitl node (`make_hitl_node`)

Sempre `AWAITING_HUMAN` + `should_stop=True`, mesmo com `skip_draft`. Não há teste que chame o nó com `skip_draft=True` (VAT / multiple / paid-no-clearing) e confirme `audit_metadata.skip_draft`.

O contrato “nunca auto-send no inbound” está implícito em `test_graph` (status final `awaiting_human`), não no nó isolado.

### send (`make_send_node`)

Só exercitado por `HitlService.approve`. Falta:

- Sem draft → `stop_reason == "no_draft"` (o serviço aborta **antes** com `HitlConflictError`; o nó em si não é chamado).
- `ticket_id` em falta → `missing_ticket`.
- `NYLAS_SEND_ENABLED=True` with key and grant: Approve POSTs `messages/send` before resolving. Flag off does not call the network. HTTP failure leaves the ticket `awaiting_human` (`tests/test_hitl.py`).
- `review_action` `APPROVE` vs `APPROVE_EDIT` gravado no `HumanReview` (API testa `edited_by_human` no draft; `test_hitl` approve **sem** `final_text` → `APPROVE`, nunca `APPROVE_EDIT` no store de reviews).

---

## G3 — Comportamento implementado e não coberto

### Ingest

| Código | Teste actual | Falta |
|---|---|---|
| `not thread_id or not message_id` (`ingest.py` L19) | Só `thread_id=None` | `message_id` vazio/`None`; ambos em falta; strings `"  "` (o código faz `.strip()`) |
| Duplicado | Mesmo `message_id`, subject diferente | Duplicado **concorrente** (dois `ainvoke` / dois workers) — Postgres unique? **não há unique constraint testada** em `message_id` |
| Parse email | `from` | `from_email` (o adapter aceita os dois, `mock_email.py` L23); `received_at` ISO string vs datetime vs ausente |

### Security

| Código | Falta |
|---|---|
| Email sem `@` → domínio `""` → não está na whitelist → quarentena | Teste |
| Whitelist CSV com espaços (`" acme-supplies.com "`) | `_whitelist` faz strip; sem teste |
| `spf_pass`/`dkim_pass` **ausentes** com `SPF_DKIM_ENABLED=True` | Tratados como fail (`is True`). Teste só envia `False`/`True` explícitos. Payload sem chaves deve quarentenar (ambos “não True”) |
| Fixture eval `017_spf_dkim_fail.json` | Não corre no pytest |

### Thread (`thread.py`)

`_ACTIVE = {OPEN, AWAITING_HUMAN}`. Prior: `active or resolved`. Escalated tem precedência.

| Caso | Teste |
|---|---|
| Prior `OPEN` | Sim (`test_open_thread_is_continuation_to_resolution`) |
| Prior `AWAITING_HUMAN` | **Não** — deve ir a resolution no **mesmo** ticket, body concatenado com `\n\n---\n\n` |
| Prior `RESOLVED` | **Não** — código **reabre** para `OPEN` (`thread.py` L48–49) e `route == "resolution"` |
| Prior `ESCALATED` | Sim; ticket novo → `DISCARDED` |
| Prior `DISCARDED` / `QUARANTINED` / `DELEGATED` | Não são `_ACTIVE` nem `RESOLVED` nem o first escalated… `DELEGATED` não entra em `_ACTIVE`. Um follow-up na mesma thread após delegate seria tratado como **thread nova** (triage outra vez) se não houver OPEN/AWAITING/RESOLVED/ESCALATED. **Comportamento não documentado em teste.** |
| Continuação no **grafo** (`ainvoke` até HITL, skip triage) | Só o nó isolado. Eval diz explicitamente que continuações são tickets novos (`scripts/eval_harness.py` L3–4, `fixtures/emails/README.md`) |

### Matching (`app/graph/match.py`)

Coberto: exact 1; exact em approval **e** posted → `MULTIPLE`; fuzzy 1 (`INV-2026-000l`); amount+supplier; not found.

| Ramo | Linhas | Teste |
|---|---|---|
| `len(exact) > 1` no **mesmo** lado (`TOO_MANY`, method exact) | L72–73 | **Não** (só MULTIPLE cross-source) |
| Fuzzy `len(hits) > 3` → `TOO_MANY` | L83–84 | **Não** |
| Fuzzy `len == 2 ou 3` → `MULTIPLE` | L85–86 | **Não** |
| Amount+supplier `len > 1` → `MULTIPLE` | L99–100 | **Não** |
| `due_flags` overdue / near-due / sem `due_date` | L107–114 | **Não** (indirecto via draft overdue) |
| `looks_like_vat_gross` isolado (extracted ≈ net×1.23, não ≈ net) | L117–130 | Só via nó + LLM notes |
| Retry: MATCH exact **não** retenta; MATCH com `confidence >= 0.85` não retenta; MATCH fuzzy baixo **sim** | `should_retry_match` | Só NOT_FOUND + flag off/on. **Não** o ramo “fuzzy match com confiança baixa retenta” |
| Retry fuzzy floor `RESOLUTION_RETRY_FUZZY_FLOOR=0.75` a encontrar ref que falha a 0.85 | — | Só amount-tolerance em `test_retry_amount_tolerance_finds_unique_match` |

### HITL HTTP (`app/api/main.py` + `hitl.py`)

`test_api.py::test_approve_and_escalate_http` cobre: GET draft 200, GET `/tickets` contém o id (**sem** `?status=`), GET `/stats` é um `dict`, approve em `OPEN` → **409**, approve com `final_text` → `resolved` + `edited_by_human`, escalate → `escalated`.

Falta (rotas que a UI usa):

| Rota / caso | Quem chama | Teste |
|---|---|---|
| `GET /tickets?status=awaiting_human` | `frontend/src/lib/api.ts` `getTickets` + tab HITL default | **Não** (`TicketRepo.list_tickets(status=...)`) |
| `GET /tickets?status=` outras vistas (`delegated`, `quarantined`, `escalated`, `resolved`) | tiles em `StatTiles.tsx` | **Não** |
| `GET /tickets` `limit=` | API default 100, ordenado por `updated_at` desc | **Não** |
| `GET /stats` chaves concretas (`open`, `awaiting_human`, …) | `StatTiles` / header | Só `isinstance(..., dict)` |
| `GET /tickets/{id}` payload `sender` / `draft` / `invoice` / `audit` | `ticket_detail()` em `app/api/tickets.py` | GET ticket no teste API é um ticket **OPEN sem draft**; não asserta nested fields. Happy path HTTP inbound+detalhe **não** existe (ingest está mocked) |
| `GET /tickets/{id}/draft` 404 ticket / 404 sem draft | UI desactiva Approve se `draft == null`, mas a API 404 existe | **Não** |
| `POST /approve` ticket inexistente → 404 | — | **Não** (`HitlService` devolve `None` → 404) |
| `POST /escalate` ticket `OPEN` → 409 | Approve 409 sim; escalate 409 **não** | **Não** |
| `POST /escalate` **com** draft grava `HumanReview` `ESCALATED_TO_EMAIL` | `hitl.py` L86–94 | Escalate no API **não** cria draft no ticket de escalate |
| Approve **sem** `final_text` (UI quando o textarea não mudou) | — | API só testa com `final_text` |
| Approve grava o operador da **sessão**, mesmo que o body traga outro `operator_id` | `tests/test_auth.py` | **Sim** |
| Login, password errada, operador inactivo, logout, sessão expirada, rotas sem cookie | `tests/test_auth.py` | **Sim** |
| CORS com origem explícita e `allow_credentials` | `CORS_ORIGINS`, default `http://localhost:5173` | **Não** há teste HTTP de preflight |

### Worker / Celery

| Caminho | Teste |
|---|---|
| `process_email.delay` **real** (Redis 6380 + worker `--pool=solo`) | **Não**. API patcha `process_email.delay` |
| Fallback Redis down | Sim, só quarentena (`evil.example`) |
| Fallback Redis down **happy path** AP → `awaiting_human` no JSON de resposta | **Não** (o teste de happy path é `run_process_email` directo, não via `POST /ingest`) |
| Worker a correr **só** o grafo inbound (não send) | Por construção; sem teste de que `make_send_node` não está em `build_graph` (assert `graph.nodes` / edges) |

### Postgres adapters não cobertos como unidade

| Classe | Métodos | Teste directo |
|---|---|---|
| `TicketRepo` | `get_by_message_id`, `list_tickets(status=, limit=)` | **Não** (só save/get_by_id + extras Day 3) |
| `DraftRepo` | save/get, `final_text`, `edited_by_human`, `attach_payment_proof` | Indirecto no API approve |
| `HumanReviewRepo` | save/get | **Nunca** (HITL testes usam `InMemoryReviewStore`; API usa `HumanReviewRepo` mas não relê a tabela) |
| Migrações | `alembic/versions/edb81d2a0b75_tickets.py`, `a1b2c3d4e5f6_full_schema.py` | **Não** (`alembic upgrade head` em CI) |

### Settings / LLM live

`settings.py` define `LLM_PRIMARY_*`, `CONFIDENCE_THRESHOLD`, `EVAL_LIVE_LLM`, `NYLAS_SEND_ENABLED`. **Não há adapter OpenAI** no repo (`grep openai` = vazio). `CONFIDENCE_THRESHOLD` não é usado para send (HITL sempre). `judge_draft(..., live=)` faz `del live` e compara strings (`app/llm/judge.py`). Testar “LLM real” agora seria inventar produto.

Útil mesmo assim: um teste de que `empty_or_placeholder_llm_setting_is_none` trata `"<key>"` e `""` como `None` (evita rebentos de `.env.example`).

---

## G4 — Eval: pytest smoke vs 30 golden

`tests/test_eval_suite.py` **não** corre o harness completo. Só 001 e 004.

| ID | Fixture | Dimensões que o golden cobre | No pytest? |
|---|---|---|---|
| 001 | `001_invoice_not_found.json` | not_found → invoicing | Smoke |
| 002 | in_approval on time | match → sender | Não |
| 003 | posted paid + clearing | `attach_payment_proof` | Não |
| 004 | unknown domain | quarantined, 0 LLM calls | Smoke |
| 005 | not AP discard | discarded | Não (há equivalente em `test_graph`) |
| 006 | delegate other operator | delegated | Não (há `test_day4` DELEGATE) |
| 007 | VAT discrepancy | skip draft, HITL | Não (há nó resolution VAT) |
| 008 | multiple sources | MULTIPLE | Não (há `match_invoices` unit) |
| 009 | posted blocked | PAYMENTS | Não |
| 010 | overdue + owner | APPROVAL_OWNERS | Não |
| 011 | unknown intent | skip identity | Não (`test_day4`) |
| 012 | low confidence intent | skip identity | Não (`test_day4`) |
| 013 | delay_reason | intent enum | Não |
| 014 | future_timing | intent enum | Não |
| 015 | fuzzy ref | method fuzzy | Não (unit match sim) |
| 016 | amount + supplier | method amount | Não (unit match sim) |
| 017 | SPF/DKIM fail | quarantined | Não (unit security sim) |
| 018 | posted partial | SENDER | Não |
| 019 | paid no clearing | HITL sem dizer “paid” | Não (unit resolution sim) |
| 020 | overdue no owner | skip draft | Não (`pick_target` no_owner sim) |

Fixtures **021–030** existem no mesmo directório. O 022 é o duplicado por conteúdo e falha no golden de propósito. A tabela acima pára no 020.

O que o eval **não** mede, mesmo a 29/30:

- Texto do draft como dimensão de `workflow_ok` (`judge_draft` corre mas **não** entra em `workflow_ok = all(dimensions.values())` — `eval_harness.py` L118–130).
- Qualquer classificação LLM real (`FixtureGuidedLLM` ignora `user_prompt`).
- Continuação de thread (documentado).
- Retry Day 7 (`RESOLUTION_RETRY_ENABLED=False` forçado no harness).
- Send / approve (inbound pára no HITL).
- `scripts/run_shadow.py` é o **mesmo** `run_all_sync()` a escrever `shadow_v1.json` com `"mode": "shadow"`. Não é um segundo dataset nem um LLM diferente. Não há teste que o script exista ou que o artefact difira.

Melhoria mínima: parametrizar pytest com `load_fixtures()` e `assert row["workflow_ok"]` nos 30, **ou** falhar o CI se `run_eval.py` exit ≠ 0. Sem isso, apagar `003_posted_paid_clearing.json` só rebenta `test_thirty_golden_fixtures_present` pelo count, não pelo comportamento.

---

## G5 — Frontend (`frontend/`) — cobertura 0

`package.json`: `dev` / `build` / `lint` (oxlint) / `preview`. Sem Vitest, Testing Library, Playwright.

Ficheiros sem teste:

| Ficheiro | Comportamento que quebra sem teste |
|---|---|
| `src/lib/api.ts` | `credentials: "include"`; 401 (excepto `/auth/login` e `/auth/me`) chama o handler de sessão; approve sem `operator_id`; escalate sem body |
| `src/lib/time.ts` | ISO **sem** `Z` tratado como UTC; `formatRelative` usa o mesmo parse |
| `src/lib/filters.ts` | `statusForFilter("all") === undefined`; a vista inicial é `"awaiting_human"` |
| `src/auth/AuthContext.tsx` | `GET /auth/me` no arranque; logout ignora erro de rede e vai para `/login` |
| `src/auth/RequireAuth.tsx` | `loading` mostra skeleton; `anon` redirecciona para `/login` |
| `src/components/HitlDialog.tsx` | Approve disabled sem draft ou com API down; Escalate continua disponível; toast só depois de sucesso |
| `src/App.tsx` | Só manda `final_text` se o texto mudou; depois do HITL limpa a selecção |
| `src/components/TicketDetail.tsx` | Tabs Email / Invoice / Draft / Audit; audit usa `created_at` e `confidence` |
| `src/components/StatTiles.tsx` | Consome `GET /stats`; esconde Open quando a contagem é zero |

Sugestão em duas camadas:

1. **Vitest** (sem browser): `statusForFilter`; `formatLocal` / `formatRelative`; dialog com Approve disabled; `api.ts` com `fetch` mock (`credentials`, 401, approve sem `operator_id`).
2. **Playwright** (1 fluxo): API+UI up → lista HITL → abrir ticket com draft → editar textarea → Approve → ticket sai da tab HITL e aparece em Resolved. Segundo fluxo: Escalate sem draft (VAT) continua clicável.

`npm run build` (`tsc -b`) é o único gate de tipos; não substitui estes casos.

---

## G6 — O que os testes **não** podem garantir (produto ainda mock)

Não são lacunas da suíte no sentido de “falta um teste do conector”; o código não existe.

| Área | Estado | Não fingir teste de |
|---|---|---|
| SAP live | `MockSAPAdapter` + `fixtures/sap_mock/` | RFC/OData |
| Email send | Approve POSTs when the flag, key, and grant are set. Flag off stays mock | Delivery to a live mailbox |
| Email inbound real | `POST /webhook/nylas` checks the HMAC and enqueues | A live Nylas delivery inside CI |
| OCR | `attachments` parseados e ignorados | PDF/VAT de scan |
| Papéis e várias empresas | Sessão de um operador, sem RBAC | JWT / RBAC / multi-tenant |
| LLM em produção | `OpenAILLMAdapter` com a chave; eval default continua `FixtureGuidedLLM` | Qualidade do gpt-4o-mini no golden set ao vivo |
| Auto-send | `CONFIDENCE_THRESHOLD` unused | Envio sem HITL |
| Checkpointer LangGraph | Opção 2: grafo acaba no `hitl` | `interrupt()` / `Command(resume=)` |

Testes novos devem continuar a injectar ports (`make_test_deps`). Um teste “live LLM” só faz sentido atrás de `EVAL_LIVE_LLM` opt-in, nunca no default CI.

---

## Backlog por prioridade

Ordem sugerida se fores a fechar lacunas (não é um plano de dias; é custo/risco).

### P0 — a suíte como gate

1. Markers `postgres` + job CI memória **sem** Docker.
2. Job CI `python scripts/run_eval.py` (os 30 golden, não só 001/004).
3. Job CI Postgres (service) + `alembic upgrade head` + pytest `-m postgres`.
4. Isolar writes (rollback ou DB `lab_test`) para o job 3 não destruir a BD de demo.

### P1 — o que a consola parte e o pytest não vê

5. `GET /tickets?status=awaiting_human` (+ 409 escalate, 404 draft, detalhe com `draft`/`audit`).
6. Vitest: dialog desactiva Approve sem draft; `api.ts` manda o cookie e omite `operator_id`; `statusForFilter`.
7. `test_node_draft.py`: `attach_payment_proof`, skip LLM quando `target is None`, `_to_email` invoicing/payments/owner.
8. Thread: prior `RESOLVED` reabre; prior `AWAITING_HUMAN` continua; um `ainvoke` de follow-up que **não** chama triage (0 calls extra de `TriageOutput`).

### P2 — ramos de matching / identidade

9. `TOO_MANY` exact e fuzzy; amount MULTIPLE; `due_flags`; retry fuzzy floor.
10. `test_node_sender.py` scores 0.6 / 0.0; routing sem rule → MINE.
11. Ingest `message_id` em falta / whitespace; SPF keys ausentes com flag on.
12. `HumanReviewRepo` Postgres após approve/escalate; `list_tickets` + `get_by_message_id`.

### P3 — nice-to-have

13. Playwright happy-path HITL.
14. Grafo: assert `send` ∉ nodes compilados.
15. Celery e2e opcional (Redis de teste + worker solo).
16. `pytest-cov` piso em `app/graph` + `app/api/hitl.py`.
17. Parametrizar os 30 fixtures no pytest (além do script).
18. Teste do validator de placeholders LLM em `Settings`.
19. Ou apagar `run_shadow.py`, ou fazê-lo diferir de verdade do eval (senão é ruído).

---

## Mapa rápido: “se eu mudar X, que teste falha?”

| Se mudares | Falha hoje? | Buraco |
|---|---|---|
| Whitelist / quarentena | `test_node_security`, `test_graph`, eval 004 | SPF sem chaves no payload |
| Discard triage | `test_node_triage`, `test_graph` | — |
| Ladder exact/fuzzy/amount | `test_node_resolution` | `TOO_MANY`, fuzzy múltiplo |
| Tabela draft target (alguns ramos) | `pick_target` parcial + eval se correres o script | near-due, PARTIAL, TOO_MANY, attach proof no pytest |
| Park HITL / no auto-send | `test_graph`, eval | Nó `hitl` + `skip_draft` |
| Approve / 409 / escalate | `test_hitl`, `test_api` | Query `?status=`; review Postgres; approve sem edit |
| Retry resolution | `test_node_resolution_retry` | Retry fuzzy, não amount |
| Intent skip identity | `test_day4` | Fronteira `== INTENT_MIN_CONFIDENCE` |
| DELEGATE | `test_day4` | Default operator sem rule |
| Thread continuation | 3 testes de nó | RESOLVED reopen, AWAITING_HUMAN, grafo |
| Filtros da UI | **Nada** | G5 |
| Celery broker | Só o mock `.delay` | Worker real |
| Texto do draft | Eval `judge_draft` (não bloqueia `workflow_ok`) | — |

---

## Relação com os planos Day 0–7

Os `PLAN_DAY*.md` marcam testes como done no dia em que o lab fechou o gate. Este ficheiro é o **delta depois da parity**: o que ficou de fora de propósito (eval sem threads, retry off no golden) e o que ficou de fora por omissão (UI, CI, ramos `TOO_MANY` / sender 0.6, isolamento da BD).
