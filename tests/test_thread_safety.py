import threading

from sqlalchemy import text

from kratos import Kratos


def _make_logger(pg_url):
    """Create a Kratos logger and truncate all tables."""
    logger = Kratos(db_url=pg_url)
    with logger._engine.connect() as conn:
        conn.execute(text("TRUNCATE audit_logs, user_logs, api_logs"))
        conn.commit()
    return logger


def test_concurrent_audit_log_writes(pg_url):
    """Multiple threads creating audit logs should not conflict."""
    logger = _make_logger(pg_url)
    results = []
    errors = []
    lock = threading.Lock()

    def worker(i: int):
        try:
            log = logger.create_audit_log(action=f"action_{i}", ip="127.0.0.1")
            with lock:
                results.append(log.id)
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors occurred: {errors}"
    assert len(results) == 20
    assert len(set(results)) == 20


def test_concurrent_api_log_upserts(pg_url):
    """Multiple threads upserting the same key should all succeed and increment attempts."""
    logger = _make_logger(pg_url)
    errors = []
    lock = threading.Lock()

    def worker():
        try:
            logger.create_api_log(
                session_id="shared",
                endpoint="/api",
                action="GET",
                ip="10.0.0.1",
            )
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors occurred: {errors}"

    log = logger.create_api_log(
        session_id="shared", endpoint="/api", action="GET", ip="10.0.0.1",
    )
    assert log.attempts == 11


def test_concurrent_mixed_log_types(pg_url):
    """Concurrent writes to different log types should not conflict."""
    logger = _make_logger(pg_url)
    errors = []
    lock = threading.Lock()

    def audit_worker(i: int):
        try:
            logger.create_audit_log(action=f"audit_{i}", ip="127.0.0.1")
        except Exception as exc:
            with lock:
                errors.append(exc)

    def user_worker(i: int):
        try:
            logger.create_user_log(identity=f"user_{i}", action="update", ip="127.0.0.1")
        except Exception as exc:
            with lock:
                errors.append(exc)

    def api_worker(i: int):
        try:
            logger.create_api_log(
                session_id=f"sess_{i}", endpoint="/api", action="GET", ip="127.0.0.1",
            )
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = []
    for i in range(10):
        threads.append(threading.Thread(target=audit_worker, args=(i,)))
        threads.append(threading.Thread(target=user_worker, args=(i,)))
        threads.append(threading.Thread(target=api_worker, args=(i,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors occurred: {errors}"
