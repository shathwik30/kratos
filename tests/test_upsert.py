from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from kratos.db import build_engine
from kratos.db.upsert import upsert_api_log
from kratos.models import Base


def _setup(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    # Clean the table before each test
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE api_logs"))
        conn.commit()
    return engine, factory


def test_first_insert_creates_row(pg_url):
    engine, factory = _setup(pg_url)
    with factory() as session:
        log = upsert_api_log(
            session,
            session_id="s1", endpoint="/api", action="GET", ip="1.2.3.4",
        )
        session.commit()
        session.refresh(log)
        assert log.attempts == 1
        assert log.session_id == "s1"


def test_second_call_increments_attempts(pg_url):
    engine, factory = _setup(pg_url)
    with factory() as session:
        upsert_api_log(
            session,
            session_id="s1", endpoint="/api", action="GET", ip="1.2.3.4",
        )
        session.commit()

    with factory() as session:
        log = upsert_api_log(
            session,
            session_id="s1", endpoint="/api", action="GET", ip="1.2.3.4",
        )
        session.commit()
        session.refresh(log)
        assert log.attempts == 2


def test_third_call_increments_to_three(pg_url):
    engine, factory = _setup(pg_url)
    attempts = None
    for _ in range(3):
        with factory() as session:
            log = upsert_api_log(
                session,
                session_id="s1", endpoint="/test", action="POST", ip="10.0.0.1",
            )
            session.commit()
            session.refresh(log)
            attempts = log.attempts
    assert attempts == 3


def test_different_keys_create_separate_rows(pg_url):
    engine, factory = _setup(pg_url)
    with factory() as session:
        log1 = upsert_api_log(
            session,
            session_id="s1", endpoint="/a", action="GET", ip="1.1.1.1",
        )
        session.commit()
        session.refresh(log1)
        log1_attempts = log1.attempts
        log1_id = log1.id

    with factory() as session:
        log2 = upsert_api_log(
            session,
            session_id="s2", endpoint="/a", action="GET", ip="1.1.1.1",
        )
        session.commit()
        session.refresh(log2)
        log2_attempts = log2.attempts
        log2_id = log2.id

    assert log1_attempts == 1
    assert log2_attempts == 1
    assert log1_id != log2_id
