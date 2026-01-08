from functools import lru_cache
from typing import Any, Optional

from coreason_vault.main import VaultManager
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from coreason_api.utils.logger import logger


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
        The PRD says: "Load secrets using VaultManager. Fail gracefully if Vault is unreachable in Dev
        (fallback to Env vars)." This implies Vault is primary source.
        """
        try:
            vault = VaultManager()

            # List of keys we want to fetch from Vault
            keys_to_fetch = ["DB_PASSWORD", "OPENAI_API_KEY", "DB_URL"]

            for key in keys_to_fetch:
                try:
                    # Pass default=None so we know if it's missing in Vault
                    secret = vault.get_secret(key, default=None)
                    if secret is not None:
                        setattr(self, key, secret)
                except Exception as e:
                    # Log warning but continue
                    logger.warning(f"Failed to fetch {key} from Vault: {e}")

        except Exception as e:
            # If VaultManager init fails
            logger.warning(f"VaultManager unreachable: {e}. using environment variables.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
