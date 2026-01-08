import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from coreason_api.main import app
from coreason_api.dependencies import get_identity_manager, get_budget_guard, get_gatekeeper, get_auditor, get_session_manager, get_redis_ledger, get_trust_anchor
from coreason_identity.models import UserContext
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from coreason_veritas.auditor import IERLogger as Auditor
from coreason_mcp.session_manager import SessionManager
from coreason_veritas.anchor import DeterminismInterceptor as TrustAnchor

@pytest.fixture
def client():
    # Using context manager to ensure lifespan events run
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

@pytest.fixture
def mock_deps():
    # Setup all mocks
    identity = MagicMock()
    user = UserContext(sub="user-1", email="test@test.com", project_context="proj-1", permissions=[])
    identity.validate_token.return_value = user

    budget = AsyncMock()
    budget.check.return_value = True
    budget.connect.return_value = None # For readiness

    gatekeeper = MagicMock(spec=Gatekeeper)
    auditor = MagicMock(spec=Auditor)
    session = MagicMock(spec=SessionManager)
    trust_anchor = MagicMock(spec=TrustAnchor)
    ledger = AsyncMock()

    return {
        "identity": identity,
        "budget": budget,
        "gatekeeper": gatekeeper,
        "auditor": auditor,
        "session": session,
        "trust_anchor": trust_anchor,
        "ledger": ledger
    }

def test_health_check(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_readiness_check(client, mock_deps):
    app.dependency_overrides[get_redis_ledger] = lambda: mock_deps["ledger"]
    response = client.get("/health/ready")
    assert response.status_code == 200
    app.dependency_overrides = {}

def test_global_exception_handler(client):
    # Route that triggers unhandled exception

    # We define a temporary route on the app to force an exception
    from fastapi import APIRouter
    router = APIRouter()

    @router.get("/force-error")
    def force_error():
        raise ValueError("Boom")

    app.include_router(router)

    response = client.get("/force-error")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal Server Error"

def test_full_flow_integration(client, mock_deps):
    # Test one full flow through main app entry point
    app.dependency_overrides[get_identity_manager] = lambda: mock_deps["identity"]
    app.dependency_overrides[get_budget_guard] = lambda: mock_deps["budget"]
    app.dependency_overrides[get_gatekeeper] = lambda: mock_deps["gatekeeper"]
    app.dependency_overrides[get_auditor] = lambda: mock_deps["auditor"]
    app.dependency_overrides[get_session_manager] = lambda: mock_deps["session"]

    response = client.post(
        "/v1/run/agent-main",
        json={"input_data": {}, "estimated_cost": 1.0},
        headers={"Authorization": "Bearer valid"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "X-Trace-ID" in response.headers

    app.dependency_overrides = {}
