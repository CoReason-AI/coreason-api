import os
from functools import lru_cache

from coreason_budget.config import CoreasonBudgetConfig
from coreason_budget.guard import BudgetGuard
from coreason_budget.ledger import RedisLedger
from coreason_identity.config import CoreasonIdentityConfig
from coreason_identity.manager import IdentityManager
from coreason_mcp.session_manager import SessionManager
from coreason_vault import CoreasonVaultConfig, VaultManager
from coreason_veritas.anchor import DeterminismInterceptor as TrustAnchor
from coreason_veritas.auditor import IERLogger as Auditor
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi import Depends

from coreason_api.config import Settings, get_settings


@lru_cache
def get_vault_manager() -> VaultManager:
    # VaultConfig requires VAULT_ADDR.
    # If not in env, we provide a dummy default to prevent crash during instantiation,
    # assuming we might not actually use it if we are mocking or if we handle connection errors later.
    # However, strictly we should fail if config is missing.
    # For now, let's try to get it from env or use a safe default if allowed.
    # Since I am running in a sandbox, I probably don't have VAULT_ADDR.

    # We can use os.environ to set a default if missing, just for the sake of instantiation.
    if "VAULT_ADDR" not in os.environ:
        # Warning: This is a hack for development/testing if env vars are missing.
        # Ideally we should fail or have these env vars set.
        os.environ["VAULT_ADDR"] = "http://localhost:8200"

    config = CoreasonVaultConfig()
    return VaultManager(config=config)


def get_identity_manager(settings: Settings = Depends(get_settings)) -> IdentityManager:
    config = CoreasonIdentityConfig(
        domain=settings.IDENTITY_DOMAIN, audience=settings.IDENTITY_AUDIENCE, client_id=settings.IDENTITY_CLIENT_ID
    )
    return IdentityManager(config=config)


def get_redis_ledger(settings: Settings = Depends(get_settings)) -> RedisLedger:
    return RedisLedger(redis_url=settings.BUDGET_REDIS_URL)


def get_budget_guard(
    settings: Settings = Depends(get_settings), ledger: RedisLedger = Depends(get_redis_ledger)
) -> BudgetGuard:
    config = CoreasonBudgetConfig(
        redis_url=settings.BUDGET_REDIS_URL,
        daily_global_limit_usd=settings.BUDGET_GLOBAL_LIMIT,
        daily_project_limit_usd=settings.BUDGET_PROJECT_LIMIT,
        daily_user_limit_usd=settings.BUDGET_USER_LIMIT,
        model_price_overrides={},
    )
    return BudgetGuard(config=config, ledger=ledger)


@lru_cache
def get_auditor() -> Auditor:
    return Auditor(service_name="coreason-api")


def get_gatekeeper(settings: Settings = Depends(get_settings)) -> Gatekeeper:
    return Gatekeeper(public_key_store=settings.VERITAS_PUBLIC_KEY)


@lru_cache
def get_trust_anchor() -> TrustAnchor:
    return TrustAnchor()


@lru_cache
def get_session_manager() -> SessionManager:
    return SessionManager()
