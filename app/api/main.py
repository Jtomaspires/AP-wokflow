"""HTTP adapter: health, ingest, HITL, tickets."""

from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session

from app.adapters.postgres_repos import DraftRepo, HumanReviewRepo
from app.adapters.postgres_tickets import TicketRepo
from app.api import auth
from app.api.deps import build_workflow_deps
from app.api.hitl import HitlConflictError, HitlService
from app.api.tickets import ticket_detail, ticket_json
from app.auth.dependencies import CurrentOperator
from app.domain.enums import TicketStatus
from app.worker.tasks import engine, process_email, run_process_email
from settings import settings

app = FastAPI(title="p2p-ai-langraph")
# Credentialed requests cannot use allow_origins=["*"]; browsers would drop the cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)


class ApproveBody(BaseModel):
    final_text: str | None = None


def _enqueue(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        task = process_email.delay(payload)
        return {"task_id": task.id}
    except Exception:
        return run_process_email(payload)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", status_code=202)
def ingest(payload: dict[str, Any]) -> dict[str, Any]:
    return _enqueue(payload)


@app.post("/webhook/mock", status_code=202)
def webhook_mock(payload: dict[str, Any]) -> dict[str, Any]:
    return _enqueue(payload)


@app.get("/stats")
def stats(operator: CurrentOperator) -> dict[str, int]:
    with Session(engine) as session:
        return TicketRepo(session).count_by_status()


@app.get("/tickets")
def list_tickets(
    operator: CurrentOperator,
    status: TicketStatus | None = None,
    limit: int = 100,
) -> list[dict]:
    with Session(engine) as session:
        tickets = TicketRepo(session).list_tickets(status=status, limit=limit)
    return [ticket_json(t) for t in tickets]


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: UUID, operator: CurrentOperator) -> dict:
    with Session(engine) as session:
        deps = build_workflow_deps(session)
        ticket = deps.tickets.get_by_id(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        return ticket_detail(deps, ticket)


@app.get("/tickets/{ticket_id}/draft")
def get_draft(ticket_id: UUID, operator: CurrentOperator) -> dict:
    with Session(engine) as session:
        ticket = TicketRepo(session).get_by_id(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        drafts = DraftRepo(session).get_by_ticket_id(ticket_id)
    if not drafts:
        raise HTTPException(status_code=404, detail="draft not found")
    return drafts[-1].model_dump(mode="json")


def _run_hitl(ticket_id: UUID, fn) -> dict:
    with Session(engine) as session:
        deps = build_workflow_deps(session)
        ticket = deps.tickets.get_by_id(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        service = HitlService(deps, HumanReviewRepo(session))
        try:
            result = fn(service)
        except HitlConflictError as exc:
            raise HTTPException(status_code=409, detail=exc.detail) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return result


@app.post("/tickets/{ticket_id}/approve")
def approve_ticket(
    ticket_id: UUID,
    operator: CurrentOperator,
    body: ApproveBody | None = None,
) -> dict:
    final_text = body.final_text if body else None
    return _run_hitl(
        ticket_id,
        lambda s: s.approve(ticket_id, operator_id=operator.id, final_text=final_text),
    )


@app.post("/tickets/{ticket_id}/escalate")
def escalate_ticket(ticket_id: UUID, operator: CurrentOperator) -> dict:
    return _run_hitl(
        ticket_id,
        lambda s: s.escalate(ticket_id, operator_id=operator.id),
    )
