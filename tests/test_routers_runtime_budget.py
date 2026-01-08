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
def client():
    return TestClient(app)


@pytest.fixture
def mock_identity():
    mock = MagicMock()
    mock_user = UserContext(
        sub="user-123", email="test@coreason.ai", project_context="proj-1", permissions=["run:agent"]
    )
    mock.validate_token.return_value = mock_user
    return mock


@pytest.fixture
def mock_budget():
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_gatekeeper():
    mock = MagicMock(spec=Gatekeeper)
    return mock


@pytest.fixture
def mock_auditor():
    return MagicMock(spec=Auditor)


@pytest.fixture
def mock_session():
    return MagicMock(spec=SessionManager)


def test_run_agent_budget_exceeded(client, mock_identity, mock_budget, mock_gatekeeper, mock_auditor, mock_session):
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
    client, mock_identity, mock_budget, mock_gatekeeper, mock_auditor, mock_session
):
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


def test_run_agent_budget_success(client, mock_identity, mock_budget, mock_gatekeeper, mock_auditor, mock_session):
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
    client, mock_identity, mock_budget, mock_gatekeeper, mock_auditor, mock_session
):
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
