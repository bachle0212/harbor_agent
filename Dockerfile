FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HARBOR_HOST=0.0.0.0 \
    HARBOR_PORT=8765

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY harbor/ harbor/

RUN mkdir -p data/articles logs

EXPOSE 8765

# Default: scrape → hash delta → upload → exit 0 (task 3).
# Desk: python -m harbor.console (see docker-compose.yml).
CMD ["python", "main.py"]
