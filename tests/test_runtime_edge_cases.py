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


@pytest.fixture
def mock_identity() -> MagicMock:
    mock = MagicMock(spec=IdentityManager)
    user_context = MagicMock()
    user_context.user_id = "test-user"
    mock.validate_token = AsyncMock(return_value=user_context)
    return mock


@pytest.fixture
def mock_budget() -> MagicMock:
    mock = MagicMock(spec=BudgetAdapter)
    mock.check_quota = AsyncMock(return_value=True)
    mock.record_transaction = AsyncMock()
    return mock


@pytest.fixture
def mock_auditor() -> MagicMock:
    mock = MagicMock(spec=Auditor)
    mock.log_event = AsyncMock()
    return mock


@pytest.fixture
def mock_mcp() -> MagicMock:
    mock = MagicMock(spec=MCPAdapter)
    mock.execute_agent = AsyncMock(return_value={"output": "success"})
    return mock


@pytest.fixture
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


def test_run_agent_negative_cost(client: TestClient) -> None:
    """Test that negative cost estimate is rejected by Pydantic validation."""
    headers = {"Authorization": "Bearer token"}
    payload = {"input_data": {}, "cost_estimate": -1.0}
    response = client.post("/v1/run/agent-edge", json=payload, headers=headers)
    assert response.status_code == 422
    assert "Input should be greater than or equal to 0" in response.text


def test_run_agent_huge_cost(client: TestClient, mock_budget: MagicMock) -> None:
    """Test extremely high cost. Should fail budget check if configured, but pass if mocked true."""
    headers = {"Authorization": "Bearer token"}
    payload = {"input_data": {}, "cost_estimate": 1e9}  # 1 Billion units

    # Mock budget to reject this specific amount
    mock_budget.check_quota.side_effect = lambda user_id, cost_estimate: cost_estimate < 1000

    response = client.post("/v1/run/agent-edge", json=payload, headers=headers)
    assert response.status_code == 402
    assert "Insufficient quota" in response.json()["detail"]


def test_run_agent_malformed_json_input(client: TestClient) -> None:
    """Test invalid JSON body."""
    headers = {"Authorization": "Bearer token"}
    response = client.post(
        "/v1/run/agent-edge", content="{invalid-json", headers={"Content-Type": "application/json", **headers}
    )
    assert response.status_code == 422


def test_run_agent_empty_agent_id(client: TestClient) -> None:
    """Test empty agent ID in path. FastAPI redirects or 404s depending on config."""
    headers = {"Authorization": "Bearer token"}
    # requests to /v1/run// are typically normalized or 404.
    response = client.post("/v1/run//", json={"input_data": {}}, headers=headers)
    assert response.status_code in (307, 404, 405)


def test_run_agent_injection_in_context(client: TestClient, mock_mcp: MagicMock) -> None:
    """Test that context keys cannot overwrite critical keys like user_id."""
    headers = {"Authorization": "Bearer token"}
    # Attempt to spoof user_id via session_context
    payload = {"input_data": {}, "session_context": {"user_id": "admin", "custom": "value"}}

    response = client.post("/v1/run/agent-edge", json=payload, headers=headers)
    assert response.status_code == 200

    # Check that the adapter was called with the AUTHENTICATED user_id, not the spoofed one.
    # The code does: ctx_data["user_id"] = user_id
    # So it should overwrite the injected "admin" with "test-user".

    call_kwargs = mock_mcp.execute_agent.call_args[1]
    context = call_kwargs["context"]
    assert context["user_id"] == "test-user"
    assert context["custom"] == "value"
