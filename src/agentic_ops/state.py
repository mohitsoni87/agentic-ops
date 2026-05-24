from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Set by monitor_loop
    pod_name: str
    namespace: str
    pod_status: str
    pod_logs: str
    pod_events: list[dict]
    # Set by rca_node
    known_error_matches: list[dict]
    root_cause: str
    rca_confidence: float
    # Set by solution_node
    proposed_solution: str
    solution_steps: list[str]
    # Set by notify_node
    incident_report: str
    incident_id: int
    notification_sent: bool
    # LangGraph message accumulator
    messages: Annotated[list[BaseMessage], add_messages]
