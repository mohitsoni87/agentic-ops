import logging

from ..state import AgentState
from ..tools.notify_tools import save_incident, send_email, send_slack
from ..utils.report import format_incident_report

log = logging.getLogger(__name__)


async def notify_node(state: AgentState) -> dict:
    report = format_incident_report(state)

    slack_ok = await send_slack.ainvoke(
        {
            "incident_report": report,
            "pod_name": state["pod_name"],
            "root_cause": state.get("root_cause", "Unknown"),
        }
    )

    email_ok = await send_email.ainvoke(
        {
            "subject": f"[K8s Incident] CrashLoopBackOff: {state['pod_name']}",
            "body": report,
        }
    )

    error_pattern = ""
    matches = state.get("known_error_matches") or []
    if matches:
        error_pattern = str(matches[0].get("error_type", ""))

    incident_id = await save_incident.ainvoke(
        {
            "pod_name": state["pod_name"],
            "namespace": state["namespace"],
            "pod_logs": state.get("pod_logs", ""),
            "error_pattern": error_pattern,
            "rca_summary": state.get("root_cause", ""),
            "solution_summary": state.get("proposed_solution", ""),
            "full_report": report,
            "slack_sent": slack_ok,
            "email_sent": email_ok,
        }
    )

    log.info(
        "Incident #%d saved for pod %s. slack=%s email=%s",
        incident_id,
        state["pod_name"],
        slack_ok,
        email_ok,
    )

    return {
        "incident_report": report,
        "incident_id": incident_id,
        "notification_sent": slack_ok or email_ok,
    }
