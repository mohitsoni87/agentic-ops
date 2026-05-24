import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from ..state import AgentState
from ..tools.kb_tools import search_solutions

log = logging.getLogger(__name__)

_TOOLS = [search_solutions]
_TOOL_MAP = {t.name: t for t in _TOOLS}

_SYSTEM = """You are a Kubernetes remediation expert.

Given a root cause analysis, propose a clear remediation plan:
1. Call search_solutions with the root cause text to find known solutions.
2. Synthesise a step-by-step remediation plan based on the results.

Always end your final response with exactly this format:
SOLUTION: <one sentence summary>
STEPS:
1. <step>
2. <step>
..."""


async def _execute_tools(tool_calls: list) -> list[ToolMessage]:
    results = []
    for tc in tool_calls:
        fn = _TOOL_MAP.get(tc["name"])
        if fn:
            result = await fn.ainvoke(tc["args"])
            results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return results


async def solution_node(state: AgentState) -> dict:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    llm_with_tools = llm.bind_tools(_TOOLS)

    human_content = (
        f"Pod: {state['pod_name']} (namespace: {state['namespace']})\n\n"
        f"=== ROOT CAUSE ===\n{state.get('root_cause', 'Unknown')}\n\n"
        f"Confidence: {state.get('rca_confidence', 0.0):.0%}\n\n"
        "Please search the solutions knowledge base and propose a remediation plan."
    )

    messages = [SystemMessage(content=_SYSTEM), HumanMessage(content=human_content)]

    response = await llm_with_tools.ainvoke(messages)

    if response.tool_calls:
        tool_results = await _execute_tools(response.tool_calls)
        messages = messages + [response] + tool_results
        response = await llm.ainvoke(messages)

    text = response.content

    proposed_solution = "No solution determined"
    if m := re.search(r"SOLUTION:\s*(.+)", text):
        proposed_solution = m.group(1).strip()

    steps: list[str] = re.findall(r"^\d+\.\s+(.+)$", text, re.MULTILINE)

    log.info(
        "Solution complete for %s: %s (%d steps)",
        state["pod_name"],
        proposed_solution,
        len(steps),
    )

    return {
        "proposed_solution": proposed_solution,
        "solution_steps": steps,
        "messages": [response],
    }
