# Kratos — Usage Guide

## 1. Installation

```bash
cd kratos

# Core only (write logs)
pip install -e .

# With admin REST API (write + read logs via HTTP)
pip install -e ".[admin]"
```

---

## 2. Writing Logs

```python
from kratos import Kratos

logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")
```

### Audit Logs

Track system-level events. `identity` is optional — useful for anonymous events like failed logins.

```python
# Without identity
log = logger.create_audit_log(action="login", ip="192.168.1.1")
print(f"id={log.id}  action={log.action}  ip={log.ip}")

# With identity
log = logger.create_audit_log(action="login", ip="192.168.1.1", identity="user123")
print(f"id={log.id}  action={log.action}  identity={log.identity}")

log = logger.create_audit_log(action="logout", ip="10.0.0.5", identity="admin")
print(f"id={log.id}  action={log.action}  identity={log.identity}")
```

### User Logs

Track user-specific events. `identity` is required.

```python
log = logger.create_user_log(identity="user123", action="profile_update", ip="10.0.0.1")
print(f"id={log.id}  identity={log.identity}  action={log.action}")

log = logger.create_user_log(identity="user456", action="password_change", ip="172.16.0.2")
print(f"id={log.id}  identity={log.identity}  action={log.action}")
```

### API Logs

Track API calls. Duplicate calls with the same `(session_id, endpoint, ip)` don't create new rows — they increment the `attempts` counter instead.

```python
# First call — creates a new row
api = logger.create_api_log(session_id="sess_abc", endpoint="/api/users", action="GET", ip="1.2.3.4")
print(f"id={api.id}  endpoint={api.endpoint}  attempts={api.attempts}")  # attempts=1

# Same session + endpoint + ip — upserts (increments attempts)
api = logger.create_api_log(session_id="sess_abc", endpoint="/api/users", action="GET", ip="1.2.3.4")
print(f"id={api.id}  endpoint={api.endpoint}  attempts={api.attempts}")  # attempts=2

# Different session — creates a new row
api = logger.create_api_log(session_id="sess_xyz", endpoint="/api/orders", action="POST", ip="5.6.7.8")
print(f"id={api.id}  endpoint={api.endpoint}  attempts={api.attempts}")  # attempts=1
```

### Handling Validation Errors

```python
from kratos import Kratos, ValidationError

logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")

try:
    logger.create_user_log(identity="", action="test", ip="bad_ip")
except ValidationError as e:
    print(f"Caught: {e}")
```

---

## 3. API Key Management

All admin REST endpoints require authentication via the `x-api-key` header. Use the Kratos client to manage API keys.

### Create your first key

```python
key = logger.create_api_key(name="default-admin")
print(f"Store this key: {key.key}")  # kra_... — only shown once!
```

### List all keys

```python
keys = logger.list_api_keys()
for k in keys:
    print(f"id={k.id}  name={k.name}  active={k.is_active}")
```

### Revoke a key

```python
revoked = logger.revoke_api_key(key_id="a1b2c3d4-...")
print(f"Revoked: {revoked.is_active}")  # False
```

---

## 4. Reading Logs (Admin REST API)

### Start the admin server

```python
import uvicorn
from kratos import Kratos
from kratos.admin import create_admin_app

logger = Kratos(db_url="postgresql://user:pass@localhost:5432/mydb")

# Bootstrap your first API key
key = logger.create_api_key(name="default-admin")
print(f"Your API key: {key.key}")

app = create_admin_app(logger)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

```bash
python main.py
```

### Swagger UI

Open `http://localhost:8000/docs` in your browser to explore and test all endpoints interactively (no auth required for docs).

### Authentication

All `/admin/*` endpoints require the `x-api-key` header:

```bash
KEY="kra_your-key-here"
```

### Endpoints

#### Stats

```bash
curl -H "x-api-key: $KEY" http://localhost:8000/admin/stats
```

```json
{"audit_logs": 3, "user_logs": 2, "api_logs": 2}
```

#### Audit Logs

```bash
# All audit logs
curl -H "x-api-key: $KEY" http://localhost:8000/admin/audit-logs

# Filter by action
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/audit-logs?action=login"

# Filter by identity
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/audit-logs?identity=user123"

# Filter by IP
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/audit-logs?ip=192.168.1.1"

# Filter by time
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/audit-logs?since=2026-01-01T00:00:00Z"

# Pagination
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/audit-logs?limit=10&offset=20"

# Get a single log by ID
curl -H "x-api-key: $KEY" http://localhost:8000/admin/audit-logs/<id>
```

#### User Logs

```bash
# All user logs
curl -H "x-api-key: $KEY" http://localhost:8000/admin/user-logs

# Filter by identity
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/user-logs?identity=user456"

# Filter by action
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/user-logs?action=password_change"

# Get a single log by ID
curl -H "x-api-key: $KEY" http://localhost:8000/admin/user-logs/<id>
```

#### API Logs

```bash
# All API logs
curl -H "x-api-key: $KEY" http://localhost:8000/admin/api-logs

# Filter by endpoint
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/api-logs?endpoint=/api/users"

# Filter by session
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/api-logs?session_id=sess_abc"

# Filter by IP
curl -H "x-api-key: $KEY" "http://localhost:8000/admin/api-logs?ip=1.2.3.4"

# Get a single log by ID
curl -H "x-api-key: $KEY" http://localhost:8000/admin/api-logs/<id>
```

