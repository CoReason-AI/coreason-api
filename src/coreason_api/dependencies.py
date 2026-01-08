from functools import lru_cache
from typing import Annotated

from coreason_budget.guard import BudgetGuard
from coreason_identity.manager import IdentityManager
from coreason_mcp.session_manager import SessionManager

# Import external managers
from coreason_vault.main import VaultManager
from coreason_veritas.auditor import Auditor
from fastapi import Depends

from coreason_api.config import Settings, get_settings

# Singleton Providers


@lru_cache
def get_vault_manager() -> VaultManager:
    return VaultManager()


@lru_cache
def get_identity_manager(vault: Annotated[VaultManager, Depends(get_vault_manager)]) -> IdentityManager:
    # VID: identity = IdentityManager(vault_manager=vault_instance)
    return IdentityManager(vault_manager=vault)


@lru_cache
def get_budget_guard(settings: Annotated[Settings, Depends(get_settings)]) -> BudgetGuard:
    # VID: budget = BudgetGuard(db_url=...)
    # We need DB_URL from settings.
    # Note: If DB_URL is None, BudgetGuard might fail.
    # We assume valid config at this point.
    return BudgetGuard(db_url=settings.DB_URL or "")


@lru_cache
def get_auditor(settings: Annotated[Settings, Depends(get_settings)]) -> Auditor:
    # VID: auditor = Auditor(service_name="coreason-api")
    return Auditor(service_name=settings.APP_NAME)


@lru_cache
def get_session_manager() -> SessionManager:
    # VID: mcp = SessionManager()
    return SessionManager()


# Type Aliases for easier use in routes
VaultDep = Annotated[VaultManager, Depends(get_vault_manager)]
IdentityDep = Annotated[IdentityManager, Depends(get_identity_manager)]
BudgetDep = Annotated[BudgetGuard, Depends(get_budget_guard)]
AuditorDep = Annotated[Auditor, Depends(get_auditor)]
SessionDep = Annotated[SessionManager, Depends(get_session_manager)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
