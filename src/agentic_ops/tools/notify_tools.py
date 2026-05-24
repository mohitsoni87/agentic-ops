import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import httpx
from langchain_core.tools import tool
from sqlalchemy import text

from ..config import settings
from ..db.connection import get_session

log = logging.getLogger(__name__)


@tool
async def send_slack(incident_report: str, pod_name: str, root_cause: str) -> bool:
    """Send an incident notification to Slack via incoming webhook."""
    if not settings.slack_webhook_url:
        log.info("[SLACK DISABLED] pod=%s root_cause=%.100s", pod_name, root_cause)
        return True

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f":rotating_light: K8s Incident: {pod_name}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Root Cause:* {root_cause}"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": incident_report[:2900]},
            },
        ]
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.slack_webhook_url, json=payload)
        success = resp.status_code == 200
        if not success:
            log.warning("Slack webhook returned %d: %s", resp.status_code, resp.text)
        return success


@tool
async def send_email(subject: str, body: str) -> bool:
    """Send an incident report via SMTP email."""
    if not settings.smtp_user:
        log.info("[EMAIL DISABLED] subject=%s", subject)
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = settings.notify_email_to
    msg.attach(MIMEText(body, "plain"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )
    return True


@tool
async def save_incident(
    pod_name: str,
    namespace: str,
    pod_logs: str,
    error_pattern: str,
    rca_summary: str,
    solution_summary: str,
    full_report: str,
    slack_sent: bool,
    email_sent: bool,
) -> int:
    """Persist the incident record to PostgreSQL and return the new incident ID."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO incidents
                  (pod_name, namespace, pod_logs, error_pattern, rca_summary,
                   solution_summary, full_report, notification_sent, slack_sent, email_sent)
                VALUES
                  (:pod_name, :namespace, :pod_logs, :error_pattern, :rca_summary,
                   :solution_summary, :full_report, :notif, :slack, :email)
                RETURNING id
            """),
            {
                "pod_name": pod_name,
                "namespace": namespace,
                "pod_logs": pod_logs[:10000],
                "error_pattern": error_pattern,
                "rca_summary": rca_summary,
                "solution_summary": solution_summary,
                "full_report": full_report,
                "notif": slack_sent or email_sent,
                "slack": slack_sent,
                "email": email_sent,
            },
        )
        await session.commit()
        return result.scalar_one()
