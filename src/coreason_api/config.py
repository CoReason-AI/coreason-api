from typing import Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from coreason_vault.main import VaultManager
from coreason_api.utils.logger import logger
import os

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "coreason-api"
    ENV: str = "development"

    # Secrets (These will be populated from Vault or Env)
    DB_PASSWORD: Optional[str] = Field(None, alias="DB_PASSWORD")
    DB_URL: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Internal usage
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def model_post_init(self, __context: Any) -> None:
        """
        After initialization, try to fetch missing secrets from Vault.
        Overrides env vars if Vault has them?
        The PRD says: "Load secrets using VaultManager. Fail gracefully if Vault is unreachable in Dev (fallback to Env vars)."
        This implies Vault is primary source.
        """
        try:
            vault = VaultManager()

            # List of keys we want to fetch from Vault
            keys_to_fetch = ["DB_PASSWORD", "OPENAI_API_KEY", "DB_URL"]

            for key in keys_to_fetch:
                # We try to get from vault.
                # If the field is already set (e.g. via env var), do we overwrite?
                # "fallback to Env vars" implies Vault is preferred.

                try:
                    # Pass default=None so we know if it's missing in Vault
                    secret = vault.get_secret(key, default=None)
                    if secret is not None:
                        setattr(self, key, secret)
                except Exception as e:
                    # Log warning but continue
                    logger.warning(f"Failed to fetch {key} from Vault: {e}")
                    # If it fails, we keep the value from env (if any)

        except Exception as e:
            # If VaultManager init fails
            logger.warning(f"VaultManager unreachable: {e}. using environment variables.")

from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()
