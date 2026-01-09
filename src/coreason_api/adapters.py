import os
from typing import Any, Dict, List, Optional

from coreason_budget.config import CoreasonBudgetConfig

# Coreason Budget
from coreason_budget.guard import BudgetGuard as _BudgetGuard
from coreason_budget.ledger import RedisLedger
from coreason_identity.config import CoreasonIdentityConfig as _CoreasonIdentityConfig

# Coreason Identity
from coreason_identity.manager import IdentityManager as _IdentityManager
from coreason_vault import CoreasonVaultConfig

# Coreason Vault
from coreason_vault import VaultManager as _VaultManager
from coreason_vault.exceptions import SecretNotFoundError

# Coreason Veritas
from coreason_veritas.auditor import IERLogger as _IERLogger
from coreason_veritas.gatekeeper import SignatureValidator as _SignatureValidator

# TrustAnchor is missing in installed package, so we stub it or look for it
try:
    from coreason_veritas.anchor import TrustAnchor as _TrustAnchor  # type: ignore[attr-defined]
except ImportError:
    # Create a stub if not found, to allow code to run
    class _TrustAnchor:  # type: ignore
        def seal_artifact(self, artifact: Any) -> Any:
            return artifact


# Coreason MCP
from coreason_manifest.loader import ManifestLoader as _ManifestLoader

# Coreason Manifest
from coreason_manifest.validator import SchemaValidator as _SchemaValidator
from coreason_mcp.session_manager import SessionManager as _SessionManager


class VaultAdapter:
    """
    Adapter for Coreason Vault to match PRD VID.
    VID:
      vault = VaultManager()
      secret = vault.get_secret("DB_PASSWORD", default="...")
    """

    def __init__(self) -> None:
        # We need to initialize the real VaultManager with a config.
        # We assume environment variables are set for VAULT_ADDR, etc.
        # or use defaults.
        # CoreasonVaultConfig requires VAULT_ADDR.
        vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.config = CoreasonVaultConfig(VAULT_ADDR=vault_addr)  # type: ignore[call-arg, unused-ignore]
        self.manager = _VaultManager(self.config)

    def get_secret(self, key: str, default: Any = None) -> Any:
        try:
            # Installed package: vault.secrets.get_secret(path) -> Dict
            # We assume 'key' is the path.
            # And we return the whole dict or specific value?
            # PRD implies value: secret = vault.get_secret(...)
            # If the result is a dict, we return it.
            return self.manager.secrets.get_secret(key)
        except (SecretNotFoundError, Exception):
            return default


class IdentityAdapter:
    """
    Adapter for IdentityManager.
    VID:
      identity = IdentityManager(config=CoreasonIdentityConfig(...))
      user = await identity.validate_token(auth_header)
    """

    # The VID matches the actual class closely, but we alias it for consistency
    # and to allow 'from coreason_api.adapters import IdentityManager'
    def __init__(self, config: _CoreasonIdentityConfig) -> None:
        self.manager = _IdentityManager(config)

    async def validate_token(self, token: str) -> Any:
        return await self.manager.validate_token(token)


class BudgetAdapter:
    """
    Adapter for BudgetGuard.
    VID:
      budget = BudgetGuard(db_url=...)
      allowed = await budget.check_quota(user_id, cost_estimate)
      await budget.record_transaction(user_id, amount, context)
    """

    def __init__(self, db_url: str) -> None:
        self.config = CoreasonBudgetConfig(redis_url=db_url)
        self.ledger = RedisLedger(redis_url=db_url)
        self.guard = _BudgetGuard(self.config, self.ledger)

    async def check_quota(self, user_id: str, cost_estimate: float) -> bool:
        # Actual: check(user_id, project_id=None, estimated_cost=0.0)
        return bool(self.guard.check(user_id=user_id, estimated_cost=cost_estimate))

    async def record_transaction(self, user_id: str, amount: float, context: Optional[Dict[str, Any]] = None) -> None:
        # Actual: charge(user_id, cost, project_id=None, model=None)
        # context might contain project_id or model
        project_id = context.get("project_id") if context else None
        model = context.get("model") if context else None
        self.guard.charge(user_id=user_id, cost=amount, project_id=project_id, model=model)


class AuditorAdapter(_IERLogger):
    """
    Adapter for Auditor (IERLogger).
    VID:
      auditor = Auditor(service_name="coreason-api")
      await auditor.log_event("EXECUTION_START", ...)
    """

    # Inheriting from IERLogger as signatures match well enough
    pass


class GatekeeperAdapter:
    """
    Adapter for Gatekeeper (SignatureValidator).
    VID:
       rules = Gatekeeper().get_policy_instruction_for_llm()
    Actual:
       SignatureValidator(public_key_store: str)
    """

    def __init__(self) -> None:
        # Needs public key. Env var or strict default?
        # Memory says: SRB_PUBLIC_KEY must be a valid PEM-formatted string.
        # If not present, we might fail or use a placeholder if testing.
        pk = os.getenv("SRB_PUBLIC_KEY", "")
        self.validator = _SignatureValidator(public_key_store=pk)

    def get_policy_instruction_for_llm(self) -> List[str]:
        return self.validator.get_policy_instruction_for_llm()

    def verify_asset(self, asset_payload: Dict[str, Any], signature: str) -> bool:
        return bool(self.validator.verify_asset(asset_payload, signature))


class MCPAdapter:
    """
    Adapter for SessionManager.
    VID:
      mcp = SessionManager()
      result = await mcp.execute_agent(agent_id, input_data, context)
    """

    def __init__(self) -> None:
        self.manager = _SessionManager()

    async def execute_agent(self, agent_id: str, input_data: Dict[str, Any], context: Any) -> Any:
        return self.manager.execute_agent(agent_id, input_data, context)


# Exports matching PRD VIDs
VaultManager = VaultAdapter
IdentityManager = IdentityAdapter
BudgetGuard = BudgetAdapter
Auditor = AuditorAdapter
Gatekeeper = GatekeeperAdapter
SessionManager = MCPAdapter
SchemaValidator = _SchemaValidator
ManifestLoader = _ManifestLoader
TrustAnchor = _TrustAnchor
CoreasonIdentityConfig = _CoreasonIdentityConfig  # Re-export config as well
