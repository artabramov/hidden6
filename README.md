# Hidden — self-hosted S3-compatible object storage secured by gocryptfs

Designed for individuals and small teams that want to protect sensitive
data within their own infrastructure while retaining compatibility with
the `S3` ecosystem.

Built with `gocryptfs` and `FastAPI`, it exposes an S3-compatible API
that can be used with standard S3 clients. All storage data is kept
encrypted and cannot be accessed directly from the underlying storage.
Internal file operations follow `POSIX` semantics with atomic guarantees
where applicable.

The application is delivered as a `Docker` image and can run in any
compatible environment. It uses two storage locations: the `cipherdir`
volume (encrypted data storage) and bind-mounted `secrets` (internal
application secrets), preferably backed by removable media.

The `cipherdir` is unlocked using a `gocryptfs passphrase` stored in
secrets. The passphrase is encrypted and requires a `master password`
for each use. If the encrypted passphrase becomes unavailable, the
decrypted view is automatically unmounted. Without the passphrase
and master password, the data remains inaccessible.

In emergency recovery scenarios, the `cipherdir` can be mounted directly
with `gocryptfs` using the decrypted passphrase. The internal filesystem
structure directly reflects the object store, allowing stored objects
to be recovered without the application.

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
