FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for psycopg2)
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# IPv6-preferring gai.conf for IPv6-only (NAT64/DNS64) networks (see comments
# in the file). docker-compose.yml bind-mounts /etc/gai.conf over this:
# /dev/null (glibc default, normal networks) unless PREFER_IPV6_GAI_CONF is set.
COPY backend/gai.conf /etc/gai.conf

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common common
COPY backend .

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive ${KEEP_ALIVE_TIMEOUT:-300}
