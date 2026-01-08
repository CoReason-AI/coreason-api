from functools import lru_cache
from typing import Optional

from coreason_vault import CoreasonVaultConfig, VaultManager
from pydantic_settings import BaseSettings, SettingsConfigDict

from coreason_api.utils.logger import logger


class Settings(BaseSettings):  # type: ignore[misc]
    APP_ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Core Secrets
    SECRET_KEY: str = "unsafe-dev-key"

    # Identity
    IDENTITY_DOMAIN: str = "https://auth.coreason.ai"
    IDENTITY_AUDIENCE: str = "coreason-api"
    IDENTITY_CLIENT_ID: Optional[str] = None

    # Budget
    BUDGET_REDIS_URL: str = "redis://localhost:6379/0"
    BUDGET_GLOBAL_LIMIT: float = 1000.0
    BUDGET_PROJECT_LIMIT: float = 100.0
    BUDGET_USER_LIMIT: float = 10.0

    # Veritas
    VERITAS_PUBLIC_KEY: str = ""  # PEM string

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    # Attempt to load secrets from Vault
    try:
        # VaultManager needs config
        vault_config = CoreasonVaultConfig()
        vault = VaultManager(config=vault_config)

        # Helper to override if exists
        updates = {}

        def override(field_name: str, secret_key: str) -> None:
            val = vault.get_secret(secret_key)
            if val:
                updates[field_name] = val

        override("SECRET_KEY", "SECRET_KEY")
        override("IDENTITY_CLIENT_ID", "IDENTITY_CLIENT_ID")
        override("BUDGET_REDIS_URL", "BUDGET_REDIS_URL")
        override("VERITAS_PUBLIC_KEY", "VERITAS_PUBLIC_KEY")

        if updates:
            # Create new settings with updates since it is frozen
            settings = settings.model_copy(update=updates)

    except Exception as e:
        if settings.APP_ENV == "production":
            logger.error(f"Failed to connect to Vault in Production: {e}")
        else:
            logger.warning(f"Vault unreachable in {settings.APP_ENV}, using env/defaults: {e}")

    return settings
