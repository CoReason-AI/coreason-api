import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from coreason_api.routers.runtime import router, verify_auth
from coreason_api.dependencies import get_identity_manager, get_budget_guard, get_gatekeeper, get_auditor, get_session_manager, get_redis_ledger
from coreason_identity.models import UserContext
from coreason_budget.guard import BudgetGuard
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from coreason_veritas.auditor import IERLogger as Auditor
from coreason_mcp.session_manager import SessionManager

app = FastAPI()
app.include_router(router)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_gatekeeper():
    return MagicMock(spec=Gatekeeper)

@pytest.fixture
def mock_auditor():
    return MagicMock(spec=Auditor)

@pytest.fixture
def mock_budget():
    m = MagicMock(spec=BudgetGuard)
    m.check.return_value = True
    return m

@pytest.fixture
def mock_session():
    return MagicMock(spec=SessionManager)

def test_run_agent_auth_missing(client):
    response = client.post("/v1/run/agent-123", json={"input_data": {}})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header"

def test_run_agent_auth_invalid(client):
    mock_identity = MagicMock()
    mock_identity.validate_token.side_effect = Exception("Invalid signature")

    app.dependency_overrides[get_identity_manager] = lambda: mock_identity

    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}},
        headers={"Authorization": "Bearer invalid"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"
    app.dependency_overrides = {}

def test_run_agent_auth_success(client, mock_gatekeeper, mock_auditor, mock_budget, mock_session):
    mock_identity = MagicMock()
    mock_user = UserContext(
        sub="user-123",
        email="test@coreason.ai",
        project_context="proj-1",
        permissions=["run:agent"]
    )
    mock_identity.validate_token.return_value = mock_user

    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    # Override other deps to avoid failures (like Gatekeeper init)
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
    app.dependency_overrides[get_auditor] = lambda: mock_auditor
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}},
        headers={"Authorization": "Bearer valid"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "execution_id" in data

    app.dependency_overrides = {}
