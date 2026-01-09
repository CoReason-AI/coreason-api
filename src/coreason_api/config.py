# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Any, Type, Dict, Tuple
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource
from pydantic.fields import FieldInfo

# Import VaultManager.
# Note: In tests this will be mocked.
# NOTE: PRD specifies `from coreason_vault.main import VaultManager`, but the installed
# package `coreason-vault` does not contain a `main` module. `VaultManager` is exposed
# at the top level.
from coreason_vault import VaultManager
from coreason_api.utils.logger import logger


class VaultSettingsSource(PydanticBaseSettingsSource):
    """
    A custom Pydantic Settings Source that loads secrets from Coreason Vault.
    It attempts to fetch a secret for every field in the Settings model.
    If Vault is unreachable, it logs a warning and returns an empty dict,
    allowing fallback to environment variables.
    """
    def get_field_value(self, field: FieldInfo, field_name: str) -> Tuple[Any, str, bool]:
        # Not used when overriding __call__
        return None, field_name, False  # pragma: no cover

    def __call__(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        try:
            # Attempt to initialize VaultManager.
            # This might fail if network/creds are missing.
            vault = VaultManager()

            # Iterate over all defined settings fields
            for field_name in self.settings_cls.model_fields:
                # Try to fetch from Vault
                # We assume the Vault key matches the Settings field name (e.g. "SECRET_KEY")
                secret_value = vault.get_secret(field_name, default=None)

                # If secret exists, add it to the data dict
                if secret_value is not None:
                    data[field_name] = secret_value

        except Exception as e:
            # PRD Requirement: Fail gracefully if Vault is unreachable in Dev.
            # We log the error but do not raise, allowing other sources (Env) to fill values.
            logger.warning(f"Vault unreachable or error loading secrets: {e}. Falling back to Environment/Defaults.")

        return data


class Settings(BaseSettings):
    # Core Application Settings
    APP_ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "insecure-default-key-do-not-use-in-prod"

    # Infrastructure Settings (Defaults provided for dev/test)
    DATABASE_URL: str = "postgresql://coreason:coreason@localhost:5432/coreason_db"

    # Model Config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """
        Configure the priority of settings sources.
        1. Vault (Highest)
        2. Init arguments
        3. Environment variables
        4. Dotenv file
        5. File secrets
        """
        return (
            VaultSettingsSource(settings_cls),
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached instance of Settings.
    """
    return Settings()
