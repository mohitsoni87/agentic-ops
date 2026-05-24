import asyncio
import logging
import time

from ..config import settings
from ..tools.k8s_tools import get_pod_events, get_pod_logs, get_pod_statuses

log = logging.getLogger(__name__)

# Dedup: track last-processed timestamp per "namespace/pod_name"
_processed: dict[str, float] = {}
_DEDUP_TTL_SECONDS = 3600


def _is_recently_processed(pod_name: str, namespace: str) -> bool:
    key = f"{namespace}/{pod_name}"
    last = _processed.get(key, 0.0)
    return (time.time() - last) < _DEDUP_TTL_SECONDS


def _mark_processed(pod_name: str, namespace: str) -> None:
    _processed[f"{namespace}/{pod_name}"] = time.time()


async def _handle_pod(graph, pod: dict) -> None:
    pod_name = pod["pod_name"]
    namespace = pod["namespace"]

    if _is_recently_processed(pod_name, namespace):
        log.debug("Skipping %s/%s (processed within last hour)", namespace, pod_name)
        return

    _mark_processed(pod_name, namespace)

    logs = await get_pod_logs.ainvoke({"pod_name": pod_name, "namespace": namespace})
    events = await get_pod_events.ainvoke({"pod_name": pod_name, "namespace": namespace})

    initial_state = {
        "pod_name": pod_name,
        "namespace": namespace,
        "pod_status": pod["status"],
        "pod_logs": logs,
        "pod_events": events,
        "messages": [],
    }

    log.info("Triggering analysis for pod: %s", pod_name)
    result = await graph.ainvoke(initial_state)
    log.info(
        "Analysis complete for %s. Incident ID: %s",
        pod_name,
        result.get("incident_id"),
    )


async def monitor_loop(graph) -> None:
    log.info(
        "Monitor started. Polling every %ds. K8s mode: %s",
        settings.poll_interval_seconds,
        settings.k8s_mode,
    )
    while True:
        try:
            pods = await get_pod_statuses.ainvoke({})
            crash_pods = [p for p in pods if p["status"] == "CrashLoopBackOff"]
            log.info("Poll complete. Found %d failing pod(s).", len(crash_pods))
            if crash_pods:
                await asyncio.gather(*[_handle_pod(graph, p) for p in crash_pods])
        except Exception:
            log.exception("Unhandled error in monitor loop")
        # Update heartbeat file so the Docker HEALTHCHECK stays green
        try:
            open("/tmp/heartbeat", "w").close()
        except OSError:
            pass
        await asyncio.sleep(settings.poll_interval_seconds)
