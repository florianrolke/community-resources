FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    SOURCE_CSV=/data/input/mobile-home-strict-form-submission-queue.csv \
    RESULTS_ROOT=/data/runs \
    STATE_FILE=/data/state/mobile-home-worker-state.json \
    BATCH_LIMIT=25 \
    RUN_MODE=once \
    LOOP_SLEEP_SECONDS=300

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && python -m playwright install chromium

COPY execution /app/execution
COPY cloud/mobile-home/run_cloud_worker.py /app/cloud/mobile-home/run_cloud_worker.py

RUN mkdir -p /data/input /data/runs /data/state /data/config /app/.tmp

EXPOSE 8080

CMD ["python", "/app/cloud/mobile-home/run_cloud_worker.py"]
