# ADR Registry

This file indexes architecture decisions referenced in code through
`NOTE (ADR-XX)` comments. The source of truth is the code. Use global
search across the project for details.

ADR-01: Connect the removable secrets volume before install.
ADR-02: Cipherdir and secrets are stored in Docker volumes.
ADR-03: Application runs inside a Docker container.
ADR-04: Environment variables are distributed in a dotenv file.
ADR-05: Application uses a single Uvicorn worker.
ADR-06: Filesystem-level encryption uses gocryptfs.
ADR-07: Passphrase is provided using a temporary file in tmpfs.
ADR-08: Cipherdir initialization uses best-effort rollback.
