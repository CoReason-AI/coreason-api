from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from coreason_api.adapters import (
    Auditor,
    BudgetGuard,
    CoreasonIdentityConfig,
    Gatekeeper,
    IdentityManager,
    SessionManager,
    VaultManager,
)
from coreason_api.config import Settings, get_settings

# Providers
# We use lru_cache to create singletons


@lru_cache()
def get_vault(settings: Settings = Depends(get_settings)) -> VaultManager:
    # VaultAdapter initializes itself from Env/Config internally in its __init__
    # But if we want to pass settings explicitly, we might need to modify adapter.
    # Current adapter uses os.getenv.
    return VaultManager()


@lru_cache()
def get_identity(settings: Settings = Depends(get_settings)) -> IdentityManager:
    # IdentityManager needs config
    config = CoreasonIdentityConfig(
        domain=settings.AUTH0_DOMAIN, audience=settings.AUTH0_AUDIENCE, client_id=settings.AUTH0_CLIENT_ID
    )
    return IdentityManager(config=config)


@lru_cache()
def get_budget(settings: Settings = Depends(get_settings)) -> BudgetGuard:
    # BudgetGuard needs db_url (redis_url)
    return BudgetGuard(db_url=settings.REDIS_URL)


@lru_cache()
def get_auditor(settings: Settings = Depends(get_settings)) -> Auditor:
    return Auditor(service_name=settings.SERVICE_NAME)


@lru_cache()
def get_gatekeeper(settings: Settings = Depends(get_settings)) -> Gatekeeper:
    # GatekeeperAdapter reads from Env for key.
    # We could modify it to take key in init, but adapter encapsulates it for now.
    return Gatekeeper()


@lru_cache()
def get_mcp(settings: Settings = Depends(get_settings)) -> SessionManager:
    return SessionManager()


# Type Aliases for dependency injection in routes
VaultDep = Annotated[VaultManager, Depends(get_vault)]
IdentityDep = Annotated[IdentityManager, Depends(get_identity)]
BudgetDep = Annotated[BudgetGuard, Depends(get_budget)]
AuditorDep = Annotated[Auditor, Depends(get_auditor)]
GatekeeperDep = Annotated[Gatekeeper, Depends(get_gatekeeper)]
MCPDep = Annotated[SessionManager, Depends(get_mcp)]
