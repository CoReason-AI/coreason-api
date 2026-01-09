from unittest.mock import patch

from coreason_api.config import Settings


class TestSettings:
    def test_settings_load_defaults(self):
        # Ensure no side effects from real vault
        with patch("coreason_api.config.VaultManager"):
            # Make sure it throws so we test fallback logic if implemented
            # or just default values if not.
            # However, our config loading logic is inside class body or methods?
            # get_settings() just returns Settings().

            settings = Settings()
            assert settings.SERVICE_NAME == "coreason-api"
            assert settings.VAULT_ADDR == "http://localhost:8200"

    def test_settings_load_env(self):
        with patch.dict("os.environ", {"SERVICE_NAME": "test-service", "ENV": "prod"}):
            settings = Settings()
            assert settings.SERVICE_NAME == "test-service"
            assert settings.ENV == "prod"
