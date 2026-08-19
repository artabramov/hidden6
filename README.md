# Hidden — self-hosted S3-compatible object storage secured by gocryptfs

Designed to protect sensitive data on privately managed infrastructure
while retaining compatibility with the `S3` ecosystem.

Built with `gocryptfs` and `FastAPI`, it exposes an S3-compatible API
that can be used with standard S3 clients. All stored data is kept
encrypted at rest and cannot be accessed directly from the underlying
storage. Internal file operations follow `POSIX` semantics with atomic
guarantees where applicable.

The application is delivered as a `Docker` image and can run in any
compatible environment. It uses two volumes: `cipherdir` (encrypted
data storage) and bind-mounted `secrets` (encryption keys), preferably
backed by removable media.

The `cipherdir` is mounted internally using a `gocryptfs passphrase`
stored in `secrets`. The passphrase itself is encrypted and requires a
`master password` for each mount. If the passphrase becomes unavailable,
the decrypted view is automatically unmounted. Without access to the
passphrase, the data remains inaccessible.

In emergency recovery scenarios, the `cipherdir` can be mounted directly
with `gocryptfs` using the decrypted passphrase. The internal filesystem
structure directly reflects the object store, allowing stored objects
to be recovered without the application.

## Use cases

The project is intentionally **not** designed as a large-scale cloud
platform or distributed object storage system. Instead, its primary
focus is data protection. Typical use cases include:

**Personal or homelab storage** — financial documents, private photos
and videos, scans, notes, correspondence, important records.

**Co-located teams and studios** — internal assets, drafts, contracts,
project files, research materials, deliverables, and unpublished media.

**Isolated infrastructure segments** — credentials, configuration files,
critical exports, and other sensitive data isolated within large-scale
systems.

**Backups and archives** — application backups, database dumps, exported
datasets, snapshots, historical records, and long-term archives.

## How it works

Externally, the application exposes an S3-compatible API for object
storage and a REST API for storage control and user management.

Internally, when the storage is unlocked, the application accesses the
decrypted cipherdir through a gocryptfs mountpoint. A watchdog monitors
the passphrase and unmounts the filesystem if it becomes unavailable.

```text
        Internals                      Externals

┌───────────────────────┐      S3-compatible API provides
│ FastAPI application   │───── access to object storage;
│ (API layer)           │      REST API provides storage
└───────────────────────┘      management and user control
            │
┌───────────────────────┐
│ gocryptfs mountpoint  │
│ (decrypted view)      │
└───────────────────────┘
            │
┌───────────────────────┐     ┌───────────────────────┐
│ watchdog              │-----│ gocryptfs passphrase  │
│ (mount supervisor)    │     │ (detachable secrets)  │
└───────────────────────┘     └───────────────────────┘
            │
┌───────────────────────┐     ┏━━━━━━━━━━━━━━━━━━━━━━━━┓
│ gocryptfs engine      │-----┃ gocryptfs cipherdir    ┃
│ (FUSE layer)          │     ┃ (encrypted storage)    ┃
└───────────────────────┘     ┗━━━━━━━━━━━━━━━━━━━━━━━━┛
```














## Project layout

The application code is organized into small packages with distinct
responsibilities. HTTP routes and their dependencies live separately
from application services, while S3-specific logic is kept independent
from low-level database and filesystem access.

Runtime management covers the gocryptfs lifecycle and watchdog, security
handles encryption and S3 authentication, and dedicated packages contain
database models, request and response schemas, middleware, and S3 XML
parsing and rendering. Optional application extensions live outside the
main package.

```text
app/
├── db/             Database setup, schema, integrity checks
├── dependencies/   FastAPI request dependencies
├── middleware/     HTTP middleware
├── models/         SQLAlchemy models
├── pydantic/       Shared Pydantic types and validation
├── repositories/   Database and filesystem access
├── routers/        HTTP and S3 API routes
├── runtime/        gocryptfs lifecycle and watchdog
├── s3/             S3-specific logic and shared operations
├── schemas/        API request and response schemas
├── security/       Encryption and S3 authentication
├── services/       Application operations and orchestration
└── xml/            S3 XML parsing and rendering
```
