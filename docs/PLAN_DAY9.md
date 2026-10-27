# Day 9 — Backend authentication (~4h)

> Operators log in; the ticket and HITL endpoints require a session. Cookie-based (`HttpOnly`), Argon2 passwords, sessions in Postgres. No JWT, no OAuth.
>
> Previous: [PLAN_DAY8.md](PLAN_DAY8.md). Next: [PLAN_DAY10.md](PLAN_DAY10.md). Charter: [README.md](README.md).

**Status:** done. The checklist below is the original brief and was not re-ticked. Cookie sessions, Argon2, and protected ticket and HITL routes are in the repo.

Why this day exists: today anyone who can reach port 8000 can approve a ticket, and `operator_id` is a free-text field in the request body. After Day 9, the operator who approves is whoever owns the session — not whatever string the client sent.

Design decisions (keep them; they shape every step below):

- **Auth is not a workflow port.** The graph never needs to know who is logged in. Auth lives in `app/auth/`, outside `WorkflowDeps`.
- **Operator ids stay strings** (`op_joao`, `op_other`). They already appear in `tickets.assigned_operator_id`, `human_reviews.operator_id`, `routing_rules.operator_id`, and `DEFAULT_OPERATOR_ID`. A UUID would break all of those.
- **Server-side sessions.** The cookie holds a random token; Postgres holds only its SHA-256. Logout and expiry are a row update, not a token blacklist.
- **New tables use `TIMESTAMPTZ`.** Existing tables stay naive `DateTime` (no contract migration today).

---

## Block (~4h)

### 9.0 Setup (10 min)

- [ ] Add `argon2-cffi` to `dependencies` in `pyproject.toml`; `pip install -e ".[dev]"`
- [ ] New settings in `settings.py` (with defaults, so `.env.dev` keeps working):

```python
# Auth
SESSION_COOKIE_NAME: str = "p2p_session"
SESSION_TTL_HOURS: int = 12
COOKIE_SECURE: bool = False          # True behind HTTPS
CORS_ORIGINS: str = "http://localhost:5173"
```

- [ ] Add the same keys to `.env.dev` with the dev values

### 9.1 Domain + package layout (15 min)

- [ ] `app/domain/models.py` — add `Operator` (no password hash in the domain model):

```python
class Operator(BaseModel):
    id: str
    email: str
    display_name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utc_now)
```

- [ ] New package `app/auth/` with `__init__.py`:

```
app/auth/
  passwords.py      # Argon2 hash / verify
  tokens.py         # token generation + sha256
  repo.py           # Postgres: operators + operator_sessions
  dependencies.py   # get_current_operator (FastAPI)
  schemas.py        # LoginBody, OperatorOut
```

### 9.2 Tables + migration (40 min)

- [ ] `app/adapters/db_models.py` — two tables:

```python
class OperatorTable(SQLModel, table=True):
    __tablename__ = "operators"
    id: str = Field(primary_key=True)
    email: str = Field(index=True, unique=True)
    display_name: str
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OperatorSessionTable(SQLModel, table=True):
    __tablename__ = "operator_sessions"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    token_hash: str = Field(index=True, unique=True)   # sha256 hex, 64 chars
    operator_id: str = Field(
        sa_column=Column(ForeignKey("operators.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
```

- [ ] `alembic revision --autogenerate -m "operators and sessions"`
- [ ] Open the generated file and check by hand:
  - only `create_table` + `create_index` in `upgrade()` (expand-only; no `alter`/`drop` on existing tables)
  - `sa.DateTime(timezone=True)` on all four timestamp columns
  - unique index on `operators.email` and `operator_sessions.token_hash`
  - FK `operator_sessions.operator_id → operators.id` with `ondelete="CASCADE"`
  - `downgrade()` drops sessions **before** operators
- [ ] `alembic upgrade head`, then `alembic downgrade -1`, then `alembic upgrade head` again (round-trip proves the downgrade)

