"""Celery task that runs the compiled graph against Postgres.

Windows worker (solo pool — eventlet/prefork break on Win):

    celery -A app.worker.tasks:celery_app worker --pool=solo --loglevel=info
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from celery import Celery
from sqlmodel import Session, create_engine

from app.api.deps import build_workflow_deps
from app.graph.app import build_graph
from app.ports.llm_port import LLMPort
from settings import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

celery_app = Celery(
    "p2p_lab",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)


def run_process_email(
    raw_payload: dict,
    *,
    llm: LLMPort | None = None,
) -> dict:
    """Run the inbound graph in-process (no broker). Does not send."""
    with Session(engine) as session:
        deps = build_workflow_deps(session, llm=llm)
        final = asyncio.run(
            build_graph(deps).ainvoke({"raw_payload": raw_payload})
        )
        ticket_id = final.get("ticket_id")
        status = None
        if ticket_id:
            ticket = deps.tickets.get_by_id(UUID(ticket_id))
            if ticket is not None:
                status = ticket.status.value
        return {"ticket_id": ticket_id, "status": status}


@celery_app.task(name="process_email")
def process_email(raw_payload: dict) -> dict:
    return run_process_email(raw_payload)
