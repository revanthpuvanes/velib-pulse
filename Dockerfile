FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Required for flock-based job locking.
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY collector/ collector/
COPY producer/ producer/
COPY consumer/ consumer/
COPY dashboard/ dashboard/
COPY scripts/ scripts/
COPY analytics/ analytics/

RUN mkdir -p \
    storage/raw \
    storage/state \
    storage/parquet/incremental \
    storage/analytics \
    storage/dashboard \
    storage/health \
    web/public/data

CMD ["python", "-m", "scripts.run_pipeline"]
