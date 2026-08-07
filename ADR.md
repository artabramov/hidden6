# ADR Registry

This file indexes architecture decisions referenced in code through
`NOTE (ADR-XX)` comments. The source of truth is the code. Use global
search across the project for details.

ADR-01: Removable media is preferred for the secrets volume.
ADR-02: Cipherdir data remains portable in a Docker volume.
ADR-03: Application runs in an isolated Docker container.
ADR-04: Application is designed for a single Uvicorn worker.
ADR-05: Application middleware execution order is fixed.
ADR-06: Environment variables are distributed in a dotenv file.
ADR-07: Filesystem-level encryption uses gocryptfs.
ADR-08: Passphrase is passed to gocryptfs through tmpfs.
ADR-09: Watchdog runs as a periodic background sleep-loop.
ADR-10: Watchdog performs an immediate emergency unmount.
ADR-11: X-Request-ID is accepted for request correlation.
ADR-12: Request context is a per-task key-value store.
ADR-13: SQLite is required for the gocryptfs-based stack.
