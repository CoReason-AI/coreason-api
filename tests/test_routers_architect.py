from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from coreason_api.dependencies import get_gatekeeper, get_mcp
from coreason_api.routers import architect

app = FastAPI()
app.include_router(architect.router)
client = TestClient(app)

mock_gatekeeper = MagicMock()
mock_gatekeeper.get_policy_instruction_for_llm.return_value = ["No infinite loops", "No crypto mining"]

mock_mcp = MagicMock()
mock_mcp.execute_agent = AsyncMock(return_value={"simulation": "success"})

app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper
app.dependency_overrides[get_mcp] = lambda: mock_mcp


def test_generate_agent():
    response = client.post("/v1/architect/generate", json={"prompt": "Build a trading bot"})
    assert response.status_code == 200
    assert "No infinite loops" in response.json()["enhanced_prompt"]


def test_simulate_agent():
    response = client.post(
        "/v1/architect/simulate", json={"agent_draft": {"code": "print('hello')"}, "input_data": {"x": 1}}
    )
    assert response.status_code == 200
    assert response.json()["result"] == {"simulation": "success"}


def test_publish_agent_success():
    manifest = {"name": "agent-x", "slug": "agent-x", "version": "1.0"}

    with (
        patch("coreason_api.routers.architect.SchemaValidator") as MockValidator,
        patch("coreason_api.routers.architect.TrustAnchor") as MockAnchor,
    ):
        MockValidator.return_value.validate.return_value = True
        MockAnchor.return_value.seal_artifact.return_value = {"signed": "yes"}

        response = client.post("/v1/architect/publish", json={"manifest": manifest, "signature": "sig"})
        assert response.status_code == 200
        assert response.json()["status"] == "published"


def test_publish_agent_isomorphism_fail():
    manifest = {"name": "agent-x", "slug": "agent-y", "version": "1.0"}
    # Schema validation passes
    with patch("coreason_api.routers.architect.SchemaValidator"):
        response = client.post("/v1/architect/publish", json={"manifest": manifest, "signature": "sig"})
        assert response.status_code == 400
        assert "Isomorphism violation" in response.json()["detail"]
