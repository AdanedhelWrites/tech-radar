#!/bin/sh
set -e

# --- PostgreSQL bağlantısını bekle (varsa) ---
if [ -n "$DB_HOST" ]; then
    echo "PostgreSQL bekleniyor ($DB_HOST:${DB_PORT:-5432})..."
    while ! nc -z "$DB_HOST" "${DB_PORT:-5432}" 2>/dev/null; do
        echo "  PostgreSQL henuz hazir degil, 2 saniye bekleniyor..."
        sleep 2
    done
    echo "PostgreSQL hazir!"
fi

# --- Redis bağlantısını bekle ---
if [ -n "$REDIS_URL" ]; then
    REDIS_HOST=$(echo "$REDIS_URL" | sed -E 's|redis://([^:]+):?.*|\1|')
    REDIS_PORT=$(echo "$REDIS_URL" | sed -E 's|redis://[^:]+:([0-9]+).*|\1|')
    REDIS_PORT=${REDIS_PORT:-6379}
    echo "Redis bekleniyor ($REDIS_HOST:$REDIS_PORT)..."
    while ! nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; do
        echo "  Redis henuz hazir degil, 2 saniye bekleniyor..."
        sleep 2
    done
    echo "Redis hazir!"
fi

# --- Migration (sadece API sunucusu icin, worker/beat icin skip) ---
# Celery komutları migration çalıştırmamalı
# Kubernetes'te RUN_STARTUP_TASKS=false: migration ayri Job'da calisir, statik
# dosyalar imajdadir (Faz B2). Compose varsayilani true (davranis degismez).
case "$1" in
    celery)
        echo "Celery modu — migration atlanıyor."
        ;;
    *)
        if [ "${RUN_STARTUP_TASKS:-true}" = "true" ]; then
            # 2026-10-08: '|| true' kaldirildi. Migration basarisizsa uygulama eski semayla
            # acilip sonradan 500 vermek yerine konteyner hemen dusmeli (set -e); compose
            # restart: unless-stopped ile yeniden dener, hata loglarda gorunur.
            echo "Migration calistiriliyor..."
            python manage.py migrate --noinput

            echo "Static dosyalar toplanıyor..."
            python manage.py collectstatic --noinput
        else
            echo "RUN_STARTUP_TASKS=false — migration ve collectstatic atlaniyor."
        fi
        ;;
esac

echo "Baslatiliyor: $@"
exec "$@"