Do **not** add an FK from `human_reviews.operator_id` to `operators.id` today — existing rows were written before operators existed. That is a separate contract migration.

### 9.3 Passwords — `app/auth/passwords.py` (10 min)

- [ ] One module-level `PasswordHasher()` (sync, stateless — safe to share)
- [ ] `hash_password(plain) -> str`
- [ ] `verify_password(hash, plain) -> bool` — catch `argon2.exceptions.VerifyMismatchError` → `False`; let other errors raise
- [ ] `needs_rehash(hash) -> bool` — on successful login, if true, store a fresh hash

### 9.4 Tokens + repo (35 min)

- [ ] `app/auth/tokens.py`:

```python
def new_token() -> str:
    return secrets.token_urlsafe(32)

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
```

- [ ] `app/auth/repo.py` — `AuthRepo(session)`:
  - `get_operator(operator_id) -> Operator | None`
  - `get_credentials(email) -> tuple[Operator, str] | None` (operator + hash; email lower-cased and stripped)
  - `upsert_operator(operator, password_hash)` (used by the seed script)
  - `update_password_hash(operator_id, password_hash)`
  - `create_session(operator_id, ttl_hours) -> str` — returns the **raw** token, stores only `token_hash`
  - `get_session_operator(token) -> Operator | None` — `None` if no row, `revoked_at` set, `expires_at <= now`, or operator inactive
  - `revoke_session(token)`

### 9.5 Schemas — `app/auth/schemas.py` (10 min)

First explicit request/response split in this API:

```python
class LoginBody(BaseModel):
    email: str
    password: str

class OperatorOut(BaseModel):
    id: str
    email: str
    display_name: str
```

`OperatorOut` never includes `password_hash` or `is_active`.

### 9.6 Endpoints — `app/api/auth.py` (35 min)

- [ ] `router = APIRouter(prefix="/auth", tags=["auth"])`, included in `app/api/main.py`
- [ ] `POST /auth/login` (body `LoginBody`) → `OperatorOut`
  - unknown email **and** wrong password both return `401 {"detail": "invalid credentials"}` — same message, so the endpoint does not reveal which emails exist
  - inactive operator → same 401
  - on success: `create_session`, then:

```python
response.set_cookie(
    key=settings.SESSION_COOKIE_NAME,
    value=token,
    httponly=True,
    samesite="lax",
    secure=settings.COOKIE_SECURE,
    max_age=settings.SESSION_TTL_HOURS * 3600,
    path="/",
)
```

- [ ] `POST /auth/logout` → `204`; revoke the session if the cookie is present; always `response.delete_cookie(SESSION_COOKIE_NAME, path="/")`
- [ ] `GET /auth/me` → `OperatorOut` or `401`

### 9.7 Dependency — `app/auth/dependencies.py` (15 min)

```python
def get_current_operator(request: Request) -> Operator:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    with Session(engine) as session:
        operator = AuthRepo(session).get_session_operator(token)
    if operator is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return operator
```

### 9.8 Protect the routes (25 min)

In `app/api/main.py`:

| Route | Auth |
|---|---|
| `GET /health` | public |
| `POST /webhook/mock`, `POST /ingest` | public (machine-to-machine; shared-secret header is out of scope) |
| `GET /stats` | **session** |
| `GET /tickets`, `GET /tickets/{id}`, `GET /tickets/{id}/draft` | **session** |
| `POST /tickets/{id}/approve`, `POST /tickets/{id}/escalate` | **session** |

- [ ] Add `operator: Operator = Depends(get_current_operator)` to each protected route
- [ ] Approve: drop `operator_id` from `ApproveBody` (keep `final_text: str | None = None`); pass `operator_id=operator.id` to `HitlService.approve`
- [ ] Escalate: remove `EscalateBody`; no request body; `operator_id=operator.id`
- [ ] `HitlService` itself does not change — it already takes `operator_id` as an argument

