# ── Stage 1: dependency builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv==0.9.8

# Copy manifest and README (hatchling requires both to build the package)
COPY pyproject.toml README.md ./

# Install all project dependencies into the system Python
RUN uv pip install --system --no-cache .

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="agentic-ops" \
      org.opencontainers.image.description="LangGraph multi-agent Kubernetes ops monitor" \
      org.opencontainers.image.source="https://github.com/your-org/agentic-ops"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ ./src/
COPY main.py .

# Non-root user (security best practice for k8s)
RUN useradd -m -u 1000 -s /bin/sh agent \
    && chown -R agent:agent /app

USER agent

# Health probe target — k8s liveness check writes to this file
# (monitor_agent updates it on each successful poll)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os,time; s=os.stat('/tmp/heartbeat'); assert time.time()-s.st_mtime < 120" || exit 1

CMD ["python", "main.py"]
