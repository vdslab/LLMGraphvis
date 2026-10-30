FROM python:3.12.16-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY backend/gai.conf /etc/gai.conf
COPY backend/requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY common common
COPY backend .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive ${KEEP_ALIVE_TIMEOUT:-300}"]
