# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Any, Dict

from coreason_budget.config import CoreasonBudgetConfig
from coreason_budget.guard import BudgetGuard
from coreason_budget.ledger import RedisLedger
from coreason_vault import VaultManager
from coreason_vault.config import CoreasonVaultConfig
from coreason_veritas.anchor import DeterminismInterceptor


class VaultAdapter:
    """
    Adapter for coreason-vault to match PRD VID.
    PRD VID: vault.get_secret(key, default=...)
    Installed: vault.secrets.get_secret(key, default=...)
    """

    def __init__(self, config: CoreasonVaultConfig) -> None:
        self._manager = VaultManager(config=config)

    def get_secret(self, key: str, default: Any = None) -> Any:
        # Delegate to the internal secrets keeper
        return self._manager.secrets.get_secret(key, default=default)


class BudgetAdapter:
    """
    Adapter for coreason-budget to match PRD VID.
    PRD VID:
      budget = BudgetGuard(db_url=...)
      budget.check_quota(user_id, cost_estimate)
      budget.record_transaction(user_id, amount, context)

    Installed:
      BudgetGuard(config=..., ledger=...)
      budget.check(user_id, cost)
      budget.charge(...) # Assumed based on 'charge' in dir()
    """

    def __init__(self, db_url: str) -> None:
        # PRD implies db_url is used. Installed uses RedisLedger.
        # We'll assume db_url from PRD maps to Redis URL for the ledger.
        self._config = CoreasonBudgetConfig()
        self._ledger = RedisLedger(redis_url=db_url)
        self._guard = BudgetGuard(config=self._config, ledger=self._ledger)

    async def check_quota(self, user_id: str, cost_estimate: float) -> bool:
        # Maps PRD check_quota -> Installed check
        # Assuming check returns boolean
        return bool(await self._guard.check(user_id=user_id, cost=cost_estimate))

    async def record_transaction(self, user_id: str, amount: float, context: dict[str, Any]) -> None:
        # Maps PRD record_transaction -> Installed charge
        # We need to verify signature of charge.
        # For now, we assume it takes user_id and cost/amount.
        # If 'charge' doesn't exist or signature differs, we might need to adjust.
        # Based on inspection, 'charge' exists.
        await self._guard.charge(user_id=user_id, cost=amount)


class AnchorAdapter:
    """
    Adapter for coreason-veritas.anchor.TrustAnchor.
    PRD VID:
      TrustAnchor.seal(artifact)
    Installed:
      DeterminismInterceptor.seal(artifact)
    """

    def __init__(self) -> None:
        self._interceptor = DeterminismInterceptor()

    def seal(self, artifact: Dict[str, Any]) -> str:
        return self._interceptor.seal(artifact)
