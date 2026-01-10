# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import MagicMock, patch

import pytest
from coreason_api.adapters import AnchorAdapter, MCPAdapter
from coreason_api.dependencies import (
    get_gatekeeper,
    get_manifest_validator,
    get_session_manager,
    get_trust_anchor,
)
from coreason_api.routers.architect import router
from coreason_manifest.validator import SchemaValidator as ManifestValidator
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_gatekeeper() -> MagicMock:
    mock = MagicMock(spec=Gatekeeper)
    mock.get_policy_instruction_for_llm.return_value = ["Policy 1"]
    return mock


@pytest.fixture
def mock_mcp() -> MagicMock:
    mock = MagicMock(spec=MCPAdapter)
    mock.execute_agent.return_value = {"result": "success"}
    return mock


@pytest.fixture
def mock_validator() -> MagicMock:
    mock = MagicMock(spec=ManifestValidator)
    mock.validate.return_value = None
    return mock


@pytest.fixture
def mock_anchor() -> MagicMock:
    mock = MagicMock(spec=AnchorAdapter)
    mock.seal.return_value = "signature_xyz"
    return mock


@pytest.fixture
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


def test_generate_vibe_unicode(client: TestClient, mock_gatekeeper: MagicMock) -> None:
    """Test prompt with Unicode characters (Emoji, Kanji, etc.)."""
    prompt = "Write code related to 🍣 and 🐍."
    response = client.post("/v1/architect/generate", json={"prompt": prompt})
    assert response.status_code == 200
    data = response.json()
    assert prompt in data["enriched_prompt"]
    assert "[GOVERNANCE POLICIES]" in data["enriched_prompt"]


def test_generate_vibe_large_prompt(client: TestClient, mock_gatekeeper: MagicMock) -> None:
    """Test extremely large prompt."""
    prompt = "code " * 10000  # ~50KB
    response = client.post("/v1/architect/generate", json={"prompt": prompt})
    assert response.status_code == 200
    data = response.json()
    assert len(data["enriched_prompt"]) > len(prompt)


def test_publish_agent_unicode_slug_match(client: TestClient) -> None:
    """Test isomorphism with Unicode slug and name."""
    with patch("coreason_manifest.loader.ManifestLoader.load_from_dict") as mock_load:
        mock_def = MagicMock()
        mock_def.metadata.name = "Café-Agent"
        mock_load.return_value = mock_def

        payload = {
            "slug": "Café-Agent",
            "agent_definition": {"metadata": {"name": "Café-Agent"}},
        }

        response = client.post("/v1/architect/publish", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "published"


def test_publish_agent_unicode_slug_mismatch(client: TestClient) -> None:
    """Test isomorphism failure with Unicode normalization difference."""
    # Assuming string equality is strict. "Cafe-Agent" != "Café-Agent"
    with patch("coreason_manifest.loader.ManifestLoader.load_from_dict") as mock_load:
        mock_def = MagicMock()
        mock_def.metadata.name = "Café-Agent"
        mock_load.return_value = mock_def

        payload = {
            "slug": "Cafe-Agent",
            "agent_definition": {"metadata": {"name": "Café-Agent"}},
        }

        response = client.post("/v1/architect/publish", json=payload)
        assert response.status_code == 400
        assert "Isomorphism check failed" in response.json()["detail"]
