from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    identity: str | None
    action: str
    ip: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserLogOut(BaseModel):
    id: str
    identity: str
    action: str
    ip: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiLogOut(BaseModel):
    id: str
    session_id: str
    endpoint: str
    action: str
    ip: str
    attempts: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StatsOut(BaseModel):
    audit_logs: int
    user_logs: int
    api_logs: int


class ApiKeyOut(BaseModel):
    id: str
    name: str
    key: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyListOut(BaseModel):
    """List response — hides the raw key value for security."""
    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ApiKeyCreateIn(BaseModel):
    name: str
