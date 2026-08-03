#!/bin/sh
set -eu
umask 077

mkdir -p /etc/hidden
if [ ! -f /etc/hidden/.env ]; then
  cp /opt/hidden/.env.example /etc/hidden/.env
  chmod 600 /etc/hidden/.env
  echo "[hidden] created .env"
fi

set -a
. /etc/hidden/.env
set +a

exec uvicorn app.main:app \
  --host "$UVICORN_HOST" \
  --port "$UVICORN_PORT" \
  --workers 1
