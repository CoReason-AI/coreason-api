from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_identity_manager,
    get_session_manager,
)
from coreason_api.main import app

client = TestClient(app)


@pytest.fixture
def mock_dependencies():
    # Identity Mock
    identity_instance = AsyncMock()
    user_context = MagicMock()
    user_context.user_id = "test_user_id"
    identity_instance.validate_token.return_value = user_context

    # Budget Mock
    budget_instance = AsyncMock()
    budget_instance.check_quota.return_value = True

    # Auditor Mock
    auditor_instance = AsyncMock()

    # MCP Mock
    mcp_instance = AsyncMock()
    mcp_instance.execute_agent.return_value = {"status": "success", "output": "test_output"}

    # Overrides
    app.dependency_overrides[get_identity_manager] = lambda: identity_instance
    app.dependency_overrides[get_budget_guard] = lambda: budget_instance
    app.dependency_overrides[get_auditor] = lambda: auditor_instance
    app.dependency_overrides[get_session_manager] = lambda: mcp_instance

    yield {
        "identity": identity_instance,
        "budget": budget_instance,
        "auditor": auditor_instance,
        "mcp": mcp_instance,
    }

    # Clean up overrides
    app.dependency_overrides = {}


def test_run_agent_success(mock_dependencies):
    response = client.post(
        "/v1/run/test-agent-123",
        json={"input_data": {"query": "hello"}, "cost_estimate": 5.0},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["result"] == {"status": "success", "output": "test_output"}
    assert "transaction_id" in data

    # Verify Chain of Command

    # 2. Auth
    mock_dependencies["identity"].validate_token.assert_called_once_with("Bearer valid-token")

    # 4. Budget Check
    mock_dependencies["budget"].check_quota.assert_called_once_with(user_id="test_user_id", cost_estimate=5.0)

    # 5. Audit Start
    mock_dependencies["auditor"].log_event.assert_any_call(
        "EXECUTION_START", {"agent_id": "test-agent-123", "user_id": "test_user_id", "cost_estimate": 5.0}
    )

    # 6. Execution
    mock_dependencies["mcp"].execute_agent.assert_called_once()
    call_args = mock_dependencies["mcp"].execute_agent.call_args
    assert call_args.kwargs["agent_id"] == "test-agent-123"
    assert call_args.kwargs["input_data"] == {"query": "hello"}

    # 7. Settlement (Background Task)
    # Background tasks are executed after the response is sent.
    # TestClient in Starlette/FastAPI runs background tasks automatically.
    # We verify it was scheduled/called.
    mock_dependencies["budget"].record_transaction.assert_called_once_with(
        user_id="test_user_id",
        amount=5.0,
        context={"agent_id": "test-agent-123", "transaction_type": "agent_execution"},
    )

    # 8. Audit End
    mock_dependencies["auditor"].log_event.assert_any_call(
        "EXECUTION_END", {"agent_id": "test-agent-123", "user_id": "test_user_id", "status": "success"}
    )


def test_run_agent_auth_failure(mock_dependencies):
    mock_dependencies["identity"].validate_token.side_effect = Exception("Invalid token")

    response = client.post(
        "/v1/run/test-agent-123",
        json={"input_data": {"query": "hello"}},
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"

    # Ensure execution didn't happen
    mock_dependencies["mcp"].execute_agent.assert_not_called()


def test_run_agent_missing_auth(mock_dependencies):
    response = client.post("/v1/run/test-agent-123", json={"input_data": {"query": "hello"}})

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header"


def test_run_agent_budget_failure(mock_dependencies):
    mock_dependencies["budget"].check_quota.return_value = False

    response = client.post(
        "/v1/run/test-agent-123",
        json={"input_data": {"query": "hello"}, "cost_estimate": 100.0},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 402
    assert response.json()["detail"] == "Insufficient quota"

    # Ensure execution didn't happen
    mock_dependencies["mcp"].execute_agent.assert_not_called()


def test_run_agent_execution_failure(mock_dependencies):
    mock_dependencies["mcp"].execute_agent.side_effect = Exception("MCP Error")

    response = client.post(
        "/v1/run/test-agent-123",
        json={"input_data": {"query": "hello"}},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 500
    assert "Agent execution failed" in response.json()["detail"]

    # Verify Audit Failure Log
    mock_dependencies["auditor"].log_event.assert_any_call(
        "EXECUTION_FAILED", {"agent_id": "test-agent-123", "user_id": "test_user_id", "error": "MCP Error"}
    )
