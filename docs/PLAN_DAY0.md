# Day 0 — Scaffold + infra (~2h, by hand)

> Mini-lab day. Create folders, `pyproject`, compose, and settings yourself. Do not generate the whole project with an agent.

**Status:** done — scaffold through settings. Next historically: Day 1 domain. Full product spec continues in [PLAN_DAY3.md](PLAN_DAY3.md)–[PLAN_DAY7.md](PLAN_DAY7.md). Charter: [README.md](README.md).

---

## Block (~2h)

### Setup (45 min)

- [x] In `p2p-ai-langraph/`: `git init` if needed; `.gitignore` (`__pycache__/`, `.env`, `.venv/`, `.pytest_cache/`)
- [x] `pyproject.toml` written by you (`version` is required for setuptools):

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
- [x] Tree (no business logic yet):

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

- [x] `__init__.py` in every `app/` package

### Docker (30 min)

Ports **5434** (Postgres) and **6380** (Redis) so this lab does not clash with P2P (`5433` / `6379`).

- [x] `docker-compose.yml`: `postgres:16-alpine` (`lab` / `lab_dev` / db `lab`), `redis:7-alpine`, healthchecks
- [x] Run **inside** `p2p-ai-langraph/`: `docker compose up -d`
- [x] `docker compose ps` — healthy

### Settings (20 min)

- [x] `settings.py`: `DATABASE_URL`, `REDIS_URL`, and placeholders for Day 1:
  - `SENDER_DOMAIN_WHITELIST` (CSV string, e.g. `acme-supplies.com`)
  - `SECURITY_CHECK_ENABLED=True` in this lab (so the whitelist actually does something)
  - `TRIAGE_DISCARD_MIN_CONFIDENCE=0.8`
- [x] Copy `.env.dev` → `.env`

### Gate

```bash
docker compose ps
python -c "from settings import settings; print(settings.DATABASE_URL)"
```

### Git

- Commit: `chore: scaffold, compose, settings`

---

## Out of scope for this day

Do not implement nodes, ports, or LangGraph. Do not copy the huge P2P `pyproject` (no Streamlit, openai, reportlab required on Day 0).
