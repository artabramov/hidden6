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

# (
#   while true; do
#     sleep "$GOCRYPTFS_WATCHDOG_INTERVAL_SECONDS"
#     cd /opt/hidden && python3 -m app.runtime.watchdog
#   done
# ) >> /proc/1/fd/1 2>> /proc/1/fd/2 &

if [ -x /opt/hidden/.venv/bin/uvicorn ]; then
  UVICORN_BIN=/opt/hidden/.venv/bin/uvicorn
else
  UVICORN_BIN=uvicorn
fi

exec "$UVICORN_BIN" app.main:app \
  --host "$UVICORN_HOST" \
  --port "$UVICORN_PORT" \
  --workers 1
