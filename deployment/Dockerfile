# ─────────────────────────────────────────────────────────────────────────────
#  Election Guide Assistant – Dockerfile
#  Multi-stage build: backend (FastAPI) + frontend (Streamlit)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS base

# Security: run as non-root
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Dependencies ──────────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application Code ──────────────────────────────────────────────────────────
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/
COPY scripts/ ./scripts/

# Create vector store directory
RUN mkdir -p data/vector_store && \
    chown -R appuser:appgroup /app

USER appuser

# ── Health Check ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Expose Ports ──────────────────────────────────────────────────────────────
EXPOSE 8000 8501

# ── Start Script ──────────────────────────────────────────────────────────────
# Use a startup script to run both services
COPY deployment/start.sh /start.sh
CMD ["/bin/bash", "/start.sh"]
