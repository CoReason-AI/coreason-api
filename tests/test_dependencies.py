# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coreason_api.adapters import AnchorAdapter, BudgetAdapter, MCPAdapter, VaultAdapter
from coreason_api.config import Settings
from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_gatekeeper,
    get_identity_manager,
    get_manifest_validator,
    get_session_manager,
    get_trust_anchor,
    get_vault_manager,
)


@pytest.fixture  # type: ignore[misc]
def mock_settings() -> Settings:
    return Settings(
        COREASON_AUTH_DOMAIN="auth.test",
        COREASON_AUTH_AUDIENCE="aud.test",
        COREASON_AUTH_CLIENT_ID="client.test",
        REDIS_URL="redis://test",
        SRB_PUBLIC_KEY="public_key",
    )


def test_get_vault_manager() -> None:
    with (
        patch("coreason_api.dependencies.CoreasonVaultConfig") as MockConfig,
        patch("coreason_api.dependencies.VaultAdapter") as MockAdapter,
    ):
        get_vault_manager.cache_clear()
        manager = get_vault_manager()
        assert manager is MockAdapter.return_value
        MockConfig.assert_called_once()
        MockAdapter.assert_called_once_with(config=MockConfig.return_value)

        # Test caching
        manager2 = get_vault_manager()
        assert manager2 is manager


def test_get_identity_manager(mock_settings: Settings) -> None:
    with (
        patch("coreason_api.dependencies.CoreasonIdentityConfig") as MockConfig,
        patch("coreason_api.dependencies.IdentityManager") as MockManager,
    ):
        get_identity_manager.cache_clear()
        manager = get_identity_manager(mock_settings)
        assert manager is MockManager.return_value
        MockConfig.assert_called_once_with(
            domain="auth.test",
            audience="aud.test",
            client_id="client.test",
        )
        MockManager.assert_called_once_with(config=MockConfig.return_value)


def test_get_budget_guard(mock_settings: Settings) -> None:
    with patch("coreason_api.dependencies.BudgetAdapter") as MockAdapter:
        get_budget_guard.cache_clear()
        guard = get_budget_guard(mock_settings)
        assert guard is MockAdapter.return_value
        MockAdapter.assert_called_once_with(db_url="redis://test")


def test_get_auditor() -> None:
    with patch("coreason_api.dependencies.Auditor") as MockAuditor:
        get_auditor.cache_clear()
        auditor = get_auditor()
        assert auditor is MockAuditor.return_value
        MockAuditor.assert_called_once_with(service_name="coreason-api")


def test_get_gatekeeper(mock_settings: Settings) -> None:
    with patch("coreason_api.dependencies.Gatekeeper") as MockGatekeeper:
        get_gatekeeper.cache_clear()
        gatekeeper = get_gatekeeper(mock_settings)
        assert gatekeeper is MockGatekeeper.return_value
        MockGatekeeper.assert_called_once_with(public_key_store="public_key")


def test_get_session_manager() -> None:
    with patch("coreason_api.dependencies.MCPAdapter") as MockAdapter:
        get_session_manager.cache_clear()
        manager = get_session_manager()
        assert manager is MockAdapter.return_value
        MockAdapter.assert_called_once()


def test_get_manifest_validator() -> None:
    with patch("coreason_api.dependencies.ManifestValidator") as MockValidator:
        get_manifest_validator.cache_clear()
        validator = get_manifest_validator()
        assert validator is MockValidator.return_value
        MockValidator.assert_called_once()


def test_get_trust_anchor() -> None:
    with patch("coreason_api.dependencies.AnchorAdapter") as MockAdapter:
        get_trust_anchor.cache_clear()
        anchor = get_trust_anchor()
        assert anchor is MockAdapter.return_value
        MockAdapter.assert_called_once()


# --- Adapter Tests ---


def test_vault_adapter() -> None:
    mock_config = MagicMock()
    with patch("coreason_api.adapters.VaultManager") as MockManager:
        adapter = VaultAdapter(config=mock_config)

        # Test get_secret
        MockManager.return_value.secrets.get_secret.return_value = "secret"
        assert adapter.get_secret("key") == "secret"
        MockManager.return_value.secrets.get_secret.assert_called_once_with("key", default=None)


@pytest.mark.asyncio  # type: ignore[misc]
async def test_budget_adapter() -> None:
    with (
        patch("coreason_api.adapters.CoreasonBudgetConfig") as _,
        patch("coreason_api.adapters.RedisLedger") as MockLedger,
        patch("coreason_api.adapters.BudgetGuard") as MockGuard,
    ):
        adapter = BudgetAdapter(db_url="redis://test")
        MockLedger.assert_called_once_with(redis_url="redis://test")

        # Setup AsyncMocks
        MockGuard.return_value.check = AsyncMock(return_value=True)
        MockGuard.return_value.charge = AsyncMock()

        # Test check_quota
        assert await adapter.check_quota("user", 10.0) is True
        MockGuard.return_value.check.assert_called_once_with(user_id="user", cost=10.0)

        # Test record_transaction
        await adapter.record_transaction("user", 5.0, {})
        MockGuard.return_value.charge.assert_called_once_with(user_id="user", cost=5.0)


def test_anchor_adapter() -> None:
    with patch("coreason_api.adapters.DeterminismInterceptor") as MockInterceptor:
        adapter = AnchorAdapter()
        MockInterceptor.return_value.seal.return_value = "sealed"
        assert adapter.seal({"data": 1}) == "sealed"
        MockInterceptor.return_value.seal.assert_called_once_with({"data": 1})


@pytest.mark.asyncio  # type: ignore[misc]
async def test_mcp_adapter() -> None:
    with patch("coreason_api.adapters.SessionManager") as MockManager:
        adapter = MCPAdapter()
        MockManager.return_value.execute_agent = AsyncMock(return_value="result")

        res = await adapter.execute_agent("agent", {}, {})
        assert res == "result"
        MockManager.return_value.execute_agent.assert_called_once_with("agent", {}, {})
