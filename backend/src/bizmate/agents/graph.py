"""One durable execution graph. Trusted context is supplied by the caller, never checkpoint data."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class AgentState(TypedDict):
    task_id: str
    route: str


def build_graph(dispatch, checkpointer):
    def step(state):
        return {"route": dispatch(state["task_id"])}

    def pause(state):
        # The preceding node's task snapshot and this interrupt are persisted before returning.
        # The resume payload conveys no authority. Dispatch reloads approval and task records.
        interrupt({"task_id": state["task_id"], "reason": "input_approval_or_external_evidence"})
        return {}

    graph = StateGraph(AgentState)
    graph.add_node("step", step)
    graph.add_node("pause", pause)
    graph.add_edge(START, "step")
    graph.add_conditional_edges(
        "step", lambda state: state["route"], {"continue": "step", "pause": "pause", "end": END}
    )
    graph.add_edge("pause", "step")
    return graph.compile(checkpointer=checkpointer)
