import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models.api_log import ApiLog


def upsert_api_log(
    session: Session,
    *,
    session_id: str,
    endpoint: str,
    action: str,
    ip: str,
) -> ApiLog:
    """Insert a new api_log row or increment attempts on conflict.

    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE for atomicity.
    """
    stmt = insert(ApiLog.__table__).values(
        id=str(uuid.uuid4()),
        session_id=session_id,
        endpoint=endpoint,
        action=action,
        ip=ip,
        attempts=1,
        created_at=func.now(),
        updated_at=func.now(),
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

    row = (
        session.query(ApiLog)
        .filter_by(session_id=session_id, endpoint=endpoint, ip=ip)
        .one()
    )
    return row
