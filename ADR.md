# ADR Registry

This file indexes architecture decisions referenced in code through
`NOTE (ADR-XX)` comments. The source of truth is the code. Use global
search across the project for details.

ADR-01: Connect the removable secrets volume before install.
ADR-02: Cipherdir uses a Docker volume; secrets use a bind mount.
ADR-03: Application runs inside a Docker container.
ADR-04: Environment variables are distributed in a dotenv file.
ADR-05: Application uses a single Uvicorn worker.
ADR-06: Filesystem-level encryption uses gocryptfs.
ADR-07: Passphrase is provided using a temporary file in tmpfs.
ADR-08: Cipherdir initialization uses best-effort rollback.
ADR-09: API errors are status-only recovery classes.
ADR-10: Watchdog performs cipherdir unmount with a grace period.

ADR-XX: Request context is a per-task key-value store.
ADR-XX: X-Request-ID is accepted for request correlation.
ADR-XX: Request context is reset before and after request.
ADR-XX: Middleware order is intentionally fixed.
ADR-XX: SQLite is used as the database backend.
ADR-XX: Dispose connections before gocryptfs unmount.
