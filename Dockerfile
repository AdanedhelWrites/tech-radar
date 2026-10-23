# ============================================
# Backend Dockerfile — Production Ready
# Multi-stage build, non-root user
# ============================================

# --- Stage 1: Dependencies ---
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce AS builder

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Taban imajin getirdigi setuptools'a gomulu paketlerde (jaraco.context, wheel)
# acik var; bunlar requirements.txt'te olmadigi icin ancak boyle kapanir.
# pip BILEREK yukseltilmiyor: pip 26.x kendi _vendor agacinda acikli msgpack
# tasiyor ve trivy onu da sayiyor, yani yukseltmek net kazanc birakmiyor.
# Tum pip kurulumlari hash'e sabitli (--require-hashes; Scorecard PinnedDependencies, 2026-10-23):
# *.in kaynak, *.txt pip-compile --generate-hashes ciktisi (Dependabot ikisini birlikte gunceller).
COPY requirements-araclar.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-araclar.txt

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

# libpq runtime dependency for psycopg2
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Son imajda kalan setuptools bu asamadan gelir; builder'i yukseltmek yetmez.
COPY requirements-araclar.txt /tmp/requirements-araclar.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements-araclar.txt && rm /tmp/requirements-araclar.txt

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Statik dosyalar imaja gomulur: Kubernetes'te kok dosya sistemi salt okunurdur
# ve migration/collectstatic pod acilisinda calismaz (Faz B2, spec 7.7).
# DEBUG=True yalniz bu komut icin: SECRET_KEY ve DB_HOST zorunlulugunu atlar;
# hicbir veritabanina baglanilmaz. Compose bind mount'u bu dizini ortuyor ve
# kendi collectstatic'ini entrypoint'te calistiriyor (RUN_STARTUP_TASKS=true).
RUN DEBUG=True python manage.py collectstatic --noinput     && chown -R appuser:appuser /app

# Make entrypoint executable
RUN chmod +x entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

# Default: run API server with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "cybernews.wsgi:application"]
