import re
import logging

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from ..state import AgentState
from ..tools.kb_tools import get_error_root_causes, search_known_errors

log = logging.getLogger(__name__)

_TOOLS = [search_known_errors, get_error_root_causes]
_TOOL_MAP = {t.name: t for t in _TOOLS}

_SYSTEM = """You are an expert Kubernetes SRE performing root cause analysis.

Given pod logs and Kubernetes events for a CrashLoopBackOff pod:
1. Call search_known_errors with the most relevant excerpt from the logs.
2. For the top match, call get_error_root_causes to retrieve known root causes.
3. Synthesise a concise root cause statement.

Always end your final response with exactly these two lines:
ROOT CAUSE: <one sentence root cause summary>
CONFIDENCE: <0.0-1.0>"""


async def _execute_tools(tool_calls: list) -> list[ToolMessage]:
    results = []
    for tc in tool_calls:
        fn = _TOOL_MAP.get(tc["name"])
        if fn:
            result = await fn.ainvoke(tc["args"])
            results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return results


async def rca_node(state: AgentState) -> dict:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    llm_with_tools = llm.bind_tools(_TOOLS)

    events_text = "\n".join(
        f"  [{e.get('type')}] {e.get('reason')}: {e.get('message')}"
        for e in state.get("pod_events", [])
    )
    human_content = (
        f"Pod: {state['pod_name']} (namespace: {state['namespace']})\n"
        f"Status: {state['pod_status']}\n\n"
        f"=== LOGS ===\n{state['pod_logs']}\n\n"
        f"=== EVENTS ===\n{events_text or '(none)'}"
    )

    messages = [SystemMessage(content=_SYSTEM), HumanMessage(content=human_content)]

    response = await llm_with_tools.ainvoke(messages)

    if response.tool_calls:
        tool_results = await _execute_tools(response.tool_calls)
        messages = messages + [response] + tool_results
        response = await llm.ainvoke(messages)

    text = response.content

    root_cause = "Unknown root cause"
    confidence = 0.5
    if m := re.search(r"ROOT CAUSE:\s*(.+)", text):
        root_cause = m.group(1).strip()
    if m := re.search(r"CONFIDENCE:\s*([\d.]+)", text):
        try:
            confidence = float(m.group(1))
        except ValueError:
            pass

    log.info("RCA complete for %s: %s (confidence=%.2f)", state["pod_name"], root_cause, confidence)

    return {
        "root_cause": root_cause,
        "rca_confidence": confidence,
        "known_error_matches": [],
        "messages": [response],
    }
