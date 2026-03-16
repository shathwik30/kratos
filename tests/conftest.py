import pytest
from testcontainers.postgres import PostgresContainer

from kratos import Kratos


@pytest.fixture(scope="session")
def pg_url():
    """Spin up a PostgreSQL container once for the entire test session."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url()


@pytest.fixture()
def logger(pg_url):
    """Provide a Kratos instance backed by the test PostgreSQL database."""
    k = Kratos(db_url=pg_url)
    yield k
    # Clean tables between tests so they don't leak state
    from sqlalchemy import text
    with k._engine.connect() as conn:
        conn.execute(text("TRUNCATE audit_logs, user_logs, api_logs, api_keys"))
        conn.commit()
