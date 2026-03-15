# Kratos

A production-ready, PostgreSQL-only logging service for HappiDost. Provides database-backed audit logs, user logs, and API logs with atomic upsert behavior.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [Project Structure](#4-project-structure)
5. [Architecture Deep Dive](#5-architecture-deep-dive)
   - [5.1 Models Layer](#51-models-layer)
   - [5.2 Database Layer](#52-database-layer)
   - [5.3 Validators Layer](#53-validators-layer)
   - [5.4 Client Layer](#54-client-layer)
6. [API Reference](#6-api-reference)
   - [6.1 Kratos Class](#61-kratos-class)
   - [6.2 create_audit_log()](#62-create_audit_log)
   - [6.3 create_user_log()](#63-create_user_log)
   - [6.4 create_api_log()](#64-create_api_log)
7. [Admin REST API](#7-admin-rest-api)
   - [7.1 Setup](#71-setup)
   - [7.2 Endpoints](#72-endpoints)
   - [7.3 Query Filters](#73-query-filters)
8. [Database Tables](#8-database-tables)
9. [The Upsert Mechanism](#9-the-upsert-mechanism)
10. [Error Handling](#10-error-handling)
11. [Thread Safety](#11-thread-safety)
12. [Testing](#12-testing)
13. [Integration Examples](#13-integration-examples)
14. [How Every File Works](#14-how-every-file-works)

---

## 1. Prerequisites

- **Python 3.10+**
- **PostgreSQL** (running instance — local, Docker, or remote)
- **Docker** (for running tests — testcontainers spins up a PostgreSQL container)

---

## 2. Installation

### From within the HappiDost project

```bash
cd happidost/kratos

# Production install
pip install -e .

# With admin REST API (includes FastAPI + uvicorn)
pip install -e ".[admin]"

# Development install (includes pytest + testcontainers)
pip install -e ".[dev]"
```

### What gets installed

| Package | Purpose |
|---------|---------|
| `sqlalchemy>=2.0` | ORM + database engine |
| `pydantic>=2.0` | Input validation |
| `psycopg2-binary>=2.9` | PostgreSQL driver |
| `fastapi>=0.110` | Admin REST API (admin only) |
| `uvicorn[standard]>=0.29` | ASGI server (admin only) |
| `pytest>=7.0` | Test runner (dev only) |
| `pytest-xdist>=3.0` | Parallel test execution (dev only) |
| `testcontainers[postgres]>=4.0` | Spins up PostgreSQL in Docker for tests (dev only) |

### Verify installation

```python
from kratos import Kratos
print("kratos installed successfully")
```

---

## 3. Quick Start

```python
from kratos import Kratos, ValidationError

# Step 1: Connect to PostgreSQL
logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")
# Tables are auto-created on initialization — no migrations needed.

# Step 2: Create an audit log (identity is optional)
log = logger.create_audit_log(action="login", ip="192.168.1.1")
print(log.id)          # "a1b2c3d4-..."  (UUID)
print(log.action)      # "login"
print(log.created_at)  # 2026-02-28 12:00:00+00:00

# Step 3: Create an audit log with identity
log = logger.create_audit_log(action="login", ip="192.168.1.1", identity="user123")
print(log.identity)    # "user123"

# Step 4: Create a user log (identity is required)
log = logger.create_user_log(identity="user123", action="profile_update", ip="10.0.0.1")
print(log.identity)    # "user123"

# Step 5: Create an API log — first call creates it
api = logger.create_api_log(
    session_id="sess_abc",
    endpoint="/api/users",
    action="GET",
    ip="1.2.3.4",
)
print(api.attempts)    # 1

# Step 6: Same call again — upserts instead of duplicating
api = logger.create_api_log(
    session_id="sess_abc",
    endpoint="/api/users",
    action="GET",
    ip="1.2.3.4",
)
print(api.attempts)    # 2  (incremented, not a new row)

# Step 7: Handle validation errors
try:
    logger.create_user_log(identity="", action="test", ip="bad_ip")
except ValidationError as e:
    print(f"Caught: {e}")
```

---

## 4. Project Structure

```
kratos/
├── pyproject.toml                   # Package config, dependencies
├── README.md                        # This file
├── src/
│   └── kratos/
│       ├── __init__.py              # Public exports: Kratos, exceptions
│       ├── client.py                # Kratos class — the public API
│       ├── exceptions.py            # KratosError, ConfigurationError, ValidationError, DatabaseError
│       ├── admin/
│       │   ├── __init__.py          # Exports create_admin_app
│       │   ├── app.py               # FastAPI app factory — wires Kratos to the admin API
│       │   ├── routes.py            # REST endpoints for querying logs + stats
│       │   └── schemas.py           # Pydantic response models (AuditLogOut, etc.)
│       ├── models/
│       │   ├── __init__.py          # Re-exports Base + all 3 models
│       │   ├── base.py              # DeclarativeBase + TimestampMixin
│       │   ├── audit_log.py         # AuditLog model
│       │   ├── user_log.py          # UserLog model
│       │   └── api_log.py           # ApiLog model (with UniqueConstraint)
│       ├── db/
│       │   ├── __init__.py          # Re-exports build_engine, SessionFactory, upsert_api_log
│       │   ├── engine.py            # PostgreSQL engine with connection pooling
│       │   ├── session.py           # SessionFactory — context manager with auto commit/rollback
│       │   └── upsert.py            # INSERT ... ON CONFLICT DO UPDATE for api_logs
│       └── validators/
│           ├── __init__.py          # Re-exports Pydantic schemas
│           └── schemas.py           # AuditLogInput, UserLogInput, ApiLogInput
└── tests/
    ├── conftest.py                  # PostgreSQL testcontainer fixture
    ├── test_models.py               # Table creation + column verification
    ├── test_client.py               # End-to-end client tests
    ├── test_upsert.py               # Upsert logic tests
    ├── test_validators.py           # Input validation tests
    └── test_thread_safety.py        # Concurrent write tests
```

**Design principle**: Each layer has a single responsibility. Models define the schema, `db/` handles connections and queries, `validators/` sanitize input, and `client.py` wires it all together behind three clean methods.

---

## 5. Architecture Deep Dive

### 5.1 Models Layer

Located in `src/kratos/models/`.

#### base.py — Foundation

```python
class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

- `Base` is the SQLAlchemy 2.x declarative base — all models inherit from it.
- `TimestampMixin` adds `created_at` and `updated_at` to every model automatically.
- `server_default=func.now()` means PostgreSQL generates the timestamp, not Python. This keeps times consistent regardless of which machine the code runs on.
- `onupdate=func.now()` on `updated_at` means it auto-updates whenever the row changes via SQLAlchemy ORM.

#### audit_log.py

```python
class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identity: Mapped[str | None] = mapped_column(String(255), nullable=True)   # optional
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)                # IPv4 + IPv6
```

- `id` uses UUID4 generated in Python via `default=lambda: str(uuid.uuid4())`.
- `identity` is **nullable** — audit logs can be anonymous (e.g., failed login attempts).
- `ip` is `String(45)` to support both IPv4 (max 15 chars) and IPv6 (max 45 chars).

#### user_log.py

Same as AuditLog except `identity` is **required** (`nullable=False`). User logs always track who did the action.

#### api_log.py

```python
class ApiLog(TimestampMixin, Base):
    __tablename__ = "api_logs"
    __table_args__ = (
        UniqueConstraint("session_id", "endpoint", "ip", name="uq_api_log_session_endpoint_ip"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
```

- The `UniqueConstraint` on `(session_id, endpoint, ip)` is what makes upserts work. PostgreSQL uses this constraint to detect conflicts.
- `attempts` starts at 1 and increments on each duplicate call.

### 5.2 Database Layer

Located in `src/kratos/db/`.

#### engine.py — Connection Pooling

```python
def build_engine(db_url: str) -> Engine:
    if not db_url:
        raise ConfigurationError("db_url must not be empty")
    if not db_url.startswith("postgresql"):
        raise ConfigurationError("Only PostgreSQL is supported...")

    return create_engine(
        db_url,
        pool_size=5,        # 5 persistent connections in the pool
        max_overflow=10,     # up to 10 extra connections under load
        pool_pre_ping=True,  # checks if connections are alive before using them
        pool_recycle=1800,   # recycles connections after 30 minutes
    )
```

**Connection pool explained**:
- In production, creating a new database connection is expensive (~50-100ms). Connection pooling reuses connections.
- `pool_size=5` — The pool keeps 5 connections open and ready.
- `max_overflow=10` — Under heavy load, up to 15 total connections (5 + 10 overflow).
- `pool_pre_ping=True` — Before giving a connection to your code, SQLAlchemy sends a lightweight `SELECT 1` to check if the connection is still alive. This prevents errors from stale connections (e.g., after PostgreSQL restarts).
- `pool_recycle=1800` — Connections older than 30 minutes are replaced with fresh ones. Prevents issues with firewalls or load balancers that kill idle connections.

#### session.py — Transaction Management

```python
class SessionFactory:
    def __init__(self, engine: Engine) -> None:
        self._session_maker = sessionmaker(bind=engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_maker()
        try:
            yield session
            session.commit()      # auto-commit on success
        except Exception as exc:
            session.rollback()    # auto-rollback on error
            raise DatabaseError(str(exc)) from exc
        finally:
            session.close()       # always return connection to pool
```

Used as:
```python
with self._session_factory.session() as session:
    session.add(some_object)
    session.flush()
    # If we get here, commit happens automatically
# If an exception was raised, rollback happens automatically
```

**Why this pattern**:
- **No leaked transactions** — every session is committed or rolled back.
- **No leaked connections** — `finally: session.close()` always runs.
- **Clean exception wrapping** — all database errors become `DatabaseError`.

#### upsert.py — Atomic INSERT ON CONFLICT

```python
def upsert_api_log(session, *, session_id, endpoint, action, ip) -> ApiLog:
    stmt = insert(ApiLog.__table__).values(
        id=str(uuid.uuid4()),
        session_id=session_id, endpoint=endpoint,
        action=action, ip=ip, attempts=1,
        created_at=func.now(), updated_at=func.now(),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_api_log_session_endpoint_ip",
        set_={
            "attempts": ApiLog.__table__.c.attempts + 1,
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)
    session.flush()

    row = session.query(ApiLog).filter_by(
        session_id=session_id, endpoint=endpoint, ip=ip
    ).one()
    return row
```

This generates:
```sql
INSERT INTO api_logs (id, session_id, endpoint, action, ip, attempts, created_at, updated_at)
VALUES ('uuid', 'sess_abc', '/api/users', 'GET', '1.1.1.1', 1, now(), now())
ON CONFLICT ON CONSTRAINT uq_api_log_session_endpoint_ip DO UPDATE SET
    attempts = api_logs.attempts + 1,
    updated_at = now();
```

**Why this is better than check-then-insert**:
- **Atomic** — PostgreSQL handles the check and update in a single operation.
- **No race conditions** — Even if 10 threads call this simultaneously, PostgreSQL serializes conflicting rows via row-level locks.
- **No application-level locks needed** — the database does it for you.

### 5.3 Validators Layer

Located in `src/kratos/validators/`.

#### schemas.py — Pydantic v2 Input Validation

Three Pydantic models validate input before it hits the database:

```python
class AuditLogInput(BaseModel):
    action: str          # must be non-empty
    ip: str              # must be valid IPv4 or IPv6
    identity: str | None = None   # optional, whitespace-only becomes None

class UserLogInput(BaseModel):
    identity: str        # must be non-empty
    action: str          # must be non-empty
    ip: str              # must be valid IPv4 or IPv6

class ApiLogInput(BaseModel):
    session_id: str      # must be non-empty
    endpoint: str        # must be non-empty
    action: str          # must be non-empty
    ip: str              # must be valid IPv4 or IPv6
```

**IP validation** uses Python's `ipaddress.ip_address()` — accepts both IPv4 (`192.168.1.1`) and IPv6 (`::1`, `2001:db8::1`).

**Why validate before the database**:
- Fail fast with clear error messages instead of cryptic PostgreSQL constraint violations.
- Pydantic strips whitespace and normalizes values consistently.
- The database layer never sees invalid data.

### 5.4 Client Layer

Located in `src/kratos/client.py`.

The `Kratos` class wires everything together:

```
User calls create_audit_log(action="login", ip="1.2.3.4")
    │
    ▼
Validator: AuditLogInput validates & cleans input
    │
    ▼
Model: AuditLog ORM object created
    │
    ▼
Session: opened from pool → add → flush → refresh → expunge → commit → close
    │
    ▼
Return: detached AuditLog object (safe to use outside the session)
```

**Key pattern — expunge before return**:
```python
with self._session_factory.session() as session:
    session.add(log)
    session.flush()          # writes to DB, generates id + timestamps
    session.refresh(log)     # loads all DB-generated values into the Python object
    session.expunge(log)     # detaches from session so it's safe after close
return log
```

Without `expunge`, accessing `log.id` after the session closes would raise a `DetachedInstanceError`.

---

## 6. API Reference

### 6.1 Kratos Class

```python
from kratos import Kratos

logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `db_url` | `str` | Yes (keyword-only) | PostgreSQL connection URL |

- Tables (`audit_logs`, `user_logs`, `api_logs`) are auto-created on initialization via `Base.metadata.create_all()`.
- Raises `ConfigurationError` if `db_url` is empty or not a PostgreSQL URL.

### 6.2 create_audit_log()

```python
log = logger.create_audit_log(action="login", ip="192.168.1.1")
log = logger.create_audit_log(action="login", ip="192.168.1.1", identity="user123")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | `str` | Yes | What happened (e.g., "login", "logout", "delete_account") |
| `ip` | `str` | Yes | IPv4 or IPv6 address |
| `identity` | `str \| None` | No | Who did it (optional for anonymous events) |

**Returns**: `AuditLog` object with `id`, `action`, `ip`, `identity`, `created_at`, `updated_at`.

### 6.3 create_user_log()

```python
log = logger.create_user_log(identity="user123", action="profile_update", ip="10.0.0.1")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `identity` | `str` | Yes | Who did it (required — cannot be empty) |
| `action` | `str` | Yes | What happened |
| `ip` | `str` | Yes | IPv4 or IPv6 address |

**Returns**: `UserLog` object with `id`, `identity`, `action`, `ip`, `created_at`, `updated_at`.

### 6.4 create_api_log()

```python
api = logger.create_api_log(session_id="sess_abc", endpoint="/api/users", action="GET", ip="1.2.3.4")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | `str` | Yes | Client session identifier |
| `endpoint` | `str` | Yes | API endpoint path |
| `action` | `str` | Yes | HTTP method or action name |
| `ip` | `str` | Yes | IPv4 or IPv6 address |

**Returns**: `ApiLog` object with `id`, `session_id`, `endpoint`, `action`, `ip`, `attempts`, `created_at`, `updated_at`.

**Upsert behavior**: If a row with the same `(session_id, endpoint, ip)` already exists, `attempts` is incremented and `updated_at` is refreshed instead of creating a new row.

---

## 7. Admin REST API

Kratos ships with an optional built-in admin API powered by FastAPI. It lets you query all logged data and view stats through REST endpoints — no extra code needed.

### 7.1 Setup

Install with the `admin` extra:

```bash
pip install -e ".[admin]"
```

Create and run the admin server:

```python
import uvicorn
from kratos import Kratos
from kratos.admin import create_admin_app

logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")
app = create_admin_app(logger)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Then open `http://localhost:8000/docs` for the interactive Swagger UI.

### 7.2 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/stats` | Total counts for all log types |
| GET | `/admin/audit-logs` | List audit logs (paginated, filterable) |
| GET | `/admin/audit-logs/{id}` | Get a single audit log by ID |
| GET | `/admin/user-logs` | List user logs (paginated, filterable) |
| GET | `/admin/user-logs/{id}` | Get a single user log by ID |
| GET | `/admin/api-logs` | List API logs (paginated, filterable) |
| GET | `/admin/api-logs/{id}` | Get a single API log by ID |

All list endpoints return results ordered by `created_at` descending (newest first).

### 7.3 Query Filters

All list endpoints support pagination:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Results per page (1–1000) |
| `offset` | int | 0 | Skip this many results |
| `since` | datetime | — | Only return logs created after this timestamp |

#### Audit log filters

| Parameter | Description |
|-----------|-------------|
| `action` | Filter by action (exact match) |
| `ip` | Filter by IP address |
| `identity` | Filter by identity |

#### User log filters

| Parameter | Description |
|-----------|-------------|
| `action` | Filter by action |
| `ip` | Filter by IP address |
| `identity` | Filter by identity |

#### API log filters

| Parameter | Description |
|-----------|-------------|
| `session_id` | Filter by session ID |
| `endpoint` | Filter by endpoint |
| `ip` | Filter by IP address |
| `action` | Filter by action |

### Example requests

```bash
# Get stats
curl http://localhost:8000/admin/stats

# List all audit logs
curl http://localhost:8000/admin/audit-logs

# Filter audit logs by action
curl "http://localhost:8000/admin/audit-logs?action=login"

# Filter user logs by identity with pagination
curl "http://localhost:8000/admin/user-logs?identity=user123&limit=10&offset=0"

# Filter API logs by endpoint
curl "http://localhost:8000/admin/api-logs?endpoint=/api/users"

# Get logs since a specific time
curl "http://localhost:8000/admin/audit-logs?since=2026-01-01T00:00:00Z"

# Get a specific log by ID
curl http://localhost:8000/admin/audit-logs/a1b2c3d4-5678-...
```

### Response format

All responses are JSON. Example for `/admin/stats`:

```json
{
  "audit_logs": 42,
  "user_logs": 15,
  "api_logs": 8
}
```

Example for `/admin/audit-logs`:

```json
[
  {
    "id": "a1b2c3d4-5678-...",
    "identity": "user123",
    "action": "login",
    "ip": "192.168.1.1",
    "created_at": "2026-02-28T10:20:47.049546Z",
    "updated_at": "2026-02-28T10:20:47.049546Z"
  }
]
```

---

## 8. Database Tables

### audit_logs

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | VARCHAR(36) | No | Primary key, UUID4 |
| identity | VARCHAR(255) | Yes | Optional |
| action | VARCHAR(255) | No | |
| ip | VARCHAR(45) | No | IPv4 + IPv6 |
| created_at | TIMESTAMP WITH TIME ZONE | No | Auto-set by PostgreSQL |
| updated_at | TIMESTAMP WITH TIME ZONE | No | Auto-updated |

### user_logs

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | VARCHAR(36) | No | Primary key, UUID4 |
| identity | VARCHAR(255) | No | **Required** |
| action | VARCHAR(255) | No | |
| ip | VARCHAR(45) | No | |
| created_at | TIMESTAMP WITH TIME ZONE | No | Auto-set |
| updated_at | TIMESTAMP WITH TIME ZONE | No | Auto-updated |

### api_logs

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | VARCHAR(36) | No | Primary key, UUID4 |
| session_id | VARCHAR(255) | No | |
| endpoint | VARCHAR(500) | No | |
| action | VARCHAR(255) | No | |
| ip | VARCHAR(45) | No | |
| attempts | INTEGER | No | Starts at 1, increments on upsert |
| created_at | TIMESTAMP WITH TIME ZONE | No | Auto-set |
| updated_at | TIMESTAMP WITH TIME ZONE | No | Updated on each upsert |

**Unique constraint**: `(session_id, endpoint, ip)` — named `uq_api_log_session_endpoint_ip`.

---

## 9. The Upsert Mechanism

### Problem

Your API gateway logs every request. The same user might hit `/api/users` 100 times in a session. You don't want 100 rows — you want one row with `attempts=100`.

### Solution

`create_api_log()` uses PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE`:

```
First call: session_id="s1", endpoint="/api/users", ip="1.2.3.4"
  → INSERT new row, attempts=1

Second call: same session_id + endpoint + ip
  → ON CONFLICT → UPDATE attempts = 2, updated_at = now()

Third call: same again
  → ON CONFLICT → UPDATE attempts = 3, updated_at = now()

Different session_id or endpoint or ip
  → INSERT new row, attempts=1
```

### Under the hood

The unique constraint `(session_id, endpoint, ip)` tells PostgreSQL: "if a row already exists with these three values, don't insert — update instead."

PostgreSQL handles this atomically using row-level locks. Even if 10 threads call `create_api_log()` with the same key simultaneously, each one will increment `attempts` correctly. No duplicates, no lost updates.

---

## 10. Error Handling

Kratos has four exception types, all inheriting from `KratosError`:

```python
from kratos import KratosError, ConfigurationError, ValidationError, DatabaseError
```

```
KratosError                  # Base — catch all kratos errors
├── ConfigurationError       # Bad db_url, non-PostgreSQL URL
├── ValidationError          # Invalid input (empty action, bad IP, etc.)
└── DatabaseError            # Database operation failed
```

### Examples

```python
from kratos import Kratos, ConfigurationError, ValidationError, DatabaseError

# ConfigurationError — bad URL
try:
    Kratos(db_url="")
except ConfigurationError as e:
    print(e)  # "db_url must not be empty"

try:
    Kratos(db_url="sqlite:///test.db")
except ConfigurationError as e:
    print(e)  # "Only PostgreSQL is supported..."

# ValidationError — bad input
logger = Kratos(db_url="postgresql://...")
try:
    logger.create_audit_log(action="", ip="127.0.0.1")
except ValidationError as e:
    print(e)  # validation error for action

try:
    logger.create_user_log(identity="user1", action="test", ip="not_an_ip")
except ValidationError as e:
    print(e)  # validation error for ip

# DatabaseError — connection failure, constraint violation, etc.
try:
    logger.create_audit_log(action="test", ip="127.0.0.1")
except DatabaseError as e:
    print(e)  # database-level error

# Catch everything
try:
    logger.create_audit_log(action="test", ip="127.0.0.1")
except KratosError as e:
    print(f"Something went wrong: {e}")
```

---

## 11. Thread Safety

Kratos is thread-safe by design:

1. **Connection pool** — Each thread gets its own connection from the pool. No shared mutable state.
2. **Per-call sessions** — Each method call creates a new session, uses it, and closes it. Sessions are never shared between threads.
3. **Atomic upserts** — PostgreSQL handles concurrent upserts via row-level locks. No application-level locking needed.

```python
import threading
from kratos import Kratos

logger = Kratos(db_url="postgresql://...")

def worker(i):
    logger.create_audit_log(action=f"action_{i}", ip="127.0.0.1")

# 20 threads writing simultaneously — all succeed
threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

---

## 12. Testing

### Prerequisites

- **Docker** must be running (testcontainers launches a PostgreSQL container)

### Run all tests

```bash
cd kratos
pip install -e ".[dev]"
pytest tests/ -v
```

### What happens

1. `conftest.py` starts a `postgres:16-alpine` Docker container (session-scoped — one container for all tests).
2. The `pg_url` fixture provides the connection URL to all tests.
3. The `logger` fixture creates a `Kratos` instance and truncates all tables after each test.
4. Tests run against a real PostgreSQL instance — no mocks, no fakes.

### Test structure

| File | Tests | What it covers |
|------|-------|---------------|
| `test_models.py` | 6 | Table creation, columns, constraints |
| `test_client.py` | 12 | End-to-end: all three log methods + validation errors |
| `test_upsert.py` | 4 | Upsert logic: insert, increment, separate keys |
| `test_validators.py` | 15 | Pydantic validation: valid input, empty strings, bad IPs, IPv6 |
| `test_thread_safety.py` | 3 | Concurrent writes, concurrent upserts, mixed log types |
| **Total** | **40** | |

### Run a single test file

```bash
pytest tests/test_client.py -v
pytest tests/test_validators.py -v
```

### Run tests in parallel

```bash
pytest tests/ -n auto
```

---

## 13. Integration Examples

### FastAPI middleware

```python
from fastapi import FastAPI, Request
from kratos import Kratos

app = FastAPI()
logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.create_api_log(
        session_id=request.cookies.get("session_id", "anonymous"),
        endpoint=request.url.path,
        action=request.method,
        ip=request.client.host,
    )
    return response
```

### Flask after_request

```python
from flask import Flask, request, session
from kratos import Kratos

app = Flask(__name__)
logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")

@app.after_request
def log_request(response):
    logger.create_api_log(
        session_id=session.get("id", "anonymous"),
        endpoint=request.path,
        action=request.method,
        ip=request.remote_addr,
    )
    return response
```

### User action tracking

```python
from kratos import Kratos

logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")

def handle_login(username: str, ip: str, success: bool):
    if success:
        logger.create_audit_log(action="login_success", ip=ip, identity=username)
        logger.create_user_log(identity=username, action="login", ip=ip)
    else:
        logger.create_audit_log(action="login_failed", ip=ip)  # no identity — failed login

def handle_profile_update(user_id: str, ip: str):
    logger.create_user_log(identity=user_id, action="profile_update", ip=ip)

def handle_account_delete(user_id: str, ip: str):
    logger.create_audit_log(action="account_deleted", ip=ip, identity=user_id)
    logger.create_user_log(identity=user_id, action="account_deleted", ip=ip)
```

### Rate limiting awareness

```python
from kratos import Kratos

logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")

def check_and_log_api_call(session_id: str, endpoint: str, ip: str):
    log = logger.create_api_log(
        session_id=session_id,
        endpoint=endpoint,
        action="GET",
        ip=ip,
    )
    if log.attempts > 100:
        raise Exception(f"Rate limit exceeded: {log.attempts} attempts")
    return log
```

---

## 14. How Every File Works

### pyproject.toml

The package manifest. Tells pip how to install kratos:
- `[build-system]` — uses setuptools to build the package.
- `[project]` — name, version, Python requirement (3.10+), runtime dependencies.
- `[project.optional-dependencies]` — dev dependencies installed with `pip install -e ".[dev]"`.
- `[tool.setuptools.packages.find]` — tells setuptools to look in `src/` for packages (src layout).

### src/kratos/__init__.py

The package entry point. When you `from kratos import Kratos`, this file controls what's available:
- Re-exports `Kratos` from `client.py`.
- Re-exports all four exception types from `exceptions.py`.
- `__all__` defines the public API.

### src/kratos/exceptions.py

Four exception classes forming a hierarchy:
- `KratosError` — base, catch-all.
- `ConfigurationError` — raised in `__init__` if the DB URL is bad.
- `ValidationError` — raised when Pydantic rejects input.
- `DatabaseError` — raised when a DB operation fails (wraps SQLAlchemy exceptions).

### src/kratos/admin/__init__.py

Exports `create_admin_app` — the single entry point for creating an admin FastAPI application.

### src/kratos/admin/app.py

`create_admin_app(kratos_instance)` — factory function that:
1. Wires the Kratos instance's session factory into the routes module.
2. Creates a FastAPI app with the `Kratos Admin` title.
3. Includes the admin router (all `/admin/*` endpoints).

Returns a ready-to-run FastAPI application.

### src/kratos/admin/routes.py

Defines all admin REST endpoints using a FastAPI `APIRouter` with prefix `/admin`:
- List endpoints (`/audit-logs`, `/user-logs`, `/api-logs`) support filtering by field values, `since` timestamp, and `limit`/`offset` pagination.
- Detail endpoints (`/audit-logs/{id}`, etc.) return a single log or 404.
- `/stats` returns total row counts for all three log tables.

All queries use SQLAlchemy `select()` statements and results are serialized through Pydantic response models.

### src/kratos/admin/schemas.py

Pydantic v2 response models for the admin API:
- `AuditLogOut`, `UserLogOut`, `ApiLogOut` — serialize ORM objects to JSON with `from_attributes=True`.
- `StatsOut` — simple counts for each log table.

### src/kratos/models/base.py

- `Base` — SQLAlchemy 2.x `DeclarativeBase`. Every model inherits from this. Calling `Base.metadata.create_all(engine)` creates all tables.
- `TimestampMixin` — adds `created_at` and `updated_at` columns using PostgreSQL's `now()` function.

### src/kratos/models/audit_log.py

The `AuditLog` ORM model. Maps to the `audit_logs` table. `identity` is nullable.

### src/kratos/models/user_log.py

The `UserLog` ORM model. Maps to the `user_logs` table. `identity` is NOT nullable.

### src/kratos/models/api_log.py

The `ApiLog` ORM model. Maps to the `api_logs` table. Has a `UniqueConstraint` on `(session_id, endpoint, ip)` and an `attempts` counter.

### src/kratos/models/__init__.py

Re-exports all models so you can do `from kratos.models import AuditLog`.

### src/kratos/db/engine.py

`build_engine()` creates a SQLAlchemy `Engine` connected to PostgreSQL with connection pooling. Rejects non-PostgreSQL URLs.

### src/kratos/db/session.py

`SessionFactory` wraps `sessionmaker`. Its `.session()` context manager handles commit/rollback/close automatically. Every database exception becomes a `DatabaseError`.

### src/kratos/db/upsert.py

`upsert_api_log()` uses `sqlalchemy.dialects.postgresql.insert` with `.on_conflict_do_update()` to atomically insert or increment. Returns the resulting ORM object.

### src/kratos/db/__init__.py

Re-exports `build_engine`, `SessionFactory`, and `upsert_api_log`.

### src/kratos/validators/schemas.py

Three Pydantic v2 models (`AuditLogInput`, `UserLogInput`, `ApiLogInput`) with `@field_validator` decorators that:
- Reject empty strings (after stripping whitespace).
- Validate IPs using `ipaddress.ip_address()`.
- Normalize whitespace-only identity to `None` in audit logs.

### src/kratos/validators/__init__.py

Re-exports the three Pydantic schemas.

### src/kratos/client.py

The `Kratos` class — the only thing users interact with:
1. `__init__` — builds engine, creates session factory, auto-creates tables.
2. `create_audit_log()` — validate → create ORM object → persist → return.
3. `create_user_log()` — same flow, identity required.
4. `create_api_log()` — validate → upsert → return.

All methods use keyword-only arguments (`*`) to prevent positional mistakes.

### tests/conftest.py

Pytest fixtures:
- `pg_url` (session-scoped) — starts a PostgreSQL Docker container via testcontainers, yields the connection URL, stops the container when all tests are done.
- `logger` (function-scoped) — creates a `Kratos` instance, truncates all tables after each test.

### tests/test_models.py

Verifies that `create_all` produces the correct tables with the correct columns and constraints.

### tests/test_client.py

End-to-end tests through the `Kratos` class: creating each log type, verifying returned fields, testing upsert increments, and ensuring invalid input raises `ValidationError`.

### tests/test_upsert.py

Tests the raw `upsert_api_log()` function: first insert, increment, multiple increments, and separate rows for different keys.

### tests/test_validators.py

Tests every validation rule: valid input, empty strings, whitespace, invalid IPs, IPv6, and whitespace-only identity normalization.

### tests/test_thread_safety.py

Spawns 10-30 threads hitting the same `Kratos` instance simultaneously. Verifies no errors and correct `attempts` counts after concurrent upserts.
