# ─── Stage 1: dependencies ────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[transcription,api]" && \
    pip install --no-cache-dir bgutil-ytdlp-pot-provider


# ─── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Install ffmpeg + Node.js (required by bgutil-ytdlp-pot-provider for PO token generation)
RUN apt-get update --fix-missing && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

COPY src/ ./src/
COPY pyproject.toml ./

# Install the app package itself (no deps — already copied above)
RUN pip install --no-cache-dir --no-deps -e .

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /data/audio /data/video /data/transcripts && \
    mkdir -p /home/appuser/.cache/huggingface && \
    chown -R appuser:appuser /app /data /home/appuser/.cache

# yt-dlp config: use node as JS runtime for challenge solving
RUN mkdir -p /home/appuser/.config/yt-dlp && \
    echo '--js-runtimes node:/usr/bin/node' > /home/appuser/.config/yt-dlp/config && \
    chown -R appuser:appuser /home/appuser/.config

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    REDIS_URL=redis://redis:6379/0 \
    WHISPER_MODEL=large-v3-turbo \
    LOG_LEVEL=INFO

EXPOSE 8000
