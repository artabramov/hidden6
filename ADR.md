# ADR Registry

This file indexes architecture decisions referenced in code through
`NOTE (ADR-XX)` comments. The source of truth is the code. Use global
search across the project for details.

ADR-01: Connect the removable secrets volume before install.

ADR-01: Source code follows project conventions.
ADR-02: Environment variables are distributed in a dotenv file.
ADR-03: Application runs inside a Docker container.
ADR-04: Application uses a single Uvicorn worker.
ADR-05: Cipherdir and secrets are stored in Docker volumes.
ADR-06: Filesystem-level encryption uses gocryptfs.
ADR-07: Passphrase is provided using a temporary file in tmpfs.
ADR-08: Cipherdir initialization uses best-effort rollback.
