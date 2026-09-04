"""Compile inbound spine: … → resolution → draft → hitl → END.

HITL option 2 (assistant pattern): the inbound graph ends at hitl with
AWAITING_HUMAN. Celery runs this graph only. Approve does not resume a
checkpointer; HitlService.approve runs make_send_node(deps). Escalate
marks ESCALATED and never sends.
"""

import inspect
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.domain.deps import WorkflowDeps
from app.domain.enums import AuditAction
from app.domain.models import AuditEntry
from app.graph.nodes.draft import make_draft_node
from app.graph.nodes.hitl import make_hitl_node
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.intent import make_intent_node
from app.graph.nodes.resolution import make_resolution_node
from app.graph.nodes.routing import make_routing_node
from app.graph.nodes.security import make_security_node
from app.graph.nodes.sender import make_sender_node
from app.graph.nodes.thread import make_thread_node
from app.graph.nodes.triage import make_triage_node
from app.graph.state import LabState


def _stop_or(next_node: str):
    def route(state: LabState) -> str:
        if state.get("should_stop"):
            return END
        return next_node

    return route


def _after_thread(state: LabState) -> str:
    if state.get("should_stop"):
        return END
    if state.get("route") == "resolution":
        return "resolution"
    return "triage"


def _after_intent(state: LabState) -> str:
    if state.get("should_stop"):
        return END
    if state.get("skip_identity"):
        return "resolution"
    return "sender"


def _after_routing(state: LabState) -> str:
    if state.get("should_stop"):
        return END
    return "resolution"


def _with_audit(node_name: str, fn, deps: WorkflowDeps):
    async def wrapped(state: LabState) -> dict:
        if inspect.iscoroutinefunction(fn):
            update = await fn(state)
        else:
            update = fn(state)
        ticket_id = update.get("ticket_id") or state.get("ticket_id")
        action = update.get("audit_action")
        if ticket_id and action:
            deps.audit.append(
                AuditEntry(
                    ticket_id=UUID(ticket_id),
                    node=node_name,
                    action=AuditAction(action),
                    confidence=update.get("audit_confidence"),
                    metadata=dict(update.get("audit_metadata") or {}),
                )
            )
        return update

    return wrapped


def build_graph(deps: WorkflowDeps):
    graph = StateGraph(LabState)
    graph.add_node("ingest", _with_audit("ingest", make_ingest_node(deps), deps))
    graph.add_node("security", _with_audit("security", make_security_node(deps), deps))
    graph.add_node("thread", _with_audit("thread", make_thread_node(deps), deps))
    graph.add_node("triage", _with_audit("triage", make_triage_node(deps), deps))
    graph.add_node("intent", _with_audit("intent", make_intent_node(deps), deps))
    graph.add_node("sender", _with_audit("sender", make_sender_node(deps), deps))
    graph.add_node("routing", _with_audit("routing", make_routing_node(deps), deps))
    graph.add_node("resolution", _with_audit("resolution", make_resolution_node(deps), deps))
    graph.add_node("draft", _with_audit("draft", make_draft_node(deps), deps))
    graph.add_node("hitl", _with_audit("hitl", make_hitl_node(deps), deps))

    graph.add_edge(START, "ingest")
    graph.add_conditional_edges("ingest", _stop_or("security"))
    graph.add_conditional_edges("security", _stop_or("thread"))
    graph.add_conditional_edges("thread", _after_thread)
    graph.add_conditional_edges("triage", _stop_or("intent"))
    graph.add_conditional_edges("intent", _after_intent)
    graph.add_edge("sender", "routing")
    graph.add_conditional_edges("routing", _after_routing)
    graph.add_edge("resolution", "draft")
    graph.add_edge("draft", "hitl")
    graph.add_edge("hitl", END)

    return graph.compile()
