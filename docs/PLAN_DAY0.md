# Day 0 — Scaffold + infra (~2h, à mão)

> Sem gerar o projecto com o agente. Tu crias pastas, `pyproject`, compose e settings.

**Status:** em curso — setup até à árvore feito; próximo: `__init__.py`.

---

## Bloco (~2h)

### Setup (45 min)

- [x] Em `p2p-ai-langraph/`: `git init` se precisares; `.gitignore` (`__pycache__/`, `.env`, `.venv/`, `.pytest_cache/`)
- [x] `pyproject.toml` escrito por ti (`version` é obrigatório para o setuptools):

```toml
[project]
name = "p2p-ai-langraph"
version = "0.0.1"
requires-python = ">=3.12"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "sqlmodel",
  "alembic",
  "psycopg2-binary",
  "celery[redis]",
  "pydantic-settings",
  "langgraph",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "httpx", "ruff"]
```

- [x] `pip install -e ".[dev]"`
- [x] Árvore (vazia de lógica):

```
app/
  domain/
  ports/
  adapters/
  graph/          # LangGraph — Day 2
  api/
  worker/
alembic/
tests/
docs/
```

- [x] `__init__.py` em cada pacote `app/`
### Docker (30 min)

Portas **5434** (Postgres) e **6380** (Redis) para não chocar com o P2P (`5433` / `6379`).

- [x] `docker-compose.yml`: `postgres:16-alpine` (`lab` / `lab_dev` / db `lab`), `redis:7-alpine`, healthchecks
- [x] Correr **dentro** de `p2p-ai-langraph/`: `docker compose up -d`
- [x] `docker compose ps` — healthy

### Settings (20 min)

- [x] `settings.py`: `DATABASE_URL`, `REDIS_URL`, e já deixa sítio para Day 1:
  - `SENDER_DOMAIN_WHITELIST` (string CSV, ex. `acme-supplies.com`)
  - `SECURITY_CHECK_ENABLED=True` neste lab (para a whitelist **fazer** alguma coisa)
  - `TRIAGE_DISCARD_MIN_CONFIDENCE=0.8`
- [x] `.env.dev` → copiar para `.env`

### Gate

```bash
docker compose ps
python -c "from settings import settings; print(settings.DATABASE_URL)"
```

### Git

- Commit: `chore: scaffold, compose, settings`

---

## Fora deste dia

Não implementes nós, ports, nem LangGraph. Não copies o `pyproject` enorme do P2P (sem Streamlit, openai, reportlab).
