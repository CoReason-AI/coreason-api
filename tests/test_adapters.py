# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
import os
from pydantic import ValidationError
from coreason_budget.config import CoreasonBudgetConfig

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
        mock_sm_instance.execute_agent = AsyncMock(return_value={"status": "error", "message": "empty inputs"})

        adapter = MCPAdapter()
        # Test empty inputs
        result = await adapter.execute_agent("", {}, {})

        mock_sm_instance.execute_agent.assert_called_once_with("", {}, {})
        assert result["status"] == "error"


@pytest.mark.anyio  # type: ignore[misc]
async def test_mcp_adapter_propagates_exceptions() -> None:
    """Test that the adapter correctly propagates exceptions from SessionManager."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value
        mock_sm_instance.execute_agent = AsyncMock(side_effect=ValueError("Unknown agent"))

        adapter = MCPAdapter()

        with pytest.raises(ValueError, match="Unknown agent"):
            await adapter.execute_agent("invalid-agent", {}, {})


@pytest.mark.anyio  # type: ignore[misc]
async def test_mcp_adapter_concurrent_calls() -> None:
    """Test that the adapter handles concurrent execution requests properly."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value
        mock_sm_instance.execute_agent = AsyncMock(side_effect=lambda a, i, c: {"id": a})

        adapter = MCPAdapter()

        # Simulate 5 concurrent calls
        tasks = [adapter.execute_agent(f"agent-{i}", {}, {}) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert {r["id"] for r in results} == {f"agent-{i}" for i in range(5)}
        assert mock_sm_instance.execute_agent.call_count == 5


@pytest.mark.anyio  # type: ignore[misc]
async def test_mcp_adapter_complex_nested_input() -> None:
    """Test that complex nested data structures are passed through correctly."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value
        mock_sm_instance.execute_agent = AsyncMock(return_value={})

        adapter = MCPAdapter()

        complex_input: Dict[str, Any] = {
            "query": "complex",
            "meta": {"nested": [1, 2, {"deep": "val"}]},
            "flags": {True, False},
        }
        complex_context: Dict[str, Any] = {"user": {"id": 1, "roles": ["admin"]}}

        await adapter.execute_agent("agent-complex", complex_input, complex_context)

        mock_sm_instance.execute_agent.assert_called_once_with("agent-complex", complex_input, complex_context)


@pytest.mark.anyio  # type: ignore[misc]
async def test_mcp_adapter_huge_payload() -> None:
    """Test that the adapter handles large payloads without issues."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value
        mock_sm_instance.execute_agent = AsyncMock(return_value={})

        adapter = MCPAdapter()

        # Create a large input (e.g. 1MB string)
        huge_string = "x" * 1024 * 1024
        huge_input = {"data": huge_string}

        await adapter.execute_agent("agent-huge", huge_input, {})

        mock_sm_instance.execute_agent.assert_called_once()
        # Verify the large string was passed correctly
        call_args = mock_sm_instance.execute_agent.call_args
        assert call_args[0][1]["data"] == huge_string


@pytest.mark.anyio  # type: ignore[misc]
async def test_mcp_adapter_sequential_calls() -> None:
    """Test that the adapter instance can be reused for sequential calls."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value
        # Return dynamic result based on call count or args could be done,
        # but simple return value is enough to verify call_count.
        mock_sm_instance.execute_agent = AsyncMock(return_value="success")

        adapter = MCPAdapter()

        for i in range(3):
            await adapter.execute_agent(f"agent-{i}", {}, {})

        assert mock_sm_instance.execute_agent.call_count == 3


def test_budget_adapter_init_without_env_var() -> None:
    """
    Test that BudgetAdapter works when initialized with explicit db_url,
    even if REDIS_URL env var is missing.
    """
    # Temporarily unset REDIS_URL if present
    old_value = os.environ.get("REDIS_URL")
    if old_value:
        del os.environ["REDIS_URL"]

    try:
        # Verify that initializing CoreasonBudgetConfig without args fails
        with pytest.raises(ValidationError):
            CoreasonBudgetConfig()

        # Now verify that BudgetAdapter works because we fixed it (expected to fail before fix)
        db_url = "redis://localhost:6379/1"

        # We mock RedisLedger to avoid actual connection attempts
        with patch("coreason_api.adapters.RedisLedger") as MockLedger:
            adapter = BudgetAdapter(db_url=db_url)

            # Verify config was initialized with the passed url
            assert adapter._config.redis_url == db_url

            # Verify ledger was initialized with the passed url
            MockLedger.assert_called_with(redis_url=db_url)
    finally:
        # Restore env var
        if old_value:
            os.environ["REDIS_URL"] = old_value


def test_budget_adapter_invalid_url() -> None:
    """Test initialization with invalid Redis URL."""
    # The real RedisLedger raises ValueError for invalid schemes

    # We must NOT mock RedisLedger if we want to test its validation,
    # OR we assume Config raises validation error.
    # However, in the trace, it was RedisLedger raising ValueError.
    # So we should expect ValueError.

    with pytest.raises(ValueError, match="Redis URL must specify one of the following schemes"):
        BudgetAdapter(db_url="http://not-redis.com")


@pytest.mark.anyio  # type: ignore[misc]
async def test_budget_adapter_negative_cost() -> None:
    """Test behavior with negative cost."""
    # The adapter propagates the call. The underlying guard might accept or reject it.
    # Since we mock the guard, we just verify the adapter passes it through.
    with (
        patch("coreason_api.adapters.BudgetGuard") as mock_guard_cls,
        patch("coreason_api.adapters.RedisLedger"),
        patch("coreason_api.adapters.CoreasonBudgetConfig"),
    ):
        mock_guard = mock_guard_cls.return_value
        mock_guard.check = AsyncMock(return_value=True)

        adapter = BudgetAdapter(db_url="redis://localhost")

        # Checking quota for negative cost (refund?)
        await adapter.check_quota("user1", -5.0)
        mock_guard.check.assert_called_with(user_id="user1", cost=-5.0)


@pytest.mark.anyio  # type: ignore[misc]
async def test_budget_adapter_empty_user() -> None:
    """Test behavior with empty user ID."""
    with (
        patch("coreason_api.adapters.BudgetGuard") as mock_guard_cls,
        patch("coreason_api.adapters.RedisLedger"),
        patch("coreason_api.adapters.CoreasonBudgetConfig"),
    ):
        mock_guard = mock_guard_cls.return_value
        mock_guard.check = AsyncMock(return_value=True)

        adapter = BudgetAdapter(db_url="redis://localhost")

        await adapter.check_quota("", 10.0)
        mock_guard.check.assert_called_with(user_id="", cost=10.0)
