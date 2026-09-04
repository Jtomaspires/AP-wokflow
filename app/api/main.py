"""HTTP adapter: health, ingest, HITL, tickets."""

from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session

from app.adapters.postgres_repos import DraftRepo, HumanReviewRepo
from app.adapters.postgres_tickets import TicketRepo
from app.api.deps import build_workflow_deps
from app.api.hitl import HitlConflictError, HitlService
from app.api.tickets import ticket_detail, ticket_json
from app.domain.enums import TicketStatus
from app.worker.tasks import engine, process_email, run_process_email

app = FastAPI(title="p2p-ai-langraph")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApproveBody(BaseModel):
    operator_id: str
    final_text: str | None = None


class EscalateBody(BaseModel):
    operator_id: str


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
def stats() -> dict[str, int]:
    with Session(engine) as session:
        return TicketRepo(session).count_by_status()


@app.get("/tickets")
def list_tickets(status: TicketStatus | None = None, limit: int = 100) -> list[dict]:
    with Session(engine) as session:
        tickets = TicketRepo(session).list_tickets(status=status, limit=limit)
    return [ticket_json(t) for t in tickets]


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: UUID) -> dict:
    with Session(engine) as session:
        deps = build_workflow_deps(session)
        ticket = deps.tickets.get_by_id(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="ticket not found")
        return ticket_detail(deps, ticket)


@app.get("/tickets/{ticket_id}/draft")
def get_draft(ticket_id: UUID) -> dict:
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
def approve_ticket(ticket_id: UUID, body: ApproveBody) -> dict:
    return _run_hitl(
        ticket_id,
        lambda s: s.approve(ticket_id, operator_id=body.operator_id, final_text=body.final_text),
    )


@app.post("/tickets/{ticket_id}/escalate")
def escalate_ticket(ticket_id: UUID, body: EscalateBody) -> dict:
    return _run_hitl(
        ticket_id,
        lambda s: s.escalate(ticket_id, operator_id=body.operator_id),
    )
