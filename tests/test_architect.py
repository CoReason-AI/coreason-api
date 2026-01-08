
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from coreason_api.routers.architect import router
from coreason_api.dependencies import get_identity_manager, get_session_manager

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)

    # Overrides
    mock_identity = AsyncMock()
    mock_session = AsyncMock()

    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    return TestClient(app)

def test_generate_agent(client):
    # Mock Gatekeeper
    with patch("coreason_api.routers.architect.Gatekeeper") as MockGatekeeper:
        MockGatekeeper.return_value.get_policy_instruction_for_llm.return_value = "No endless loops."

        response = client.post("/v1/architect/generate", json={"prompt": "Write a hello world"})
        assert response.status_code == 200
        data = response.json()
        assert "No endless loops." in data["generated_agent_code"]
        assert data["policy_compliance"] is True

def test_simulate_agent(client):
    pass

@pytest.fixture
def mock_deps():
    mock_identity = AsyncMock()
    mock_session = AsyncMock()
    mock_session.execute_agent.return_value = "simulation-result"
    return mock_identity, mock_session

def test_simulate_agent_refined(mock_deps):
    mock_identity, mock_session = mock_deps
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    client = TestClient(app)

    response = client.post("/v1/architect/simulate", json={
        "agent_code": {"code": "print('hi')"},
        "input_data": {"x": 1}
    })

    assert response.status_code == 200
    assert response.json()["result"] == "simulation-result"

def test_publish_agent_success(mock_deps):
    mock_identity, _ = mock_deps
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity

    client = TestClient(app)

    # Mock ManifestValidator and TrustAnchor
    with patch("coreason_api.routers.architect.ManifestValidator"), \
         patch("coreason_api.routers.architect.TrustAnchor") as MockAnchor:

        # Validator passes (no exception)

        # Anchor seals
        mock_artifact = MagicMock()
        mock_artifact.id = "art-1"
        mock_artifact.signature = "sig-1"
        MockAnchor.return_value.seal.return_value = mock_artifact

        payload = {
            "slug": "my-agent",
            "name": "my-agent",
            "agent_manifest": {"version": "1.0"}
        }

        response = client.post("/v1/architect/publish", json=payload)
        assert response.status_code == 200
        assert response.json() == {"artifact_id": "art-1", "signature": "sig-1"}

def test_publish_agent_isomorphism_fail(mock_deps):
    mock_identity, _ = mock_deps
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    payload = {
        "slug": "my-agent",
        "name": "Other Name",
        "agent_manifest": {}
    }

    response = client.post("/v1/architect/publish", json=payload)
    assert response.status_code == 400
    assert "Isomorphism" in response.json()["detail"]