#### API Keys

```bash
# Create a new API key (full key shown only in response)
curl -X POST -H "x-api-key: $KEY" -H "Content-Type: application/json" \
     -d '{"name": "my-service"}' http://localhost:8000/admin/api-keys

# List all API keys (key values masked)
curl -H "x-api-key: $KEY" http://localhost:8000/admin/api-keys

# Revoke an API key
curl -X DELETE -H "x-api-key: $KEY" http://localhost:8000/admin/api-keys/<key-id>
```

---

## 5. Full Example (main.py)

This is a complete working example that creates sample logs, bootstraps an API key, and starts the admin server:

```python
import uvicorn

from kratos import Kratos
from kratos.admin import create_admin_app

DB_URL = "postgresql://user:pass@localhost:5432/mydb"

logger = Kratos(db_url=DB_URL)

# ──────────────────────────────────────────────
# STEP 1: Create logs using Kratos
# ──────────────────────────────────────────────

# Audit logs — track system-level events (identity is optional)
log = logger.create_audit_log(action="login", ip="192.168.1.1")
print(f"[audit]  id={log.id}  action={log.action}  ip={log.ip}")

log = logger.create_audit_log(action="login", ip="192.168.1.1", identity="user123")
print(f"[audit]  id={log.id}  action={log.action}  identity={log.identity}")

log = logger.create_audit_log(action="logout", ip="10.0.0.5", identity="admin")
print(f"[audit]  id={log.id}  action={log.action}  identity={log.identity}")

# User logs — track user-specific events (identity is required)
log = logger.create_user_log(identity="user123", action="profile_update", ip="10.0.0.1")
print(f"[user]   id={log.id}  identity={log.identity}  action={log.action}")

log = logger.create_user_log(identity="user456", action="password_change", ip="172.16.0.2")
print(f"[user]   id={log.id}  identity={log.identity}  action={log.action}")

# API logs — track API calls with upsert (duplicate calls increment attempts)
api = logger.create_api_log(session_id="sess_abc", endpoint="/api/users", action="GET", ip="1.2.3.4")
print(f"[api]    id={api.id}  endpoint={api.endpoint}  attempts={api.attempts}")

api = logger.create_api_log(session_id="sess_abc", endpoint="/api/users", action="GET", ip="1.2.3.4")
print(f"[api]    id={api.id}  endpoint={api.endpoint}  attempts={api.attempts}  (upserted)")

api = logger.create_api_log(session_id="sess_xyz", endpoint="/api/orders", action="POST", ip="5.6.7.8")
print(f"[api]    id={api.id}  endpoint={api.endpoint}  attempts={api.attempts}")

print("\nSample data created.\n")

# ──────────────────────────────────────────────
# STEP 2: Bootstrap an API key for admin access
# ──────────────────────────────────────────────

api_key = logger.create_api_key(name="default-admin")
print(f"API Key created: {api_key.key}")
print("Use this key in the x-api-key header to access admin endpoints.\n")

# ──────────────────────────────────────────────
# STEP 3: Start the admin API to view the data
# ──────────────────────────────────────────────
#
# All endpoints now require the x-api-key header:
#
#   curl -H "x-api-key: <your-key>" http://localhost:8000/admin/stats
#   curl -H "x-api-key: <your-key>" http://localhost:8000/admin/audit-logs
#   curl -H "x-api-key: <your-key>" http://localhost:8000/admin/user-logs
#   curl -H "x-api-key: <your-key>" http://localhost:8000/admin/api-logs
#
# API Key Management:
#   curl -X POST -H "x-api-key: <your-key>" -H "Content-Type: application/json" \
#        -d '{"name": "my-service"}' http://localhost:8000/admin/api-keys
#   curl -H "x-api-key: <your-key>" http://localhost:8000/admin/api-keys
#   curl -X DELETE -H "x-api-key: <your-key>" http://localhost:8000/admin/api-keys/<key-id>
#
# Swagger UI (no auth required): http://localhost:8000/docs
#

app = create_admin_app(logger)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Run it

```bash
cd happidost/kratos
pip install -e ".[admin]"
cd ..
python main.py
```

### Expected output

```
[audit]  id=a1b2c3d4-...  action=login  ip=192.168.1.1
[audit]  id=e5f6g7h8-...  action=login  identity=user123
[audit]  id=i9j0k1l2-...  action=logout  identity=admin
[user]   id=m3n4o5p6-...  identity=user123  action=profile_update
[user]   id=q7r8s9t0-...  identity=user456  action=password_change
[api]    id=u1v2w3x4-...  endpoint=/api/users  attempts=1
[api]    id=u1v2w3x4-...  endpoint=/api/users  attempts=2  (upserted)
[api]    id=y5z6a7b8-...  endpoint=/api/orders  attempts=1

Sample data created.

API Key created: kra_x9VI1psRf3U1I5qxCRkfhmaMTznlGbU_T_fsinS4LhA
Use this key in the x-api-key header to access admin endpoints.

INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Then use the printed key to access the admin API:

```bash
curl -H "x-api-key: kra_x9VI1psRf3U1I5qxCRkfhm..." http://localhost:8000/admin/stats
```

Or visit `http://localhost:8000/docs` to browse the Swagger UI.
