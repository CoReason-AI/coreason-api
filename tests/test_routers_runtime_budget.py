# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_identity.models import UserContext
from coreason_mcp.session_manager import SessionManager
from coreason_veritas.auditor import IERLogger as Auditor
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi import FastAPI
from fastapi.testclient import TestClient

from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_gatekeeper,
    get_identity_manager,
    get_session_manager,
)
from coreason_api.routers.runtime import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_identity() -> Any:
    mock = MagicMock()
    mock_user = UserContext(
        sub="user-123", email="test@coreason.ai", project_context="proj-1", permissions=["run:agent"]
    )
    mock.validate_token.return_value = mock_user
    return mock


@pytest.fixture
def mock_budget() -> Any:
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_gatekeeper() -> Any:
    mock = MagicMock(spec=Gatekeeper)
    return mock


@pytest.fixture
def mock_auditor() -> Any:
    return MagicMock(spec=Auditor)


@pytest.fixture
def mock_session() -> Any:
    return MagicMock(spec=SessionManager)


def test_run_agent_budget_exceeded(
    client: TestClient, mock_identity: Any, mock_budget: Any, mock_gatekeeper: Any, mock_auditor: Any, mock_session: Any
) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
    app.dependency_overrides[get_auditor] = lambda: mock_auditor
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    # Simulate budget exceeded exception
    mock_budget.check.side_effect = Exception("BudgetExceededError")

    response = client.post(
        "/v1/run/agent-123", json={"input_data": {}, "estimated_cost": 10.0}, headers={"Authorization": "Bearer valid"}
    )

    if response.status_code == 422:
        print(response.json())

    assert response.status_code == 402
    assert response.json()["detail"] == "Budget quota exceeded"

    app.dependency_overrides = {}


def test_run_agent_budget_check_failure_generic(
    client: TestClient, mock_identity: Any, mock_budget: Any, mock_gatekeeper: Any, mock_auditor: Any, mock_session: Any
) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
    app.dependency_overrides[get_auditor] = lambda: mock_auditor
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    # Simulate connection error
    mock_budget.check.side_effect = Exception("Redis connection failed")

    response = client.post("/v1/run/agent-123", json={"input_data": {}}, headers={"Authorization": "Bearer valid"})

    assert response.status_code == 402  # Fail closed
    assert response.json()["detail"] == "Budget check failed"

    app.dependency_overrides = {}


def test_run_agent_budget_success(
    client: TestClient, mock_identity: Any, mock_budget: Any, mock_gatekeeper: Any, mock_auditor: Any, mock_session: Any
) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
    app.dependency_overrides[get_auditor] = lambda: mock_auditor
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    mock_budget.check.return_value = True

    response = client.post(
        "/v1/run/agent-123", json={"input_data": {}, "estimated_cost": 1.0}, headers={"Authorization": "Bearer valid"}
    )

    if response.status_code == 422:
        print(response.json())

    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    mock_budget.check.assert_called_with(user_id="user-123", project_id="proj-1", estimated_cost=1.0)

    app.dependency_overrides = {}


def test_run_agent_budget_exceeded_bool_false(
    client: TestClient, mock_identity: Any, mock_budget: Any, mock_gatekeeper: Any, mock_auditor: Any, mock_session: Any
) -> None:
    # Test case where check returns False instead of raising exception
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
    app.dependency_overrides[get_auditor] = lambda: mock_auditor
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    mock_budget.check.return_value = False

    response = client.post(
        "/v1/run/agent-123", json={"input_data": {}, "estimated_cost": 1.0}, headers={"Authorization": "Bearer valid"}
    )

    assert response.status_code == 402
    assert response.json()["detail"] == "Budget quota exceeded"

    app.dependency_overrides = {}
