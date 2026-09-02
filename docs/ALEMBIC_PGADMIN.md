# Day 1 — Alembic + viewing tables in pgAdmin

Notes from this lab (`p2p-ai-langraph`). The compose database is named `lab` and is published on the **host at port 5434**.

Day 3 adds a second migration (audit, drafts, HITL tables, extra ticket columns). This page describes the **first** migration (`tickets` only).

---

## 1. What Alembic is

Alembic is **not** pgAdmin. It:

1. reads `TicketTable` (`app/adapters/db_models.py`);
2. generates a Python file with the SQL (`CREATE TABLE`, indexes);
3. applies that SQL to Postgres (`upgrade`).

`TicketRepo` only writes **rows**. Without `upgrade`, the table does not exist yet.

### Steps already run

| Command | Result |
|---------|----------|
| `alembic init alembic` | `alembic.ini` + `alembic/` folder |
| `env.py` | imports `app.adapters.db_models`, `target_metadata = SQLModel.metadata`, URL = `settings.DATABASE_URL` |
| `alembic revision --autogenerate -m "tickets"` | created `alembic/versions/edb81d2a0b75_tickets.py` |
| `alembic upgrade head` | `Running upgrade  -> edb81d2a0b75, tickets` — SQL applied |

Error seen earlier: `Can't load plugin: sqlalchemy.dialects:driver` — `alembic.ini` still had the sample URL `driver://...`. `env.py` now uses the real URL (`postgresql+psycopg2://lab:lab_dev@localhost:5434/lab`).

The generated migration needs `import sqlmodel` (autogenerate uses `sqlmodel.sql.sqltypes.AutoString()`). Without it, `upgrade` blows up.

### The migration file

`alembic/versions/edb81d2a0b75_tickets.py`

- `revision = 'edb81d2a0b75'` — id of this change
- `down_revision = None` — first migration

**`upgrade()`** (what went to Postgres):

- table `public.tickets`
- columns: `id` (UUID, PK), `thread_id`, `message_id`, `sender_email`, `subject`, `body` (Text), `received_at`, `status`, `is_ap` (nullable), `created_at`, `updated_at`
- **unique** index on `message_id` (one email → one ticket, as in P2P)
- non-unique indexes on `sender_email`, `status`, `thread_id`

**`downgrade()`** — drops indexes and the table (you do not need this day to day).

Alembic also creates table `alembic_version` with one row (`edb81d2a0b75`) so it knows what is already applied.

### Useful commands

```bash
# generate (already done for tickets)
alembic revision --autogenerate -m "tickets"

# apply
alembic upgrade head

# which revision is in the DB
alembic current
```

---

## 2. Viewing tables in pgAdmin

The **Example** server in pgAdmin (user `postgres`, port **5432**) is **another** project. Do not use that connection for this lab.

### Connect to the lab (5434)

1. Object Explorer → **Servers** → right-click → **Register** → **Server…**
2. **General** tab: Name = e.g. `p2p-ai-langraph` (label in the tree only).
3. **Connection** tab:

| Field | Value |
|--------|--------|
| Host name/address | `127.0.0.1` |
| Port | **5434** |
| Maintenance database | `lab` |
| Username | `lab` |
| Password | `lab_dev` |

4. Save password if you want → **Save**.

The container listens on 5432 **inside**; on Windows/pgAdmin you use **5434** (`ports: "5434:5432"` in `docker-compose.yml`).

The container must be running: `docker compose up -d db` at the lab root.

### Where `tickets` is

```
Servers → p2p-ai-langraph → Databases → lab → Schemas → public → Tables
```

You should see **`tickets`** and **`alembic_version`**. After Day 3: drafts, audit, etc.

### SQL vs data (grid)

The **SQL** tab (with `tickets` selected) shows `CREATE TABLE` — **structure**, not rows.

To see the table **populated** (grid):

- right-click **tickets** → **View/Edit Data** → **All Rows**

or Query Tool:

```sql
SELECT * FROM tickets;
```

After Day 1, `tickets` is **empty**: Alembic only created the schema. Rows appear when `TicketRepo.save_ticket` (Gate 3) or the ingest node saves a ticket.

`alembic_version` already has a row — Alembic history, not emails.

---

## 3. Quick picture

```
TicketTable (Python)  →  alembic revision  →  file in versions/
                              ↓
                       alembic upgrade
                              ↓
                    Postgres lab:5434  →  pgAdmin (View/Edit Data)
```
