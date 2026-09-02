"""HTTP adapter: health, ingest queue, ticket lookup."""

from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from sqlmodel import Session

from app.adapters.postgres_tickets import TicketRepo
from app.domain.models import Ticket
from app.worker.tasks import engine, process_email, run_process_email

app = FastAPI(title="p2p-ai-langraph")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", status_code=202)
def ingest(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        task = process_email.delay(payload)
        return {"task_id": task.id}
    except Exception:
        result = run_process_email(payload)
        return result


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: UUID) -> Ticket:
    with Session(engine) as session:
        ticket = TicketRepo(session).get_by_id(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket
