from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select

from .db import build_engine, SessionFactory, upsert_api_log
from .exceptions import ConfigurationError, ValidationError
from .models import Base, AuditLog, UserLog, ApiLog, ApiKey
from .validators import AuditLogInput, UserLogInput, ApiLogInput


class Kratos:
    """Database-backed logging client.

    Usage::

        logger = Kratos(db_url="postgresql://user:pass@localhost/mydb")
        logger.create_audit_log(action="login", ip="192.168.1.1")
    """

    def __init__(self, *, db_url: str) -> None:
        if not db_url:
            raise ConfigurationError("db_url must not be empty")

        self._engine = build_engine(db_url)
        self._session_factory = SessionFactory(self._engine)

        Base.metadata.create_all(self._engine)

    def create_audit_log(
        self,
        *,
        action: str,
        ip: str,
        identity: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry. Identity is optional."""
        try:
            data = AuditLogInput(action=action, ip=ip, identity=identity)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc

        log = AuditLog(action=data.action, ip=data.ip, identity=data.identity)
        with self._session_factory.session() as session:
            session.add(log)
            session.flush()
            session.refresh(log)
            session.expunge(log)
        return log

    def create_user_log(
        self,
        *,
        identity: str,
        action: str,
        ip: str,
    ) -> UserLog:
        """Create a user log entry. Identity is required."""
        try:
            data = UserLogInput(identity=identity, action=action, ip=ip)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc

        log = UserLog(identity=data.identity, action=data.action, ip=data.ip)
        with self._session_factory.session() as session:
            session.add(log)
            session.flush()
            session.refresh(log)
            session.expunge(log)
        return log

    def create_api_log(
        self,
        *,
        session_id: str,
        endpoint: str,
        action: str,
        ip: str,
    ) -> ApiLog:
        """Create or upsert an API log entry.

        If a row with the same (session_id, endpoint, ip) already exists,
        the attempts counter is incremented instead of creating a duplicate.
        """
        try:
            data = ApiLogInput(session_id=session_id, endpoint=endpoint, action=action, ip=ip)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc

        with self._session_factory.session() as session:
            log = upsert_api_log(
                session,
                session_id=data.session_id,
                endpoint=data.endpoint,
                action=data.action,
                ip=data.ip,
            )
            session.expunge(log)
        return log

    # ── API Key Management ──────────────────────────

    def create_api_key(self, *, name: str) -> ApiKey:
        """Create a new API key for admin authentication.

        Returns the ApiKey object — the raw `key` field is only visible
        at creation time, so callers should store it immediately.
        """
        name = (name or "").strip()
        if not name:
            raise ValidationError("API key name must not be empty")

        api_key = ApiKey(name=name)
        with self._session_factory.session() as session:
            session.add(api_key)
            session.flush()
            session.refresh(api_key)
            session.expunge(api_key)
        return api_key

    def list_api_keys(self) -> list[ApiKey]:
        """List all API keys (active and revoked)."""
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
        with self._session_factory.session() as session:
            rows = session.execute(stmt).scalars().all()
            for r in rows:
                session.expunge(r)
            return list(rows)

    def revoke_api_key(self, *, key_id: str) -> ApiKey:
        """Revoke an API key by its ID."""
        with self._session_factory.session() as session:
            api_key = session.get(ApiKey, key_id)
            if not api_key:
                raise ValidationError(f"API key with id '{key_id}' not found")
            api_key.is_active = False
            session.flush()
            session.refresh(api_key)
            session.expunge(api_key)
        return api_key
