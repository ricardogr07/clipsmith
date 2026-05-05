FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

# Install core pipeline only — cloud/Azure packages are local-CLI-only
RUN pip install --no-cache-dir -e ".[vision]"

# Bake the Whisper model so containers start immediately without downloading it.
# Uses the "small" model matching the default in config.yaml (transcribe.model).
# Rebuild the image if you switch to "medium" or "large-v3".
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

VOLUME ["/app/work", "/app/out"]

ENTRYPOINT ["clipsmith"]
