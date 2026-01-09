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
    with patch("coreason_api.config.VaultManager") as mock:
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
