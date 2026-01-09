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
from typing import Any, Generator
from unittest.mock import patch

import pytest

from coreason_api.config import Settings, get_settings


# Clear cache before tests
@pytest.fixture(autouse=True)  # type: ignore[misc]
def clear_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield


def test_settings_load_from_vault() -> None:
    """Test that settings are loaded from Vault when available."""
    with patch("coreason_api.config.VaultManager") as MockVault:
        mock_instance = MockVault.return_value

        # Define mock behavior for get_secret
        def get_secret_side_effect(key: str, default: Any = None) -> Any:
            secrets = {
                "APP_ENV": "production",
                "SECRET_KEY": "vault-super-secret",
                "DATABASE_URL": "postgresql://vault:5432/db",
            }
            return secrets.get(key, default)

        mock_instance.get_secret.side_effect = get_secret_side_effect

        # Instantiate settings
        settings = Settings()

        assert settings.APP_ENV == "production"
        assert settings.SECRET_KEY == "vault-super-secret"
        assert settings.DATABASE_URL == "postgresql://vault:5432/db"


def test_settings_fallback_to_env_when_vault_fails() -> None:
    """Test that settings fall back to environment variables when Vault is unreachable."""
    with patch("coreason_api.config.VaultManager") as MockVault:
        # Simulate Vault connection failure
        MockVault.side_effect = Exception("Connection refused to Vault")

        # Set environment variables
        env_vars = {"APP_ENV": "staging", "SECRET_KEY": "env-secret-key"}

        with patch.dict(os.environ, env_vars):
            settings = Settings()

            assert settings.APP_ENV == "staging"
            assert settings.SECRET_KEY == "env-secret-key"


def test_settings_defaults_when_vault_empty() -> None:
    """Test that defaults are used when Vault returns no secrets and env vars are unset."""
    with patch("coreason_api.config.VaultManager") as MockVault:
        mock_instance = MockVault.return_value
        mock_instance.get_secret.return_value = None

        # Ensure strict environment with no relevant vars
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.APP_ENV == "development"
            assert settings.DEBUG is False
            assert settings.SECRET_KEY == "insecure-default-key-do-not-use-in-prod"


def test_get_settings_singleton() -> None:
    """Test that get_settings returns a cached instance."""
    with patch("coreason_api.config.VaultManager") as MockVault:
        # Configure mock to return None (defaults) so Pydantic doesn't explode
        mock_instance = MockVault.return_value
        mock_instance.get_secret.return_value = None

        with patch.dict(os.environ, {}, clear=True):
            s1 = get_settings()
            s2 = get_settings()
            assert s1 is s2
