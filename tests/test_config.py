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

from coreason_api.config import Settings, get_settings


@pytest.fixture  # type: ignore[misc]
def mock_vault_manager() -> Generator[MagicMock, None, None]:
    # Patch VaultAdapter because that's what config.py uses now
    with (
        patch("coreason_api.config.VaultAdapter") as mock,
        patch("coreason_api.config.CoreasonVaultConfig") as _,
    ):
        instance = mock.return_value
        instance.get_secret.return_value = None
        yield instance


@pytest.fixture  # type: ignore[misc]
def clean_env() -> Generator[None, None, None]:
    """Ensure environment is clean for settings tests"""
    old_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(old_env)


def test_vault_settings_source_success(mock_vault_manager: MagicMock, clean_env: None) -> None:
    # Setup Vault to return a specific value for SECRET_KEY
    def get_secret_side_effect(field_name: str, default: str | None = None) -> str | None:
        if field_name == "SECRET_KEY":
            return "vault-secret-key"
        return default

    mock_vault_manager.get_secret.side_effect = get_secret_side_effect

    # We need to ensure VAULT_ADDR is set so CoreasonVaultConfig doesn't explode
    os.environ["VAULT_ADDR"] = "http://localhost:8200"

    # Instantiate settings. This triggers VaultSettingsSource
    settings = Settings()

    assert settings.SECRET_KEY == "vault-secret-key"
    # Verify vault was called
    mock_vault_manager.get_secret.assert_any_call("SECRET_KEY", default=None)


def test_vault_settings_source_failure_fallback(mock_vault_manager: MagicMock, clean_env: None) -> None:
    # Setup Vault to raise an exception
    mock_vault_manager.get_secret.side_effect = Exception("Connection refused")

    os.environ["VAULT_ADDR"] = "http://localhost:8200"

    # Settings should still load, falling back to defaults/env
    settings = Settings()

    # Should use the default value from class definition
    assert settings.SECRET_KEY == "insecure-default-key-do-not-use-in-prod"


def test_vault_settings_source_init_failure(clean_env: None) -> None:
    # If VaultAdapter init fails (e.g. config error), it should also fallback
    with patch("coreason_api.config.VaultAdapter", side_effect=Exception("Init failed")):
        os.environ["VAULT_ADDR"] = "http://localhost:8200"
        settings = Settings()
        assert settings.SECRET_KEY == "insecure-default-key-do-not-use-in-prod"


def test_get_settings_cached() -> None:
    # Ensure lru_cache works
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
