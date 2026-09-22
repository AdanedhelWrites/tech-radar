# ============================================
# Backend Dockerfile — Production Ready
# Multi-stage build, non-root user
# ============================================

# --- Stage 1: Dependencies ---
FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9 AS builder

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Taban imajin getirdigi setuptools'a gomulu paketlerde (jaraco.context, wheel)
# acik var; bunlar requirements.txt'te olmadigi icin ancak boyle kapanir.
# pip BILEREK yukseltilmiyor: pip 26.x kendi _vendor agacinda acikli msgpack
# tasiyor ve trivy onu da sayiyor, yani yukseltmek net kazanc birakmiyor.
RUN pip install --no-cache-dir --upgrade setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9

# libpq runtime dependency for psycopg2
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Son imajda kalan setuptools bu asamadan gelir; builder'i yukseltmek yetmez.
RUN pip install --no-cache-dir --upgrade setuptools wheel

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Static files directory (owned by appuser)
RUN mkdir -p /app/staticfiles && chown -R appuser:appuser /app

# Make entrypoint executable
RUN chmod +x entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

# Default: run API server with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "cybernews.wsgi:application"]
