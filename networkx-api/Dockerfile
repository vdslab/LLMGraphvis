FROM python:3.12.16-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY networkx-api/requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY common common
COPY networkx-api .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--timeout-keep-alive", "60"]
