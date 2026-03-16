import uuid
import secrets

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


def _generate_api_key() -> str:
    """Generate a secure random API key with a 'kra_' prefix."""
    return f"kra_{secrets.token_urlsafe(32)}"


class ApiKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True, default=_generate_api_key
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
