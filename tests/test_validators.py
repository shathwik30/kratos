import pytest
from pydantic import ValidationError as PydanticValidationError

from kratos.validators.schemas import AuditLogInput, UserLogInput, ApiLogInput


class TestAuditLogInput:
    def test_valid_without_identity(self):
        data = AuditLogInput(action="login", ip="192.168.1.1")
        assert data.action == "login"
        assert data.ip == "192.168.1.1"
        assert data.identity is None

    def test_valid_with_identity(self):
        data = AuditLogInput(action="login", ip="10.0.0.1", identity="user123")
        assert data.identity == "user123"

    def test_ipv6_valid(self):
        data = AuditLogInput(action="login", ip="::1")
        assert data.ip == "::1"

    def test_invalid_ip(self):
        with pytest.raises(PydanticValidationError):
            AuditLogInput(action="login", ip="not_an_ip")

    def test_empty_action(self):
        with pytest.raises(PydanticValidationError):
            AuditLogInput(action="", ip="127.0.0.1")

    def test_whitespace_identity_becomes_none(self):
        data = AuditLogInput(action="test", ip="127.0.0.1", identity="  ")
        assert data.identity is None


class TestUserLogInput:
    def test_valid(self):
        data = UserLogInput(identity="user1", action="update", ip="10.0.0.1")
        assert data.identity == "user1"

    def test_empty_identity(self):
        with pytest.raises(PydanticValidationError):
            UserLogInput(identity="", action="update", ip="10.0.0.1")

    def test_whitespace_identity(self):
        with pytest.raises(PydanticValidationError):
            UserLogInput(identity="  ", action="update", ip="10.0.0.1")

    def test_invalid_ip(self):
        with pytest.raises(PydanticValidationError):
            UserLogInput(identity="user1", action="update", ip="bad")


class TestApiLogInput:
    def test_valid(self):
        data = ApiLogInput(session_id="s1", endpoint="/api", action="GET", ip="1.2.3.4")
        assert data.session_id == "s1"
        assert data.endpoint == "/api"

    def test_empty_session_id(self):
        with pytest.raises(PydanticValidationError):
            ApiLogInput(session_id="", endpoint="/api", action="GET", ip="1.2.3.4")

    def test_empty_endpoint(self):
        with pytest.raises(PydanticValidationError):
            ApiLogInput(session_id="s1", endpoint="", action="GET", ip="1.2.3.4")

    def test_empty_action(self):
        with pytest.raises(PydanticValidationError):
            ApiLogInput(session_id="s1", endpoint="/api", action="", ip="1.2.3.4")

    def test_invalid_ip(self):
        with pytest.raises(PydanticValidationError):
            ApiLogInput(session_id="s1", endpoint="/api", action="GET", ip="xyz")
