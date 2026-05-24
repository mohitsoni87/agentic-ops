"""
Seed the knowledge base with known Kubernetes error patterns, root causes, and solutions.

Usage:
    uv run python -m src.agentic_ops.db.seed_data
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on the path when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from dotenv import load_dotenv

load_dotenv()

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text

from src.agentic_ops.config import settings
from src.agentic_ops.db.connection import get_session, init_db

log = logging.getLogger(__name__)

KNOWN_ERRORS = [
    {
        "error_type": "OOMKilled",
        "pattern": "Container exceeded memory limit, OOMKilled, Java heap space out of memory",
        "log_keywords": ["OOMKilled", "OutOfMemoryError", "memory limit", "heap space", "Killed"],
        "root_cause": (
            "The container was killed by the Linux OOM killer because it exceeded the memory "
            "limit configured in the pod spec. This is often caused by a memory leak, "
            "insufficient memory limits, or a sudden spike in workload."
        ),
        "solution_title": "Increase memory limits or fix memory leak",
        "solution_description": (
            "Either raise the container memory limit in the deployment spec, "
            "or profile the application to identify and fix the memory leak."
        ),
        "solution_steps": [
            "Check current memory usage: kubectl top pod <pod-name>",
            "Review the deployment memory limits: kubectl get deployment <name> -o yaml",
            "Increase the memory limit in the deployment spec (e.g., from 256Mi to 512Mi)",
            "If the increase does not resolve it, profile the application for memory leaks",
            "Consider adding Vertical Pod Autoscaler (VPA) to auto-tune resource requests",
        ],
    },
    {
        "error_type": "ImagePullBackOff",
        "pattern": "ImagePullBackOff, Failed to pull image, invalid image tag, unauthorized registry",
        "log_keywords": ["ImagePullBackOff", "ErrImagePull", "pull access denied", "invalid tag", "manifest unknown"],
        "root_cause": (
            "Kubernetes cannot pull the container image. This is typically caused by: "
            "an incorrect or non-existent image tag, a private registry without credentials, "
            "or network issues reaching the registry."
        ),
        "solution_title": "Fix image tag or add registry credentials",
        "solution_description": (
            "Verify the image name and tag exist in the registry, "
            "and ensure the necessary imagePullSecret is configured."
        ),
        "solution_steps": [
            "Verify the image exists: docker pull <image>:<tag>",
            "Check the image name in the deployment spec for typos",
            "If the registry is private, create an imagePullSecret: "
            "kubectl create secret docker-registry regcred --docker-server=... --docker-username=... --docker-password=...",
            "Add the secret to the pod spec under imagePullSecrets",
            "Redeploy: kubectl rollout restart deployment/<name>",
        ],
    },
    {
        "error_type": "MissingEnvVar",
        "pattern": "Required environment variable not set, exit code 1, env var missing, cannot start without config",
        "log_keywords": ["environment variable", "env var", "not set", "required", "exit code 1", "missing config"],
        "root_cause": (
            "The container exited immediately because a required environment variable was not "
            "provided. This is usually a misconfigured ConfigMap, Secret, or deployment spec "
            "where the env var reference is missing or misspelled."
        ),
        "solution_title": "Add missing environment variable to deployment spec",
        "solution_description": (
            "Identify the missing variable name from the logs and add it to the deployment "
            "via a ConfigMap, Secret, or direct env entry."
        ),
        "solution_steps": [
            "Read the error log to identify the exact variable name",
            "Check if a ConfigMap or Secret for this variable already exists: kubectl get configmap,secret",
            "If missing, create it: kubectl create configmap <name> --from-literal=KEY=VALUE",
            "Add the env var to the deployment spec under spec.containers[].env or envFrom",
            "Redeploy: kubectl rollout restart deployment/<name>",
        ],
    },
    {
        "error_type": "LivenessProbeFailed",
        "pattern": "Liveness probe failed, connection refused, readiness probe failed, probe timeout exceeded",
        "log_keywords": ["liveness probe", "readiness probe", "probe failed", "connection refused", "timeout"],
        "root_cause": (
            "The Kubernetes liveness or readiness probe is failing, causing the pod to be "
            "restarted repeatedly. This can happen when the application takes longer to start "
            "than the initialDelaySeconds allows, or when the health endpoint is incorrect."
        ),
        "solution_title": "Tune probe timing or fix health endpoint",
        "solution_description": (
            "Increase initialDelaySeconds for the liveness probe, or fix the health check "
            "endpoint path in the deployment spec."
        ),
        "solution_steps": [
            "Check probe settings: kubectl get deployment <name> -o yaml | grep -A10 livenessProbe",
            "Increase initialDelaySeconds to give the app more startup time (e.g., from 10 to 60)",
            "Verify the probe endpoint path matches the actual health route in the application",
            "Test the health endpoint manually: kubectl exec <pod> -- curl localhost:<port>/health",
            "Apply the updated deployment: kubectl apply -f deployment.yaml",
        ],
    },
    {
        "error_type": "ConfigMapNotFound",
        "pattern": "ConfigMap not found, secret not found, volume mount error, config file missing",
        "log_keywords": ["configmap", "not found", "secret", "volume", "mount", "no such file"],
        "root_cause": (
            "The pod references a ConfigMap or Secret that does not exist in the namespace. "
            "The pod will fail to start because the volume or env var cannot be mounted."
        ),
        "solution_title": "Create the missing ConfigMap or Secret",
        "solution_description": (
            "Identify the missing ConfigMap/Secret name from the events and create it "
            "in the correct namespace before the pod can start."
        ),
        "solution_steps": [
            "Check pod events for the missing resource name: kubectl describe pod <pod-name>",
            "Verify what ConfigMaps/Secrets exist: kubectl get configmap,secret -n <namespace>",
            "Create the missing ConfigMap: kubectl create configmap <name> --from-file=config.yaml",
            "Or create a Secret: kubectl create secret generic <name> --from-literal=key=value",
            "Restart the pod: kubectl delete pod <pod-name> (deployment will recreate it)",
        ],
    },
    {
        "error_type": "CrashExit1",
        "pattern": "Container exited with code 1, unhandled exception, application crash, panic",
        "log_keywords": ["exit code 1", "unhandled exception", "panic", "fatal error", "segmentation fault"],
        "root_cause": (
            "The application crashed with a non-zero exit code due to an unhandled exception, "
            "a panic, or a fatal error in the application code. Review the logs for the "
            "specific exception or error message."
        ),
        "solution_title": "Fix the application crash",
        "solution_description": (
            "Investigate the application logs for the root exception, fix the code, "
            "build a new image, and redeploy."
        ),
        "solution_steps": [
            "Get full crash logs: kubectl logs <pod-name> --previous",
            "Identify the exception type and stack trace",
            "Fix the application code and unit test the fix locally",
            "Build and push a new container image with a new tag",
            "Update the deployment image tag and rollout: kubectl set image deployment/<name> container=<new-image>",
        ],
    },
    {
        "error_type": "DiskPressure",
        "pattern": "Evicted due to disk pressure, node disk full, ephemeral storage exceeded, no space left on device",
        "log_keywords": ["disk pressure", "evicted", "ephemeral storage", "no space left", "DiskPressure"],
        "root_cause": (
            "The pod was evicted because the node ran out of disk space or the pod exceeded "
            "its ephemeral storage limit. Excessive logs, large temp files, or accumulated "
            "container images are common causes."
        ),
        "solution_title": "Free disk space and set ephemeral storage limits",
        "solution_description": (
            "Clean up disk space on the node and set ephemeral storage limits "
            "on the pod to prevent future evictions."
        ),
        "solution_steps": [
            "Check node disk usage: kubectl describe node <node-name> | grep -A5 'Conditions'",
            "Clean unused Docker images on the node: docker image prune -a",
            "Clear old log files in large volumes or PVCs",
            "Add ephemeral storage limits to the deployment spec: resources.limits.ephemeral-storage: 1Gi",
            "Consider adding a log rotation policy to the application",
        ],
    },
]


async def seed() -> None:
    log.info("Initialising database...")
    await init_db()

    embedder = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.openai_api_key,
    )

    async with get_session() as session:
        # Check if already seeded
        count_result = await session.execute(text("SELECT COUNT(*) FROM known_errors"))
        count = count_result.scalar_one()
        if count > 0:
            log.info("Knowledge base already seeded (%d entries). Skipping.", count)
            return

        log.info("Seeding %d known error entries...", len(KNOWN_ERRORS))

        for entry in KNOWN_ERRORS:
            log.info("  Embedding: %s", entry["error_type"])

            # Embed the error pattern
            error_emb = await embedder.aembed_query(entry["pattern"])
            error_emb_str = f"[{','.join(str(x) for x in error_emb)}]"

            error_id_result = await session.execute(
                text("""
                    INSERT INTO known_errors (error_type, pattern, log_keywords, embedding)
                    VALUES (:et, :p, :kw, :emb::vector)
                    RETURNING id
                """),
                {
                    "et": entry["error_type"],
                    "p": entry["pattern"],
                    "kw": entry["log_keywords"],
                    "emb": error_emb_str,
                },
            )
            error_id = error_id_result.scalar_one()

            # Embed and insert root cause
            rc_emb = await embedder.aembed_query(entry["root_cause"])
            rc_emb_str = f"[{','.join(str(x) for x in rc_emb)}]"

            rc_id_result = await session.execute(
                text("""
                    INSERT INTO root_causes (known_error_id, description, embedding)
                    VALUES (:eid, :desc, :emb::vector)
                    RETURNING id
                """),
                {"eid": error_id, "desc": entry["root_cause"], "emb": rc_emb_str},
            )
            rc_id = rc_id_result.scalar_one()

            # Embed and insert solution
            sol_text = entry["solution_description"]
            sol_emb = await embedder.aembed_query(sol_text)
            sol_emb_str = f"[{','.join(str(x) for x in sol_emb)}]"

            import json

            await session.execute(
                text("""
                    INSERT INTO solutions (root_cause_id, title, description, steps, embedding)
                    VALUES (:rcid, :title, :desc, :steps::jsonb, :emb::vector)
                """),
                {
                    "rcid": rc_id,
                    "title": entry["solution_title"],
                    "desc": sol_text,
                    "steps": json.dumps(entry["solution_steps"]),
                    "emb": sol_emb_str,
                },
            )

        await session.commit()
        log.info("Seeding complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(seed())
