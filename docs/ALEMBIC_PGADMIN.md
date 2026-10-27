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

---

## Day 3 — `full_schema` (`a1b2c3d4e5f6`)

Second migration on the same `lab` database (port **5434**).

- `tickets` extra columns: `intent`, `language`, `assigned_operator_id`, `confidence`, `is_thread_continuation`
- new tables: `senders`, `routing_rules`, `invoice_cache`, `response_drafts`, `audit_entries`, `human_reviews`
- unique `message_id` on tickets is unchanged

Runtime senders/SAP still come from `fixtures/` JSON, not those cache tables.

```bash
alembic upgrade head
alembic current
```

In pgAdmin, refresh schema `public` — you should see the extra tables next to `tickets`.

## Operators and sessions (`88673197cd63`)

Expand-only migration. It creates tables and indexes. It does not alter tickets, reviews, or the other Day 3 tables.

- `operators`: `id` (string PK, same shape as `op_joao`), unique `email`, `display_name`, `password_hash` (Argon2), `is_active`, `created_at` `TIMESTAMPTZ`
- `operator_sessions`: UUID PK, unique `token_hash` (SHA-256 hex of the cookie), `operator_id` FK to `operators.id` with `ON DELETE CASCADE`, `created_at`, `expires_at`, nullable `revoked_at`. All four timestamps are `TIMESTAMPTZ`
- `downgrade()` drops `operator_sessions` before `operators`

There is still no FK from `human_reviews.operator_id` to `operators.id`. Reviews written before operators existed would not match.

Passwords are not in the migration. Create a login with:

```powershell
python scripts/seed_operator.py --id op_joao --email joao@company.com --name "João"
```

The script prompts twice and stores only the hash. Running it again resets that operator's password.

```bash
alembic upgrade head
alembic current
```

`alembic_version` should read `88673197cd63`. In pgAdmin, refresh `public` and you should see `operators` and `operator_sessions`.

## Ticket content hash (`f3a91c2e8b40`)

Expand-only. Adds nullable `tickets.content_hash` (`VARCHAR(16)`) and a non-unique index `ix_tickets_content_hash`. Existing rows stay `NULL` and are not backfilled. New ingest writes the hash of sender, subject, and the first 300 characters of the body.

```bash
alembic upgrade head
alembic current
```

`alembic_version` should read `f3a91c2e8b40`.

## Ticket HITL deadline (`a8c2e4b19d70`)

Expand-only. Adds nullable `tickets.hitl_deadline` (`timestamp`) and a non-unique index `ix_tickets_hitl_deadline`. Existing rows stay `NULL` and are not backfilled. The HITL node writes 00:00 UTC on the invoice due date, or now plus 24 hours when there is no due date.

```bash
alembic upgrade head
alembic current
```

`alembic_version` should read `a8c2e4b19d70`.
