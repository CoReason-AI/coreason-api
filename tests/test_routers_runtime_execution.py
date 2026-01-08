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
from coreason_api.middleware import TraceIDMiddleware
from coreason_api.routers.runtime import router

app = FastAPI()
app.add_middleware(TraceIDMiddleware)
app.include_router(router)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_deps() -> dict[str, Any]:
    identity = MagicMock()
    user = UserContext(sub="user-1", email="test@test.com", project_context="proj-1", permissions=[])
    identity.validate_token.return_value = user

    budget = AsyncMock()
    budget.check.return_value = True

    gatekeeper = MagicMock(spec=Gatekeeper)
    auditor = MagicMock(spec=Auditor)
    session = MagicMock(spec=SessionManager)

    return {"identity": identity, "budget": budget, "gatekeeper": gatekeeper, "auditor": auditor, "session": session}


def test_run_agent_full_flow_success(client: TestClient, mock_deps: dict[str, Any]) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_deps["identity"]
    app.dependency_overrides[get_budget_guard] = lambda: mock_deps["budget"]
    app.dependency_overrides[get_gatekeeper] = lambda: mock_deps["gatekeeper"]
    app.dependency_overrides[get_auditor] = lambda: mock_deps["auditor"]
    app.dependency_overrides[get_session_manager] = lambda: mock_deps["session"]

    response = client.post(
        "/v1/run/agent-123",
        json={"input_data": {}, "estimated_cost": 0.5},
        headers={"Authorization": "Bearer valid", "X-Trace-ID": "trace-123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["execution_id"] == "trace-123"

    app.dependency_overrides = {}


def test_run_agent_audit_failure_swallowed(client: TestClient, mock_deps: dict[str, Any]) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_deps["identity"]
    app.dependency_overrides[get_budget_guard] = lambda: mock_deps["budget"]
    app.dependency_overrides[get_gatekeeper] = lambda: mock_deps["gatekeeper"]
    app.dependency_overrides[get_auditor] = lambda: mock_deps["auditor"]
    app.dependency_overrides[get_session_manager] = lambda: mock_deps["session"]

    mock_deps["auditor"].log_llm_transaction.side_effect = Exception("Log failed")

    response = client.post("/v1/run/agent-123", json={"input_data": {}}, headers={"Authorization": "Bearer valid"})

    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    app.dependency_overrides = {}


def test_run_agent_settlement_failure_swallowed(client: TestClient, mock_deps: dict[str, Any]) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_deps["identity"]
    app.dependency_overrides[get_budget_guard] = lambda: mock_deps["budget"]
    app.dependency_overrides[get_gatekeeper] = lambda: mock_deps["gatekeeper"]
    app.dependency_overrides[get_auditor] = lambda: mock_deps["auditor"]
    app.dependency_overrides[get_session_manager] = lambda: mock_deps["session"]

    # Budget check passes, but charge fails
    mock_deps["budget"].check.return_value = True
    mock_deps["budget"].charge.side_effect = Exception("Charge failed")

    response = client.post("/v1/run/agent-123", json={"input_data": {}}, headers={"Authorization": "Bearer valid"})

    # Should still succeed (fire and forget)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    app.dependency_overrides = {}
