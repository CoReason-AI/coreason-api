
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from coreason_api.routers.runtime import router
from coreason_api.dependencies import (
    get_identity_manager, get_budget_guard, get_auditor, get_session_manager
)
from coreason_api.middleware import TraceIDMiddleware

# Define a minimal UserContext mock since we import it for type hinting
class MockUserContext:
    def __init__(self, user_id):
        self.user_id = user_id

@pytest.fixture
def mock_app_dependencies():
    app = FastAPI()
    app.include_router(router)
    app.add_middleware(TraceIDMiddleware)

    mock_identity = AsyncMock()
    mock_budget = AsyncMock()
    mock_auditor = AsyncMock()
    mock_session = AsyncMock()

    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    app.dependency_overrides[get_auditor] = lambda: mock_auditor
    app.dependency_overrides[get_session_manager] = lambda: mock_session

    return app, mock_identity, mock_budget, mock_auditor, mock_session

@pytest.mark.asyncio
async def test_run_agent_success(mock_app_dependencies):
    app, mock_identity, mock_budget, mock_auditor, mock_session = mock_app_dependencies
    client = TestClient(app)

    # Setup mocks
    mock_identity.validate_token.return_value = MockUserContext("user-123")
    mock_budget.check_quota.return_value = True
    mock_session.execute_agent.return_value = {"output": "success"}

    payload = {
        "input_data": {"query": "test"},
        "context": {"env": "prod"}
    }
    headers = {"Authorization": "Bearer token123"}

    response = client.post("/v1/run/agent-007", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["result"] == {"output": "success"}
    assert "trace_id" in data

    # Verify Chain of Command

    # 2. Auth
    mock_identity.validate_token.assert_awaited_once_with("Bearer token123")

    # 4. Budget Check
    mock_budget.check_quota.assert_awaited_once()

    # 5. Audit Start
    mock_auditor.log_event.assert_awaited()
    assert mock_auditor.log_event.call_args_list[0].args[0] == "EXECUTION_START"

    # 6. Execution
    mock_session.execute_agent.assert_awaited_once()

    # 8. Audit End
    # Note: Settlement is background task, might not run immediately in test client context without explicit handling?
    # Starlette TestClient runs background tasks synchronously.

    # 7. Settlement
    mock_budget.record_transaction.assert_awaited_once()

    # 8. Audit End (should be second call to log_event, or later)
    assert mock_auditor.log_event.call_count >= 2
    assert mock_auditor.log_event.call_args_list[-1].args[0] == "EXECUTION_COMPLETE"

@pytest.mark.asyncio
async def test_run_agent_insufficient_funds(mock_app_dependencies):
    app, mock_identity, mock_budget, _, _ = mock_app_dependencies
    client = TestClient(app)

    mock_identity.validate_token.return_value = MockUserContext("user-123")
    mock_budget.check_quota.return_value = False # Deny

    payload = {"input_data": {}}
    headers = {"Authorization": "Bearer token"}

    response = client.post("/v1/run/agent-007", json=payload, headers=headers)

    assert response.status_code == 402
    assert response.json()["detail"] == "Insufficient funds"

@pytest.mark.asyncio
async def test_run_agent_unauthorized(mock_app_dependencies):
    app, mock_identity, _, _, _ = mock_app_dependencies
    client = TestClient(app)

    mock_identity.validate_token.side_effect = Exception("Invalid token")

    payload = {"input_data": {}}
    headers = {"Authorization": "Bearer bad_token"}

    response = client.post("/v1/run/agent-007", json=payload, headers=headers)

    assert response.status_code == 401
    assert "Authentication failed" in response.json()["detail"]
