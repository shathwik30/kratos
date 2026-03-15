from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AuditLog, UserLog, ApiLog
from .schemas import AuditLogOut, UserLogOut, ApiLogOut, StatsOut

router = APIRouter(prefix="/admin", tags=["admin"])

# Will be set by create_admin_app
_session_factory = None


def _get_session() -> Session:
    return _session_factory.session()


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    action: str | None = Query(None),
    ip: str | None = Query(None),
    identity: str | None = Query(None),
    since: datetime | None = Query(None, description="Filter logs created after this timestamp"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if ip:
        stmt = stmt.where(AuditLog.ip == ip)
    if identity:
        stmt = stmt.where(AuditLog.identity == identity)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)

    with _get_session() as session:
        rows = session.execute(stmt).scalars().all()
        return [AuditLogOut.model_validate(r) for r in rows]


@router.get("/audit-logs/{log_id}", response_model=AuditLogOut)
def get_audit_log(log_id: str):
    with _get_session() as session:
        row = session.get(AuditLog, log_id)
        if row:
            return AuditLogOut.model_validate(row)
    raise HTTPException(status_code=404, detail="Audit log not found")


@router.get("/user-logs", response_model=list[UserLogOut])
def list_user_logs(
    action: str | None = Query(None),
    ip: str | None = Query(None),
    identity: str | None = Query(None),
    since: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    stmt = select(UserLog)
    if action:
        stmt = stmt.where(UserLog.action == action)
    if ip:
        stmt = stmt.where(UserLog.ip == ip)
    if identity:
        stmt = stmt.where(UserLog.identity == identity)
    if since:
        stmt = stmt.where(UserLog.created_at >= since)
    stmt = stmt.order_by(UserLog.created_at.desc()).offset(offset).limit(limit)

    with _get_session() as session:
        rows = session.execute(stmt).scalars().all()
        return [UserLogOut.model_validate(r) for r in rows]


@router.get("/user-logs/{log_id}", response_model=UserLogOut)
def get_user_log(log_id: str):
    with _get_session() as session:
        row = session.get(UserLog, log_id)
        if row:
            return UserLogOut.model_validate(row)
    raise HTTPException(status_code=404, detail="User log not found")


@router.get("/api-logs", response_model=list[ApiLogOut])
def list_api_logs(
    session_id: str | None = Query(None),
    endpoint: str | None = Query(None),
    ip: str | None = Query(None),
    action: str | None = Query(None),
    since: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    stmt = select(ApiLog)
    if session_id:
        stmt = stmt.where(ApiLog.session_id == session_id)
    if endpoint:
        stmt = stmt.where(ApiLog.endpoint == endpoint)
    if ip:
        stmt = stmt.where(ApiLog.ip == ip)
    if action:
        stmt = stmt.where(ApiLog.action == action)
    if since:
        stmt = stmt.where(ApiLog.created_at >= since)
    stmt = stmt.order_by(ApiLog.created_at.desc()).offset(offset).limit(limit)

    with _get_session() as session:
        rows = session.execute(stmt).scalars().all()
        return [ApiLogOut.model_validate(r) for r in rows]


@router.get("/api-logs/{log_id}", response_model=ApiLogOut)
def get_api_log(log_id: str):
    with _get_session() as session:
        row = session.get(ApiLog, log_id)
        if row:
            return ApiLogOut.model_validate(row)
    raise HTTPException(status_code=404, detail="API log not found")


@router.get("/stats", response_model=StatsOut)
def get_stats():
    with _get_session() as session:
        audit_count = session.execute(select(func.count(AuditLog.id))).scalar()
        user_count = session.execute(select(func.count(UserLog.id))).scalar()
        api_count = session.execute(select(func.count(ApiLog.id))).scalar()
        return StatsOut(
            audit_logs=audit_count,
            user_logs=user_count,
            api_logs=api_count,
        )
