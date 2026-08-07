#!/bin/sh
set -eu
umask 077

mkdir -p /etc/hidden
if [ ! -f /etc/hidden/.env ]; then
  cp /opt/hidden/.env /etc/hidden/.env
  chmod 600 /etc/hidden/.env
fi

set -a
. /etc/hidden/.env
set +a

mkdir -p \
  "$INSTALL_CIPHERDIR" \
  "$INSTALL_MOUNTPOINT"

# NOTE (ADR-10): Watchdog runs as a periodic background sleep-loop.
# It periodically validates runtime state and triggers an emergency
# unmount when secrets, passphrase, or the application process are
# missing. Output is redirected to PID 1 so it appears in container
# logs alongside the application.

(
  while true; do
    sleep "$GOCRYPTFS_WATCHDOG_INTERVAL_SECONDS"
    cd "$INSTALL_SOURCE_CODE" && python3 -m app.runtime.watchdog
  done
) >> /proc/1/fd/1 2>> /proc/1/fd/2 &

# NOTE (ADR-04): Application is designed for a single Uvicorn worker.
# This is not a tuning choice but a consequence of the encryption stack:
# gocryptfs is hostile to server-class DBs on FUSE, which forces SQLite,
# which is itself single-writer. Multiple workers therefore provide
# near-zero throughput gain on writes and would actively conflict
# with three in-process gates:
# 1. Filesystem locks in app/locks.py are per-process structures;
#    cross-process serialization would require file/IPC-based locks
#    and a redesign.
# 2. The SQLite WAL writer is single-writer by design; write
#    transactions serialize on the same lock regardless of worker
#    count, so adding workers buys no write throughput, only
#    contention.
# 3. Master-password attempt spacing uses in-process asyncio state;
#    splitting that gate across processes would require a file or
#    IPC like the watchdog heartbeat.

exec uvicorn app.main:app \
  --host "$UVICORN_HOST" \
  --port "$UVICORN_PORT" \
  --workers 1
