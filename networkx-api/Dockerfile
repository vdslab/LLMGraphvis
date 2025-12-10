FROM python:3.12

WORKDIR /app

# Install system dependencies (usually not needed for full image as it has compilers, but libpq might be needed)
# libpq-dev is usually present or installable. 
# But let's try WITHOUT apt-get if possible, or minimal.
# Reverting apt-get to original minimal if possible, but fa2 needs headers.
# python:3.12 includes gcc.

# Minimal check
# RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--timeout-keep-alive", "60"]
