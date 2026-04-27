import asyncio

import pytest
from fastapi import HTTPException

from app.auth import api_key as api_key_module
from app.auth.api_key import extract_api_key, verify_api_key
from app.config import Settings


def test_settings_parse_api_keys(monkeypatch):
    monkeypatch.setenv("MCP_API_KEYS", "alpha, beta, ,gamma")

    settings = Settings()

    assert settings.api_keys == ["alpha", "beta", "gamma"]
    assert settings.api_keys_count == 3
    assert settings.validate_api_key("beta") is True
    assert settings.validate_api_key("missing") is False


def test_settings_allows_any_key_when_unconfigured(monkeypatch):
    monkeypatch.delenv("MCP_API_KEYS", raising=False)

    settings = Settings()

    assert settings.api_keys == []
    assert settings.validate_api_key("anything") is True


def test_extract_api_key_supports_bearer_and_raw_values():
    assert extract_api_key(None) is None
    assert extract_api_key("Bearer token-123") == "token-123"
    assert extract_api_key("raw-token") == "raw-token"


def test_verify_api_key_accepts_dev_mode(monkeypatch):
    monkeypatch.setenv("MCP_DEV_MODE", "true")

    assert asyncio.run(verify_api_key(None)) is True


def test_verify_api_key_rejects_missing_header(monkeypatch):
    monkeypatch.setenv("MCP_DEV_MODE", "false")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(verify_api_key(None))

    assert exc_info.value.status_code == 401


def test_verify_api_key_checks_configured_keys(monkeypatch):
    monkeypatch.setenv("MCP_DEV_MODE", "false")
    monkeypatch.setattr(api_key_module.settings, "api_keys", ["expected"])

    assert asyncio.run(verify_api_key("Bearer expected")) is True

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(verify_api_key("Bearer wrong"))

    assert exc_info.value.status_code == 401
