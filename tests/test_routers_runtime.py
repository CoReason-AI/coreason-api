from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from coreason_api.dependencies import get_auditor, get_budget, get_gatekeeper, get_identity, get_mcp
from coreason_api.routers import runtime

app = FastAPI()
app.include_router(runtime.router)

client = TestClient(app)

# Mocks
mock_identity = MagicMock()
mock_identity.validate_token = AsyncMock(return_value={"user_id": "test_user"})

mock_budget = MagicMock()
mock_budget.check_quota = AsyncMock(return_value=True)
mock_budget.record_transaction = AsyncMock()

mock_auditor = MagicMock()
mock_auditor.log_event = AsyncMock()

mock_mcp = MagicMock()
mock_mcp.execute_agent = AsyncMock(return_value={"output": "success"})

mock_gatekeeper = MagicMock()

# Overrides
app.dependency_overrides[get_identity] = lambda: mock_identity
app.dependency_overrides[get_budget] = lambda: mock_budget
app.dependency_overrides[get_auditor] = lambda: mock_auditor
app.dependency_overrides[get_mcp] = lambda: mock_mcp
app.dependency_overrides[get_gatekeeper] = lambda: mock_gatekeeper


def test_run_agent_success():
    response = client.post(
        "/v1/run/agent-123", json={"input_data": {"query": "foo"}}, headers={"Authorization": "Bearer valid-token"}
    )
    assert response.status_code == 200
    assert response.json()["result"] == {"output": "success"}

    # Check calls
    assert mock_identity.validate_token.call_count >= 1  # Middleware might trigger calls too? No, only router.
    mock_budget.check_quota.assert_called_with("test_user", 0.01)
    mock_auditor.log_event.assert_called()
    mock_mcp.execute_agent.assert_called()
    # Settlement is background task, might not run immediately in test client context without explicit handling?
    # FastAPI TestClient runs background tasks.


def test_run_agent_insufficient_funds():
    mock_budget.check_quota.return_value = False

    response = client.post(
        "/v1/run/agent-123", json={"input_data": {"query": "foo"}}, headers={"Authorization": "Bearer valid-token"}
    )
    assert response.status_code == 402
    assert "Insufficient budget" in response.json()["detail"]

    # Reset
    mock_budget.check_quota.return_value = True


def test_run_agent_auth_failure():
    mock_identity.validate_token.side_effect = Exception("Invalid token")

    response = client.post(
        "/v1/run/agent-123", json={"input_data": {"query": "foo"}}, headers={"Authorization": "Bearer bad-token"}
    )
    assert response.status_code == 401

    # Reset
    mock_identity.validate_token.side_effect = None
