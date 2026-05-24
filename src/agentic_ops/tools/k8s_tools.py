from langchain_core.tools import tool

from ..config import settings

# ---------------------------------------------------------------------------
# Mock pod data — 2 crashing, 1 healthy
# ---------------------------------------------------------------------------
MOCK_PODS: dict[str, dict] = {
    "api-server-xyz": {
        "namespace": "default",
        "status": "CrashLoopBackOff",
        "restart_count": 12,
        "logs": (
            "WARNING: Starting JVM with 256Mi heap\n"
            "INFO: Connecting to database...\n"
            "INFO: Loading application context\n"
            "ERROR: Killed\n"
            "OOMKilled: container exceeded memory limit of 256Mi\n"
            "java.lang.OutOfMemoryError: Java heap space\n"
            "\tat java.util.Arrays.copyOf(Arrays.java:3210)\n"
            "\tat com.example.service.DataProcessor.process(DataProcessor.java:142)\n"
            "Container will be restarted.\n"
        ),
        "events": [
            {
                "type": "Warning",
                "reason": "OOMKilling",
                "message": "Memory cgroup out of memory: Kill process 1234 (java) score 999",
            },
            {
                "type": "Warning",
                "reason": "BackOff",
                "message": "Back-off restarting failed container api-server in pod api-server-xyz",
            },
        ],
    },
    "db-migrator-abc": {
        "namespace": "default",
        "status": "CrashLoopBackOff",
        "restart_count": 5,
        "logs": (
            "INFO: Starting database migration runner v2.1.0\n"
            "ERROR: required environment variable DATABASE_URL is not set\n"
            "FATAL: cannot connect to database without DATABASE_URL\n"
            "Exiting with code 1\n"
        ),
        "events": [
            {
                "type": "Warning",
                "reason": "BackOff",
                "message": "Back-off restarting failed container db-migrator in pod db-migrator-abc",
            },
        ],
    },
    "web-frontend-def": {
        "namespace": "default",
        "status": "Running",
        "restart_count": 0,
        "logs": (
            "INFO: Server started on :8080\n"
            "INFO: Ready to accept connections\n"
            "INFO: Health check passed\n"
        ),
        "events": [],
    },
}


@tool
async def get_pod_statuses() -> list[dict]:
    """Return the status of all pods across all namespaces."""
    if settings.k8s_mode == "mock":
        return [
            {
                "pod_name": name,
                "namespace": data["namespace"],
                "status": data["status"],
                "restart_count": data["restart_count"],
            }
            for name, data in MOCK_PODS.items()
        ]

    from kubernetes import client, config as k8s_config  # lazy import

    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()

    v1 = client.CoreV1Api()
    pods = v1.list_pod_for_all_namespaces(watch=False)
    result = []
    for pod in pods.items:
        for cs in pod.status.container_statuses or []:
            status = "Running"
            if cs.state.waiting and cs.state.waiting.reason:
                status = cs.state.waiting.reason
            result.append(
                {
                    "pod_name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": status,
                    "restart_count": cs.restart_count,
                }
            )
    return result


@tool
async def get_pod_logs(pod_name: str, namespace: str = "default") -> str:
    """Retrieve the last 100 log lines from a pod."""
    if settings.k8s_mode == "mock":
        return MOCK_PODS.get(pod_name, {}).get("logs", "No logs available.")

    from kubernetes import client, config as k8s_config  # lazy import

    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()

    v1 = client.CoreV1Api()
    return v1.read_namespaced_pod_log(
        name=pod_name, namespace=namespace, tail_lines=100
    )


@tool
async def get_pod_events(pod_name: str, namespace: str = "default") -> list[dict]:
    """Get Kubernetes warning events for a specific pod."""
    if settings.k8s_mode == "mock":
        return MOCK_PODS.get(pod_name, {}).get("events", [])

    from kubernetes import client, config as k8s_config  # lazy import

    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()

    v1 = client.CoreV1Api()
    events = v1.list_namespaced_event(
        namespace=namespace,
        field_selector=f"involvedObject.name={pod_name}",
    )
    return [
        {"type": e.type, "reason": e.reason, "message": e.message}
        for e in events.items
    ]
