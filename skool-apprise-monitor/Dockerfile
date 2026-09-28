FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Install Python deps (playwright already installed in base image)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV STATE_DIR=/app/state
ENV EVENTS_DIR=/app/state/events

# State + events directories (mount as volume for persistence)
RUN mkdir -p /app/state/events

# Copy monitor + digest scripts
COPY skool_apprise_monitor.py .
COPY skool_daily_digest_v3.py .

# Copy Dhruv's LinkedIn post monitor
COPY dhruv-linkedin-monitor/ ./dhruv-linkedin-monitor/

# Entrypoint runs both monitors in parallel
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
