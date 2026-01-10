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
from typing import Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_api.adapters import MCPAdapter


@pytest.fixture
def mock_session_manager() -> Tuple[MagicMock, AsyncMock]:
    manager = MagicMock()
    session_mock = AsyncMock()
    session_mock.call_tool = AsyncMock(return_value={"status": "executed"})

    connect_ctx = AsyncMock()
    connect_ctx.__aenter__.return_value = session_mock
    connect_ctx.__aexit__.return_value = None

    manager.connect.return_value = connect_ctx
    return manager, session_mock


@pytest.mark.asyncio
async def test_context_propagation(mock_session_manager: Tuple[MagicMock, AsyncMock]) -> None:
    manager_mock, session_mock = mock_session_manager
    adapter = MCPAdapter(server_url="http://test")
    adapter._session_manager = manager_mock

    await adapter.execute_agent("agent", input_data={"key": "val"}, context={"user_id": "123", "trace_id": "abc"})

    # Check that arguments contain merged context
    session_mock.call_tool.assert_awaited_once()
    args = session_mock.call_tool.call_args[1]["arguments"]
    assert args["key"] == "val"
    assert args["user_id"] == "123"
    assert args["trace_id"] == "abc"


@pytest.mark.asyncio
async def test_input_priority_over_context(mock_session_manager: Tuple[MagicMock, AsyncMock]) -> None:
    manager_mock, session_mock = mock_session_manager
    adapter = MCPAdapter(server_url="http://test")
    adapter._session_manager = manager_mock

    # Input data has "user_id" which is also in context
    await adapter.execute_agent("agent", input_data={"user_id": "override"}, context={"user_id": "default"})

    args = session_mock.call_tool.call_args[1]["arguments"]
    # Input data should win (according to {**context, **input_data})
    assert args["user_id"] == "override"


@pytest.mark.asyncio
async def test_non_dict_response(mock_session_manager: Tuple[MagicMock, AsyncMock]) -> None:
    manager_mock, session_mock = mock_session_manager
    session_mock.call_tool.return_value = "string response"

    adapter = MCPAdapter(server_url="http://test")
    adapter._session_manager = manager_mock

    result = await adapter.execute_agent("agent", {}, {})
    assert result == "string response"


@pytest.mark.asyncio
async def test_none_response(mock_session_manager: Tuple[MagicMock, AsyncMock]) -> None:
    manager_mock, session_mock = mock_session_manager
    session_mock.call_tool.return_value = None

    adapter = MCPAdapter(server_url="http://test")
    adapter._session_manager = manager_mock

    result = await adapter.execute_agent("agent", {}, {})
    assert result is None


@pytest.mark.asyncio
async def test_connection_timeout(mock_session_manager: Tuple[MagicMock, AsyncMock]) -> None:
    manager_mock, _ = mock_session_manager
    manager_mock.connect.side_effect = asyncio.TimeoutError("Connect timed out")

    adapter = MCPAdapter(server_url="http://test")
    adapter._session_manager = manager_mock

    with pytest.raises(asyncio.TimeoutError, match="Connect timed out"):
        await adapter.execute_agent("agent", {}, {})


@pytest.mark.asyncio
async def test_special_chars_agent_id(mock_session_manager: Tuple[MagicMock, AsyncMock]) -> None:
    manager_mock, session_mock = mock_session_manager
    adapter = MCPAdapter(server_url="http://test")
    adapter._session_manager = manager_mock

    special_id = "agent/v1@beta"
    await adapter.execute_agent(special_id, {}, {})

    # Verify config name handling (f-string)
    call_args = manager_mock.connect.call_args
    config = call_args[0][0]
    assert config.name == f"agent-{special_id}"

    # Verify tool name
    session_mock.call_tool.assert_awaited_once_with(name=special_id, arguments={})
