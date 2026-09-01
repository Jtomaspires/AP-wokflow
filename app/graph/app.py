"""Compile ingest → security → triage as a LangGraph StateGraph."""

from langgraph.graph import END, START, StateGraph

from app.domain.deps import WorkflowDeps
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.security import make_security_node
from app.graph.nodes.triage import make_triage_node
from app.graph.state import LabState


def _stop_or(next_node: str):
    def route(state: LabState) -> str:
        if state.get("should_stop"):
            return END
        return next_node

    return route


def build_graph(deps: WorkflowDeps):
    graph = StateGraph(LabState)
    graph.add_node("ingest", make_ingest_node(deps))
    graph.add_node("security", make_security_node(deps))
    graph.add_node("triage", make_triage_node(deps))

    graph.add_edge(START, "ingest")
    graph.add_conditional_edges("ingest", _stop_or("security"))
    graph.add_conditional_edges("security", _stop_or("triage"))
    graph.add_edge("triage", END)

    return graph.compile()
