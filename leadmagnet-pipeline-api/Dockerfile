FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Pipeline scripts
COPY execution/ execution/
COPY widget-demo/ widget-demo/
COPY landing-page-demo/ landing-page-demo/
COPY batch_all.py .
COPY server.py .

# Create .tmp directories
RUN mkdir -p .tmp/screenshots .tmp/html .tmp/branding .tmp/redesigns/history \
    .tmp/analysis .tmp/facts .tmp/comparisons .tmp/qa .tmp/sites .tmp/deploy-repo \
    widget-demo/output landing-page-demo/output

EXPOSE 8000

# Run with uvicorn — 1 worker, long timeout for pipeline runs
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "600"]
