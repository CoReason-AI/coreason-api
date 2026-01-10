# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_identity_manager,
    get_policy_guard,
    get_session_manager,
)
from coreason_api.main import app
from coreason_identity.models import UserContext
from coreason_veritas.exceptions import ComplianceViolationError
from coreason_veritas.gatekeeper import PolicyGuard
from fastapi.testclient import TestClient


class TestRuntimePolicy:
    def setup_method(self) -> None:
        # Clear overrides before each test
        app.dependency_overrides = {}
        self.client = TestClient(app)

    def teardown_method(self) -> None:
        app.dependency_overrides = {}

    def test_run_agent_policy_denied(self) -> None:
        """
        Test that the runtime endpoint returns 403 Forbidden when Policy Check fails.
        """
        # Mock Dependencies
        mock_identity_manager = MagicMock()
        mock_identity_manager.validate_token = AsyncMock(
            return_value=UserContext(
                sub="user_123",
                email="test@example.com",
                project_context=None,
                permissions=[],
            )
        )
        app.dependency_overrides[get_identity_manager] = lambda: mock_identity_manager

        # Mock Policy Guard directly using the class
        mock_policy_guard = MagicMock(spec=PolicyGuard)
        mock_policy_guard.verify_access.side_effect = ComplianceViolationError("Access Denied by Policy")
        app.dependency_overrides[get_policy_guard] = lambda: mock_policy_guard

        # Mock other dependencies
        mock_budget = MagicMock()
        app.dependency_overrides[get_budget_guard] = lambda: mock_budget
        mock_auditor = MagicMock()
        app.dependency_overrides[get_auditor] = lambda: mock_auditor
        mock_mcp = MagicMock()
        app.dependency_overrides[get_session_manager] = lambda: mock_mcp

        # Execute Request
        response = self.client.post(
            "/v1/run/agent_x",
            json={"input_data": {"foo": "bar"}},
            headers={"Authorization": "Bearer valid_token"},
        )

        # Verify Response
        assert response.status_code == 403
        assert response.json()["detail"] == "Policy violation: Access Denied by Policy"

        # Verify Audit was NOT called
        mock_auditor.log_event.assert_not_called()

    def test_run_agent_policy_returns_false(self) -> None:
        """
        Test that the runtime endpoint returns 403 Forbidden when Policy Check returns False.
        """
        mock_identity_manager = MagicMock()
        mock_identity_manager.validate_token = AsyncMock(
            return_value=UserContext(
                sub="user_123",
                email="test@example.com",
                project_context=None,
                permissions=[],
            )
        )
        app.dependency_overrides[get_identity_manager] = lambda: mock_identity_manager

        mock_policy_guard = MagicMock(spec=PolicyGuard)
        mock_policy_guard.verify_access.return_value = False
        app.dependency_overrides[get_policy_guard] = lambda: mock_policy_guard

        # Mock other dependencies
        mock_budget = MagicMock()
        app.dependency_overrides[get_budget_guard] = lambda: mock_budget
        mock_auditor = MagicMock()
        app.dependency_overrides[get_auditor] = lambda: mock_auditor
        mock_mcp = MagicMock()
        app.dependency_overrides[get_session_manager] = lambda: mock_mcp

        # Execute Request
        response = self.client.post(
            "/v1/run/agent_x",
            json={"input_data": {"foo": "bar"}},
            headers={"Authorization": "Bearer valid_token"},
        )

        # Verify Response
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied by policy"

    def test_run_agent_policy_error(self) -> None:
        """
        Test that the runtime endpoint returns 500 Internal Server Error when Policy Check raises generic exception.
        """
        # Mock Dependencies
        mock_identity_manager = MagicMock()
        mock_identity_manager.validate_token = AsyncMock(
            return_value=UserContext(
                sub="user_123",
                email="test@example.com",
                project_context=None,
                permissions=[],
            )
        )
        app.dependency_overrides[get_identity_manager] = lambda: mock_identity_manager

        mock_policy_guard = MagicMock(spec=PolicyGuard)
        mock_policy_guard.verify_access.side_effect = Exception("Unexpected DB Error")
        app.dependency_overrides[get_policy_guard] = lambda: mock_policy_guard

        # Mock other dependencies
        mock_budget = MagicMock()
        app.dependency_overrides[get_budget_guard] = lambda: mock_budget
        mock_auditor = MagicMock()
        app.dependency_overrides[get_auditor] = lambda: mock_auditor
        mock_mcp = MagicMock()
        app.dependency_overrides[get_session_manager] = lambda: mock_mcp

        # Execute Request
        response = self.client.post(
            "/v1/run/agent_x",
            json={"input_data": {"foo": "bar"}},
            headers={"Authorization": "Bearer valid_token"},
        )

        # Verify Response
        assert response.status_code == 500
        assert response.json()["detail"] == "Policy check failed"

    def test_run_agent_policy_allowed(self) -> None:
        """
        Test that execution proceeds when Policy Check passes.
        """
        # Mock Dependencies
        mock_identity_manager = MagicMock()
        mock_identity_manager.validate_token = AsyncMock(
            return_value=UserContext(
                sub="user_123",
                email="test@example.com",
                project_context=None,
                permissions=[],
            )
        )
        app.dependency_overrides[get_identity_manager] = lambda: mock_identity_manager

        mock_policy_guard = MagicMock(spec=PolicyGuard)
        mock_policy_guard.verify_access.return_value = True
        app.dependency_overrides[get_policy_guard] = lambda: mock_policy_guard

        mock_budget = MagicMock()
        mock_budget.check_quota = AsyncMock(return_value=True)
        mock_budget.record_transaction = MagicMock()
        app.dependency_overrides[get_budget_guard] = lambda: mock_budget

        mock_auditor = MagicMock()
        mock_auditor.log_event = AsyncMock()
        app.dependency_overrides[get_auditor] = lambda: mock_auditor

        mock_mcp = MagicMock()
        mock_mcp.execute_agent = AsyncMock(return_value="Success")
        app.dependency_overrides[get_session_manager] = lambda: mock_mcp

        # Execute Request
        response = self.client.post(
            "/v1/run/agent_x",
            json={"input_data": {"foo": "bar"}},
            headers={"Authorization": "Bearer valid_token"},
        )

        # Verify Response
        assert response.status_code == 200
        assert response.json()["result"] == "Success"

        # Verify Policy Check was called
        # We need to verify what arguments were passed.
        # UserContext.model_dump() is called in runtime.py.
        # So verify_access receives the dict.
        user_ctx_dict: Dict[str, Any] = {
            "sub": "user_123",
            "email": "test@example.com",
            "project_context": None,
            "permissions": [],
        }
        mock_policy_guard.verify_access.assert_called_once_with(agent_id="agent_x", user_context=user_ctx_dict)

    def test_run_agent_policy_rich_context(self) -> None:
        """
        Test that complex context data (project_context, permissions) is passed correctly to PolicyGuard.
        """
        mock_identity_manager = MagicMock()
        project_ctx = '{"id": "proj_999", "role": "admin"}'
        permissions = ["read:agents", "exec:agent_y"]

        mock_identity_manager.validate_token = AsyncMock(
            return_value=UserContext(
                sub="user_rich",
                email="rich@example.com",
                project_context=project_ctx,
                permissions=permissions,
            )
        )
        app.dependency_overrides[get_identity_manager] = lambda: mock_identity_manager

        mock_policy_guard = MagicMock(spec=PolicyGuard)
        mock_policy_guard.verify_access.return_value = True
        app.dependency_overrides[get_policy_guard] = lambda: mock_policy_guard

        # Mock other dependencies
        mock_budget = MagicMock()
        mock_budget.check_quota = AsyncMock(return_value=True)
        mock_budget.record_transaction = MagicMock()
        app.dependency_overrides[get_budget_guard] = lambda: mock_budget

        mock_auditor = MagicMock()
        mock_auditor.log_event = AsyncMock()
        app.dependency_overrides[get_auditor] = lambda: mock_auditor

        mock_mcp = MagicMock()
        mock_mcp.execute_agent = AsyncMock(return_value="Success")
        app.dependency_overrides[get_session_manager] = lambda: mock_mcp

        # Execute Request
        self.client.post(
            "/v1/run/agent_y",
            json={"input_data": {}},
            headers={"Authorization": "Bearer valid_token"},
        )

        # Verify arguments passed to verify_access
        expected_ctx: Dict[str, Any] = {
            "sub": "user_rich",
            "email": "rich@example.com",
            "project_context": project_ctx,
            "permissions": permissions,
        }
        mock_policy_guard.verify_access.assert_called_once_with(agent_id="agent_y", user_context=expected_ctx)
