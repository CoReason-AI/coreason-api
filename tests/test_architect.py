from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_api.dependencies import get_gatekeeper, get_manifest_validator, get_session_manager, get_trust_anchor
from coreason_api.main import app
from fastapi.testclient import TestClient


@pytest.fixture  # type: ignore[misc]
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture  # type: ignore[misc]
def mock_gatekeeper() -> MagicMock:
    mock = MagicMock()
    mock.get_policy_instruction_for_llm.return_value = ["Policy 1", "Policy 2"]
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_mcp() -> MagicMock:
    mock = MagicMock()
    mock.execute_agent = AsyncMock(return_value={"result": "success"})
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_validator() -> MagicMock:
    mock = MagicMock()
    mock.validate.return_value = True
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_anchor() -> MagicMock:
    mock = MagicMock()
    mock.seal.return_value = "hex_signature"
    return mock


@pytest.fixture  # type: ignore[misc]
def overrides(
    mock_gatekeeper: MagicMock, mock_mcp: MagicMock, mock_validator: MagicMock, mock_anchor: MagicMock
) -> Generator[None, None, None]:
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
    app.dependency_overrides[get_session_manager] = lambda: mock_mcp
    app.dependency_overrides[get_manifest_validator] = lambda: mock_validator
    app.dependency_overrides[get_trust_anchor] = lambda: mock_anchor
    yield
    app.dependency_overrides = {}


def test_generate_vibe(client: TestClient, overrides: None) -> None:
    response = client.post("/v1/architect/generate", json={"prompt": "Create a hello world agent"})
    assert response.status_code == 200
    data = response.json()
    assert "enriched_prompt" in data
    assert "Policy 1" in data["enriched_prompt"]
    assert data["policies"] == ["Policy 1", "Policy 2"]


def test_generate_vibe_failure(client: TestClient, mock_gatekeeper: MagicMock) -> None:
    mock_gatekeeper.get_policy_instruction_for_llm.side_effect = Exception("Gatekeeper Error")
    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper

    response = client.post("/v1/architect/generate", json={"prompt": "Create a hello world agent"})
    assert response.status_code == 500
    assert "Failed to generate vibe" in response.json()["detail"]
    app.dependency_overrides = {}


def test_simulate_agent(client: TestClient, overrides: None, mock_mcp: MagicMock) -> None:
    agent_def = {"name": "test-agent"}
    input_data = {"key": "value"}

    response = client.post("/v1/architect/simulate", json={"agent_definition": agent_def, "input_data": input_data})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify execute_agent called with correct context
    args, kwargs = mock_mcp.execute_agent.call_args
    assert kwargs["agent_id"] == "draft"
    assert kwargs["context"]["agent_definition"] == agent_def
    assert kwargs["context"]["mode"] == "simulation"


def test_simulate_agent_failure(client: TestClient, mock_mcp: MagicMock) -> None:
    mock_mcp.execute_agent = AsyncMock(side_effect=Exception("Simulation Error"))
    app.dependency_overrides[get_session_manager] = lambda: mock_mcp

    response = client.post("/v1/architect/simulate", json={"agent_definition": {}, "input_data": {}})
    assert response.status_code == 500
    assert "Simulation failed" in response.json()["detail"]
    app.dependency_overrides = {}


def test_publish_agent(client: TestClient, overrides: None, mock_validator: MagicMock, mock_anchor: MagicMock) -> None:
    # Mock ManifestLoader to return object with matching name
    with pytest.MonkeyPatch.context() as m:
        mock_loader = MagicMock()
        mock_def = MagicMock()
        mock_def.metadata.name = "my-agent"
        mock_loader.load_from_dict.return_value = mock_def
        m.setattr("coreason_manifest.loader.ManifestLoader", mock_loader)

        agent_def = {"metadata": {"name": "my-agent"}}
        response = client.post("/v1/architect/publish", json={"agent_definition": agent_def, "slug": "my-agent"})
        assert response.status_code == 200
        data = response.json()
        assert data["signature"] == "hex_signature"
        assert data["status"] == "published"

        mock_validator.validate.assert_called_once()
        mock_anchor.seal.assert_called_once()


def test_publish_agent_isomorphism_failure(client: TestClient, overrides: None) -> None:
    # Mock ManifestLoader
    with pytest.MonkeyPatch.context() as m:
        mock_loader = MagicMock()
        mock_def = MagicMock()
        mock_def.metadata.name = "other-agent"
        mock_loader.load_from_dict.return_value = mock_def
        m.setattr("coreason_manifest.loader.ManifestLoader", mock_loader)

        agent_def = {"metadata": {"name": "other-agent"}}
        response = client.post("/v1/architect/publish", json={"agent_definition": agent_def, "slug": "my-agent"})
        assert response.status_code == 400
        assert "Isomorphism check failed" in response.json()["detail"]


def test_publish_agent_schema_failure(client: TestClient, mock_validator: MagicMock) -> None:
    mock_validator.validate.side_effect = Exception("Schema Error")
    app.dependency_overrides[get_manifest_validator] = lambda: mock_validator

    response = client.post("/v1/architect/publish", json={"agent_definition": {}, "slug": "my-agent"})
    assert response.status_code == 400
    assert "Invalid agent definition" in response.json()["detail"]
    app.dependency_overrides = {}


def test_publish_agent_parse_failure(client: TestClient, overrides: None) -> None:
    # Mock ManifestLoader to raise Exception
    with pytest.MonkeyPatch.context() as m:
        mock_loader = MagicMock()
        mock_loader.load_from_dict.side_effect = Exception("Parsing Error")
        m.setattr("coreason_manifest.loader.ManifestLoader", mock_loader)

        agent_def = {"metadata": {"name": "my-agent"}}
        response = client.post("/v1/architect/publish", json={"agent_definition": agent_def, "slug": "my-agent"})
        assert response.status_code == 400
        assert "Failed to parse agent definition" in response.json()["detail"]


def test_publish_agent_seal_failure(client: TestClient, overrides: None, mock_anchor: MagicMock) -> None:
    # Mock ManifestLoader to return valid object
    with pytest.MonkeyPatch.context() as m:
        mock_loader = MagicMock()
        mock_def = MagicMock()
        mock_def.metadata.name = "my-agent"
        mock_loader.load_from_dict.return_value = mock_def
        m.setattr("coreason_manifest.loader.ManifestLoader", mock_loader)

        mock_anchor.seal.side_effect = Exception("Sealing Error")

        agent_def = {"metadata": {"name": "my-agent"}}
        response = client.post("/v1/architect/publish", json={"agent_definition": agent_def, "slug": "my-agent"})
        assert response.status_code == 500
        assert "Failed to seal artifact" in response.json()["detail"]
