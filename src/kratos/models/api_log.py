import uuid

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ApiLog(TimestampMixin, Base):
    __tablename__ = "api_logs"
    __table_args__ = (
        UniqueConstraint("session_id", "endpoint", "ip", name="uq_api_log_session_endpoint_ip"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
