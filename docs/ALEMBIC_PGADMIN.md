# Day 1 — Alembic + ver tabelas no pgAdmin

Notas do que fizemos neste lab (`p2p-ai-langraph`). A BD do compose chama-se `lab` e está publicada no **host na porta 5434**.

---

## 1. O que é o Alembic

O Alembic **não** é o pgAdmin. É a ferramenta que:

1. lê o `TicketTable` (`app/adapters/db_models.py`);
2. gera um ficheiro Python com o SQL (`CREATE TABLE`, índices);
3. aplica esse SQL no Postgres (`upgrade`).

O `TicketRepo` só grava **linhas**. Sem `upgrade`, a tabela ainda não existe.

### Passos que já correste

| Comando | Resultado |
|---------|----------|
| `alembic init alembic` | `alembic.ini` + pasta `alembic/` |
| `env.py` | importa `app.adapters.db_models`, `target_metadata = SQLModel.metadata`, URL = `settings.DATABASE_URL` |
| `alembic revision --autogenerate -m "tickets"` | criou `alembic/versions/edb81d2a0b75_tickets.py` |
| `alembic upgrade head` | `Running upgrade  -> edb81d2a0b75, tickets` — SQL aplicado na BD |

Erro que vimos antes: `Can't load plugin: sqlalchemy.dialects:driver` — o `alembic.ini` ainda tinha o URL de exemplo `driver://...`. O `env.py` passa a usar o URL real (`postgresql+psycopg2://lab:lab_dev@localhost:5434/lab`).

Na migration gerada faz falta `import sqlmodel` (o autogenerate usa `sqlmodel.sql.sqltypes.AutoString()`). Sem isso o `upgrade` rebenta.

### O ficheiro da migration

`alembic/versions/edb81d2a0b75_tickets.py`

- `revision = 'edb81d2a0b75'` — id desta alteração
- `down_revision = None` — é a primeira migration

**`upgrade()`** (o que foi para o Postgres):

- tabela `public.tickets`
- colunas: `id` (UUID, PK), `thread_id`, `message_id`, `sender_email`, `subject`, `body` (Text), `received_at`, `status`, `is_ap` (nullable), `created_at`, `updated_at`
- índice **unique** em `message_id` (um email → um ticket, como no P2P)
- índices (não unique) em `sender_email`, `status`, `thread_id`

**`downgrade()`** — remove índices e a tabela (não precisas disto no dia a dia).

Alembic também cria a tabela `alembic_version` com uma linha (`edb81d2a0b75`) para saber o que já aplicou.

### Comandos úteis

```bash
# gerar (já feito)
alembic revision --autogenerate -m "tickets"

# aplicar (já feito)
alembic upgrade head

# ver que revision está na BD
alembic current
```

---

## 2. Ver as tabelas no pgAdmin

O **Example** no pgAdmin (user `postgres`, porta **5432**) é **outro** projecto. Não uses essa ligação para este lab.

### Ligar ao lab (5434)

1. Object Explorer → **Servers** → botão direito → **Register** → **Server…**
2. Tab **General:** Name = por exemplo `p2p-ai-langraph` (só o rótulo na árvore).
3. Tab **Connection:**

| Campo | Valor |
|--------|--------|
| Host name/address | `127.0.0.1` |
| Port | **5434** |
| Maintenance database | `lab` |
| Username | `lab` |
| Password | `lab_dev` |

4. Save password se quiseres → **Save**.

O contentor escuta 5432 **por dentro**; no Windows/pgAdmin usas **5434** (`ports: "5434:5432"` no `docker-compose.yml`).

O contentor tem de estar a correr: `docker compose up -d db` na raiz do lab.

### Onde está `tickets`

```
Servers → p2p-ai-langraph → Databases → lab → Schemas → public → Tables
```

Deves ver **`tickets`** e **`alembic_version`**.

### SQL vs dados (grelha)

A tab **SQL** (com `tickets` seleccionado) mostra o `CREATE TABLE` — a **estrutura**, não as linhas.

Para ver a tabela **preenchida** (grelha):

- botão direito em **tickets** → **View/Edit Data** → **All Rows**

ou Query Tool:

```sql
SELECT * FROM tickets;
```

Hoje `tickets` está **vazia**: o Alembic só criou o esquema. As linhas aparecem quando o `TicketRepo.save_ticket` (Gate 3) ou o workflow de ingestão gravar um ticket.

`alembic_version` já tem uma linha — é o histórico do Alembic, não emails.

---

## 3. Relação rápida

```
TicketTable (Python)  →  alembic revision  →  ficheiro em versions/
                              ↓
                       alembic upgrade
                              ↓
                    Postgres lab:5434  →  pgAdmin (View/Edit Data)
```
