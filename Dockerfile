# Containerized FastAPI backend
# Python version matches our chosen runtime.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    HF_HOME=/home/app/.cache/huggingface \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=2

WORKDIR /app

# Create a non-root service account.
RUN groupadd --gid 10001 app \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        --shell /usr/sbin/nologin \
        app \
    && mkdir -p /home/app/.cache \
    && chown -R app:app /home/app

# Install dependencies first to reuse Docker's build cache.
COPY requirements.txt ./requirements.txt

RUN python -m pip install --no-cache-dir \
    -r requirements.txt \
    && python -m pip check

# Copy only application and migration files.
COPY backend/app ./backend/app
COPY backend/alembic ./backend/alembic
COPY alembic.ini ./alembic.ini

# No application secrets are included in this image.
USER app

EXPOSE 8000

# Liveness only: checks the FastAPI process.
# Database readiness is checked separately.
HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=60s \
    --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

# One worker is intentional: Day 15 uses in-memory
# LangGraph checkpoints, which are not shared across workers.
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--app-dir", "/app/backend", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]