# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from functools import lru_cache
from typing import Annotated

from coreason_budget.guard import BudgetGuard

# Identity: PRD says `from coreason_identity.manager import IdentityManager`.
# Installed package requires `config` arg, not `vault`.
from coreason_identity.config import CoreasonIdentityConfig
from coreason_identity.manager import IdentityManager

# Manifest: PRD says `ManifestValidator`, package has `SchemaValidator`.
from coreason_manifest.validator import SchemaValidator as ManifestValidator
from coreason_mcp.session_manager import SessionManager

# External Dependencies with adaptation to installed packages
from coreason_vault import VaultManager

# Veritas: PRD says `Auditor`, package has `IERLogger` implementing `log_event`.
from coreason_veritas.auditor import IERLogger as Auditor

# Veritas: PRD says `Gatekeeper`, package has `SignatureValidator`.
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi import Depends

from coreason_api.config import Settings, get_settings


@lru_cache
def get_vault_manager() -> VaultManager:
    """
    Returns a singleton instance of VaultManager.
    """
    return VaultManager()


@lru_cache
def get_identity_manager(settings: Annotated[Settings, Depends(get_settings)]) -> IdentityManager:
    """
    Returns a singleton instance of IdentityManager.
    Uses Settings to construct CoreasonIdentityConfig.
    """
    config = CoreasonIdentityConfig(
        domain=settings.COREASON_AUTH_DOMAIN,
        audience=settings.COREASON_AUTH_AUDIENCE,
        client_id=settings.COREASON_AUTH_CLIENT_ID,
    )
    return IdentityManager(config=config)


@lru_cache
def get_budget_guard(settings: Annotated[Settings, Depends(get_settings)]) -> BudgetGuard:
    """
    Returns a singleton instance of BudgetGuard.
    """
    return BudgetGuard(db_url=settings.DATABASE_URL)


@lru_cache
def get_auditor() -> Auditor:
    """
    Returns a singleton instance of Auditor (implemented by IERLogger).
    """
    return Auditor(service_name="coreason-api")


@lru_cache
def get_gatekeeper(settings: Annotated[Settings, Depends(get_settings)]) -> Gatekeeper:
    """
    Returns a singleton instance of Gatekeeper (implemented by SignatureValidator).
    Requires SRB Public Key from settings.
    """
    # Note: SignatureValidator may attempt to validate the key on init.
    # We must ensure settings.SRB_PUBLIC_KEY is a valid PEM or handle the error if it's dummy.
    # For now, we assume the dummy value in dev config is acceptable or we should mock it in tests.
    return Gatekeeper(public_key_store=settings.SRB_PUBLIC_KEY)


@lru_cache
def get_session_manager() -> SessionManager:
    """
    Returns a singleton instance of SessionManager.
    """
    return SessionManager()


@lru_cache
def get_manifest_validator() -> ManifestValidator:
    """
    Returns a singleton instance of ManifestValidator (implemented by SchemaValidator).
    """
    return ManifestValidator()
