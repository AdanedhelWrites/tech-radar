#!/usr/bin/env bash
# Tek kullanimlik PostgreSQL + Redis'e karsi manage.py calistirir (Faz B1).
# Canli compose yiginina (teknoloji-*) ve canli Redis'e dokunmaz.
#
#   scripts/pg_test.sh test news --noinput    # testler PostgreSQL'de
#   scripts/pg_test.sh --sqlite <komut>       # DEBUG=True, DB_HOST bos -> depo kokundeki db.sqlite3
#   scripts/pg_test.sh temizle                # konteynerleri ve agi siler
#
# Depo koku konteynerde /app'tir; komut bu betigin bulundugu deponun kodunu kullanir.
set -euo pipefail

AG=fazb-test
PG=fazb-test-pg
REDIS=fazb-test-redis
PG_IMAJ='postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea'
REDIS_IMAJ='redis:7.4.10-alpine@sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2'
UYGULAMA_IMAJ="${UYGULAMA_IMAJ:-teknoloji-haberleri-api:latest}"
# Yalniz bu gecici konteyner icin; hicbir gercek veritabaninda kullanilmaz.
PAROLA=yerel-gecici-test

KOK="$(cd "$(dirname "$0")/.." && (pwd -W 2>/dev/null || pwd))"

if [ "${1:-}" = "temizle" ]; then
  docker rm -f "$PG" "$REDIS" >/dev/null 2>&1 || true
  docker network rm "$AG" >/dev/null 2>&1 || true
  echo "temizlendi"
  exit 0
fi

docker network inspect "$AG" >/dev/null 2>&1 || docker network create "$AG" >/dev/null
if ! docker inspect "$PG" >/dev/null 2>&1; then
  docker run -d --name "$PG" --network "$AG" \
    -e POSTGRES_USER=cybernews -e POSTGRES_PASSWORD="$PAROLA" -e POSTGRES_DB=cybernews \
    "$PG_IMAJ" >/dev/null
fi
if ! docker inspect "$REDIS" >/dev/null 2>&1; then
  docker run -d --name "$REDIS" --network "$AG" "$REDIS_IMAJ" >/dev/null
fi
# -h 127.0.0.1: ilk acilistaki gecici sunucu yalniz unix soketini dinler; TCP hazir olunca gecer.
hazir=0
for _ in $(seq 1 60); do
  if docker exec "$PG" pg_isready -h 127.0.0.1 -U cybernews -d cybernews >/dev/null 2>&1; then
    hazir=1; break
  fi
  sleep 1
done
[ "$hazir" = 1 ] || { echo "PostgreSQL 60 sn icinde hazir olmadi" >&2; exit 1; }

ORTAM=(-e "REDIS_URL=redis://$REDIS:6379/0" -e "CELERY_BROKER_URL=redis://$REDIS:6379/1"
       -e "SECRET_KEY=$(openssl rand -hex 32)")
if [ "${1:-}" = "--sqlite" ]; then
  shift
  ORTAM+=(-e DEBUG=True -e DB_HOST=)
else
  ORTAM+=(-e DEBUG=False -e "DB_HOST=$PG" -e DB_NAME=cybernews -e DB_USER=cybernews
          -e "DB_PASSWORD=$PAROLA" -e DB_PORT=5432)
fi

MSYS_NO_PATHCONV=1 docker run --rm -i --network "$AG" -v "$KOK:/app" "${ORTAM[@]}" \
  --entrypoint python "$UYGULAMA_IMAJ" manage.py "$@"
