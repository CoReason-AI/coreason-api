from typing import Any
from unittest.mock import MagicMock

import pytest
from coreason_identity.models import UserContext
from coreason_mcp.session_manager import SessionManager
from coreason_veritas.anchor import DeterminismInterceptor as TrustAnchor
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi import FastAPI
from fastapi.testclient import TestClient

from coreason_api.dependencies import get_gatekeeper, get_identity_manager, get_session_manager, get_trust_anchor
from coreason_api.routers.architect import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_identity() -> Any:
    mock = MagicMock()
    mock_user = UserContext(
        sub="user-1", email="test@test.com", project_context="proj-1", permissions=["generate:agent"]
    )
    mock.validate_token.return_value = mock_user
    return mock


@pytest.fixture
def mock_gatekeeper() -> Any:
    return MagicMock(spec=Gatekeeper)


@pytest.fixture
def mock_session_manager() -> Any:
    return MagicMock(spec=SessionManager)


@pytest.fixture
def mock_trust_anchor() -> Any:
    return MagicMock(spec=TrustAnchor)


def test_generate_agent(client: TestClient, mock_identity: Any, mock_gatekeeper: Any) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper

    response = client.post(
        "/v1/architect/generate", json={"prompt": "Build a finance agent"}, headers={"Authorization": "Bearer valid"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "generated_code" in data
    assert "policies_enforced" in data

    app.dependency_overrides = {}


def test_simulate_agent(client: TestClient, mock_identity: Any, mock_session_manager: Any) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_session_manager] = lambda: mock_session_manager

    response = client.post(
        "/v1/architect/simulate",
        json={"agent_code": "print('hello')", "input_data": {"val": 1}},
        headers={"Authorization": "Bearer valid"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "output" in data
    assert "logs" in data

    app.dependency_overrides = {}


def test_publish_agent_success(client: TestClient, mock_identity: Any, mock_trust_anchor: Any) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_trust_anchor] = lambda: mock_trust_anchor

    from unittest.mock import patch

    with patch("coreason_api.routers.architect.ManifestValidator") as MockValidator:
        MockValidator.return_value.validate.return_value = True

        response = client.post(
            "/v1/architect/publish",
            json={"name": "My Agent", "slug": "my-agent", "agent_code": "code", "manifest": {"some": "data"}},
            headers={"Authorization": "Bearer valid"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-published-123"
        assert data["signature"] == "sealed-signature-mock"

    app.dependency_overrides = {}


def test_publish_agent_isomorphism_fail(client: TestClient, mock_identity: Any, mock_trust_anchor: Any) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_trust_anchor] = lambda: mock_trust_anchor

    response = client.post(
        "/v1/architect/publish",
        json={"name": "My Agent", "slug": "different-slug", "agent_code": "code", "manifest": {}},
        headers={"Authorization": "Bearer valid"},
    )

    assert response.status_code == 400
    assert "isomorphic" in response.json()["detail"]

    app.dependency_overrides = {}


def test_publish_agent_manifest_fail(client: TestClient, mock_identity: Any, mock_trust_anchor: Any) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_trust_anchor] = lambda: mock_trust_anchor

    from unittest.mock import patch

    with patch("coreason_api.routers.architect.ManifestValidator") as MockValidator:
        MockValidator.return_value.validate.side_effect = Exception("Schema Error")

        response = client.post(
            "/v1/architect/publish",
            json={"name": "My Agent", "slug": "my-agent", "agent_code": "code", "manifest": {}},
            headers={"Authorization": "Bearer valid"},
        )

        assert response.status_code == 400
        assert "Manifest validation failed" in response.json()["detail"]

    app.dependency_overrides = {}


def test_publish_agent_anchor_fail(client: TestClient, mock_identity: Any, mock_trust_anchor: Any) -> None:
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_trust_anchor] = lambda: mock_trust_anchor

    # Trigger exception in trust_anchor usage (e.g. enforce_config)
    mock_trust_anchor.enforce_config.side_effect = Exception("Anchor error")

    from unittest.mock import patch

    with patch("coreason_api.routers.architect.ManifestValidator") as MockValidator:
        MockValidator.return_value.validate.return_value = True

        response = client.post(
            "/v1/architect/publish",
            json={"name": "My Agent", "slug": "my-agent", "agent_code": "code", "manifest": {"config": {}}},
            headers={"Authorization": "Bearer valid"},
        )

        # It should swallow the error and return success as per current impl
        assert response.status_code == 200

    app.dependency_overrides = {}
