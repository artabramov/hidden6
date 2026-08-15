# Architecture Decision Registry

This file indexes architecture decisions referenced in code through
`NOTE (ADR-XX)` comments. The source of truth is the code. Use global
search across the project for details.

ADR-01: Removable media is preferred for the secrets volume.
ADR-02: Cipherdir data remains portable in a Docker volume.
ADR-03: Environment variables are provided in a dotenv file.
ADR-04: Application runs in an isolated Docker container.
ADR-05: Application is designed for a single Uvicorn worker.
ADR-06: Application middleware execution order is fixed.
ADR-07: Filesystem-level encryption uses gocryptfs.
ADR-08: Gocryptfs dependency executes before all others.
ADR-09: Gocryptfs passphrase is protected by master password.
ADR-10: Passphrase is passed to gocryptfs through tmpfs.
ADR-11: HTTP 401/502/503 are reserved for internal errors.
ADR-12: Watchdog runs as a periodic background sleep-loop.
ADR-13: Watchdog performs an immediate emergency unmount.
ADR-14: X-Request-ID is accepted for request correlation.
ADR-15: Request context is isolated between requests.
ADR-16: Sensitive application and request data is not logged.
ADR-17: SQLite is configured for the gocryptfs-backed stack.
ADR-18: SQLite database integrity is enforced on every mount.
ADR-19: SQLite ORM relationships do not use implicit loading.
ADR-20: S3 request authentication uses AWS Signature Version 4.
ADR-21: S3 authorization is owner-and-root (no IAM policies).
ADR-22: S3 routes are excluded from the OpenAPI schema.
ADR-23: S3 objects follow the objekt naming convention.
ADR-24: S3 object keys map to nested filesystem paths.
ADR-25: S3 upload bodies are decoded from aws-chunked framing.
ADR-26: S3 multipart uploads are tracked in the database.
ADR-27: S3 versioning keeps the current object on the key path.
ADR-28: S3 empty key directories are kept after rollback.
