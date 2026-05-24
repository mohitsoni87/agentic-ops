from datetime import datetime


def format_incident_report(state: dict) -> str:
    steps = state.get("solution_steps") or []
    steps_text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps)) or "N/A"
    confidence = state.get("rca_confidence", 0.0)
    logs_excerpt = (state.get("pod_logs") or "")[:1000]

    return f"""# Kubernetes Incident Report
**Generated:** {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}

---

## Affected Pod
| Field | Value |
|-------|-------|
| Pod | `{state.get('pod_name', 'N/A')}` |
| Namespace | `{state.get('namespace', 'N/A')}` |
| Status | `{state.get('pod_status', 'N/A')}` |

---

## Root Cause Analysis
{state.get('root_cause', 'N/A')}

**Confidence:** {confidence:.0%}

---

## Proposed Remediation
{state.get('proposed_solution', 'N/A')}

### Steps
{steps_text}

---

## Raw Logs (excerpt)
```
{logs_excerpt}
```
"""
