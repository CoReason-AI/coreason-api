import os
import sys
from unittest.mock import patch

# It seems `patch` isn't restoring the original mock state correctly when patching a Mock object in `sys.modules`.
# Let's try to forcefully reset the `VaultManager` mock in `conftest` or `sys.modules`.


def test_settings_vault_integration():
    # Get the global mock
    vault_mock = sys.modules["coreason_vault.main"].VaultManager
    vault_mock.reset_mock()
    # Mock the return value of instantiation
    instance_mock = vault_mock.return_value
    instance_mock.get_secret.side_effect = None
    instance_mock.get_secret.return_value = "super_secret_from_vault"

    from coreason_api import config

    settings = config.Settings()

    assert settings.DB_PASSWORD == "super_secret_from_vault"
    instance_mock.get_secret.assert_any_call("DB_PASSWORD", default=None)


def test_settings_vault_fallback():
    vault_mock = sys.modules["coreason_vault.main"].VaultManager
    vault_mock.reset_mock()
    instance_mock = vault_mock.return_value
    # Resetting the instance mock specifics
    instance_mock.get_secret.reset_mock()
    instance_mock.get_secret.return_value = None  # Clear previous return value
    instance_mock.get_secret.side_effect = Exception("Fail")

    with patch.dict(os.environ, {"DB_PASSWORD": "fallback_from_env"}):
        from coreason_api import config

        settings = config.Settings()

        assert settings.DB_PASSWORD == "fallback_from_env"
