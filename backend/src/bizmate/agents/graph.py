from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from bizmate.domain.models import TaskStatus


class AgentState(TypedDict):
    request: str
    status: str
    next_action: str


def scaffold_node(state: AgentState) -> dict[str, str]:
    # BM-07/BM-08: add intent, policy-validated plans, checkpoints and safe recovery here.
    # Never use a fabricated LLM result or mark this no-op graph COMPLETED.
    return {
        "status": TaskStatus.AWAITING_INPUT.value,
        "next_action": (
            "Request saved for development. Workflow execution is not implemented (BM-07)."
        ),
    }


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("scaffold", scaffold_node)
    graph.add_edge(START, "scaffold")
    graph.add_edge("scaffold", END)
    return graph.compile()
