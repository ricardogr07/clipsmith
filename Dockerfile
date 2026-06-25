FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r clipsmith && useradd -r -g clipsmith -d /home/clipsmith -m clipsmith

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
COPY alembic.ini alembic.ini
COPY alembic/ alembic/
COPY config.yaml config.yaml
COPY scripts/start_server.sh /app/start_server.sh

# Install all extras needed for API server + cloud ACI offload
# Runs after Azure CLI so pip's azure packages take ownership of the namespace
RUN pip install --no-cache-dir -e ".[server,vision,observability,cloud]"

# Bake the Whisper model into /app/.cache so the clipsmith user can access it.
# Uses the "small" model matching the default in config.yaml (transcribe.model).
# Rebuild the image if you switch to "medium" or "large-v3".
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

RUN mkdir -p /home/clipsmith/.azure /app/data /app/work /app/out && \
    chmod +x /app/start_server.sh && \
    chown -R clipsmith:clipsmith /app/.cache /home/clipsmith /app/data /app/work /app/out

VOLUME ["/app/work", "/app/out", "/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER clipsmith

CMD ["/app/start_server.sh"]
