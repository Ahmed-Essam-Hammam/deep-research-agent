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

# Run as an unprivileged user (fixed UID so Kubernetes runAsNonRoot can verify it).
# Running containers as root introduces unnecessary security risks.
# If an attacker manages to exploit your application, having root privileges inside the container gives them more control.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY --chown=app:app . .

USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1


# Foward traffic from the AWS LaodBalancer to the FastAPI server
# --proxy-headers: Read the forwarded information.
# --forwarded-allow-ips: Decide whether to trust the sender of that information.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]