# Operator console

Vite + React + TypeScript console built with shadcn/ui. Operators sign in with the account stored by the backend; the session stays in an `HttpOnly` cookie. Naive UTC timestamps from the API are shown in the browser's local timezone.

## Run

API must already be on port **8000** (see the [root README](../README.md)). Create an operator once from the repository root:

```powershell
python scripts/seed_operator.py --id op_joao --email joao@company.com --name "João"
```

The script prompts for the password twice.

```powershell
copy .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173` and sign in. Keep both the UI and API on `localhost`; mixing it with `127.0.0.1` prevents the browser from sending the session cookie. `VITE_API_URL` must be `http://localhost:8000`.

## Layout

- **Header:** awaiting counter, API health, refresh, signed-in operator and sign out
- **Status tiles:** counts from `GET /stats`; clicking one filters the feed
- **Left:** ticket feed (`GET /tickets?status=`)
- **Right:** tabbed email, invoice, draft and audit timeline
- **Review & decide:** modal for editing, approving or escalating an `awaiting_human` ticket

Approve is disabled when there is no draft or the API is down. Escalate is disabled while the API is down, and still works without a draft when health is ok. The review is stored under the signed-in operator id. A 401 on any route except `/auth/login` and `/auth/me` clears the local operator state; `RequireAuth` then sends the browser to `/login`.

The draft tab shows `final_text` when a review edited the reply, otherwise `generated_text`. The audit tab is a timeline: each row has the node, action, confidence, and `created_at` from `GET /tickets/{id}`. When the ticket is awaiting a human, Draft opens first. Otherwise Audit opens first.
