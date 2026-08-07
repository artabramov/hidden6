# ADR Registry

This file indexes architecture decisions referenced in code through
`NOTE (ADR-XX)` comments. The source of truth is the code. Use global
search across the project for details.

ADR-01: Removable media is preferred for the secrets volume.
ADR-02: Cipherdir data remains portable in a Docker volume.
ADR-03: Application runs in an isolated Docker container.
ADR-04: Application is designed for a single Uvicorn worker.
ADR-05: Environment variables are distributed in a dotenv file.
ADR-06: Filesystem-level encryption uses gocryptfs.
ADR-07: Passphrase is passed to gocryptfs through tmpfs.
ADR-XX: Dispose connections before gocryptfs unmount.

ADR-10: Watchdog runs as a periodic background sleep-loop.
ADR-11: Watchdog performs an immediate emergency unmount.

ADR-XX: Request context is a per-task key-value store.
ADR-XX: X-Request-ID is accepted for request correlation.
ADR-XX: Request context is reset before and after request.
ADR-XX: Middleware order is intentionally fixed.
ADR-XX: SQLite is used as the database backend.
