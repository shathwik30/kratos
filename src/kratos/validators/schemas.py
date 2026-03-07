import ipaddress

from pydantic import BaseModel, field_validator


def _validate_ip(v: str) -> str:
    """Validate that the string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(v)
    except ValueError:
        raise ValueError(f"Invalid IP address: {v!r}")
    return v


def _validate_non_empty(v: str, field_name: str) -> str:
    if not v or not v.strip():
        raise ValueError(f"{field_name} must not be empty")
    return v.strip()


class AuditLogInput(BaseModel):
    action: str
    ip: str
    identity: str | None = None

    @field_validator("action")
    @classmethod
    def action_not_empty(cls, v: str) -> str:
        return _validate_non_empty(v, "action")

    @field_validator("ip")
    @classmethod
    def ip_valid(cls, v: str) -> str:
        return _validate_ip(v)

    @field_validator("identity")
    @classmethod
    def identity_strip(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class UserLogInput(BaseModel):
    identity: str
    action: str
    ip: str

    @field_validator("identity")
    @classmethod
    def identity_not_empty(cls, v: str) -> str:
        return _validate_non_empty(v, "identity")

    @field_validator("action")
    @classmethod
    def action_not_empty(cls, v: str) -> str:
        return _validate_non_empty(v, "action")

    @field_validator("ip")
    @classmethod
    def ip_valid(cls, v: str) -> str:
        return _validate_ip(v)


class ApiLogInput(BaseModel):
    session_id: str
    endpoint: str
    action: str
    ip: str

    @field_validator("session_id")
    @classmethod
    def session_id_not_empty(cls, v: str) -> str:
        return _validate_non_empty(v, "session_id")

    @field_validator("endpoint")
    @classmethod
    def endpoint_not_empty(cls, v: str) -> str:
        return _validate_non_empty(v, "endpoint")

    @field_validator("action")
    @classmethod
    def action_not_empty(cls, v: str) -> str:
        return _validate_non_empty(v, "action")

    @field_validator("ip")
    @classmethod
    def ip_valid(cls, v: str) -> str:
        return _validate_ip(v)
