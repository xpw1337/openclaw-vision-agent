# Headless agent worker image — core/ pipeline + NATS worker, no Streamlit.
FROM python:3.12-slim

WORKDIR /app

COPY requirements-agent.txt .
RUN pip install --no-cache-dir -r requirements-agent.txt

COPY core/ core/
COPY agent/ agent/

RUN useradd --create-home --uid 1000 worker
USER worker

EXPOSE 8080

CMD ["python", "-m", "agent.worker"]
