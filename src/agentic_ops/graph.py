from langgraph.graph import END, START, StateGraph

from .agents.notify_agent import notify_node
from .agents.rca_agent import rca_node
from .agents.solution_agent import solution_node
from .state import AgentState


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("rca", rca_node)
    builder.add_node("solution", solution_node)
    builder.add_node("notify", notify_node)

    builder.add_edge(START, "rca")
    builder.add_edge("rca", "solution")
    builder.add_edge("solution", "notify")
    builder.add_edge("notify", END)

    return builder.compile()
