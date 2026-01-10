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


def test_vault_adapter() -> None:
    mock_config = MagicMock()
    with patch("coreason_api.adapters.VaultManager") as mock_manager_cls:
        mock_manager = mock_manager_cls.return_value
        mock_secrets = MagicMock()
        mock_manager.secrets = mock_secrets
        mock_secrets.get_secret.return_value = "secret_value"

        adapter = VaultAdapter(config=mock_config)
        val = adapter.get_secret("MY_KEY")

        assert val == "secret_value"
        mock_secrets.get_secret.assert_called_with("MY_KEY", default=None)


def test_vault_adapter_defaults() -> None:
    mock_config = MagicMock()
    with patch("coreason_api.adapters.VaultManager") as mock_manager_cls:
        mock_manager = mock_manager_cls.return_value
        mock_secrets = MagicMock()
        mock_manager.secrets = mock_secrets
        mock_secrets.get_secret.return_value = "default_value"

        adapter = VaultAdapter(config=mock_config)
        val = adapter.get_secret("MY_KEY", default="default_value")

        assert val == "default_value"
        mock_secrets.get_secret.assert_called_with("MY_KEY", default="default_value")


def test_vault_adapter_error() -> None:
    mock_config = MagicMock()
    with patch("coreason_api.adapters.VaultManager") as mock_manager_cls:
        mock_manager = mock_manager_cls.return_value
        mock_secrets = MagicMock()
        mock_manager.secrets = mock_secrets
        mock_secrets.get_secret.side_effect = Exception("Vault Error")

        adapter = VaultAdapter(config=mock_config)
        with pytest.raises(Exception, match="Vault Error"):
            adapter.get_secret("MY_KEY")


@pytest.mark.anyio  # type: ignore[misc]
async def test_budget_adapter() -> None:
    with (
        patch("coreason_api.adapters.BudgetGuard") as mock_guard_cls,
        patch("coreason_api.adapters.RedisLedger"),
        patch("coreason_api.adapters.CoreasonBudgetConfig"),
    ):
        mock_guard = mock_guard_cls.return_value
        mock_guard.check = AsyncMock(return_value=True)
        mock_guard.charge = AsyncMock()

        adapter = BudgetAdapter(db_url="redis://localhost")

        # Test Check
        assert await adapter.check_quota("user1", 10.0)
        mock_guard.check.assert_called_with(user_id="user1", cost=10.0)

        # Test Charge
        await adapter.record_transaction("user1", 10.0, {})
        mock_guard.charge.assert_called_with(user_id="user1", cost=10.0)


@pytest.mark.anyio  # type: ignore[misc]
async def test_budget_adapter_quota_exceeded() -> None:
    with (
        patch("coreason_api.adapters.BudgetGuard") as mock_guard_cls,
        patch("coreason_api.adapters.RedisLedger"),
        patch("coreason_api.adapters.CoreasonBudgetConfig"),
    ):
        mock_guard = mock_guard_cls.return_value
        mock_guard.check = AsyncMock(return_value=False)

        adapter = BudgetAdapter(db_url="redis://localhost")
        assert not await adapter.check_quota("user1", 1000.0)


@pytest.mark.anyio  # type: ignore[misc]
async def test_budget_adapter_charge_failure() -> None:
    with (
        patch("coreason_api.adapters.BudgetGuard") as mock_guard_cls,
        patch("coreason_api.adapters.RedisLedger"),
        patch("coreason_api.adapters.CoreasonBudgetConfig"),
    ):
        mock_guard = mock_guard_cls.return_value
        mock_guard.charge = AsyncMock(side_effect=Exception("Redis Down"))

        adapter = BudgetAdapter(db_url="redis://localhost")
        with pytest.raises(Exception, match="Redis Down"):
            await adapter.record_transaction("user1", 10.0, {})


def test_anchor_adapter() -> None:
    with patch("coreason_api.adapters.DeterminismInterceptor") as mock_interceptor_cls:
        mock_interceptor = mock_interceptor_cls.return_value
        mock_interceptor.seal.return_value = "hex_signature"

        adapter = AnchorAdapter()
        sig = adapter.seal({"key": "value"})

        assert sig == "hex_signature"
        mock_interceptor.seal.assert_called_with({"key": "value"})


@pytest.mark.anyio  # type: ignore[misc]
async def test_mcp_adapter() -> None:
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value
        # Configure the mock to return a result when execute_agent is called
        mock_sm_instance.execute_agent = AsyncMock(
            return_value={"status": "success", "agent_id": "agent-123", "output": "real_output"}
        )

        adapter = MCPAdapter()
        assert mock_sm_cls.called

        # Test execute_agent
        result = await adapter.execute_agent("agent-123", {"input": "val"}, {"context": "val"})

        # Assert delegation
        mock_sm_instance.execute_agent.assert_called_once_with("agent-123", {"input": "val"}, {"context": "val"})
        assert result["status"] == "success"
        assert result["output"] == "real_output"


def test_mcp_adapter_initialization_failure() -> None:
    with patch("coreason_api.adapters.SessionManager", side_effect=Exception("Init Failed")):
        with pytest.raises(Exception, match="Init Failed"):
            MCPAdapter()


@pytest.mark.anyio  # type: ignore[misc]
async def test_mcp_adapter_empty_inputs() -> None:
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value
        mock_sm_instance.execute_agent = AsyncMock(
            return_value={"status": "error", "message": "empty inputs"}
        )

        adapter = MCPAdapter()
        # Test empty inputs
        result = await adapter.execute_agent("", {}, {})

        mock_sm_instance.execute_agent.assert_called_once_with("", {}, {})
        assert result["status"] == "error"
