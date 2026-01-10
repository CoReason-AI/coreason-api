# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_api.adapters import BudgetAdapter, MCPAdapter
from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_identity_manager,
    get_session_manager,
)
from coreason_api.routers.runtime import router
from coreason_identity.manager import IdentityManager
from coreason_veritas.auditor import IERLogger as Auditor
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture  # type: ignore[misc]
def mock_identity() -> MagicMock:
    mock = MagicMock(spec=IdentityManager)
    user_context = MagicMock()
    user_context.user_id = "test-user"
    mock.validate_token = AsyncMock(return_value=user_context)
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_budget() -> MagicMock:
    mock = MagicMock(spec=BudgetAdapter)
    mock.check_quota = AsyncMock(return_value=True)
    mock.record_transaction = AsyncMock()
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_auditor() -> MagicMock:
    mock = MagicMock(spec=Auditor)
    mock.log_event = AsyncMock()
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_mcp() -> MagicMock:
    mock = MagicMock(spec=MCPAdapter)
    mock.execute_agent = AsyncMock(return_value={"output": "success"})
    return mock


@pytest.fixture  # type: ignore[misc]
def client(
    mock_identity: MagicMock,
    mock_budget: MagicMock,
    mock_auditor: MagicMock,
    mock_mcp: MagicMock,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    app.dependency_overrides[get_auditor] = lambda: mock_auditor
    app.dependency_overrides[get_session_manager] = lambda: mock_mcp

    return TestClient(app)


def test_run_agent_success(
    client: TestClient,
    mock_identity: MagicMock,
    mock_budget: MagicMock,
    mock_auditor: MagicMock,
    mock_mcp: MagicMock,
) -> None:
    headers = {"Authorization": "Bearer token"}
    payload = {"input_data": {"query": "hello"}, "cost_estimate": 2.5}

    response = client.post("/v1/run/agent-123", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["result"] == {"output": "success"}

    # Verify Chain of Command
    mock_identity.validate_token.assert_called_with("Bearer token")
    mock_budget.check_quota.assert_called_with(user_id="test-user", cost_estimate=2.5)

    mock_auditor.log_event.assert_any_call(
        "EXECUTION_START", {"agent_id": "agent-123", "user_id": "test-user", "cost_estimate": 2.5}
    )

    mock_mcp.execute_agent.assert_called_with(
        agent_id="agent-123", input_data={"query": "hello"}, context={"user_id": "test-user"}
    )

    mock_auditor.log_event.assert_any_call(
        "EXECUTION_END", {"agent_id": "agent-123", "user_id": "test-user", "status": "success"}
    )


def test_run_agent_no_auth(client: TestClient) -> None:
    response = client.post("/v1/run/agent-123", json={"input_data": {}})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header"


def test_run_agent_invalid_auth(client: TestClient, mock_identity: MagicMock) -> None:
    mock_identity.validate_token.side_effect = Exception("Invalid token")
    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}},
        headers={"Authorization": "Bearer bad-token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"


def test_run_agent_insufficient_quota(client: TestClient, mock_budget: MagicMock) -> None:
    mock_budget.check_quota.return_value = False
    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}, "cost_estimate": 1000},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 402
    assert response.json()["detail"] == "Insufficient quota"


def test_run_agent_budget_check_error(client: TestClient, mock_budget: MagicMock) -> None:
    mock_budget.check_quota.side_effect = Exception("Budget DB down")
    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Error checking budget"


def test_run_agent_audit_failure(client: TestClient, mock_auditor: MagicMock) -> None:
    # Fail on start audit
    mock_auditor.log_event.side_effect = Exception("Audit DB down")
    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Audit logging failed"


def test_run_agent_execution_failure(client: TestClient, mock_mcp: MagicMock, mock_auditor: MagicMock) -> None:
    mock_mcp.execute_agent.side_effect = Exception("Agent crashed")
    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 500
    assert "Agent execution failed" in response.json()["detail"]

    # Verify we logged failure
    mock_auditor.log_event.assert_called_with(
        "EXECUTION_FAILED", {"agent_id": "agent-123", "user_id": "test-user", "error": "Agent crashed"}
    )


def test_run_agent_audit_end_failure(client: TestClient, mock_auditor: MagicMock) -> None:
    # Fail on end audit, but execution succeeded
    # We need to control side_effect to succeed on first call, fail on second
    mock_auditor.log_event.side_effect = [None, Exception("Audit DB down")]

    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    assert response.json()["result"] == {"output": "success"}
    # Should log error but not fail request
