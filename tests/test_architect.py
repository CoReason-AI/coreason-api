# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coreason_api.adapters import AnchorAdapter, MCPAdapter
from coreason_api.dependencies import (
    get_gatekeeper,
    get_manifest_validator,
    get_session_manager,
    get_trust_anchor,
)
from coreason_api.routers.architect import router

# We don't import AgentDefinition here to avoid issues if we can't inspect it easily in tests
# from coreason_manifest.models import AgentDefinition
from coreason_manifest.validator import SchemaValidator as ManifestValidator
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture  # type: ignore[misc]
def mock_gatekeeper() -> MagicMock:
    mock = MagicMock(spec=Gatekeeper)
    mock.get_policy_instruction_for_llm.return_value = ["Policy 1", "Policy 2"]
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_mcp() -> MagicMock:
    mock = MagicMock(spec=MCPAdapter)
    mock.execute_agent = AsyncMock(return_value={"output": "simulated"})
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_validator() -> MagicMock:
    mock = MagicMock(spec=ManifestValidator)
    mock.validate.return_value = None
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_anchor() -> MagicMock:
    mock = MagicMock(spec=AnchorAdapter)
    mock.seal.return_value = "signature_xyz"
    return mock


@pytest.fixture  # type: ignore[misc]
def client(
    mock_gatekeeper: MagicMock,
    mock_mcp: MagicMock,
    mock_validator: MagicMock,
    mock_anchor: MagicMock,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
    app.dependency_overrides[get_session_manager] = lambda: mock_mcp
    app.dependency_overrides[get_manifest_validator] = lambda: mock_validator
    app.dependency_overrides[get_trust_anchor] = lambda: mock_anchor

    return TestClient(app)


def test_generate_vibe(client: TestClient, mock_gatekeeper: MagicMock) -> None:
    response = client.post("/v1/architect/generate", json={"prompt": "Write code"})
    assert response.status_code == 200
    data = response.json()
    assert "Policy 1" in data["enriched_prompt"]
    assert data["policies"] == ["Policy 1", "Policy 2"]
    mock_gatekeeper.get_policy_instruction_for_llm.assert_called_once()


def test_generate_vibe_failure(client: TestClient, mock_gatekeeper: MagicMock) -> None:
    mock_gatekeeper.get_policy_instruction_for_llm.side_effect = Exception("Policy Error")
    response = client.post("/v1/architect/generate", json={"prompt": "Write code"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to generate vibe"


def test_simulate_agent(client: TestClient, mock_mcp: MagicMock) -> None:
    response = client.post(
        "/v1/architect/simulate",
        json={"agent_definition": {"name": "test"}, "input_data": {"x": 1}},
    )
    assert response.status_code == 200
    assert response.json()["result"] == {"output": "simulated"}

    mock_mcp.execute_agent.assert_called_with(
        agent_id="draft",
        input_data={"x": 1},
        context={"agent_definition": {"name": "test"}, "mode": "simulation"},
    )


def test_simulate_agent_failure(client: TestClient, mock_mcp: MagicMock) -> None:
    mock_mcp.execute_agent.side_effect = Exception("Sim Error")
    response = client.post(
        "/v1/architect/simulate",
        json={"agent_definition": {"name": "test"}, "input_data": {"x": 1}},
    )
    assert response.status_code == 500
    assert "Simulation failed" in response.json()["detail"]


def test_publish_agent_success(client: TestClient, mock_validator: MagicMock, mock_anchor: MagicMock) -> None:
    agent_def = {"metadata": {"name": "my-agent"}, "spec": {}}

    # Mock ManifestLoader in the original module
    with patch("coreason_manifest.loader.ManifestLoader.load_from_dict") as mock_load:
        # We use a plain Mock or MagicMock and ensure it doesn't try to spec against a class we can't fully inspect
        mock_agent = MagicMock()
        mock_agent.metadata.name = "my-agent"
        mock_load.return_value = mock_agent

        response = client.post(
            "/v1/architect/publish",
            json={"agent_definition": agent_def, "slug": "my-agent"},
        )

        assert response.status_code == 200
        assert response.json()["signature"] == "signature_xyz"
        assert response.json()["status"] == "published"

        mock_validator.validate.assert_called_with(agent_def)
        mock_anchor.seal.assert_called_with(agent_def)


def test_publish_agent_validation_error(client: TestClient, mock_validator: MagicMock) -> None:
    mock_validator.validate.side_effect = Exception("Invalid Schema")
    response = client.post(
        "/v1/architect/publish",
        json={"agent_definition": {}, "slug": "slug"},
    )
    assert response.status_code == 400
    assert "Invalid agent definition" in response.json()["detail"]


def test_publish_agent_isomorphism_error(client: TestClient) -> None:
    with patch("coreason_manifest.loader.ManifestLoader.load_from_dict") as mock_load:
        mock_agent = MagicMock()
        mock_agent.metadata.name = "real-name"
        mock_load.return_value = mock_agent

        response = client.post(
            "/v1/architect/publish",
            json={"agent_definition": {}, "slug": "wrong-slug"},
        )
        assert response.status_code == 400
        assert "Isomorphism check failed" in response.json()["detail"]


def test_publish_agent_parse_error(client: TestClient) -> None:
    with patch("coreason_manifest.loader.ManifestLoader.load_from_dict") as mock_load:
        mock_load.side_effect = Exception("Parse Error")

        response = client.post(
            "/v1/architect/publish",
            json={"agent_definition": {}, "slug": "slug"},
        )
        assert response.status_code == 400
        assert "Failed to parse agent definition" in response.json()["detail"]


def test_publish_agent_sealing_error(client: TestClient, mock_anchor: MagicMock) -> None:
    with patch("coreason_manifest.loader.ManifestLoader.load_from_dict") as mock_load:
        mock_agent = MagicMock()
        mock_agent.metadata.name = "slug"
        mock_load.return_value = mock_agent

        mock_anchor.seal.side_effect = Exception("Seal Error")

        response = client.post(
            "/v1/architect/publish",
            json={"agent_definition": {}, "slug": "slug"},
        )
        assert response.status_code == 500
        assert "Failed to seal artifact" in response.json()["detail"]


# --- Edge Cases ---


def test_generate_vibe_empty_prompt(client: TestClient, mock_gatekeeper: MagicMock) -> None:
    response = client.post("/v1/architect/generate", json={"prompt": ""})
    assert response.status_code == 200
    data = response.json()
    assert "[GOVERNANCE POLICIES]" in data["enriched_prompt"]


def test_publish_agent_slug_case_mismatch(client: TestClient) -> None:
    # Verify strict equality (Case Sensitive)
    with patch("coreason_manifest.loader.ManifestLoader.load_from_dict") as mock_load:
        mock_agent = MagicMock()
        mock_agent.metadata.name = "MyAgent"
        mock_load.return_value = mock_agent

        response = client.post(
            "/v1/architect/publish",
            json={"agent_definition": {}, "slug": "myagent"},
        )
        assert response.status_code == 400
        assert "Isomorphism check failed" in response.json()["detail"]
