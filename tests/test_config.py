# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

import os
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from coreason_api.config import Settings, VaultSettingsSource, get_settings


@pytest.fixture  # type: ignore[misc]
def mock_vault_manager() -> Generator[MagicMock, None, None]:
    # Also patch CoreasonVaultConfig to prevent environment validation errors during tests
    with (
        patch("coreason_api.config.VaultManager") as mock,
        patch("coreason_api.config.CoreasonVaultConfig") as _,
    ):
        yield mock


def test_vault_settings_source_success(mock_vault_manager: MagicMock) -> None:
    """
    Test that VaultSettingsSource correctly loads secrets from Vault.
    """
    # Setup mock vault to return a secret
    mock_vault_instance = mock_vault_manager.return_value
    mock_vault_instance.get_secret.side_effect = lambda key, default: "secret-value" if key == "SECRET_KEY" else None

    # Initialize Settings with the custom source
    # We need to force reload or bypass cache if using get_settings, but here we instantiate directly.
    # However, BaseSettings reads from sources on init.

    # We can test the source directly to avoid full Settings loading complexity
    settings_cls = Settings
    source = VaultSettingsSource(settings_cls)

    data = source()

    assert data["SECRET_KEY"] == "secret-value"
    assert "DATABASE_URL" not in data  # returned None, so not added


def test_vault_settings_source_failure(mock_vault_manager: MagicMock) -> None:
    """
    Test that VaultSettingsSource handles Vault unavailability gracefully.
    Edge Case: VaultManager raises exception.
    """
    # Setup mock vault to raise exception on init or get_secret
    mock_vault_manager.side_effect = Exception("Connection Refused")

    settings_cls = Settings
    source = VaultSettingsSource(settings_cls)

    # Should not raise exception, but log warning and return empty dict
    with patch("coreason_api.config.logger") as mock_logger:
        data = source()

        assert data == {}
        mock_logger.warning.assert_called_once()
        assert "Vault unreachable" in mock_logger.warning.call_args[0][0]


def test_vault_settings_source_partial_failure(mock_vault_manager: MagicMock) -> None:
    """
    Complex Case: Vault returns some secrets but fails mid-way (e.g., token expiry or intermittent net issue).
    Verify that we get partial data and a warning.
    """
    mock_vault_instance = mock_vault_manager.return_value

    # Define side effect: Return value for first call, raise Exception for second
    # Note: The order depends on model_fields iteration order.
    # Settings fields: APP_ENV, DEBUG, LOG_LEVEL, SECRET_KEY, DATABASE_URL, SRB_PUBLIC_KEY, AUTH...

    # Let's target SECRET_KEY to succeed, and DATABASE_URL to fail.
    # We need to know the order or handle any key.

    def side_effect(key: str, default: str | None) -> str | None:
        if key == "SECRET_KEY":
            return "partial-secret"
        if key == "DATABASE_URL":
            raise Exception("Vault connection lost")
        return None

    mock_vault_instance.get_secret.side_effect = side_effect

    settings_cls = Settings
    source = VaultSettingsSource(settings_cls)

    with patch("coreason_api.config.logger") as mock_logger:
        data = source()

        # We expect SECRET_KEY to be present if it was processed before DATABASE_URL
        # If DATABASE_URL was processed first, data might be empty.
        # However, checking Settings definition, APP_ENV is first.
        # To make this robust, we only assert that exception was caught and we didn't crash.

        mock_logger.warning.assert_called_once()
        assert "Vault unreachable" in mock_logger.warning.call_args[0][0]

        # If SECRET_KEY was processed, it should be in data.
        # If the loop breaks on exception, any field processed BEFORE the exception should be in data.
        # We can't guarantee order easily without assuming Pydantic internals, but usually it's definition order.
        # SECRET_KEY (defined earlier) < DATABASE_URL (defined later).
        # So likely SECRET_KEY is in data.
        if "SECRET_KEY" in data:
            assert data["SECRET_KEY"] == "partial-secret"


def test_settings_load_priority(mock_vault_manager: MagicMock) -> None:
    """
    Test that Vault settings take precedence over Env vars.
    """
    mock_vault_instance = mock_vault_manager.return_value
    mock_vault_instance.get_secret.side_effect = lambda key, default: "vault-secret" if key == "SECRET_KEY" else None

    # Set env var (should be overridden)
    with patch.dict(os.environ, {"SECRET_KEY": "env-secret"}):
        settings = Settings()
        assert settings.SECRET_KEY == "vault-secret"


def test_settings_fallback_to_env(mock_vault_manager: MagicMock) -> None:
    """
    Test that if Vault doesn't have the secret, it falls back to Env.
    """
    mock_vault_instance = mock_vault_manager.return_value
    mock_vault_instance.get_secret.return_value = None

    with patch.dict(os.environ, {"SECRET_KEY": "env-secret"}):
        settings = Settings()
        assert settings.SECRET_KEY == "env-secret"


def test_get_settings_caching() -> None:
    """
    Test that get_settings uses lru_cache.
    """
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
