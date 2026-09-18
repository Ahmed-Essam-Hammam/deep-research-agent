FROM python:3.13-slim

WORKDIR /app

# Tells Python not to create .pyc bytecode files.
# Tells Python to output logs immediately rather than buffering them.
# Tells pip not to keep its package download/cache files.
ENV PYTHONDONTWRITEBYTECODE=1 \                      
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps needed to build/run psycopg2 and friends
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install -r requirements.txt


COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