### 9.9 CORS (10 min)

Browsers reject `allow_origins=["*"]` together with credentials, so the cookie would never be sent from the UI.

- [ ] In `app/api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] Use `http://localhost:5173` and `http://localhost:8000` everywhere. `localhost` and `127.0.0.1` are different sites for cookies — mixing them silently drops the session.

### 9.10 Seed script — `scripts/seed_operator.py` (15 min)

Not an Alembic data migration: a migration would put a password hash in git.

- [ ] CLI: `python scripts/seed_operator.py --id op_joao --email joao@company.com --name "João"`
- [ ] Prompt for the password with `getpass` (twice, must match); never accept it as a CLI argument
- [ ] `upsert_operator` — running it again resets the password
- [ ] Seed `op_joao` (the `DEFAULT_OPERATOR_ID`) and optionally `op_other` for the delegate story

### 9.11 Tests (40 min)

- [ ] `tests/test_auth.py` (real login flow, `httpx.AsyncClient` like `tests/test_api.py`):
  - login ok → `200`, `Set-Cookie` contains `HttpOnly` and `SameSite=lax`, body has no `password_hash`
  - wrong password → `401 invalid credentials`
  - unknown email → `401 invalid credentials` (same body)
  - inactive operator → `401`
  - `GET /auth/me` without cookie → `401`; with cookie → `200`
  - logout → `204`; the same cookie on `/auth/me` → `401`
  - expired session (insert a row with `expires_at` in the past) → `401`
  - `GET /tickets` without cookie → `401`
  - approve with a session → the stored `HumanReview.operator_id` equals the session operator, even if the client sends a different `operator_id`
- [ ] `tests/test_api.py` — existing HITL tests must still pass:
  - add a fixture that sets `app.dependency_overrides[get_current_operator] = lambda: Operator(id="op_joao", email="joao@test", display_name="Test")` and clears it after the test
  - remove `operator_id` from the approve/escalate request bodies
- [ ] Unit tests for `passwords.py` and `tokens.py` (hash ≠ plain; verify true/false; two tokens differ; hash is 64 hex chars)

### Gate

```powershell
alembic upgrade head
python scripts/seed_operator.py --id op_joao --email joao@company.com --name "João"
pytest
```

API running — PowerShell keeps the cookie in a session variable:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/tickets            # expect 401
Invoke-RestMethod -Method POST -Uri http://localhost:8000/auth/login -ContentType "application/json" -Body '{"email":"joao@company.com","password":"<your password>"}' -SessionVariable s
Invoke-RestMethod -Uri http://localhost:8000/auth/me -WebSession $s
Invoke-RestMethod -Uri http://localhost:8000/tickets -WebSession $s
Invoke-RestMethod -Method POST -Uri http://localhost:8000/auth/logout -WebSession $s
Invoke-RestMethod -Uri http://localhost:8000/auth/me -WebSession $s   # expect 401
```

- [ ] Update the curl/PowerShell examples in `README.md`, `Start.md`, and `Demo.md` (login first, then `-WebSession $s` on ticket and HITL calls). The webhook examples do not change.

### Git

- Commit: `feat: operators and sessions tables (expand-only migration)`
- Commit: `feat: cookie session auth on ticket and HITL routes`
- Commit: `test: auth flow and protected routes`

---

## Definition of Done — Day 9

- [ ] Approve and escalate record the **session** operator, not a body field
- [ ] Ticket, stats, and HITL routes return 401 without a session
- [ ] Webhook and health still work without auth
- [ ] No password or password hash in git, logs, or API responses
- [ ] All existing tests green; new auth tests green

---

## Out of scope for this day

Roles/permissions, password reset, sign-up, OAuth/SSO, login rate limiting, CSRF tokens (`SameSite=Lax` is the mitigation for now), webhook authentication, FK from `human_reviews` to `operators`, frontend changes (Day 11).
