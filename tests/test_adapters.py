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

import pytest
from coreason_api.adapters import AnchorAdapter, BudgetAdapter, MCPAdapter, VaultAdapter
from coreason_mcp.config import McpServerConfig


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


@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_mcp_adapter() -> None:
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value

        # Setup session context manager mock
        session_mock = AsyncMock()
        session_mock.call_tool = AsyncMock(
            return_value={"status": "success", "agent_id": "agent-123", "output": "real_output"}
        )
        connect_ctx = AsyncMock()
        connect_ctx.__aenter__.return_value = session_mock
        connect_ctx.__aexit__.return_value = None
        mock_sm_instance.connect.return_value = connect_ctx

        adapter = MCPAdapter(server_url="http://mock")
        assert mock_sm_cls.called

        # Test execute_agent
        result = await adapter.execute_agent("agent-123", {"input": "val"}, {"context": "val"})

        # Assert connection
        mock_sm_instance.connect.assert_called_once()
        config_arg = mock_sm_instance.connect.call_args[0][0]
        assert isinstance(config_arg, McpServerConfig)
        assert config_arg.url == "http://mock"

        # Assert call_tool
        session_mock.call_tool.assert_awaited_once_with(name="agent-123", arguments={"input": "val", "context": "val"})
        assert result["status"] == "success"
        assert result["output"] == "real_output"


def test_mcp_adapter_initialization_failure() -> None:
    with patch("coreason_api.adapters.SessionManager", side_effect=Exception("Init Failed")):
        with pytest.raises(Exception, match="Init Failed"):
            MCPAdapter(server_url="http://mock")


@pytest.mark.anyio
async def test_mcp_adapter_empty_inputs() -> None:
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value

        session_mock = AsyncMock()
        session_mock.call_tool = AsyncMock(return_value={"status": "error", "message": "empty inputs"})
        connect_ctx = AsyncMock()
        connect_ctx.__aenter__.return_value = session_mock
        connect_ctx.__aexit__.return_value = None
        mock_sm_instance.connect.return_value = connect_ctx

        adapter = MCPAdapter(server_url="http://mock")
        # Test empty inputs
        result = await adapter.execute_agent("", {}, {})

        session_mock.call_tool.assert_awaited_once_with(name="", arguments={})
        assert result["status"] == "error"


@pytest.mark.anyio
async def test_mcp_adapter_propagates_exceptions() -> None:
    """Test that the adapter correctly propagates exceptions from SessionManager."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value

        # Simulate connect failure
        mock_sm_instance.connect.side_effect = ValueError("Connect Failed")

        adapter = MCPAdapter(server_url="http://mock")

        with pytest.raises(ValueError, match="Connect Failed"):
            await adapter.execute_agent("invalid-agent", {}, {})


@pytest.mark.anyio
async def test_mcp_adapter_concurrent_calls() -> None:
    """Test that the adapter handles concurrent execution requests properly."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value

        # Need separate mocks for each call if we want strict verification,
        # but for simple concurrency check, returning a new context manager is fine.
        # But side_effect needs to be callable

        def side_effect_connect(config: Any) -> AsyncMock:
            session_mock = AsyncMock()
            # We can make call_tool return something based on config
            agent_id = config.name.replace("agent-", "")
            session_mock.call_tool.return_value = {"id": f"agent-{agent_id}"}

            ctx = AsyncMock()
            ctx.__aenter__.return_value = session_mock
            return ctx

        mock_sm_instance.connect.side_effect = side_effect_connect

        adapter = MCPAdapter(server_url="http://mock")

        # Simulate 5 concurrent calls
        tasks = [adapter.execute_agent(f"agent-{i}", {}, {}) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert {r["id"] for r in results} == {f"agent-{i}" for i in range(5)}
        assert mock_sm_instance.connect.call_count == 5


@pytest.mark.anyio
async def test_mcp_adapter_complex_nested_input() -> None:
    """Test that complex nested data structures are passed through correctly."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value

        session_mock = AsyncMock()
        session_mock.call_tool = AsyncMock(return_value={})
        connect_ctx = AsyncMock()
        connect_ctx.__aenter__.return_value = session_mock
        mock_sm_instance.connect.return_value = connect_ctx

        adapter = MCPAdapter(server_url="http://mock")

        complex_input: Dict[str, Any] = {
            "query": "complex",
            "meta": {"nested": [1, 2, {"deep": "val"}]},
            "flags": {True, False},
        }
        complex_context: Dict[str, Any] = {"user": {"id": 1, "roles": ["admin"]}}

        await adapter.execute_agent("agent-complex", complex_input, complex_context)

        # We merge input_data and context into call_tool arguments
        expected_arguments = {**complex_context, **complex_input}
        session_mock.call_tool.assert_awaited_once_with(name="agent-complex", arguments=expected_arguments)


@pytest.mark.anyio
async def test_mcp_adapter_huge_payload() -> None:
    """Test that the adapter handles large payloads without issues."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value

        session_mock = AsyncMock()
        session_mock.call_tool = AsyncMock(return_value={})
        connect_ctx = AsyncMock()
        connect_ctx.__aenter__.return_value = session_mock
        mock_sm_instance.connect.return_value = connect_ctx

        adapter = MCPAdapter(server_url="http://mock")

        # Create a large input (e.g. 1MB string)
        huge_string = "x" * 1024 * 1024
        huge_input = {"data": huge_string}

        await adapter.execute_agent("agent-huge", huge_input, {})

        mock_sm_instance.connect.assert_called_once()
        session_mock.call_tool.assert_awaited_once()
        # Verify the large string was passed correctly
        call_args = session_mock.call_tool.call_args
        assert call_args[1]["arguments"]["data"] == huge_string


@pytest.mark.anyio
async def test_mcp_adapter_sequential_calls() -> None:
    """Test that the adapter instance can be reused for sequential calls."""
    with patch("coreason_api.adapters.SessionManager") as mock_sm_cls:
        mock_sm_instance = mock_sm_cls.return_value

        session_mock = AsyncMock()
        session_mock.call_tool = AsyncMock(return_value="success")
        connect_ctx = AsyncMock()
        connect_ctx.__aenter__.return_value = session_mock
        mock_sm_instance.connect.return_value = connect_ctx

        adapter = MCPAdapter(server_url="http://mock")

        for i in range(3):
            await adapter.execute_agent(f"agent-{i}", {}, {})

        assert mock_sm_instance.connect.call_count == 3
