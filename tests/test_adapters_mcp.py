# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_api.adapters import MCPAdapter
from coreason_mcp.config import McpServerConfig


@pytest.fixture
def mock_session_manager() -> Tuple[MagicMock, AsyncMock]:
    manager = MagicMock()
    # Mock the context manager behavior of connect
    session_mock = AsyncMock()
    session_mock.call_tool = AsyncMock(return_value={"status": "executed"})

    # SessionManager.connect returns an async context manager that yields session_mock
    connect_ctx = AsyncMock()
    connect_ctx.__aenter__.return_value = session_mock
    connect_ctx.__aexit__.return_value = None

    manager.connect.return_value = connect_ctx
    return manager, session_mock


@pytest.mark.asyncio
async def test_mcp_adapter_execute_agent(mock_session_manager: Tuple[MagicMock, AsyncMock]) -> None:
    manager_mock, session_mock = mock_session_manager
    adapter = MCPAdapter(server_url="http://test-server")
    # Inject the mock manager
    adapter._session_manager = manager_mock

    result = await adapter.execute_agent(agent_id="my-agent", input_data={"key": "value"}, context={"user": "test"})

    # Check result
    assert result == {"status": "executed"}

    # Check connect called with correct config
    manager_mock.connect.assert_called_once()
    call_args = manager_mock.connect.call_args
    config_arg = call_args[0][0]
    assert isinstance(config_arg, McpServerConfig)
    assert config_arg.url == "http://test-server"
    assert config_arg.name == "agent-my-agent"

    # Check call_tool
    session_mock.call_tool.assert_awaited_once_with(name="my-agent", arguments={"key": "value", "user": "test"})
