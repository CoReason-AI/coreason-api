import os
from unittest.mock import patch

import pytest

from coreason_api.config import get_settings


@pytest.fixture
def mock_vault():
    with patch("coreason_api.config.VaultManager") as MockVault:
        yield MockVault


@pytest.fixture
def mock_vault_config():
    with patch("coreason_api.config.CoreasonVaultConfig") as MockConfig:
        yield MockConfig


@pytest.fixture
def mock_logger():
    with patch("coreason_api.config.logger") as MockLogger:
        yield MockLogger


def test_settings_defaults(mock_vault, mock_vault_config):
    # Clear cache
    get_settings.cache_clear()

    # Simulate Vault failure
    mock_vault.side_effect = Exception("Vault down")

    settings = get_settings()
    assert settings.APP_ENV == "development"
    assert settings.SECRET_KEY == "unsafe-dev-key"
    assert settings.DEBUG is False


def test_settings_from_vault(mock_vault, mock_vault_config):
    get_settings.cache_clear()

    mock_instance = mock_vault.return_value

    # Mock return values for different keys
    def side_effect(key, default=None):
        vals = {
            "SECRET_KEY": "vault-secret",
            "IDENTITY_CLIENT_ID": "vault-client-id",
            "BUDGET_REDIS_URL": "redis://vault:6379",
            "VERITAS_PUBLIC_KEY": "vault-pub-key",
        }
        return vals.get(key)

    mock_instance.get_secret.side_effect = side_effect

    settings = get_settings()
    # Check Vault was inited with config
    mock_vault.assert_called_with(config=mock_vault_config.return_value)

    assert settings.SECRET_KEY == "vault-secret"
    assert settings.IDENTITY_CLIENT_ID == "vault-client-id"
    assert settings.BUDGET_REDIS_URL == "redis://vault:6379"
    assert settings.VERITAS_PUBLIC_KEY == "vault-pub-key"


def test_vault_failure_handling_dev(mock_vault, mock_logger, mock_vault_config):
    get_settings.cache_clear()

    mock_vault.side_effect = Exception("Connection refused")

    settings = get_settings()
    # Should not raise
    assert settings.SECRET_KEY == "unsafe-dev-key"
    # Should log warning
    mock_logger.warning.assert_called()


def test_vault_failure_handling_prod(mock_vault, mock_logger, mock_vault_config):
    get_settings.cache_clear()

    # Mock environment variable
    with patch.dict(os.environ, {"APP_ENV": "production"}):
        mock_vault.side_effect = Exception("Connection refused")
        settings = get_settings()

        # Should log error
        mock_logger.error.assert_called()
        # Verify app_env is production
        assert settings.APP_ENV == "production"
