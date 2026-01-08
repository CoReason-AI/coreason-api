# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import MagicMock, patch

import pytest

from coreason_api.config import Settings
from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_gatekeeper,
    get_identity_manager,
    get_redis_ledger,
    get_session_manager,
    get_trust_anchor,
    get_vault_manager,
)


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        APP_ENV="test",
        IDENTITY_DOMAIN="test-domain",
        IDENTITY_AUDIENCE="test-aud",
        IDENTITY_CLIENT_ID="test-client",
        BUDGET_REDIS_URL="redis://test:6379",
        VERITAS_PUBLIC_KEY="test-pub-key",
    )


def test_get_vault_manager() -> None:
    get_vault_manager.cache_clear()
    with (
        patch("coreason_api.dependencies.VaultManager") as MockVault,
        patch("coreason_api.dependencies.CoreasonVaultConfig") as MockConfig,
    ):
        mgr = get_vault_manager()
        assert mgr == MockVault.return_value
        MockConfig.assert_called()
        MockVault.assert_called_with(config=MockConfig.return_value)
        # Check singleton (lru_cache)
        mgr2 = get_vault_manager()
        assert mgr is mgr2


def test_get_identity_manager(mock_settings: Settings) -> None:
    # Not cached anymore
    with (
        patch("coreason_api.dependencies.IdentityManager") as MockId,
        patch("coreason_api.dependencies.CoreasonIdentityConfig") as MockConfig,
    ):
        mgr = get_identity_manager(mock_settings)
        assert mgr == MockId.return_value
        MockConfig.assert_called_with(domain="test-domain", audience="test-aud", client_id="test-client")
        MockId.assert_called_with(config=MockConfig.return_value)


def test_get_redis_ledger(mock_settings: Settings) -> None:
    # Not cached anymore
    with patch("coreason_api.dependencies.RedisLedger") as MockLedger:
        ledger = get_redis_ledger(mock_settings)
        assert ledger == MockLedger.return_value
        MockLedger.assert_called_with(redis_url="redis://test:6379")


def test_get_budget_guard(mock_settings: Settings) -> None:
    # Not cached anymore

    mock_ledger_instance = MagicMock()

    with (
        patch("coreason_api.dependencies.BudgetGuard") as MockGuard,
        patch("coreason_api.dependencies.CoreasonBudgetConfig") as MockConfig,
    ):
        guard = get_budget_guard(mock_settings, mock_ledger_instance)
        assert guard == MockGuard.return_value
        MockConfig.assert_called_with(
            redis_url="redis://test:6379",
            daily_global_limit_usd=1000.0,
            daily_project_limit_usd=100.0,
            daily_user_limit_usd=10.0,
            model_price_overrides={},
        )
        MockGuard.assert_called_with(config=MockConfig.return_value, ledger=mock_ledger_instance)


def test_get_auditor() -> None:
    get_auditor.cache_clear()
    with patch("coreason_api.dependencies.Auditor") as MockAuditor:
        aud = get_auditor()
        assert aud == MockAuditor.return_value
        MockAuditor.assert_called_with(service_name="coreason-api")


def test_get_gatekeeper(mock_settings: Settings) -> None:
    # Not cached anymore
    with patch("coreason_api.dependencies.Gatekeeper") as MockGate:
        gate = get_gatekeeper(mock_settings)
        assert gate == MockGate.return_value
        MockGate.assert_called_with(public_key_store="test-pub-key")


def test_get_trust_anchor() -> None:
    get_trust_anchor.cache_clear()
    with patch("coreason_api.dependencies.TrustAnchor") as MockAnchor:
        anchor = get_trust_anchor()
        assert anchor == MockAnchor.return_value


def test_get_session_manager() -> None:
    get_session_manager.cache_clear()
    with patch("coreason_api.dependencies.SessionManager") as MockSM:
        sm = get_session_manager()
        assert sm == MockSM.return_value
