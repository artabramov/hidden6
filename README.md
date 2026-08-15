# hidden6

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
