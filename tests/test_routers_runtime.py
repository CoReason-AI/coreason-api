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
from unittest.mock import MagicMock

import pytest
from coreason_budget.guard import BudgetGuard
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
def mock_gatekeeper() -> Any:
    return MagicMock(spec=Gatekeeper)


@pytest.fixture
def mock_auditor() -> Any:
    return MagicMock(spec=Auditor)


@pytest.fixture
def mock_budget() -> Any:
    m = MagicMock(spec=BudgetGuard)
    m.check.return_value = True
    return m


@pytest.fixture
def mock_session() -> Any:
    return MagicMock(spec=SessionManager)


def test_run_agent_auth_missing(client: TestClient) -> None:
    response = client.post("/v1/run/agent-123", json={"input_data": {}})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header"


def test_run_agent_auth_invalid(client: TestClient) -> None:
    mock_identity = MagicMock()
    mock_identity.validate_token.side_effect = Exception("Invalid signature")

    app.dependency_overrides[get_identity_manager] = lambda: mock_identity

    response = client.post("/v1/run/agent-123", json={"input_data": {}}, headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"
    app.dependency_overrides = {}


def test_run_agent_auth_success(
    client: TestClient, mock_gatekeeper: Any, mock_auditor: Any, mock_budget: Any, mock_session: Any
) -> None:
    mock_identity = MagicMock()
    mock_user = UserContext(
        sub="user-123", email="test@coreason.ai", project_context="proj-1", permissions=["run:agent"]
    )
    mock_identity.validate_token.return_value = mock_user

    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    # Override other deps to avoid failures (like Gatekeeper init)
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
    app.dependency_overrides[get_auditor] = lambda: mock_auditor
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    response = client.post("/v1/run/agent-123", json={"input_data": {}}, headers={"Authorization": "Bearer valid"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "execution_id" in data

    app.dependency_overrides = {}
