import pytest

from kratos import Kratos, ConfigurationError, ValidationError


def test_empty_db_url_raises():
    with pytest.raises(ConfigurationError):
        Kratos(db_url="")


def test_create_audit_log(logger):
    log = logger.create_audit_log(action="login", ip="192.168.1.1")
    assert log.id is not None
    assert log.action == "login"
    assert log.ip == "192.168.1.1"
    assert log.identity is None
    assert log.created_at is not None


def test_create_audit_log_with_identity(logger):
    log = logger.create_audit_log(action="login", ip="10.0.0.1", identity="user123")
    assert log.identity == "user123"


def test_create_user_log(logger):
    log = logger.create_user_log(identity="user1", action="profile_update", ip="10.0.0.1")
    assert log.id is not None
    assert log.identity == "user1"
    assert log.action == "profile_update"


def test_create_user_log_empty_identity_raises(logger):
    with pytest.raises(ValidationError):
        logger.create_user_log(identity="", action="test", ip="127.0.0.1")


def test_create_user_log_invalid_ip_raises(logger):
    with pytest.raises(ValidationError):
        logger.create_user_log(identity="user1", action="test", ip="bad_ip")


def test_create_api_log_first_call(logger):
    log = logger.create_api_log(session_id="s1", endpoint="/api/users", action="GET", ip="1.2.3.4")
    assert log.attempts == 1
    assert log.session_id == "s1"


def test_create_api_log_upsert(logger):
    logger.create_api_log(session_id="s1", endpoint="/api/users", action="GET", ip="1.2.3.4")
    log = logger.create_api_log(session_id="s1", endpoint="/api/users", action="GET", ip="1.2.3.4")
    assert log.attempts == 2


def test_create_api_log_invalid_ip_raises(logger):
    with pytest.raises(ValidationError):
        logger.create_api_log(session_id="s1", endpoint="/test", action="GET", ip="not_ip")


def test_create_api_log_empty_session_id_raises(logger):
    with pytest.raises(ValidationError):
        logger.create_api_log(session_id="", endpoint="/test", action="GET", ip="127.0.0.1")


def test_create_audit_log_invalid_ip_raises(logger):
    with pytest.raises(ValidationError):
        logger.create_audit_log(action="test", ip="invalid")


def test_multiple_audit_logs_get_unique_ids(logger):
    log1 = logger.create_audit_log(action="a", ip="127.0.0.1")
    log2 = logger.create_audit_log(action="b", ip="127.0.0.1")
    assert log1.id != log2.id


# ── API Key Management ──────────────────────────────────


def test_create_api_key(logger):
    key = logger.create_api_key(name="test-key")
    assert key.id is not None
    assert key.name == "test-key"
    assert key.key.startswith("kra_")
    assert key.is_active is True
    assert key.created_at is not None


def test_create_api_key_empty_name_raises(logger):
    with pytest.raises(ValidationError):
        logger.create_api_key(name="")


def test_create_api_key_whitespace_name_raises(logger):
    with pytest.raises(ValidationError):
        logger.create_api_key(name="   ")


def test_list_api_keys(logger):
    logger.create_api_key(name="key-1")
    logger.create_api_key(name="key-2")
    keys = logger.list_api_keys()
    assert len(keys) == 2
    names = {k.name for k in keys}
    assert names == {"key-1", "key-2"}


def test_list_api_keys_empty(logger):
    keys = logger.list_api_keys()
    assert keys == []


def test_revoke_api_key(logger):
    key = logger.create_api_key(name="to-revoke")
    assert key.is_active is True
    revoked = logger.revoke_api_key(key_id=key.id)
    assert revoked.is_active is False
    assert revoked.id == key.id


def test_revoke_api_key_not_found_raises(logger):
    with pytest.raises(ValidationError, match="not found"):
        logger.revoke_api_key(key_id="nonexistent-id")


def test_api_keys_have_unique_values(logger):
    key1 = logger.create_api_key(name="key-1")
    key2 = logger.create_api_key(name="key-2")
    assert key1.key != key2.key
    assert key1.id != key2.id
