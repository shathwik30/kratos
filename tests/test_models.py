from sqlalchemy import inspect

from kratos.models import AuditLog
from kratos.db import build_engine
from kratos.models import Base


def test_tables_created(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.create_all(engine)
    tables = inspect(engine).get_table_names()
    assert "audit_logs" in tables
    assert "user_logs" in tables
    assert "api_logs" in tables
    assert "api_keys" in tables


def test_audit_log_columns(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("audit_logs")}
    assert cols == {"id", "identity", "action", "ip", "created_at", "updated_at"}


def test_user_log_columns(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("user_logs")}
    assert cols == {"id", "identity", "action", "ip", "created_at", "updated_at"}


def test_api_log_columns(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("api_logs")}
    assert cols == {"id", "session_id", "endpoint", "action", "ip", "attempts", "created_at", "updated_at"}


def test_api_key_columns(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("api_keys")}
    assert cols == {"id", "name", "key", "is_active", "created_at", "updated_at"}


def test_audit_log_identity_nullable():
    log = AuditLog(action="test", ip="127.0.0.1")
    assert log.identity is None


def test_api_log_unique_constraint(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.create_all(engine)
    constraints = inspect(engine).get_unique_constraints("api_logs")
    constraint_columns = [sorted(c["column_names"]) for c in constraints]
    assert sorted(["session_id", "endpoint", "ip"]) in constraint_columns


def test_api_key_unique_constraint(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.create_all(engine)
    indexes = inspect(engine).get_indexes("api_keys")
    unique_cols = [idx["column_names"] for idx in indexes if idx.get("unique")]
    # The key column should have a unique index
    assert any("key" in cols for cols in unique_cols)
